#!/usr/bin/env python3
"""Hidden unit checks for t01. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.pricing import apply_discount  # noqa: E402

CASES = [
    (19.99, 15, 16.99),
    (100.0, 10, 90.0),
    (9.99, 10, 8.99),
    (250.0, 20, 200.0),
    (0.0, 50, 0.0),
    (19.99, 0, 19.99),
    (1234.56, 33, 827.16),
]

failures = []
for price, pct, want in CASES:
    got = apply_discount(price, pct)
    if abs(got - want) > 1e-9:
        failures.append(f"apply_discount({price}, {pct}) = {got!r}, want {want!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
