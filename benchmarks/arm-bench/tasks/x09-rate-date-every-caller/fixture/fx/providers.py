"""Rate sources by name. Every source takes the same arguments as
rates.fetch_rate and returns the same thing."""
from .rates import fetch_rate

# Currencies pegged to the euro: the rate never changes.
PEGGED = {"BGN": 0.5113, "XOF": 0.0015}


def fixed_rate(base, quote="EUR"):
    if base == quote:
        return 1.0
    return PEGGED[base]


SOURCES = {"ecb": fetch_rate, "fixed": fixed_rate}
