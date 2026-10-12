from .rates import fetch_rate


def to_eur(txn):
    return round(txn.amount * fetch_rate(txn.currency), 2)
