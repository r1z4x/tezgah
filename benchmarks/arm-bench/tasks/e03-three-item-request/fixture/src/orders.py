"""Order lines, built on the stock helpers."""

from src.stock import compute_backorder


def line_status(item, wanted):
    """Return a one-line status for one order line."""
    short = compute_backorder(item, wanted)
    if short:
        return "%s: %d short" % (item["sku"], short)
    return "%s: ready" % (item["sku"],)
