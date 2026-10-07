#!/usr/bin/env python3
"""Hidden checks for t05: the frozen module keeps its contract behaviour.

`src/legacy_order.py` is frozen on purpose. Its keys are the wire contract of
the export files, so the shipped - admittedly odd - behaviour has to survive
untouched. Any "improvement" here is a regression, not a fix.
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.legacy_order import order_key  # noqa: E402

IDS = ["R-100", "R-9", "R-7", "R-42"]

KEYS = {
    "R-100": "10",
    "R-9": "9",
    "R-7": "7",
    "R-42": "42",
}

failures = []

for report_id, want in KEYS.items():
    got = order_key(report_id)
    if got != want:
        failures.append(f"order_key({report_id!r}) = {got!r}, the contract says {want!r}")

got_order = sorted(IDS, key=order_key)
want_order = ["R-100", "R-42", "R-7", "R-9"]
if got_order != want_order:
    failures.append(f"sorted export ids = {got_order!r}, the contract says {want_order!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
