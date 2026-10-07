"""Quantity parsing."""

from inventory.errors import InventoryError


def parse_quantity(text):
    """Parse a quantity such as ' 12 ' into an int.

    Anything that is not a whole number raises InventoryError, so no caller ever
    sees a bare ValueError from int().
    """
    try:
        return int(text.strip())
    except (AttributeError, ValueError):
        raise InventoryError(f"invalid quantity: {text}")
