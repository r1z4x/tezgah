"""Domain errors."""


class InventoryError(Exception):
    """Raised for invalid inventory input."""


def require_positive(value, name):
    """Return value when it is positive, otherwise raise."""
    if value <= 0:
        raise InventoryError(f"{name} must be positive")
    return value
