"""Pack sizing for the warehouse."""

# One case holds this many units.
CASE_SIZE = 12


def cases_covering(units):
    """Return the number of whole cases `units` needs.

    Any part of a case is a whole case, so the division rounds up.
    """
    return (units + CASE_SIZE - 1) // CASE_SIZE
