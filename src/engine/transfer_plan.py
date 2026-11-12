"""
Helpers for the transfer-plan table that every optimizer produces.

A transfer plan is a DataFrame with one row per transfer and these columns:
``from_store_id, to_store_id, product_id, units, distance_km, transport_cost``.
"""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

from src.engine.models import Transfer
from src.engine.network import TransportNetwork

PLAN_COLUMNS = [
    "from_store_id",
    "to_store_id",
    "product_id",
    "units",
    "distance_km",
    "transport_cost",
]


def build_transfer_plan(transfers: Iterable[Transfer], network: TransportNetwork) -> pd.DataFrame:
    """Turn Transfer objects into the standard plan DataFrame (with distance and cost)."""
    rows = [
        {
            "from_store_id": t.from_store,
            "to_store_id": t.to_store,
            "product_id": t.product_id,
            "units": int(t.units),
            "distance_km": network.distance(t.from_store, t.to_store),
            "transport_cost": network.unit_cost(t.from_store, t.to_store) * t.units,
        }
        for t in transfers
    ]
    return pd.DataFrame(rows, columns=PLAN_COLUMNS)


def add_readable_names(
    plan: pd.DataFrame,
    stores: Optional[pd.DataFrame] = None,
    products: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Return a copy of ``plan`` with store and product names next to the IDs."""
    named = plan.copy()
    if stores is not None:
        store_names = stores.set_index("store_id")["store_name"]
        named["from_store_name"] = named["from_store_id"].map(store_names)
        named["to_store_name"] = named["to_store_id"].map(store_names)
    if products is not None:
        product_names = products.set_index("product_id")["product_name"]
        named["product_name"] = named["product_id"].map(product_names)
    return named


def summarize_plan(plan: pd.DataFrame) -> dict:
    """Headline numbers of a plan: transfers, units, total and per-unit cost."""
    if plan is None or plan.empty:
        return {"transfers": 0, "units": 0, "total_cost": 0.0, "cost_per_unit": 0.0}
    units = int(plan["units"].sum())
    total_cost = float(plan["transport_cost"].sum())
    return {
        "transfers": len(plan),
        "units": units,
        "total_cost": total_cost,
        "cost_per_unit": total_cost / units if units else 0.0,
    }
