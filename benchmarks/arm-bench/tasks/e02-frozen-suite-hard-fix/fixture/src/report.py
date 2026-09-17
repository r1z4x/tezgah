"""Report rendering."""

from .catalog import sorted_names


def render(names):
    """Return the names in release order, joined for the release report."""
    return " | ".join(sorted_names(names))
