"""Name folding for catalogue listings."""


def fold(name: str) -> str:
    """Return the comparison key a display name sorts by."""
    return name.lower()
