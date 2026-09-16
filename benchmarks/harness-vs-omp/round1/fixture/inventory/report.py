"""Human-readable inventory reports."""

from inventory.core import calc_total, find_item
from inventory.parsing import parse_quantity


def summary(items):
    """Return a one-line summary of the inventory."""
    return f"items={len(items)} total={calc_total(items):.2f}"


def describe(items, name):
    """Return a line describing one item, or a not-found message."""
    item = find_item(items, name)
    if item is None:
        return f"{name}: not found"
    return f"{name}: {item['price']:.2f}"


def parse_quantities(texts):
    """Parse a list of quantity strings."""
    return [parse_quantity(t) for t in texts]
