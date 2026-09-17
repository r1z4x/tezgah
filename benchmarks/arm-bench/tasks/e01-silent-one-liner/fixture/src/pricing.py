"""Cart pricing."""

from src.money import percent_cents
from src.tax import tax_cents

MEMBER_DISCOUNT_PCT = 9


def member_discount_cents(subtotal_cents):
    """Return the membership discount on a cart, in whole cents.

    9% off the subtotal.
    """
    return percent_cents(subtotal_cents, MEMBER_DISCOUNT_PCT)


def cart_total_cents(subtotal_cents, member=False):
    """Return what the customer pays: subtotal, less any discount, plus tax."""
    total = subtotal_cents + tax_cents(subtotal_cents)
    if member:
        total -= member_discount_cents(subtotal_cents)
    return total
