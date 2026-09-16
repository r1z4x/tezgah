"""Order table rendering."""

from src.formatting import format_row


def render_order_table(rows: list[tuple[str, int]], width: int = 12) -> list[str]:
    """Return one formatted row per `(label, value)` pair."""
    return [format_row(label, width=width, value=value) for label, value in rows]
