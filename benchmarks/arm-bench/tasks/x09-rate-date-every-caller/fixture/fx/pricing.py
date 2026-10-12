from functools import partial

from .rates import fetch_rate

eur_rate = partial(fetch_rate, quote="EUR")


def invoice_line(txn):
    rate = eur_rate(txn.currency)
    return "%s %.2f EUR @ %.4f" % (txn.day.isoformat(), txn.amount * rate, rate)
