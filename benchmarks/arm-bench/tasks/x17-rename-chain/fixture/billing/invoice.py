"""Invoices: {"id": str, "items": [item, ...]}."""
from billing.totals import calc

TAX_RATE_PCT = 20


def tax(cents):
    """Tax on `cents` at TAX_RATE_PCT percent, rounded half up to a whole cent."""
    return (cents * TAX_RATE_PCT + 50) // 100


def total(invoice):
    """Amount due for `invoice`, in cents: net plus tax."""
    net = calc(invoice["items"])
    return net + tax(net)
