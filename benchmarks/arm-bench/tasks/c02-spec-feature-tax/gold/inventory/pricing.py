"""Pricing helpers."""

BULK_DISCOUNT_PCT = 5


def line_total(item):
    """Return the price for one item line (quantity * unit price)."""
    return round(item["quantity"] * item["unit_price"], 2)


def bulk_total(items):
    """Return the total after the bulk discount is applied."""
    total = sum(line_total(item) for item in items)
    return round(total * (100 - BULK_DISCOUNT_PCT) / 100, 2)


def total_with_tax(items, rate):
    """Return the summed price plus tax at `rate`, rounded to cents."""
    if rate < 0:
        raise ValueError("rate must not be negative")
    total = sum(item["price"] for item in items)
    return round(total + (total * rate), 2)
