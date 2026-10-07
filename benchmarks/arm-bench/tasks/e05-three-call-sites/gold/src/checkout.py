"""What the customer is billed."""

from src.units import cases_covering


def billable_cases(units):
    """Return the number of cases `units` is billed as."""
    return cases_covering(units)
