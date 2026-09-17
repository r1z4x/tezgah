"""The end-of-day order feed."""

# sku, unit price in whole cents, quantity
FEED = [
    ("A1", 1200, 2),
    ("B2", 500, 3),
    ("C3", 250, 4),
]


def load_rows():
    """Return the process-wide rows, one dict per line of the feed.

    The store fills each row's `total`; a consumer reads the rows as they are.
    """
    return [{"sku": sku, "amount": amount, "qty": qty, "total": amount * qty}
            for sku, amount, qty in FEED]
