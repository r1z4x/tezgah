from .money import to_cents


def refund_cents(amount):
    """What we pay back for a returned amount, in cents."""
    return to_cents(amount)
