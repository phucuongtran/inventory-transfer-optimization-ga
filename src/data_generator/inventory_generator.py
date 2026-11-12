"""
Generate current stock levels with deliberate imbalances.

For each product, the stores that sell it are randomly split into three groups:
- excess   : 1.2x - 1.7x of ``max_days`` of stock
- shortage : 0.3x - 0.8x of ``min_days`` of stock
- balanced : between ``min_days`` and 0.9x ``max_days`` of stock
so that most products have both a store to take from and a store to give to.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

import pandas as pd

from src.config import (
    EXCESS_PERCENT,
    MAX_INVENTORY_DAYS,
    MIN_INVENTORY_DAYS,
    RANDOM_SEED,
    SHORTAGE_PERCENT,
)

# Never put more than this share of a product's stores out of balance.
MAX_IMBALANCED_SHARE = 0.7


def split_store_counts(num_stores: int, excess_percent: float, shortage_percent: float) -> Tuple[int, int]:
    """How many stores get excess and how many get a shortage (at least 1 each)."""
    if num_stores < 4:
        return 1, 1

    num_excess = max(1, int(num_stores * excess_percent / 100))
    num_shortage = max(1, int(num_stores * shortage_percent / 100))

    limit = num_stores * MAX_IMBALANCED_SHARE
    if num_excess + num_shortage > limit:
        scale = limit / (num_excess + num_shortage)
        num_excess = max(1, int(num_excess * scale))
        num_shortage = max(1, int(num_shortage * scale))
    return num_excess, num_shortage


class InventoryGenerator:
    def __init__(self, sales: pd.DataFrame, seed: Optional[int] = RANDOM_SEED):
        self.sales = sales
        self.rng = random.Random(seed)

    def generate(
        self,
        min_days: float = MIN_INVENTORY_DAYS,
        max_days: float = MAX_INVENTORY_DAYS,
        excess_percent: float = EXCESS_PERCENT,
        shortage_percent: float = SHORTAGE_PERCENT,
    ) -> pd.DataFrame:
        """Return columns: store_id, product_id, current_stock, last_updated."""
        avg_sales = (
            self.sales.groupby(["store_id", "product_id"])["quantity"]
            .mean()
            .rename("avg_daily_sales")
            .reset_index()
        )
        all_stores = sorted(avg_sales["store_id"].unique())
        records: List[dict] = []

        for product_id, product_sales in avg_sales.groupby("product_id"):
            selling = product_sales[product_sales["avg_daily_sales"] > 0]
            if len(selling) < 2:
                records += self._small_random_stock(int(product_id), all_stores)
                continue

            store_ids = [int(s) for s in selling["store_id"]]
            self.rng.shuffle(store_ids)
            num_excess, num_shortage = split_store_counts(len(store_ids), excess_percent, shortage_percent)
            excess_stores = set(store_ids[:num_excess])
            shortage_stores = set(store_ids[num_excess : num_excess + num_shortage])

            for row in selling.itertuples(index=False):
                store_id = int(row.store_id)
                if store_id in excess_stores:
                    days_of_stock = self.rng.uniform(max_days * 1.2, max_days * 1.7)
                elif store_id in shortage_stores:
                    days_of_stock = self.rng.uniform(min_days * 0.3, min_days * 0.8)
                else:
                    days_of_stock = self.rng.uniform(min_days, max_days * 0.9)

                daily_sales = max(1, row.avg_daily_sales)
                records.append(
                    {
                        "store_id": store_id,
                        "product_id": int(product_id),
                        "current_stock": max(1, int(daily_sales * days_of_stock)),
                    }
                )

        inventory = pd.DataFrame(records)
        inventory["last_updated"] = self.sales["date"].max()
        return inventory

    def _small_random_stock(self, product_id: int, stores: List[int]) -> List[dict]:
        """Products sold in fewer than two stores: just 0-9 units everywhere."""
        return [
            {"store_id": int(s), "product_id": product_id, "current_stock": self.rng.randint(0, 9)}
            for s in stores
        ]
