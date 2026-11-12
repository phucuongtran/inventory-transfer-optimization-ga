"""Generate the complete sample dataset and write it to CSV files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.config import (
    COST_MATRIX_FILE,
    DATA_DIR,
    DISTANCE_MATRIX_FILE,
    EXCESS_PERCENT,
    INVENTORY_FILE,
    MAX_INVENTORY_DAYS,
    MIN_INVENTORY_DAYS,
    NUM_PRODUCTS,
    PRODUCTS_FILE,
    RANDOM_SEED,
    SALES_DAYS,
    SALES_FILE,
    SHORTAGE_PERCENT,
    STORES_FILE,
)
from src.data_generator.distance_calculator import build_cost_matrix, build_distance_matrix
from src.data_generator.inventory_generator import InventoryGenerator
from src.data_generator.product_generator import ProductGenerator, products_to_dataframe
from src.data_generator.sales_generator import SalesGenerator
from src.data_generator.store_generator import StoreGenerator, stores_to_dataframe
from src.engine.analyzer import InventoryAnalyzer
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_all_data(
    output_dir: Path = DATA_DIR,
    num_products: int = NUM_PRODUCTS,
    days: int = SALES_DAYS,
    seed: Optional[int] = RANDOM_SEED,
    min_days: float = MIN_INVENTORY_DAYS,
    max_days: float = MAX_INVENTORY_DAYS,
    excess_percent: float = EXCESS_PERCENT,
    shortage_percent: float = SHORTAGE_PERCENT,
) -> None:
    """Create stores, products, sales, inventory and the distance/cost matrices."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Generating sample data (seed=%s) into %s", seed, output_dir)

    stores = StoreGenerator(seed).generate()
    products = ProductGenerator(seed).generate(num_products)
    sales = SalesGenerator(stores, products, seed).generate(days)
    inventory = InventoryGenerator(sales, seed).generate(
        min_days, max_days, excess_percent, shortage_percent
    )

    stores_df = stores_to_dataframe(stores)
    products_df = products_to_dataframe(products)
    distance_matrix = build_distance_matrix(stores_df)
    cost_matrix = build_cost_matrix(distance_matrix, stores_df)

    stores_df.to_csv(output_dir / STORES_FILE, index=False)
    products_df.to_csv(output_dir / PRODUCTS_FILE, index=False)
    sales.to_csv(output_dir / SALES_FILE, index=False)
    inventory.to_csv(output_dir / INVENTORY_FILE, index=False)
    distance_matrix.to_csv(output_dir / DISTANCE_MATRIX_FILE)
    cost_matrix.to_csv(output_dir / COST_MATRIX_FILE)

    logger.info(
        "Created %d stores, %d products, %d sales records, %d inventory rows",
        len(stores),
        len(products),
        len(sales),
        len(inventory),
    )
    _log_transfer_potential(sales, inventory, min_days, max_days)


def _log_transfer_potential(sales, inventory, min_days, max_days) -> None:
    """Warn if too few products have both excess and needed stock to optimize."""
    analyzer = InventoryAnalyzer(sales, inventory, min_days=min_days, max_days=max_days)
    analyzer.analyze()
    excess, needed = analyzer.identify_imbalances()

    transferable = set(excess["product_id"]) & set(needed["product_id"])
    logger.info(
        "Products with both excess and needed stock: %d of %d",
        len(transferable),
        inventory["product_id"].nunique(),
    )
    if len(transferable) < 10:
        logger.warning(
            "Few products can be transferred; consider another --seed for richer imbalances."
        )
