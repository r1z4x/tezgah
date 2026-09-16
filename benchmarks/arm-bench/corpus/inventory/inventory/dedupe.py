"""Sequence helpers."""


def unique(items):
    """Return items with duplicates removed, preserving order."""
    out = []
    for i, item in enumerate(items):
        if item not in items[:i]:
            out.append(item)
    return out
