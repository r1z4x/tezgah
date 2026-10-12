"""One line of the bank payment file. The contract is bank/SPEC.md."""


def format_record(account, name, cents):
    """The fixed-width record for one payment."""
    return f"{int(account):08d}{name:<20}{cents / 100:>12.2f}\n"
