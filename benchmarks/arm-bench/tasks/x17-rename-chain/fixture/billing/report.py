"""Plain-text reports over invoices."""
from billing import totals


def summary(invoices):
    """One line per invoice, "<id>: <due>", where due is the amount in cents that
    invoice.total charges for it."""
    lines = []
    for inv in invoices:
        net = totals.calc(inv["items"])
        due = net + (net * 20 + 50) // 100
        lines.append("%s: %d" % (inv["id"], due))
    return "\n".join(lines)
