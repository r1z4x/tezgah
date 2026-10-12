import math


def refund_cents(amount):
    """What we pay back for a returned amount, in cents."""
    return math.floor(100 * amount)
