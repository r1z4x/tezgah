"""Warehouse reporting, built on the stock helpers."""

from src.stock import available, backorder_units


def shortage_rows(items, wanted_by_sku):
    """Return `(sku, backorder)` for every sku that cannot be filled in full."""
    rows = []
    for item in items:
        short = backorder_units(item, wanted_by_sku.get(item["sku"], 0))
        if short:
            rows.append((item["sku"], short))
    return rows


def fillable_now(items, wanted_by_sku):
    """Return how many of the wanted units can be reserved right now."""
    return sum(min(wanted_by_sku.get(item["sku"], 0), available(item))
               for item in items)
