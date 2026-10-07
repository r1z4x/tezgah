#!/usr/bin/env python3
"""Print a per-category summary of a ledger file.

Usage: ledger_cli.py [--largest N] FILE
"""

from __future__ import annotations

import sys
from decimal import Decimal

from ledger import LedgerError, read_entries, totals


def ranked(per_category: dict[str, Decimal], largest: int | None) -> list[tuple[str, Decimal]]:
    """Return the categories to print: name order, or the largest N by total."""
    if largest is None:
        return sorted(per_category.items())
    return sorted(per_category.items(), key=lambda item: (-item[1], item[0]))[:largest]


def report(per_category: dict[str, Decimal], largest: int | None) -> str:
    """Return the summary report for the per-category totals."""
    lines = [f"{category} {total:.2f}" for category, total in ranked(per_category, largest)]
    if largest is None:
        lines.append(f"TOTAL {sum(per_category.values()):.2f}")
    return "".join(line + "\n" for line in lines)


def parse_largest(raw: str) -> int | None:
    """Return the positive integer `raw` encodes, or None when it is invalid."""
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def main(argv: list[str]) -> int:
    args = list(argv)
    largest = None
    if args and args[0] == "--largest":
        args.pop(0)
        if not args:
            print("error: --largest expects a positive integer", file=sys.stderr)
            return 2
        raw = args.pop(0)
        largest = parse_largest(raw)
        if largest is None:
            print(f"error: --largest expects a positive integer, got {raw!r}", file=sys.stderr)
            return 2

    if len(args) != 1:
        print("error: expected exactly one FILE argument", file=sys.stderr)
        return 2

    try:
        entries = read_entries(args[0])
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(report(totals(entries), largest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
