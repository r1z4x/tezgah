"""Invoices: {"id": str, "items": [item, ...], "discount_pct": int (optional)}."""
from billing import config
from billing.totals import discounted


def tax(cents):
    """Tax on `cents` at config.TAX_RATE_PCT percent, rounded half up to a whole cent."""
    return (cents * config.TAX_RATE_PCT + 50) // 100


def total(invoice):
    """Amount due for `invoice`, in cents: the discounted net plus tax on it."""
    net = discounted(invoice["items"], invoice.get("discount_pct", 0))
    return net + tax(net)
