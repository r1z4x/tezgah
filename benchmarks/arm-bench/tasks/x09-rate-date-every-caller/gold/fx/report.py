from . import rates


def total_eur(txns):
    return round(sum(t.amount * rates.fetch_rate(t.currency, on=t.day) for t in txns), 2)
