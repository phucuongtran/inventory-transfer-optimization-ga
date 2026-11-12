"""
Central configuration for the Inventory Transfer Optimization System.

Every tunable number of the project lives in this file, grouped by topic.
Paths are absolute (anchored at the project root), so the program works no
matter which directory it is started from.
"""

from __future__ import annotations

from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
VISUALIZATIONS_DIR = PROJECT_ROOT / "visualizations"
LOGS_DIR = PROJECT_ROOT / "logs"

# Input files expected inside DATA_DIR
STORES_FILE = "stores.csv"
PRODUCTS_FILE = "products.csv"
SALES_FILE = "sales_data.csv"
INVENTORY_FILE = "inventory_data.csv"
DISTANCE_MATRIX_FILE = "distance_matrix.csv"
COST_MATRIX_FILE = "transport_cost_matrix.csv"

REQUIRED_DATA_FILES = (
    SALES_FILE,
    INVENTORY_FILE,
    STORES_FILE,
    PRODUCTS_FILE,
    DISTANCE_MATRIX_FILE,
    COST_MATRIX_FILE,
)

# ============================================================================
# REPRODUCIBILITY
# ============================================================================

RANDOM_SEED = 2025

# ============================================================================
# INVENTORY THRESHOLDS (in days of stock)
# ============================================================================

MIN_INVENTORY_DAYS = 7  # Below this -> the store NEEDS more stock
MAX_INVENTORY_DAYS = 21  # Above this -> the store has EXCESS stock

# ============================================================================
# SAMPLE DATA GENERATION
# ============================================================================

NUM_PRODUCTS = 30
SALES_DAYS = 90
EXCESS_PERCENT = 20  # Share of store-product pairs generated with excess stock
SHORTAGE_PERCENT = 20  # Share of store-product pairs generated with a shortage

STORE_CITIES = {
    "Hanoi": {"lat_range": (20.9, 21.1), "lon_range": (105.7, 105.9), "count": 7},
    "Da Nang": {"lat_range": (16.0, 16.1), "lon_range": (108.2, 108.3), "count": 5},
    "Ho Chi Minh City": {
        "lat_range": (10.7, 10.9),
        "lon_range": (106.6, 106.8),
        "count": 8,
    },
}

# ============================================================================
# TRANSPORT COST MODEL (VND per unit shipped)
# ============================================================================

BASE_COST_PER_KM = 2_000
INTERCITY_FACTOR = 1.2  # Shipping between two different cities costs 20% more
# (upper distance bound in km, multiplier). The first bound that the distance
# is below wins: short trips are relatively expensive, long trips cheaper per km.
DISTANCE_FACTORS = (
    (100, 1.2),
    (500, 1.0),
    (float("inf"), 0.5),
)

# ============================================================================
# GENETIC ALGORITHM
# ============================================================================

GA_POPULATION_SIZE = 50
GA_GENERATIONS = 50
GA_CROSSOVER_PROB = 0.6
GA_MUTATION_PROB = 0.3
GA_TOURNAMENT_SIZE = 3

# Penalty (VND) added to the fitness for every needed unit that a plan leaves
# unfilled. It must be higher than the most expensive per-unit route
# (~1.4M VND with the default cost model); otherwise "transfer nothing" would
# be the cheapest - and therefore the "best" - plan.
GA_UNMET_NEED_PENALTY = 2_000_000
