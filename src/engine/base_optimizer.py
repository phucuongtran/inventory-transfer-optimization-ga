"""
Common skeleton shared by every optimizer.

A subclass only implements ``_find_transfers(excess, needed)`` and returns a list
of :class:`Transfer`. This base class takes care of the rest: empty-input
handling, timing, building the plan DataFrame and logging a summary.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, List, Tuple

import pandas as pd

from src.engine.models import Transfer
from src.engine.network import TransportNetwork
from src.engine.transfer_plan import PLAN_COLUMNS, build_transfer_plan, summarize_plan
from src.utils.logger import get_logger

logger = get_logger(__name__)

StoreProduct = Tuple[int, int]


class BaseOptimizer(ABC):
    #: Human-readable name used in logs and reports.
    name = "Optimizer"
    #: Short identifier used in output file names (e.g. ``rule_based_transfers.csv``).
    slug = "optimizer"

    def __init__(self, network: TransportNetwork):
        self.network = network
        self.execution_time = 0.0

    def optimize(self, excess: pd.DataFrame, needed: pd.DataFrame) -> pd.DataFrame:
        """Return the transfer plan (see ``transfer_plan.PLAN_COLUMNS``)."""
        logger.info("Running %s...", self.name)
        start = time.perf_counter()

        if excess.empty or needed.empty:
            logger.info("No excess or needed inventory: nothing to transfer.")
            plan = pd.DataFrame(columns=PLAN_COLUMNS)
        else:
            plan = build_transfer_plan(self._find_transfers(excess, needed), self.network)

        self.execution_time = time.perf_counter() - start
        summary = summarize_plan(plan)
        logger.info(
            "%s finished in %.2fs: %d transfers, %d units, %s VND (%s VND/unit)",
            self.name,
            self.execution_time,
            summary["transfers"],
            summary["units"],
            f"{summary['total_cost']:,.0f}",
            f"{summary['cost_per_unit']:,.0f}",
        )
        return plan

    @abstractmethod
    def _find_transfers(self, excess: pd.DataFrame, needed: pd.DataFrame) -> List[Transfer]:
        """Decide which transfers to make."""


# ----------------------------------------------------------------------
# Small helpers used by the optimizers
# ----------------------------------------------------------------------
def units_by_store_product(df: pd.DataFrame, units_column: str) -> Dict[StoreProduct, int]:
    """{(store_id, product_id): units} from an excess or needed table."""
    return {
        (int(row.store_id), int(row.product_id)): int(getattr(row, units_column))
        for row in df.itertuples(index=False)
    }


def stores_by_product(df: pd.DataFrame) -> Dict[int, List[int]]:
    """{product_id: [store_id, ...]} keeping the row order of ``df``."""
    result: Dict[int, List[int]] = defaultdict(list)
    for row in df.itertuples(index=False):
        result[int(row.product_id)].append(int(row.store_id))
    return dict(result)
