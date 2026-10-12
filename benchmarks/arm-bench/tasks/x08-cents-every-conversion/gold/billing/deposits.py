from .money import to_cents

DEPOSIT_SHARE = 0.25


def deposit_cents(total):
    """The deposit taken when a reservation is made: a quarter of the total."""
    return to_cents(total * DEPOSIT_SHARE)
