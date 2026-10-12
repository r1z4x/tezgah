from .money import to_cents

RATES = {"standard": 4.35, "express": 9.95, "pickup": 0.0}


def shipping_cents(method):
    return to_cents(RATES[method])
