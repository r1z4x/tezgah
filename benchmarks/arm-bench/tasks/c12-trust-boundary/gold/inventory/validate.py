"""Input validation for the inventory API."""

from inventory.errors import InventoryError


def load_items(raw):
    """Validate a raw list of item dicts and return a cleaned list.

    Every entry must be a dict with a string ``name`` and a numeric
    ``price`` greater than zero.
    """
    out = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise InventoryError(f"item {index}: name required")
        name = entry.get("name")
        if not isinstance(name, str):
            raise InventoryError(f"item {index}: name required")
        price = entry.get("price")
        if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
            raise InventoryError(f"item {index}: price must be positive")
        out.append({"name": name, "price": price})
    return out
