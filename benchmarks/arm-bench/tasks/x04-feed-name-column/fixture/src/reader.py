"""Read a stock feed back (format: docs/FEED.md).

Used by src/reconcile.py on today's feed and on every archived one.
"""


def split_fields(line):
    """Split one feed line on the `|` separators, undoing `\\` escapes."""
    fields, cur, chars = [], [], iter(line)
    for ch in chars:
        if ch == "\\":
            cur.append(next(chars, ""))
        elif ch == "|":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def parse_line(line):
    sku, qty, price = split_fields(line)
    return {"sku": sku, "qty": int(qty), "price_cents": int(price)}


def read_feed(text):
    return [parse_line(line) for line in text.splitlines() if line.strip()]
