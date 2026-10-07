"""Proration: the price of part of a cycle."""

CYCLE_DAYS = 30


def prorated_cents(monthly_cents, days, round_up=True):
    """Return the price for `days` of a cycle, in whole cents.

    A charge rounds the part of a cent up, in the member's favour. A caller
    whose money is a hold asks for `round_up=False`: a hold must not cover more
    than the exact share.
    """
    product = monthly_cents * days
    if round_up:
        return -(-product // CYCLE_DAYS)        # ceiling division
    return product // CYCLE_DAYS
