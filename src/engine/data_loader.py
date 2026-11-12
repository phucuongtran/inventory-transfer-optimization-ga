"""Load every input CSV of the project in one call."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd

from src.config import (
    COST_MATRIX_FILE,
    DISTANCE_MATRIX_FILE,
    INVENTORY_FILE,
    PRODUCTS_FILE,
    REQUIRED_DATA_FILES,
    SALES_FILE,
    STORES_FILE,
)
from src.engine.network import TransportNetwork


@dataclass
class ProjectData:
    """All input tables, already typed and ready to use."""

    sales: pd.DataFrame
    inventory: pd.DataFrame
    stores: pd.DataFrame
    products: pd.DataFrame
    network: TransportNetwork


def find_missing_files(data_dir: Path) -> List[str]:
    """Names of required input files that do not exist in ``data_dir``."""
    return [name for name in REQUIRED_DATA_FILES if not (Path(data_dir) / name).exists()]


def load_project_data(data_dir: Path) -> ProjectData:
    """Read all input files from ``data_dir``."""
    data_dir = Path(data_dir)

    sales = pd.read_csv(data_dir / SALES_FILE, parse_dates=["date"])
    inventory = pd.read_csv(data_dir / INVENTORY_FILE)
    # Store IDs can be saved as floats (e.g. "8.0"); normalise them to int.
    inventory["store_id"] = inventory["store_id"].astype(int)

    return ProjectData(
        sales=sales,
        inventory=inventory,
        stores=pd.read_csv(data_dir / STORES_FILE),
        products=pd.read_csv(data_dir / PRODUCTS_FILE),
        network=TransportNetwork.from_csv(
            data_dir / DISTANCE_MATRIX_FILE, data_dir / COST_MATRIX_FILE
        ),
    )
