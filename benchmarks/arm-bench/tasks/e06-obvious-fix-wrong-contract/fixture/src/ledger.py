"""The end-of-day order feed."""

# sku, unit price in whole cents, quantity
FEED = [
    ("A1", 1200, 2),
    ("B2", 500, 3),
    ("C3", 250, 4),
]


def load_rows():
    """Return the process-wide rows, one dict per line of the feed."""
    return [{"sku": sku, "amount": amount, "qty": qty, "total": None}
            for sku, amount, qty in FEED]
