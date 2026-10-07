"""Input validation for the inventory API."""

from inventory.errors import InventoryError


def load_items(raw):
    """Validate a raw list of item dicts and return a cleaned list.

    Every entry must be a dict with a string ``name`` and a numeric
    ``price`` greater than zero.
    """
    out = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise InventoryError(f"invalid entry: {entry!r}")
        name = entry.get("name")
        price = entry.get("price")
        if not isinstance(name, str) or not name:
            raise InventoryError(f"invalid name: {name!r}")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise InventoryError(f"invalid price: {price!r}")
        out.append({"name": name, "price": price})
    return out
