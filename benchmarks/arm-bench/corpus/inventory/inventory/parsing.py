"""Parsing helpers for inventory input."""


def parse_quantity(text):
    """Parse a quantity such as ' 12 ' into an int."""
    return int(text.strip())
