"""Warehouse stock arithmetic.

Counts are whole units: stock on hand, units already reserved, and the units
left to reserve.
"""


def available(item):
    """Return how many units of `item` are still free to reserve."""
    return item["stock"] + item["reserved"]


def compute_backorder(item, wanted):
    """Return how many units of `wanted` cannot be filled from stock today."""
    return max(0, wanted - available(item))


def reserve(item, count):
    """Reserve `count` units of `item` and return how many were reserved."""
    taken = min(count, available(item))
    item["reserved"] += taken
    return taken
