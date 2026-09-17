"""Case labels and the shipment weight that follows them."""

from src.units import cases_covering

KG_PER_CASE = 8


def case_labels(units):
    """Return the number of case labels `units` needs."""
    return cases_covering(units)


def shipping_weight_kg(units):
    """Return the weight of the shipment carrying `units`."""
    return case_labels(units) * KG_PER_CASE
