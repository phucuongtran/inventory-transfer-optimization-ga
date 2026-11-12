"""Generate a sample product catalog (names, categories, prices in VND)."""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import List, Optional

import pandas as pd

from src.config import RANDOM_SEED
from src.engine.models import Product

PRODUCT_NAMES = {
    "Electronics": [
        "AirPods Pro", "Galaxy Buds2", "Sony WH-1000XM4", "Logitech G502 Mouse",
        "Keychron K2 Keyboard", "Samsung T7 SSD", "Anker PowerCore", "JBL Flip 6",
    ],
    "Clothing": [
        # Men
        "Classic Oxford Shirt", "Slim Fit Chinos", "Linen Casual Shirt", "Stretch Denim Jeans",
        "Polo Shirt", "Crewneck T-Shirt", "Lightweight Jacket", "Cotton Shorts",
        # Women
        "Summer Maxi Dress", "High-Waist Jeans", "Silk Blouse", "Wrap Dress",
        "Cotton V-Neck Tee", "Pleated Skirt", "Linen Trousers", "Knit Cardigan",
        # Footwear
        "Classic Canvas Sneakers", "Leather Loafers", "Ankle Boots", "Strappy Sandals",
        "Running Shoes", "Casual Slip-ons",
        # Accessories
        "Leather Belt", "Patterned Scarf", "Structured Tote Bag", "Minimalist Watch",
        "Aviator Sunglasses", "Beaded Bracelet", "Straw Hat",
    ],
    "Home Goods": [
        # Kitchen
        "Non-Stick Frying Pan", "Stainless Steel Pot Set", "Ceramic Dinner Set", "Chef's Knife",
        "Bamboo Cutting Board", "Rice Cooker", "Electric Kettle", "Coffee Maker",
        # Living room
        "Throw Pillow Set", "Cotton Throw Blanket", "Table Lamp", "Wall Clock",
        "Picture Frame Set", "Decorative Vase", "Area Rug", "Floor Cushion",
        # Bedroom
        "Cotton Bed Sheet Set", "Memory Foam Pillow", "Duvet Cover", "Bedside Table",
        "Storage Basket", "Blackout Curtains",
        # Bathroom
        "Bath Towel Set", "Shower Curtain", "Bathroom Organizer", "Soap Dispenser Set",
    ],
    "Food": [
        # Basics
        "Jasmine Rice", "Instant Noodles", "Fish Sauce", "Soy Sauce", "Coconut Milk",
        "Palm Sugar", "Rice Vinegar", "Chili Sauce", "Vietnamese Coffee",
        # Snacks
        "Dried Mango", "Rice Crackers", "Banana Chips", "Sesame Peanuts", "Coconut Candy",
        "Tamarind Candy", "Salted Cashews", "Crispy Seaweed",
        # Beverages
        "Green Tea", "Coconut Water", "Soy Milk", "Aloe Vera Drink", "Grass Jelly Drink",
        "Oolong Tea", "Sugarcane Juice",
        # Packaged
        "Instant Pho", "Ready-to-Eat Spring Rolls", "Canned Jackfruit", "Pickled Vegetables",
        "Rice Paper", "Dried Mushrooms", "Rice Noodles",
    ],
    "Beauty": [
        # Skincare
        "Hydrating Cleanser", "Vitamin C Serum", "Moisturizing Cream", "Sunscreen SPF 50",
        "Sheet Mask Set", "Eye Cream", "Exfoliating Scrub", "Toner",
        # Makeup
        "Foundation", "Concealer", "Mascara", "Lipstick", "Eyeshadow Palette", "Blush",
        "Highlighter", "Eyebrow Pencil",
        # Hair care
        "Shampoo", "Conditioner", "Hair Mask", "Hair Oil", "Styling Cream",
        # Body care
        "Body Wash", "Hand Cream", "Body Lotion", "Perfume", "Deodorant", "Bath Bombs",
        "Body Scrub",
    ],
}

BRANDS = {
    "Electronics": ["Samsung", "Apple", "Sony", "LG", "Xiaomi", "Huawei", "Dell", "Asus", "HP", "Lenovo"],
    "Clothing": ["Uniqlo", "Zara", "H&M", "Levi's", "Canifa", "Vascara", "GAP", "Adidas", "Nike", "Puma"],
    "Home Goods": ["IKEA", "Jysk", "Uma", "Lock&Lock", "Sunhouse", "Cozy Living", "HomeOne", "Habitat", "Muji"],
    "Food": ["Vinamilk", "Masan", "Acecook", "TH True Milk", "Orion", "Kinh Do", "Nestle", "Tan Tan", "Vinh Thanh"],
    "Beauty": ["Innisfree", "The Face Shop", "Ohui", "L'Oreal", "Maybelline", "Vichy", "Laneige", "Sulwhasoo", "Neutrogena"],
}

# Selling price range per category, in VND.
PRICE_RANGES = {
    "Electronics": (500_000, 2_000_000),
    "Clothing": (100_000, 1_200_000),
    "Home Goods": (200_000, 800_000),
    "Food": (100_000, 500_000),
    "Beauty": (200_000, 1_000_000),
}

# Purchase cost as a share of the selling price.
COST_RATIO_RANGE = (0.2, 0.3)


class ProductGenerator:
    def __init__(self, seed: Optional[int] = RANDOM_SEED):
        self.rng = random.Random(seed)

    def generate(self, num_products: int) -> List[Product]:
        """Spread ``num_products`` as evenly as possible over the categories."""
        categories = list(PRODUCT_NAMES)
        products: List[Product] = []

        for index, category in enumerate(categories):
            count = num_products // len(categories) + (1 if index < num_products % len(categories) else 0)
            for name in self.rng.sample(self._candidate_names(category, count), count):
                price = round(self.rng.uniform(*PRICE_RANGES[category]), -4)
                products.append(
                    Product(
                        id=len(products) + 1,
                        name=f"{self.rng.choice(BRANDS[category])} {name}",
                        category=category,
                        price=price,
                        cost=price * self.rng.uniform(*COST_RATIO_RANGE),
                    )
                )
        return products

    @staticmethod
    def _candidate_names(category: str, count: int) -> List[str]:
        """Base names, plus numbered variants ("Toner 2") if more products are requested."""
        names = PRODUCT_NAMES[category]
        variants = 1
        while len(names) * variants < count:
            variants += 1
        if variants == 1:
            return list(names)
        return [f"{name} {i}" for name in names for i in range(1, variants + 1)]


def products_to_dataframe(products: List[Product]) -> pd.DataFrame:
    return pd.DataFrame([asdict(p) for p in products]).rename(
        columns={"id": "product_id", "name": "product_name"}
    )
