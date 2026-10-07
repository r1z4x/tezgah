"""Shopping cart helpers."""


def make_cart(items=None):
    """Create a cart; passing items seeds it."""
    return {"items": list(items) if items is not None else []}


def add_item(cart, name, price, qty=1):
    """Append an item to the cart and return the cart."""
    cart["items"].append({"name": name, "price": price, "qty": qty})
    return cart
