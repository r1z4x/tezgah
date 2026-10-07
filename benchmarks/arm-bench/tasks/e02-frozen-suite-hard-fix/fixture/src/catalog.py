"""Catalogue listing order.

The order the release notes use is documented in README.md.
"""

from .textfold import fold


def sorted_names(names):
    """Return the names in release order."""
    return sorted(names, key=fold)
