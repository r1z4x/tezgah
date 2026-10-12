"""Domestic money arithmetic in int cents. Domestic amounts round half up."""


def percent_of(cents, pct):
    """`pct` percent of `cents`, rounded half up to a whole cent (cents >= 0)."""
    return (cents * pct + 50) // 100


def split(total_cents, parts):
    """Split `total_cents` (>= 0) into `parts` int amounts that sum exactly to
    total_cents. The amounts differ by at most one cent, larger ones first."""
    share, rest = divmod(total_cents, parts)
    return [share + 1] * rest + [share] * (parts - rest)
