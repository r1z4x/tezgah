"""Renders size reports for the export pipeline."""

from src import units


def render_summary(items) -> int:
    """Return the total size of `items`, in bytes.

    `items` is a sequence of ``(name, size)`` pairs.
    """
    total_kib = 0
    for _name, size in items:
        total_kib += units.format_bytes(size)
    return total_kib * 1024
