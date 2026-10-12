"""Plain-text reports over invoices."""
from billing import invoice


def summary(invoices):
    """One line per invoice, "<id>: <due>", where due is the amount in cents that
    invoice.total charges for it."""
    return "\n".join("%s: %d" % (inv["id"], invoice.total(inv)) for inv in invoices)
