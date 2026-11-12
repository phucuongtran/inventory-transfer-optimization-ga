"""Distance and transport-cost lookups between stores."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

Route = Tuple[int, int]


def load_matrix(path: Path) -> pd.DataFrame:
    """Read a square store x store matrix CSV, with integer store IDs on both axes."""
    matrix = pd.read_csv(path, index_col=0)
    matrix.index = matrix.index.astype(int)
    matrix.columns = matrix.columns.astype(int)
    return matrix


def _matrix_to_dict(matrix: pd.DataFrame) -> Dict[Route, float]:
    """Flatten a matrix into {(from, to): value}, skipping the diagonal and NaNs."""
    values = {}
    for from_store, row in matrix.iterrows():
        for to_store, value in row.items():
            if from_store != to_store and pd.notna(value):
                values[(int(from_store), int(to_store))] = float(value)
    return values


class TransportNetwork:
    """Fast lookups of distance (km) and per-unit transport cost (VND) between stores."""

    def __init__(self, distance_matrix: pd.DataFrame, cost_matrix: pd.DataFrame):
        self.distance_matrix = distance_matrix
        self.cost_matrix = cost_matrix
        self._distances = _matrix_to_dict(distance_matrix)
        self._unit_costs = {
            route: cost for route, cost in _matrix_to_dict(cost_matrix).items() if cost > 0
        }

    @classmethod
    def from_csv(cls, distance_path: Path, cost_path: Path) -> "TransportNetwork":
        return cls(load_matrix(distance_path), load_matrix(cost_path))

    def distance(self, from_store: int, to_store: int) -> float:
        """Distance in km; ``inf`` if the route is unknown."""
        if from_store == to_store:
            return 0.0
        return self._distances.get((from_store, to_store), math.inf)

    def unit_cost(self, from_store: int, to_store: int) -> Optional[float]:
        """Cost of shipping one unit, or ``None`` if the route is not allowed."""
        return self._unit_costs.get((from_store, to_store))

    def is_valid_route(self, from_store: int, to_store: int) -> bool:
        return (from_store, to_store) in self._unit_costs
