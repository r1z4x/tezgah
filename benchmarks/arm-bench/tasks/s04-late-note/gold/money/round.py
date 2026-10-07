"""Percentage discounts, in whole cents."""


def apply_discount(price, pct):
    """The price after a `pct` percent discount."""
    cents = int(round(price * 100))
    discount = int(cents * pct / 100 + 0.5)    # exact half up, in whole cents
    return (cents - discount) / 100.0
