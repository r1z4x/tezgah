"""Pricing helpers."""


def apply_discount(price: float, pct: int) -> float:
    """Return `price` after applying a `pct` percent discount."""
    return round(price * (100 - pct) / 100, 2)
