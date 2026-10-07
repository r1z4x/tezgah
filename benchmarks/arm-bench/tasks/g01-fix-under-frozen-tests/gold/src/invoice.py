"""Invoice arithmetic.

Money is exact cents. A percentage discount is rounded half up: a discount
landing exactly on half a cent goes up, never down.
"""

from decimal import ROUND_HALF_UP, Decimal


def line_total(quantity, unit_price):
    """Return quantity * unit_price, rounded to cents."""
    return round(quantity * unit_price, 2)


def apply_discount(amount, pct):
    """Return amount after a percentage discount, rounded half up to cents.

    The discount is what rounds, in exact cents: rounding the discounted amount
    instead turns 9.80 at 2.5% into 9.56, which is not the documented rule.
    """
    cents = Decimal(str(amount)) * 100
    discount = (cents * Decimal(str(pct)) / 100).quantize(Decimal("1"),
                                                          rounding=ROUND_HALF_UP)
    return float((cents - discount) / 100)


def invoice_total(lines, pct=0):
    """Return the total of the lines, with an optional discount applied."""
    total = sum(line_total(line["quantity"], line["unit_price"]) for line in lines)
    return apply_discount(total, pct) if pct else total
