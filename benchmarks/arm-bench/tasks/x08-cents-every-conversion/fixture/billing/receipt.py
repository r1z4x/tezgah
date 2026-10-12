def receipt_line(label, amount):
    """One printed receipt line: the label, then the amount in cents."""
    return "%-12s %8d" % (label, amount * 100)
