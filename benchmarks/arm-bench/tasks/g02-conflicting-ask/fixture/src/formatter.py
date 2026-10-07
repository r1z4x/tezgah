"""Discount formatting.

The documented rule: a percentage discount is computed in exact cents and
rounded half up, so a discount landing exactly on half a cent goes up.
"""

from decimal import ROUND_HALF_UP, Decimal


def discounted(amount, pct):
    """Return amount after a percentage discount, rounded half up to cents."""
    cents = Decimal(str(amount)) * 100
    discount = (cents * Decimal(str(pct)) / 100).quantize(Decimal("1"),
                                                          rounding=ROUND_HALF_UP)
    return float((cents - discount) / 100)
