"""What the picker fetches."""

from src.units import cases_covering


def cases_to_pick(units):
    """Return the number of cases the picker takes off the shelf."""
    return cases_covering(units)
