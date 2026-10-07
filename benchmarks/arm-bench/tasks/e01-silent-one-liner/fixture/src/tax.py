"""Sales tax."""

from src.money import percent_cents

TAX_PCT = 7


def tax_cents(subtotal_cents):
    """Return the sales tax on a cart, in whole cents.

    7% of the subtotal.
    """
    return percent_cents(subtotal_cents, TAX_PCT)
