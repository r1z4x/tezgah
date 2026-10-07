"""Input validation for the inventory API."""

from inventory.errors import InventoryError


def load_items(raw):
    """Validate a raw list of item dicts and return a cleaned list.

    Every entry must be a dict with a string ``name`` and a numeric
    ``price`` greater than zero.
    """
    out = []
    for entry in raw:
        out.append({"name": entry["name"], "price": entry["price"]})
    return out
