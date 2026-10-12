DEPOSIT_SHARE = 0.25


def deposit_cents(total):
    """The deposit taken when a reservation is made: a quarter of the total."""
    return round(total * DEPOSIT_SHARE * 100)
