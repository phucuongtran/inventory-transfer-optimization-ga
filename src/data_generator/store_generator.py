"""Generate sample stores spread over the cities defined in ``config.STORE_CITIES``."""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import Dict, List, Optional

import pandas as pd

from src.config import RANDOM_SEED, STORE_CITIES
from src.engine.models import Store

BRAND_NAMES = [
    "Saigon Retail", "VinMart", "Hapro", "Mega Market", "Bach Hoa Xanh",
    "Lotus Market", "Co.op Mart", "FiviMart", "CircleK", "Aeon",
    "Lan Chi", "Satra", "Nam An Market", "Sunshine", "Golden Star",
]

DISTRICTS = {
    "Hanoi": [
        "Ba Đình", "Hoàn Kiếm", "Tây Hồ", "Long Biên", "Cầu Giấy",
        "Đống Đa", "Hai Bà Trưng", "Hoàng Mai", "Thanh Xuân", "Mỹ Đình",
    ],
    "Da Nang": [
        "Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu",
        "Hòa Vang", "Cẩm Lệ", "An Hải", "Mỹ Khê", "Hòa Khánh",
    ],
    "Ho Chi Minh City": [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Thủ Đức", "Bình Thạnh",
        "Phú Nhuận", "Tân Bình", "Gò Vấp", "Bình Tân", "Tân Phú", "Nhà Bè",
    ],
}

MALLS = {
    "Hanoi": [
        "Vincom Center Bà Triệu", "Lotte Center", "Aeon Mall Long Biên", "Times City",
        "Royal City", "Tràng Tiền Plaza", "Indochina Plaza",
    ],
    "Da Nang": [
        "Vincom Plaza", "Lotte Mart", "Indochina Riverside Mall", "Sense Market",
        "Han Market Complex",
    ],
    "Ho Chi Minh City": [
        "Vincom Center", "Saigon Centre", "Vivo City", "Crescent Mall", "Estella Place",
        "SC Vivocity", "Landmark 81", "Diamond Plaza",
    ],
}


class StoreGenerator:
    def __init__(self, seed: Optional[int] = RANDOM_SEED, cities: Dict = STORE_CITIES):
        self.rng = random.Random(seed)
        self.cities = cities

    def generate(self) -> List[Store]:
        """Create ``count`` stores per city at random coordinates inside the city box."""
        stores = []
        for city, info in self.cities.items():
            for _ in range(info["count"]):
                stores.append(
                    Store(
                        id=len(stores) + 1,
                        name=self._random_name(city),
                        city=city,
                        latitude=self.rng.uniform(*info["lat_range"]),
                        longitude=self.rng.uniform(*info["lon_range"]),
                    )
                )
        return stores

    def _random_name(self, city: str) -> str:
        """50% "<brand> <district>", 30% "<brand> - <mall>", 20% "<district> Market Center"."""
        style = self.rng.choices(["brand", "mall", "market"], weights=[0.5, 0.3, 0.2])[0]
        if style == "brand":
            return f"{self.rng.choice(BRAND_NAMES)} {self.rng.choice(DISTRICTS[city])}"
        if style == "mall":
            return f"{self.rng.choice(BRAND_NAMES)} - {self.rng.choice(MALLS[city])}"
        return f"{self.rng.choice(DISTRICTS[city])} Market Center"


def stores_to_dataframe(stores: List[Store]) -> pd.DataFrame:
    return pd.DataFrame([asdict(s) for s in stores]).rename(
        columns={"id": "store_id", "name": "store_name"}
    )
