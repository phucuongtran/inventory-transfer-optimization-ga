"""
Compare the optimizers and write the final report files:

- ``result_summary.txt``     - side-by-side comparison and the recommended algorithm
- ``best_transfer_plan.csv`` - the plan of the recommended algorithm
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.engine.transfer_plan import summarize_plan
from src.utils.logger import get_logger

logger = get_logger(__name__)

SUMMARY_FILE = "result_summary.txt"
BEST_PLAN_FILE = "best_transfer_plan.csv"

# Readable columns first in the exported plan.
_LEADING_COLUMNS = [
    "from_store_name",
    "to_store_name",
    "product_name",
    "units",
    "transport_cost",
    "distance_km",
]


@dataclass
class OptimizationResult:
    """Everything one optimizer produced."""

    algorithm: str
    plan: pd.DataFrame
    impact: Optional[pd.DataFrame]
    execution_time: float

    @property
    def summary(self) -> dict:
        return summarize_plan(self.plan)

    def improvement(self, metric: str) -> float:
        """A value from the ``Improvement`` column of the impact table (0 if missing)."""
        if self.impact is None or metric not in self.impact.index:
            return 0
        return self.impact.loc[metric, "Improvement"]


def select_best(results: List[OptimizationResult]) -> Optional[OptimizationResult]:
    """The plan that resolves the most shortages wins; ties go to the cheaper plan."""
    candidates = [r for r in results if not r.plan.empty]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda r: (r.improvement("Reduction in Needed Items"), -r.summary["total_cost"]),
    )


def write_final_results(
    results: List[OptimizationResult], results_dir: Path
) -> Optional[OptimizationResult]:
    """Write the summary and best-plan files; return the recommended result."""
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    best = select_best(results)
    (results_dir / SUMMARY_FILE).write_text(_format_summary(results, best), encoding="utf-8")

    if best is None:
        logger.warning("No algorithm produced a transfer plan.")
    else:
        plan = best.plan.sort_values("transport_cost", ascending=False)
        ordered = [c for c in _LEADING_COLUMNS if c in plan.columns]
        plan = plan[ordered + [c for c in plan.columns if c not in ordered]]
        plan.to_csv(results_dir / BEST_PLAN_FILE, index=False)
        logger.info("Recommended algorithm: %s (%d transfers)", best.algorithm, len(plan))

    return best


def _format_summary(results: List[OptimizationResult], best: Optional[OptimizationResult]) -> str:
    lines = [
        "INVENTORY OPTIMIZATION RESULTS SUMMARY",
        "=" * 50,
        f"Report Generated: {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}",
        "",
        "ALGORITHM COMPARISON",
        "-" * 30,
    ]
    for result in results:
        marker = "[BEST]" if result is best else "      "
        lines.append(f"\n{marker} {result.algorithm}")
        if result.plan.empty:
            lines.append("   Status: no transfers generated")
            continue
        s = result.summary
        lines += [
            f"   Execution Time:            {result.execution_time:.2f} s",
            f"   Transfers:                 {s['transfers']:,}",
            f"   Units Transferred:         {s['units']:,}",
            f"   Total Transport Cost:      {s['total_cost']:,.0f} VND",
            f"   Cost per Unit:             {s['cost_per_unit']:,.0f} VND",
            f"   Needed Items Resolved:     {result.improvement('Reduction in Needed Items')}",
            f"   Increase in Balanced Items: {result.improvement('Increase in Balanced Items')}",
        ]

    lines += ["", "", "RECOMMENDED SOLUTION", "-" * 25]
    if best is None:
        lines.append("None - no algorithm produced transfers.")
    else:
        s = best.summary
        lines += [
            f"Best Algorithm: {best.algorithm}",
            "(rule: most needed items resolved, then lowest transport cost)",
            f"Recommended Transfers: {s['transfers']:,}",
            f"Total Units: {s['units']:,}",
            f"Total Cost: {s['total_cost']:,.0f} VND",
        ]
    return "\n".join(lines) + "\n"
