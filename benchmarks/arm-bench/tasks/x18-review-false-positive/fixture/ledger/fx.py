"""Currency conversion for settlement.

The settlement agreement fixes the rounding of converted amounts: whole cents,
round half to even (banker's rounding), so that half-cent results do not drift
in one direction across a batch. This differs from domestic amounts on purpose.
"""
from decimal import ROUND_HALF_EVEN, Decimal


def convert(cents, rate):
    """`cents` converted at `rate` (a decimal string), rounded half to even."""
    exact = Decimal(cents) * Decimal(rate)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
