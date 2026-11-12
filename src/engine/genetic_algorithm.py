"""
Genetic Algorithm (GA) optimizer, written from scratch.

Vocabulary
----------
- Individual : one candidate transfer plan (a list of :class:`Transfer`).
- Fitness    : transport cost + penalty for every needed unit left unfilled.
               Lower is better.
- Generation : one round of selection -> crossover -> mutation -> evaluation.

Every plan is "repaired" after crossover/mutation so that it never ships more
than a store has in excess, nor more than a store needs.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm

from src.config import (
    GA_CROSSOVER_PROB,
    GA_GENERATIONS,
    GA_MUTATION_PROB,
    GA_POPULATION_SIZE,
    GA_TOURNAMENT_SIZE,
    GA_UNMET_NEED_PENALTY,
    RANDOM_SEED,
)
from src.engine.base_optimizer import BaseOptimizer, stores_by_product, units_by_store_product
from src.engine.models import Transfer
from src.engine.network import TransportNetwork
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GAConfig:
    population_size: int = GA_POPULATION_SIZE
    num_generations: int = GA_GENERATIONS
    crossover_prob: float = GA_CROSSOVER_PROB
    mutation_prob: float = GA_MUTATION_PROB
    tournament_size: int = GA_TOURNAMENT_SIZE
    unmet_need_penalty: float = GA_UNMET_NEED_PENALTY


@dataclass
class Individual:
    transfers: List[Transfer] = field(default_factory=list)
    fitness: float = math.inf

    def copy(self) -> "Individual":
        # Transfers are immutable, so copying the list is enough.
        return Individual(list(self.transfers), self.fitness)


class GeneticAlgorithmOptimizer(BaseOptimizer):
    name = "Genetic Algorithm"
    slug = "ga"

    def __init__(
        self,
        network: TransportNetwork,
        config: Optional[GAConfig] = None,
        seed: Optional[int] = RANDOM_SEED,
        show_progress: bool = True,
    ):
        super().__init__(network)
        self.config = config or GAConfig()
        self.rng = random.Random(seed)
        self.show_progress = show_progress
        #: (generation, best fitness, average fitness) for each generation.
        self.history: List[Tuple[int, float, float]] = []
        self.best_fitness: Optional[float] = None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def _find_transfers(self, excess: pd.DataFrame, needed: pd.DataFrame) -> List[Transfer]:
        self._prepare(excess, needed)
        if not self._products:
            logger.info("No product has both excess and needed stock.")
            return []

        cfg = self.config
        logger.info(
            "GA settings: population=%d, generations=%d, crossover=%.2f, mutation=%.2f, "
            "%d transferable products",
            cfg.population_size,
            cfg.num_generations,
            cfg.crossover_prob,
            cfg.mutation_prob,
            len(self._products),
        )

        population = [self._evaluate(Individual(self._random_plan())) for _ in range(cfg.population_size)]
        best = min(population, key=_fitness).copy()
        self.history = [_generation_stats(0, population)]

        progress = tqdm(
            range(1, cfg.num_generations + 1),
            desc="GA evolution",
            unit="gen",
            disable=not self.show_progress,
        )
        for generation in progress:
            population = self._next_generation(population)

            # Elitism: never lose the best plan found so far.
            generation_best = min(population, key=_fitness)
            if generation_best.fitness < best.fitness:
                best = generation_best.copy()
            else:
                worst = max(range(len(population)), key=lambda i: population[i].fitness)
                population[worst] = best.copy()

            self.history.append(_generation_stats(generation, population))
            progress.set_postfix(best=f"{best.fitness:,.0f}")

        self.best_fitness = best.fitness
        delivered = sum(t.units for t in best.transfers)
        logger.info(
            "GA best fitness %s (initial %s); fills %d of %d needed units",
            f"{best.fitness:,.0f}",
            f"{self.history[0][1]:,.0f}",
            delivered,
            self._fillable_need,
        )
        return best.transfers

    def _next_generation(self, population: List[Individual]) -> List[Individual]:
        cfg = self.config
        parents = [self._tournament(population) for _ in range(len(population))]

        offspring: List[Individual] = []
        for i in range(0, len(parents), 2):
            parent1 = parents[i]
            parent2 = parents[i + 1] if i + 1 < len(parents) else parents[0]
            if self.rng.random() < cfg.crossover_prob:
                offspring.extend(self._crossover(parent1, parent2))
            else:
                offspring.extend([parent1.copy(), parent2.copy()])
        offspring = offspring[: cfg.population_size]

        for child in offspring:
            if self.rng.random() < cfg.mutation_prob:
                self._mutate(child)
            self._evaluate(child)
        return offspring

    # ------------------------------------------------------------------
    # Problem data
    # ------------------------------------------------------------------
    def _prepare(self, excess: pd.DataFrame, needed: pd.DataFrame) -> None:
        """Index the excess / needed tables for fast lookups."""
        self._excess_capacity = units_by_store_product(excess, "excess_units")
        self._need_capacity = units_by_store_product(needed, "needed_units")
        self._suppliers = stores_by_product(excess)
        self._receivers = stores_by_product(needed)
        self._products = sorted(set(self._suppliers) & set(self._receivers))
        self._fillable_need = sum(
            units for (_, product), units in self._need_capacity.items() if product in self._suppliers
        )

    def _max_units(self, from_store: int, to_store: int, product: int) -> int:
        return min(
            self._excess_capacity.get((from_store, product), 0),
            self._need_capacity.get((to_store, product), 0),
        )

    # ------------------------------------------------------------------
    # Fitness
    # ------------------------------------------------------------------
    def _evaluate(self, individual: Individual) -> Individual:
        """Fitness = transport cost + penalty x unfilled needed units (lower is better)."""
        transport_cost = sum(
            self.network.unit_cost(t.from_store, t.to_store) * t.units for t in individual.transfers
        )
        unmet_units = self._fillable_need - sum(t.units for t in individual.transfers)
        individual.fitness = transport_cost + self.config.unmet_need_penalty * unmet_units
        return individual

    # ------------------------------------------------------------------
    # Genetic operators
    # ------------------------------------------------------------------
    def _random_plan(self) -> List[Transfer]:
        """A random but valid plan: random supplier order, random partial amounts."""
        excess_left = dict(self._excess_capacity)
        plan: List[Transfer] = []

        for product in self._products:
            suppliers = list(self._suppliers[product])
            receivers = list(self._receivers[product])
            self.rng.shuffle(suppliers)
            self.rng.shuffle(receivers)

            for to_store in receivers:
                still_needed = self._need_capacity[(to_store, product)]
                for from_store in suppliers:
                    if still_needed <= 0:
                        break
                    available = excess_left[(from_store, product)]
                    if available <= 0 or not self.network.is_valid_route(from_store, to_store):
                        continue
                    units = self.rng.randint(1, min(available, still_needed))
                    plan.append(Transfer(from_store, to_store, product, units))
                    excess_left[(from_store, product)] -= units
                    still_needed -= units
        return plan

    def _random_transfer(self) -> Optional[Transfer]:
        product = self.rng.choice(self._products)
        from_store = self.rng.choice(self._suppliers[product])
        to_store = self.rng.choice(self._receivers[product])
        max_units = self._max_units(from_store, to_store, product)
        if max_units <= 0 or not self.network.is_valid_route(from_store, to_store):
            return None
        return Transfer(from_store, to_store, product, self.rng.randint(1, max_units))

    def _tournament(self, population: List[Individual]) -> Individual:
        """Pick a few random individuals and return the fittest one."""
        size = min(self.config.tournament_size, len(population))
        return min(self.rng.sample(population, size), key=_fitness)

    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Single-point crossover: swap the tails of the two plans."""
        plan1, plan2 = parent1.transfers, parent2.transfers
        shortest = min(len(plan1), len(plan2))
        if shortest < 2:  # No point to cut at.
            return parent1.copy(), parent2.copy()

        point = self.rng.randint(1, shortest - 1)
        child1 = Individual(self._repair(plan1[:point] + plan2[point:]))
        child2 = Individual(self._repair(plan2[:point] + plan1[point:]))
        return child1, child2

    def _mutate(self, individual: Individual) -> None:
        """Apply one random small change, then repair the plan."""
        plan = individual.transfers
        if not plan:
            individual.transfers = self._random_plan()
            return

        index = self.rng.randrange(len(plan))
        transfer = plan[index]
        mutation = self.rng.choice(("change_quantity", "remove", "add", "change_route"))

        if mutation == "change_quantity":
            max_units = self._max_units(transfer.from_store, transfer.to_store, transfer.product_id)
            if max_units > 0:
                plan[index] = replace(transfer, units=self.rng.randint(1, max_units))

        elif mutation == "remove":
            if len(plan) > 1:
                plan.pop(index)

        elif mutation == "add":
            new_transfer = self._random_transfer()
            if new_transfer is not None:
                plan.append(new_transfer)

        else:  # change_route: new supplier or new receiver for the same product
            if self.rng.random() < 0.5:
                options = [s for s in self._suppliers[transfer.product_id] if s != transfer.from_store]
                if options:
                    plan[index] = replace(transfer, from_store=self.rng.choice(options))
            else:
                options = [s for s in self._receivers[transfer.product_id] if s != transfer.to_store]
                if options:
                    plan[index] = replace(transfer, to_store=self.rng.choice(options))

        individual.transfers = self._repair(plan)

    def _repair(self, plan: List[Transfer]) -> List[Transfer]:
        """Make a plan feasible.

        Drops invalid routes (incl. self-transfers), caps every transfer by the
        excess still available and the need still open, and merges duplicate
        routes into a single transfer.
        """
        excess_used: Dict[Tuple[int, int], int] = defaultdict(int)
        need_filled: Dict[Tuple[int, int], int] = defaultdict(int)
        merged: Dict[Tuple[int, int, int], int] = {}

        for t in plan:
            if not self.network.is_valid_route(t.from_store, t.to_store):
                continue
            source = (t.from_store, t.product_id)
            target = (t.to_store, t.product_id)
            units = min(
                t.units,
                self._excess_capacity.get(source, 0) - excess_used[source],
                self._need_capacity.get(target, 0) - need_filled[target],
            )
            if units <= 0:
                continue
            route = (t.from_store, t.to_store, t.product_id)
            merged[route] = merged.get(route, 0) + units
            excess_used[source] += units
            need_filled[target] += units

        return [Transfer(f, to, p, units) for (f, to, p), units in merged.items()]


def _fitness(individual: Individual) -> float:
    return individual.fitness


def _generation_stats(generation: int, population: List[Individual]) -> Tuple[int, float, float]:
    values = [ind.fitness for ind in population]
    return generation, min(values), sum(values) / len(values)
