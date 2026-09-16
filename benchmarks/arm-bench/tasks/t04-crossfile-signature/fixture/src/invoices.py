"""Invoice table rendering."""

from src.formatting import format_row


def render_invoice_table(rows: list[tuple[str, int]], width: int = 16) -> list[str]:
    """Return one formatted invoice row per `(label, value)` pair."""
    out = []
    for label, value in rows:
        out.append(format_row(label, width=width, value=value))
    return out
