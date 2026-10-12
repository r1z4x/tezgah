from . import providers


def convert_all(txns, source="ecb"):
    get = providers.SOURCES[source]
    return [round(t.amount * get(t.currency, on=t.day), 2) for t in txns]
