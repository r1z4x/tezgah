"""Parsing helpers for inventory input."""

import unicodedata


def parse_quantity(text):
    """Parse a quantity such as ' 12 ' into an int.

    Numbers pasted from documents can carry invisible format characters
    (zero-width space, BOM, word joiners, directional marks); those are
    Unicode category ``Cf`` and are dropped before conversion.
    """
    visible = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return int(visible.strip())
