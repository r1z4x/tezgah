"""The billing run."""

from src.ledger import load_rows


def charge_cents(rows=None):
    """Return the amount to charge, in whole cents: the sum of the row totals."""
    rows = load_rows() if rows is None else rows
    return sum(row["total"] for row in rows)
