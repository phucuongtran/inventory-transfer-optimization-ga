"""
Inventory Transfer Optimization - command-line entry point.

Pipeline:  [generate data] -> analyze inventory -> run optimizers -> write results
           [-> export transfer network]

Examples:
    python src/main.py --generate-data --all     # fresh sample data + both algorithms
    python src/main.py --rule-based              # fast greedy algorithm only
    python src/main.py --all --network           # also export GraphML + charts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Allow `python src/main.py` as well as `python -m src.main`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.data_generator.generate_data import generate_all_data  # noqa: E402
from src.engine.analyzer import InventoryAnalyzer  # noqa: E402
from src.engine.base_optimizer import BaseOptimizer  # noqa: E402
from src.engine.data_loader import ProjectData, find_missing_files, load_project_data  # noqa: E402
from src.engine.genetic_algorithm import GAConfig, GeneticAlgorithmOptimizer  # noqa: E402
from src.engine.results_manager import (  # noqa: E402
    OptimizationResult,
    write_final_results,
)
from src.engine.rule_based import RuleBasedOptimizer  # noqa: E402
from src.engine.transfer_plan import add_readable_names  # noqa: E402
from src.utils.logger import get_logger, setup_logging  # noqa: E402

logger = get_logger("main")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory Transfer Optimization System")

    paths = parser.add_argument_group("folders")
    paths.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    paths.add_argument("--results-dir", type=Path, default=config.RESULTS_DIR)
    paths.add_argument("--vis-dir", type=Path, default=config.VISUALIZATIONS_DIR)

    steps = parser.add_argument_group("what to run")
    steps.add_argument("--generate-data", action="store_true", help="Create sample data first")
    steps.add_argument("--rule-based", action="store_true", help="Run the rule-based optimizer")
    steps.add_argument("--ga", action="store_true", help="Run the genetic algorithm")
    steps.add_argument("--all", action="store_true", help="Run both optimizers and compare")
    steps.add_argument("--network", action="store_true", help="Export the best plan as a network (GraphML + PNG)")

    data = parser.add_argument_group("sample data")
    data.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    data.add_argument("--products", type=int, default=config.NUM_PRODUCTS)
    data.add_argument("--days", type=int, default=config.SALES_DAYS, help="Days of sales history")
    data.add_argument("--excess-percent", type=int, default=config.EXCESS_PERCENT)
    data.add_argument("--shortage-percent", type=int, default=config.SHORTAGE_PERCENT)

    thresholds = parser.add_argument_group("inventory thresholds")
    thresholds.add_argument("--min-days", type=int, default=config.MIN_INVENTORY_DAYS)
    thresholds.add_argument("--max-days", type=int, default=config.MAX_INVENTORY_DAYS)

    ga = parser.add_argument_group("genetic algorithm")
    ga.add_argument("--ga-population", type=int, default=config.GA_POPULATION_SIZE)
    ga.add_argument("--ga-generations", type=int, default=config.GA_GENERATIONS)
    ga.add_argument("--ga-crossover", type=float, default=config.GA_CROSSOVER_PROB)
    ga.add_argument("--ga-mutation", type=float, default=config.GA_MUTATION_PROB)
    ga.add_argument("--ga-penalty", type=float, default=config.GA_UNMET_NEED_PENALTY,
                    help="VND penalty per needed unit left unfilled")

    return parser.parse_args(argv)


def build_optimizers(args: argparse.Namespace, data: ProjectData) -> List[BaseOptimizer]:
    optimizers: List[BaseOptimizer] = []
    if args.rule_based or args.all:
        optimizers.append(RuleBasedOptimizer(data.network))
    if args.ga or args.all:
        ga_config = GAConfig(
            population_size=args.ga_population,
            num_generations=args.ga_generations,
            crossover_prob=args.ga_crossover,
            mutation_prob=args.ga_mutation,
            unmet_need_penalty=args.ga_penalty,
        )
        optimizers.append(GeneticAlgorithmOptimizer(data.network, ga_config, seed=args.seed))
    return optimizers


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(config.LOGS_DIR)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Data
    if args.generate_data:
        generate_all_data(
            output_dir=args.data_dir,
            num_products=args.products,
            days=args.days,
            seed=args.seed,
            min_days=args.min_days,
            max_days=args.max_days,
            excess_percent=args.excess_percent,
            shortage_percent=args.shortage_percent,
        )
    missing = find_missing_files(args.data_dir)
    if missing:
        logger.error("Missing data files in %s: %s. Run with --generate-data first.", args.data_dir, missing)
        return 1
    data = load_project_data(args.data_dir)

    # 2. Analysis
    logger.info("\n=== INVENTORY ANALYSIS ===")
    analyzer = InventoryAnalyzer(
        data.sales, data.inventory, data.stores, data.products, args.min_days, args.max_days
    )
    analysis = analyzer.analyze()
    excess, needed = analyzer.identify_imbalances()
    analysis.to_csv(args.results_dir / "inventory_analysis.csv", index=False)
    excess.to_csv(args.results_dir / "excess_inventory.csv", index=False)
    needed.to_csv(args.results_dir / "needed_inventory.csv", index=False)

    # 3. Optimization
    optimizers = build_optimizers(args, data)
    if not optimizers:
        logger.info("Analysis saved. Add --rule-based, --ga or --all to compute transfers.")
        return 0

    results = []
    for optimizer in optimizers:
        logger.info("\n=== %s ===", optimizer.name.upper())
        plan = add_readable_names(optimizer.optimize(excess, needed), data.stores, data.products)
        impact, _ = analyzer.evaluate_plan_impact(plan)

        plan.to_csv(args.results_dir / f"{optimizer.slug}_transfers.csv", index=False)
        if impact is not None:
            impact.to_csv(args.results_dir / f"{optimizer.slug}_impact.csv")
        results.append(OptimizationResult(optimizer.name, plan, impact, optimizer.execution_time))

    # 4. Results
    logger.info("\n=== RESULTS ===")
    best = write_final_results(results, args.results_dir)
    logger.info("Results saved to %s", args.results_dir)

    # 5. Network export
    if args.network and best is not None:
        import matplotlib

        matplotlib.use("Agg")  # write image files only, no window
        from src.visualization.transfer_network import export_network

        export_network(best.plan, args.vis_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
