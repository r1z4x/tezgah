from .money import to_cents

VAT_RATE = 0.2


def tax_cents(net, rate=VAT_RATE):
    """VAT on a net amount, in cents."""
    return to_cents(net * rate)
