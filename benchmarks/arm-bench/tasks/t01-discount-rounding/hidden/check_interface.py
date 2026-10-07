#!/usr/bin/env python3
"""Hidden interface checks for t01: the public signature may not change."""
import inspect
import os
import sys

sys.path.insert(0, os.getcwd())

from src.pricing import apply_discount  # noqa: E402

failures = []
params = list(inspect.signature(apply_discount).parameters)
if params != ["price", "pct"]:
    failures.append(f"signature is {params}, expected ['price', 'pct']")

try:
    got = apply_discount(price=19.99, pct=15)
except TypeError as exc:
    failures.append(f"keyword call raised {exc!r}")
else:
    if abs(got - 16.99) > 1e-9:
        failures.append(f"keyword call returned {got!r}, want 16.99")

got = apply_discount(100.0, 10)
if not isinstance(got, float):
    failures.append(f"return type is {type(got).__name__}, want float")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
