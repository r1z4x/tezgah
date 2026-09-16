#!/usr/bin/env python3
"""The rename must be complete: the old symbol gone, the new one in use.

Ported from the historical runner's RENAME_TASKS check. The hidden test beside
this one guards behaviour; this guards the rename itself, because behaviour
alone cannot tell a completed rename from no change at all.
"""
import os
import re
import sys

OLD, NEW = "calc_total", "compute_total"
root = os.getcwd()
still, hits = [], 0
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
    for name in filenames:
        if not name.endswith(".py"):
            continue
        path = os.path.join(dirpath, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if re.search(r"\b%s\b" % OLD, text):
            still.append(os.path.relpath(path, root))
        hits += len(re.findall(r"\b%s\b" % NEW, text))
if still:
    print("%s is still referenced in: %s" % (OLD, ", ".join(sorted(still))))
    sys.exit(1)
if hits < 2:
    print("%s appears %d time(s); the definition and its call sites must all use it"
          % (NEW, hits))
    sys.exit(1)
print("ok")
