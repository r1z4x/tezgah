"""Turns parsed rows into the form the downstream reader expects."""

from src import report


def export_row(row) -> dict:
    """Return the exported form of `row`, a ``{"name": ..., "size": ...}`` map."""
    total = report.render_summary([(row["name"], row["size"])])
    return {"name": row["name"], "bytes": total}
