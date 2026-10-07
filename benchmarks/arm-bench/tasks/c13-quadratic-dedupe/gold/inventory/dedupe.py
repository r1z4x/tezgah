"""Sequence helpers."""


def unique(items):
    """Return items with duplicates removed, preserving order."""
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
