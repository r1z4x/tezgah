"""Parsing amounts typed by people."""
from decimal import Decimal, InvalidOperation

from ledger.errors import LedgerError


def parse_amount(text):
    """Parse a decimal amount such as "12.50", "1,234.50" or "-3" into int cents.
    Commas are thousands separators. Anything unparseable raises LedgerError."""
    try:
        value = Decimal(text.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise LedgerError("not an amount: %r" % (text,)) from exc
    return int(value * 100)
