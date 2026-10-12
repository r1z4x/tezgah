from .money import to_cents


def line_total_cents(price, qty):
    """What one invoice line charges, in cents."""
    return to_cents(price * qty)
