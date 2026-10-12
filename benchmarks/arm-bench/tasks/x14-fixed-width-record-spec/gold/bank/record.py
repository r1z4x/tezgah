"""One line of the bank payment file. The contract is bank/SPEC.md."""
import unicodedata


def _ascii(name):
    bare = "".join(ch for ch in unicodedata.normalize("NFKD", name)
                   if not unicodedata.combining(ch))
    return "".join(ch if ch.isascii() else "?" for ch in bare)


def format_record(account, name, cents):
    """The fixed-width record for one payment."""
    if len(account) > 8:
        raise ValueError("account %r is wider than 8 digits" % account)
    text = "" if name is None else _ascii(name)
    if len(text) > 20:
        text = text[:19] + "~"
    sign = "-" if cents < 0 else ""
    units, rest = divmod(abs(cents), 100)
    amount = "%s%d.%02d" % (sign, units, rest)
    if len(amount) > 12:
        raise OverflowError("amount %s is wider than 12 characters" % amount)
    return account.zfill(8) + text.ljust(20) + amount.rjust(12) + "\r\n"
