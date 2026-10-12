from datetime import date

# Units of EUR per unit of the currency, by the day the rate was published.
PUBLISHED = {
    "USD": {date(2026, 1, 5): 0.91, date(2026, 1, 6): 0.95, date(2026, 1, 7): 0.97},
    "GBP": {date(2026, 1, 5): 1.15, date(2026, 1, 6): 1.17, date(2026, 1, 7): 1.19},
}


def fetch_rate(base, quote="EUR", *, on):
    """Units of `quote` per unit of `base`: the rate published on `on` (a
    datetime.date), or failing that the most recent one published before it."""
    if base == quote:
        return 1.0
    if quote != "EUR":
        raise ValueError("only EUR quotes are published")
    table = PUBLISHED[base]
    days = [day for day in table if day <= on]
    if not days:
        raise LookupError("no %s rate published by %s" % (base, on))
    return table[max(days)]
