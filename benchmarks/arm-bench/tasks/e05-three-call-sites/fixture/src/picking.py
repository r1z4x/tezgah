"""What the picker fetches."""

from src.units import CASE_SIZE


def cases_to_pick(units):
    """Return the number of cases the picker takes off the shelf."""
    return units // CASE_SIZE
