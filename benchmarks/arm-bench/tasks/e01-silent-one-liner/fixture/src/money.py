"""Whole-cent percentages."""


def percent_cents(amount_cents, pct):
    """Return `pct` percent of `amount_cents`, in whole cents."""
    return amount_cents * pct // 100
