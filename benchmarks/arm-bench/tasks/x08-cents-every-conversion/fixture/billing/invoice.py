def line_total_cents(price, qty):
    """What one invoice line charges, in cents."""
    return int(price * qty * 100)
