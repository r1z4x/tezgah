from .money import to_cents


def discount_cents(amount, percent):
    """The discount on `amount` at `percent` (0-100), in cents."""
    return to_cents(amount * percent / 100)
