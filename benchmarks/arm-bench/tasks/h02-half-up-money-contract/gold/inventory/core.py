"""Inventory core helpers."""

from decimal import ROUND_HALF_UP, Decimal


def calc_total(items):
    """Return the sum of item prices."""
    return sum(item["price"] for item in items)


def apply_discount(price, pct):
    """Return price after a percentage discount, rounded to cents.

    The contract is exact cents, rounded half up: a discount landing on half a
    cent goes up. Floats cannot carry that - `round(24.5)` is 24, and a tenth of
    a percent is not representable in binary - so the discount is taken off in
    cents with Decimal rather than in currency units with a float.
    """
    cents = Decimal(str(price)) * 100
    discount = (cents * Decimal(str(pct)) / 100).quantize(Decimal("1"),
                                                          rounding=ROUND_HALF_UP)
    return float((cents - discount) / 100)


def find_item(items, name):
    """Return the first item with the given name, or None."""
    for item in items:
        if item["name"] == name:
            return item
    return None
