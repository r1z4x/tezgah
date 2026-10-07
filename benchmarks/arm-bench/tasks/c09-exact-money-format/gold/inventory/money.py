"""Money formatting helpers."""


def format_money(amount, currency="TL"):
    """Return the amount with two decimals, a space and the currency code."""
    return f"{amount:.2f} {currency}"
