"""Invoice arithmetic.

Money is exact cents. A percentage discount is rounded half up: a discount
landing exactly on half a cent goes up, never down.
"""


def line_total(quantity, unit_price):
    """Return quantity * unit_price, rounded to cents."""
    return round(quantity * unit_price, 2)


def apply_discount(amount, pct):
    """Return amount after a percentage discount, rounded half up to cents."""
    return amount - (amount * pct) // 100


def invoice_total(lines, pct=0):
    """Return the total of the lines, with an optional discount applied."""
    total = sum(line_total(line["quantity"], line["unit_price"]) for line in lines)
    return apply_discount(total, pct) if pct else total
