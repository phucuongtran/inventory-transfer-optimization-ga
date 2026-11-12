"""Plain data classes shared across the project."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Store:
    """A retail store and its location."""

    id: int
    name: str
    city: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Product:
    """A product in the catalog. Prices are in VND."""

    id: int
    name: str
    category: str
    price: float
    cost: float


@dataclass(frozen=True)
class Transfer:
    """Move ``units`` of ``product_id`` from ``from_store`` to ``to_store``.

    Frozen (immutable) on purpose: optimizers can freely share Transfer objects
    between candidate plans without one plan accidentally editing another.
    """

    from_store: int
    to_store: int
    product_id: int
    units: int
