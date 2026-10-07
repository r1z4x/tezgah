"""Proration: the price of part of a cycle."""

CYCLE_DAYS = 30


def prorated_cents(monthly_cents, days):
    """Return the price for `days` of a cycle, in whole cents.

    Whole cents only. The part of a cent is dropped, so a part of a cycle never
    comes out above its exact share.
    """
    return monthly_cents * days // CYCLE_DAYS
