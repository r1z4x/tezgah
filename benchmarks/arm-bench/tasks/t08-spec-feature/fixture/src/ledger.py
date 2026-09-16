"""Parsing and aggregation for the ledger CLI."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path


class LedgerError(Exception):
    """Raised when a ledger file cannot be read or parsed."""


def read_entries(path: str) -> list[tuple[str, Decimal]]:
    """Return the `(category, amount)` pairs recorded in the file at `path`.

    One entry per line: `CATEGORY AMOUNT`, separated by whitespace. Blank lines
    and lines whose first non-space character is `#` are ignored. A line that
    is not a category plus a finite decimal amount is a `LedgerError`.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(f"cannot read {path}: {exc.strerror}") from exc

    entries: list[tuple[str, Decimal]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise LedgerError(f"line {number}: malformed entry")
        try:
            amount = Decimal(parts[1])
        except InvalidOperation:
            raise LedgerError(f"line {number}: malformed entry") from None
        if not amount.is_finite():
            raise LedgerError(f"line {number}: malformed entry")
        entries.append((parts[0], amount))
    return entries


def totals(entries: list[tuple[str, Decimal]]) -> dict[str, Decimal]:
    """Return the summed amount per category."""
    out: dict[str, Decimal] = {}
    for category, amount in entries:
        out[category] = out.get(category, Decimal(0)) + amount
    return out
