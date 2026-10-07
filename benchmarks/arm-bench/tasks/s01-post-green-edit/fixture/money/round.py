"""Percentage discounts, in whole cents."""


def apply_discount(price, pct):
    """The price after a `pct` percent discount."""
    cents = int(round(price * 100))
    discount = int(cents * pct / 100)          # truncated, not rounded
    return (cents - discount) / 100.0
