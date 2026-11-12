"""Distance (haversine, km) and transport-cost (VND per unit) matrices between stores."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import BASE_COST_PER_KM, DISTANCE_FACTORS, INTERCITY_FACTOR

EARTH_RADIUS_KM = 6371


def build_distance_matrix(stores: pd.DataFrame) -> pd.DataFrame:
    """Great-circle distance between every pair of stores (``stores`` needs lat/lon)."""
    lat = np.radians(stores["latitude"].to_numpy())
    lon = np.radians(stores["longitude"].to_numpy())

    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2
    distances = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))

    ids = stores["store_id"].astype(int).to_list()
    return pd.DataFrame(distances, index=ids, columns=ids)


def distance_factor(distance_km: float) -> float:
    """Per-km price multiplier: short trips cost more per km, long trips less."""
    for upper_bound, factor in DISTANCE_FACTORS:
        if distance_km < upper_bound:
            return factor
    return DISTANCE_FACTORS[-1][1]


def build_cost_matrix(distance_matrix: pd.DataFrame, stores: pd.DataFrame) -> pd.DataFrame:
    """Cost of shipping one unit = base/km x km x intercity factor x distance factor.

    The diagonal (a store to itself) is left empty (NaN): it is not a valid route.
    """
    city_of = stores.set_index("store_id")["city"]
    costs = pd.DataFrame(np.nan, index=distance_matrix.index, columns=distance_matrix.columns)

    for from_id in distance_matrix.index:
        for to_id in distance_matrix.columns:
            if from_id == to_id:
                continue
            km = distance_matrix.loc[from_id, to_id]
            city_factor = INTERCITY_FACTOR if city_of[from_id] != city_of[to_id] else 1.0
            costs.loc[from_id, to_id] = BASE_COST_PER_KM * km * city_factor * distance_factor(km)
    return costs
