"""The end-of-day report."""

from src.ledger import load_rows

MEMBER_DISCOUNT_PCT = 10


def line_total_cents(total_cents, member=False):
    """Return a line total after any member discount, in whole cents."""
    if not member:
        return total_cents
    return total_cents - total_cents * MEMBER_DISCOUNT_PCT // 100


def render(member=False):
    """Return the report text: one `sku xqty total` line per row."""
    lines = []
    for row in load_rows():
        total = line_total_cents(row["total"], member)
        lines.append(f'{row["sku"]} x{row["qty"]} {total}')
    return "\n".join(lines)
