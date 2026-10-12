from decimal import ROUND_HALF_UP, Decimal


def to_cents(amount):
    """Integer cents for a float amount in currency units, rounded half up.

    Goes through the shortest decimal repr of the float, so 4.35 is 435 even
    though 4.35 * 100 == 434.99999999999994."""
    return int(Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP) * 100)
