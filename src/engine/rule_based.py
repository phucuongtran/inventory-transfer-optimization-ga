"""
Rule-based (greedy) optimizer.

For every needed item, biggest need first:
    take stock from the stores that have excess of the same product,
    closest store first, until the need is covered or the excess runs out.

Fast and deterministic; see docs/logic.md for a worked example.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from src.engine.base_optimizer import BaseOptimizer, stores_by_product, units_by_store_product
from src.engine.models import Transfer


class RuleBasedOptimizer(BaseOptimizer):
    name = "Rule-Based"
    slug = "rule_based"

    def _find_transfers(self, excess: pd.DataFrame, needed: pd.DataFrame) -> List[Transfer]:
        excess = excess.sort_values("excess_units", ascending=False)
        needed = needed.sort_values("needed_units", ascending=False)

        remaining_excess = units_by_store_product(excess, "excess_units")
        suppliers_by_product = stores_by_product(excess)
        transfers: List[Transfer] = []

        for row in needed.itertuples(index=False):
            to_store, product = int(row.store_id), int(row.product_id)
            still_needed = int(row.needed_units)

            suppliers = [s for s in suppliers_by_product.get(product, []) if s != to_store]
            suppliers.sort(key=lambda store: self.network.distance(store, to_store))

            for from_store in suppliers:
                if still_needed <= 0:
                    break
                available = remaining_excess[(from_store, product)]
                if available <= 0 or not self.network.is_valid_route(from_store, to_store):
                    continue

                units = min(still_needed, available)
                transfers.append(Transfer(from_store, to_store, product, units))
                remaining_excess[(from_store, product)] -= units
                still_needed -= units

        return transfers
