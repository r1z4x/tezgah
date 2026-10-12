RATES = {"standard": 4.35, "express": 9.95, "pickup": 0.0}


def shipping_cents(method):
    return int(RATES[method]*100)
