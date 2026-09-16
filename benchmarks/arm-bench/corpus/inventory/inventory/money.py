"""Money formatting helpers."""


def format_money(amount, currency="TL"):
    """Return the amount formatted with two decimals and a currency."""
    return f"{amount:.2f}{currency}"
