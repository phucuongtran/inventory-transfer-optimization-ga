"""
Inventory analysis.

1. ``analyze()``             - sales statistics + days of inventory per store-product.
2. ``identify_imbalances()`` - split items into Excess / Needed.
3. ``evaluate_plan_impact()`` - simulate a transfer plan and compare before vs after.

Definition used throughout the project
--------------------------------------
``avg_daily_sales`` is the average quantity sold on the days a product *was*
sold in a store (the sample data has at most one sales record per
store-product-day). ``days_of_inventory = current_stock / avg_daily_sales``.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from src.config import MAX_INVENTORY_DAYS, MIN_INVENTORY_DAYS
from src.utils.logger import get_logger

logger = get_logger(__name__)

KEYS = ["store_id", "product_id"]

STATUS_EXCESS = "Excess"
STATUS_NEEDED = "Needed"
STATUS_BALANCED = "Balanced"

# Used instead of 0 to avoid dividing by zero for items that never sold.
MIN_DAILY_SALES = 0.01


def classify_inventory(
    df: pd.DataFrame,
    min_days: float,
    max_days: float,
    status_column: str = "inventory_status",
) -> pd.DataFrame:
    """Add ``days_of_inventory``, a status column, ``excess_units`` and ``needed_units``.

    ``df`` must contain ``current_stock`` and ``avg_daily_sales``.
    - Excess: more than ``max_days`` of stock -> units above ``max_days`` can be given away.
    - Needed: less than ``min_days`` of stock -> units missing to reach ``min_days``.
    """
    result = df.copy()
    stock = result["current_stock"]
    daily = result["avg_daily_sales"]
    result["days_of_inventory"] = stock / daily

    is_excess = (result["days_of_inventory"] > max_days) & (stock > 0)
    is_needed = result["days_of_inventory"] < min_days

    result[status_column] = np.select(
        [is_needed, is_excess], [STATUS_NEEDED, STATUS_EXCESS], default=STATUS_BALANCED
    )
    # Excess: keep floor(max_days x daily) units, give the rest away.
    # Needed: round UP, so that receiving these units really lifts the item to min_days.
    result["excess_units"] = np.where(is_excess, stock - np.floor(max_days * daily), 0).astype(int)
    result["needed_units"] = np.where(is_needed, np.ceil(min_days * daily - stock), 0).astype(int)
    return result


class InventoryAnalyzer:
    def __init__(
        self,
        sales: pd.DataFrame,
        inventory: pd.DataFrame,
        stores: Optional[pd.DataFrame] = None,
        products: Optional[pd.DataFrame] = None,
        min_days: float = MIN_INVENTORY_DAYS,
        max_days: float = MAX_INVENTORY_DAYS,
    ):
        self.sales = sales.assign(date=pd.to_datetime(sales["date"]))
        self.inventory = inventory
        self.stores = stores
        self.products = products
        self.min_days = min_days
        self.max_days = max_days
        self.analysis: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # 1. Analysis
    # ------------------------------------------------------------------
    def analyze(self) -> pd.DataFrame:
        """Return one row per store-product with sales metrics and inventory status."""
        stats = (
            self.sales.groupby(KEYS)
            .agg(
                quantity_sum=("quantity", "sum"),
                quantity_mean=("quantity", "mean"),
                quantity_std=("quantity", "std"),
                quantity_count=("quantity", "count"),
                revenue_sum=("revenue", "sum"),
                revenue_mean=("revenue", "mean"),
                last_sale_date=("date", "max"),
            )
            .reset_index()
        )
        # Coefficient of variation: how consistent the sales are.
        stats["quantity_cv"] = stats["quantity_std"] / stats["quantity_mean"]
        stats["days_since_last_sale"] = (self.sales["date"].max() - stats["last_sale_date"]).dt.days

        analysis = self.inventory.merge(stats, on=KEYS, how="left")
        metric_columns = [
            "quantity_sum",
            "quantity_mean",
            "quantity_std",
            "quantity_count",
            "revenue_sum",
            "revenue_mean",
            "quantity_cv",
        ]
        analysis[metric_columns] = analysis[metric_columns].fillna(0)
        analysis["avg_daily_sales"] = analysis["quantity_mean"].replace(0, MIN_DAILY_SALES)

        if self.stores is not None:
            analysis["city"] = analysis["store_id"].map(self.stores.set_index("store_id")["city"])
        if self.products is not None:
            analysis["category"] = analysis["product_id"].map(
                self.products.set_index("product_id")["category"]
            )

        median_sales = analysis["avg_daily_sales"].median()
        analysis["sales_velocity"] = np.where(
            analysis["avg_daily_sales"] >= median_sales, "Fast", "Slow"
        )

        self.analysis = classify_inventory(analysis, self.min_days, self.max_days)
        return self.analysis

    # ------------------------------------------------------------------
    # 2. Imbalances
    # ------------------------------------------------------------------
    def identify_imbalances(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return ``(excess, needed)``: the items with too much / too little stock."""
        analysis = self.analysis if self.analysis is not None else self.analyze()
        excess = analysis[analysis["inventory_status"] == STATUS_EXCESS].copy()
        needed = analysis[analysis["inventory_status"] == STATUS_NEEDED].copy()

        logger.info(
            "Inventory status (needed < %s days < balanced < %s days < excess):",
            self.min_days,
            self.max_days,
        )
        logger.info("  - Excess items:   %d (%d units)", len(excess), excess["excess_units"].sum())
        logger.info("  - Needed items:   %d (%d units)", len(needed), needed["needed_units"].sum())
        logger.info("  - Balanced items: %d", len(analysis) - len(excess) - len(needed))
        return excess, needed

    # ------------------------------------------------------------------
    # 3. Impact of a plan
    # ------------------------------------------------------------------
    def evaluate_plan_impact(self, plan: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
        """Simulate ``plan`` and return ``(impact_table, post_transfer_analysis)``.

        ``impact_table`` has the metrics as rows and the columns
        ``Before Transfer``, ``After Transfer``, ``Improvement`` and ``Transfer Plan``.
        """
        before = self.analysis if self.analysis is not None else self.analyze()
        if plan is None or plan.empty:
            return None, before

        after = before.copy()
        after["current_stock"] = after["current_stock"] + self._net_stock_change(plan, after)
        after = classify_inventory(
            after, self.min_days, self.max_days, status_column="post_inventory_status"
        )

        before_counts = before["inventory_status"].value_counts()
        after_counts = after["post_inventory_status"].value_counts()

        days_before = before["days_of_inventory"]
        days_after = after["days_of_inventory"]
        turnover_before = 365 / days_before.mean() if days_before.mean() > 0 else 0
        turnover_after = 365 / days_after.mean() if days_after.mean() > 0 else 0

        value_before = self._inventory_value(before)
        value_after = self._inventory_value(after)
        excess_value_before = self._inventory_value(before, "inventory_status", STATUS_EXCESS)
        excess_value_after = self._inventory_value(after, "post_inventory_status", STATUS_EXCESS)

        total_units = plan["units"].sum()
        total_cost = plan["transport_cost"].sum()

        impact = {
            "Before Transfer": {
                "Excess Items": before_counts.get(STATUS_EXCESS, 0),
                "Needed Items": before_counts.get(STATUS_NEEDED, 0),
                "Balanced Items": before_counts.get(STATUS_BALANCED, 0),
                "Avg Days of Inventory": days_before.mean(),
                "Inventory Imbalance (StdDev)": days_before.std(),
                "Product Turnover": turnover_before,
                "Total Inventory Value": value_before,
                "Excess Inventory Value": excess_value_before,
            },
            "After Transfer": {
                "Excess Items": after_counts.get(STATUS_EXCESS, 0),
                "Needed Items": after_counts.get(STATUS_NEEDED, 0),
                "Balanced Items": after_counts.get(STATUS_BALANCED, 0),
                "Avg Days of Inventory": days_after.mean(),
                "Inventory Imbalance (StdDev)": days_after.std(),
                "Product Turnover": turnover_after,
                "Total Inventory Value": value_after,
                "Excess Inventory Value": excess_value_after,
            },
            "Improvement": {
                "Reduction in Excess Items": before_counts.get(STATUS_EXCESS, 0)
                - after_counts.get(STATUS_EXCESS, 0),
                "Reduction in Needed Items": before_counts.get(STATUS_NEEDED, 0)
                - after_counts.get(STATUS_NEEDED, 0),
                "Increase in Balanced Items": after_counts.get(STATUS_BALANCED, 0)
                - before_counts.get(STATUS_BALANCED, 0),
                "Product Turnover Improvement": f"{_percent_change(turnover_before, turnover_after):.2f}%",
                "Inventory Balance Improvement": f"{-_percent_change(days_before.std(), days_after.std()):.2f}%",
                "Reduction in Excess Value": excess_value_before - excess_value_after,
            },
            "Transfer Plan": {
                "Total Transfers": len(plan),
                "Total Units Transferred": total_units,
                "Total Transport Cost": total_cost,
                "Avg Cost Per Unit": total_cost / total_units if total_units > 0 else 0,
            },
        }
        return pd.DataFrame(impact), after

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _net_stock_change(plan: pd.DataFrame, analysis: pd.DataFrame) -> pd.Series:
        """Units gained (+) or lost (-) by each row of ``analysis`` when ``plan`` is applied."""
        outgoing = plan.rename(columns={"from_store_id": "store_id"}).assign(change=-plan["units"])
        incoming = plan.rename(columns={"to_store_id": "store_id"}).assign(change=plan["units"])
        change = (
            pd.concat([outgoing[KEYS + ["change"]], incoming[KEYS + ["change"]]])
            .groupby(KEYS)["change"]
            .sum()
        )
        index = pd.MultiIndex.from_frame(analysis[KEYS])
        return pd.Series(change.reindex(index).fillna(0).to_numpy(), index=analysis.index)

    def _inventory_value(
        self, df: pd.DataFrame, status_column: Optional[str] = None, status: Optional[str] = None
    ) -> float:
        """Stock value at product cost (or plain unit count if product costs are unknown)."""
        if status_column is not None:
            df = df[df[status_column] == status]
        if self.products is None or "cost" not in self.products.columns:
            return float(df["current_stock"].sum())
        unit_cost = df["product_id"].map(self.products.set_index("product_id")["cost"])
        return float((df["current_stock"] * unit_cost).sum())


def _percent_change(before: float, after: float) -> float:
    return (after - before) / before * 100 if before > 0 else 0.0
