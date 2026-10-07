#!/usr/bin/env python3
"""Score the impact answer by precision and recall, not set equality.

Exact equality cannot tell an over-broad answer (a transitive caller that does
not call the function) from a wrong one - the defect that made the historical
t19 look like a ground-truth limitation. This prints both numbers.
"""
import os
import re
import sys

EXPECTED = ['inventory/core.py', 'inventory/report.py', 'tests/test_core.py']
answer = os.path.join(os.getcwd(), "ANSWER.md")
if not os.path.exists(answer):
    print("no ANSWER.md")
    sys.exit(1)
with open(answer, encoding="utf-8") as fh:
    text = fh.read()
found = {m.strip() for m in re.findall(r"(?m)^\s*FILE:\s*(\S+)\s*$", text)}
if not found:
    print("ANSWER.md carries no 'FILE: <path>' line")
    sys.exit(1)
expected = set(EXPECTED)
misses = sorted(expected - found)
extra = sorted(found - expected)
precision = len(found & expected) / len(found)
recall = len(found & expected) / len(expected)
print("precision %.2f recall %.2f" % (precision, recall))
for path in misses:
    print("missing:", path)
for path in extra:
    print("not a direct call site:", path)
sys.exit(0 if not misses and not extra else 1)
