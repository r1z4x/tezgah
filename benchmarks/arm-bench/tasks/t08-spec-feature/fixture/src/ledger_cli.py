#!/usr/bin/env python3
"""Print a per-category summary of a ledger file.

Usage: ledger_cli.py FILE
"""

from __future__ import annotations

import sys

from ledger import LedgerError, read_entries, totals


def report(per_category: dict) -> str:
    """Return the summary report for the per-category totals."""
    lines = [f"{category} {total:.2f}" for category, total in sorted(per_category.items())]
    lines.append(f"TOTAL {sum(per_category.values()):.2f}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("error: expected exactly one FILE argument", file=sys.stderr)
        return 2

    try:
        entries = read_entries(argv[0])
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(report(totals(entries)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
