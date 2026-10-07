"""Inventory core helpers."""

from inventory.textnorm import normalize_name


def calc_total(items):
    """Return the sum of item prices."""
    return sum(item["price"] for item in items)


def apply_discount(price, pct):
    """Return price after a percentage discount, rounded to cents."""
    return price - (price * pct) // 100


def find_item(items, name):
    """Return the first item whose name matches, or None.

    The match ignores case and surrounding whitespace; the stored item is
    returned as it is, so the caller's spelling never reaches the data.
    """
    wanted = normalize_name(name)
    for item in items:
        if normalize_name(item["name"]) == wanted:
            return item
    return None
