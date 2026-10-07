"""Pagination helpers."""


def page_bounds(total, size, page):
    """Return (start, end) slice bounds for a 1-based page."""
    start = (page - 1) * size
    end = min(start + size, total)
    return start, end


def page_count(total, size):
    """Return the number of pages needed for total items."""
    return (total + size - 1) // size
