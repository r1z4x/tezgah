"""Inventory core helpers."""

from decimal import ROUND_HALF_UP, Decimal

from inventory.textnorm import normalize_name


def calc_total(items):
    """Return the sum of item prices."""
    return sum(item["price"] for item in items)


def apply_discount(price, pct):
    """Return price after a percentage discount, rounded to cents.

    Exact cents, rounded half up: a discount landing on half a cent goes up.
    """
    cents = Decimal(str(price)) * 100
    discount = (cents * Decimal(str(pct)) / 100).quantize(Decimal("1"),
                                                          rounding=ROUND_HALF_UP)
    return float((cents - discount) / 100)


def find_item(items, name):
    """Return the first item whose name matches, or None.

    The match ignores case and surrounding whitespace and returns the stored
    item unchanged.
    """
    wanted = normalize_name(name)
    for item in items:
        if normalize_name(item["name"]) == wanted:
            return item
    return None
