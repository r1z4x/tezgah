"""Line-item arithmetic. An item is a dict {"qty": int, "unit_cents": int};
every amount is an int number of cents."""


def calc(items):
    """Net amount of `items`: the sum of qty * unit_cents."""
    return sum(item["qty"] * item["unit_cents"] for item in items)


def line_count(items):
    """Number of units across `items`."""
    return sum(item["qty"] for item in items)
