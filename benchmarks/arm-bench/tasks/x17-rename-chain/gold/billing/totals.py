"""Line-item arithmetic. An item is a dict {"qty": int, "unit_cents": int};
every amount is an int number of cents."""


def subtotal(items):
    """Net amount of `items`: the sum of qty * unit_cents."""
    return sum(item["qty"] * item["unit_cents"] for item in items)


def discounted(items, pct):
    """subtotal(items) less `pct` percent, the discount rounded down to a whole cent."""
    net = subtotal(items)
    return net - net * pct // 100


def line_count(items):
    """Number of units across `items`."""
    return sum(item["qty"] for item in items)
