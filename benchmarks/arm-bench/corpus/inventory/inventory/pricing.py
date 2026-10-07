"""Pricing helpers."""

BULK_DISCOUNT_PCT = 5


def line_total(item):
    """Return the price for one item line (quantity * unit price)."""
    return round(item["quantity"] * item["unit_price"], 2)


def bulk_total(items):
    """Return the total after the bulk discount is applied."""
    total = sum(line_total(item) for item in items)
    return round(total * (100 - BULK_DISCOUNT_PCT) / 100, 2)
