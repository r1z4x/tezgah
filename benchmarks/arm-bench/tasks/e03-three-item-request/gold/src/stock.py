"""Warehouse stock arithmetic.

Counts are whole units: stock on hand, units already reserved, and the units
left to reserve.
"""


def available(item):
    """Return how many units of `item` are still free to reserve."""
    return item["stock"] - item["reserved"]


def backorder_units(item, wanted):
    """Return how many units of `wanted` cannot be filled from stock today."""
    return max(0, wanted - available(item))


def reserve(item, count):
    """Reserve `count` units of `item` and return how many were reserved.

    A reservation is all or nothing: asking for more than is free raises
    `ValueError` and leaves `item` as it was, rather than quietly reserving
    fewer units than the caller asked for.
    """
    free = available(item)
    if count > free:
        raise ValueError("cannot reserve %d of %s: %d available"
                         % (count, item["sku"], free))
    item["reserved"] += count
    return count
