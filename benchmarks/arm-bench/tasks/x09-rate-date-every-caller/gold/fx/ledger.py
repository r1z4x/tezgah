from .rates import fetch_rate as lookup


def post(txn):
    """The ledger entry for one transaction: its day, the rate used, the EUR."""
    rate = lookup(txn.currency, on=txn.day)
    return {"day": txn.day.isoformat(), "rate": rate,
            "eur": round(txn.amount * rate, 2)}
