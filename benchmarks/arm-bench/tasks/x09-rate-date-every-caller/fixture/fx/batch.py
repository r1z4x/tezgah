from . import providers


def convert_all(txns, source="ecb"):
    get = providers.SOURCES[source]
    return [round(t.amount * get(t.currency), 2) for t in txns]
