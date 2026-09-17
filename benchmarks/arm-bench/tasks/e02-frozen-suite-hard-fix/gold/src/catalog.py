"""Catalogue listing order.

The order the release notes use is documented in README.md.
"""

from .textfold import fold


def sorted_names(names):
    """Return the names in release order.

    Decided by the folded key, ties by the ordinal order of the original
    spelling - which means the key carries the original name as its second
    element; the folded key alone leaves equal keys in input order.
    """
    return sorted(names, key=lambda name: (fold(name), name))
