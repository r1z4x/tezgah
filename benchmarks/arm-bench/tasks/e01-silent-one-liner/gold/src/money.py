"""Whole-cent percentages."""


def percent_cents(amount_cents, pct, round_up=False):
    """Return `pct` percent of `amount_cents`, in whole cents.

    The odd fraction of a cent goes to the customer, so a caller whose money is
    a discount asks for `round_up`.
    """
    product = amount_cents * pct
    if round_up:
        return -(-product // 100)       # ceiling division
    return product // 100
