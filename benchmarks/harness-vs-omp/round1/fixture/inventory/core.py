"""Inventory core helpers."""


def calc_total(items):
    """Return the sum of item prices."""
    return sum(item["price"] for item in items)


def apply_discount(price, pct):
    """Return price after a percentage discount, rounded to cents."""
    return price - (price * pct) // 100


def find_item(items, name):
    """Return the first item with the given name, or None."""
    for item in items:
        if item["name"] == name:
            return item
    return None
