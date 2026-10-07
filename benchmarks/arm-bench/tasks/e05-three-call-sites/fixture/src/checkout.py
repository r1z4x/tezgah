"""What the customer is billed."""

from src.units import CASE_SIZE


def billable_cases(units):
    """Return the number of cases `units` is billed as."""
    return units // CASE_SIZE
