from . import rates


def total_eur(txns):
    return round(sum(t.amount * rates.fetch_rate(t.currency) for t in txns), 2)
