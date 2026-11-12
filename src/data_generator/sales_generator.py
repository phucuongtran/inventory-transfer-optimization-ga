"""Generate daily sales records with city preferences and seasonal effects."""

from __future__ import annotations

import datetime as dt
import random
from typing import Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from src.config import RANDOM_SEED
from src.engine.models import Product, Store

# Demand multiplier per category, by city.
CITY_CATEGORY_FACTORS = {
    "Hanoi": {"Electronics": 1.5, "Clothing": 1.3, "Home Goods": 0.9, "Food": 1.0, "Beauty": 0.8},
    "Da Nang": {"Electronics": 0.9, "Clothing": 1.0, "Home Goods": 1.4, "Food": 1.1, "Beauty": 1.3},
    "Ho Chi Minh City": {"Electronics": 1.3, "Clothing": 1.1, "Home Goods": 1.0, "Food": 1.5, "Beauty": 1.2},
}

# Extra multipliers for some months.
HOLIDAY_MONTHS = (1, 12)  # Tet and Christmas
HOLIDAY_FACTORS = {"Electronics": 1.5, "Home Goods": 1.3}
SUMMER_MONTHS = (6, 7, 8)
SUMMER_FACTORS = {"Clothing": 1.2, "Beauty": 1.3}

# Every store sells a random subset of the catalog each day.
PRODUCTS_SOLD_PER_DAY = (10, 29)
UNITS_PER_SALE = (1, 9)


def demand_factors(city: str, month: int) -> Dict[str, float]:
    """Category multipliers for a store in ``city`` during ``month``."""
    factors = dict(CITY_CATEGORY_FACTORS.get(city, CITY_CATEGORY_FACTORS["Ho Chi Minh City"]))
    seasonal = {}
    if month in HOLIDAY_MONTHS:
        seasonal = HOLIDAY_FACTORS
    elif month in SUMMER_MONTHS:
        seasonal = SUMMER_FACTORS
    for category, multiplier in seasonal.items():
        factors[category] *= multiplier
    return factors


class SalesGenerator:
    def __init__(self, stores: List[Store], products: List[Product], seed: Optional[int] = RANDOM_SEED):
        self.stores = stores
        self.products = products
        self.rng = random.Random(seed)

    def generate(self, days: int, end_date: Optional[dt.date] = None) -> pd.DataFrame:
        """Sales for the ``days`` days up to ``end_date`` (default: today).

        Columns: date, store_id, product_id, quantity, revenue, cost.
        At most one record per store-product-day.
        """
        end_date = end_date or dt.date.today()
        dates = pd.date_range(end=end_date, periods=days + 1, freq="D")
        records = []

        for date in tqdm(dates, desc="Generating sales", unit="day"):
            for store in self.stores:
                factors = demand_factors(store.city, date.month)
                count = min(self.rng.randint(*PRODUCTS_SOLD_PER_DAY), len(self.products))

                for product in self.rng.sample(self.products, count):
                    base = self.rng.randint(*UNITS_PER_SALE)
                    quantity = max(1, int(base * factors[product.category]))
                    records.append(
                        {
                            "date": date,
                            "store_id": store.id,
                            "product_id": product.id,
                            "quantity": quantity,
                            "revenue": quantity * product.price,
                            "cost": quantity * product.cost,
                        }
                    )
        return pd.DataFrame(records)
