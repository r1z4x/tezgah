VAT_RATE = 0.2


def tax_cents(net, rate=VAT_RATE):
    """VAT on a net amount, in cents."""
    return int(round(net * rate, 2) * 100)
