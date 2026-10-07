"""Shopping cart helpers."""


def make_cart(items=[]):
    """Create a cart; passing items seeds it."""
    return {"items": items}


def add_item(cart, name, price, qty=1):
    """Append an item to the cart and return the cart."""
    cart["items"].append({"name": name, "price": price, "qty": qty})
    return cart
