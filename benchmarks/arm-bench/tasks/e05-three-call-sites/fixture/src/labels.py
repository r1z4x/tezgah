"""Case labels and the shipment weight that follows them."""

from src.units import CASE_SIZE

KG_PER_CASE = 8


def case_labels(units):
    """Return the number of case labels `units` needs."""
    return units // CASE_SIZE


def shipping_weight_kg(units):
    """Return the weight of the shipment carrying `units`."""
    return case_labels(units) * KG_PER_CASE
