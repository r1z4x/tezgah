#!/usr/bin/env python3
"""Census of the live evidence ledgers: how long sessions get, how far apart a
repeated call sits, and how often an irreversible-shaped command is actually
attempted.

    python3 to_human/blocks/E5-ledger-census/census.py

Answers three design questions with data instead of a guess:

  1. is the loop guard's 200-row tail window big enough?  (repeat gap)
  2. how large is a normal session, i.e. how often is the window even binding?
  3. is the consent gate's frequency really zero?  (irreversible verbs)

Prints one JSON object. Read-only: it never writes to the ledger.
"""
import collections
import glob
import json
import os
import re
import statistics
import sys

EVID = os.path.expanduser("~/.cache/tezgah/evidence")
IRREVERSIBLE = re.compile(
    r"push\s+--force|push\s+-f\b|branch\s+-D\b|rm\s+-rf|reset\s+--hard|"
    r"drop\s+table|terraform\s+apply|npm\s+publish|vercel\s+deploy|"
    r"gh\s+api\s+-X\s+DELETE|migrate", re.I)


def main() -> int:
    files = sorted(glob.glob(os.path.join(EVID, "*.jsonl")))
    sizes, gaps, irreversible = [], [], collections.Counter()
    rows_total = ids = 0
    for path in files:
        entries = []
        for line in open(path, errors="replace"):
            try:
                entries.append(json.loads(line))
            except ValueError:
                pass
        sizes.append(len(entries))
        last_seen = {}
        for index, entry in enumerate(entries):
            digest = entry.get("id")
            if digest:
                ids += 1
                if digest in last_seen:
                    gaps.append(index - last_seen[digest])
                last_seen[digest] = index
            detail = str(entry.get("detail") or "")
            if entry.get("kind") in ("run", "edit") and IRREVERSIBLE.search(detail):
                irreversible[IRREVERSIBLE.search(detail).group(0).lower()] += 1
        rows_total += len(entries)

    out = {
        "sessions": len(files),
        "rows": rows_total,
        "session_lines": {
            "median": statistics.median(sizes) if sizes else 0,
            "p95": sorted(sizes)[int(0.95 * (len(sizes) - 1))] if sizes else 0,
            "max": max(sizes) if sizes else 0,
        },
        "rows_with_an_id": ids,
        "repeat_gaps": {
            "n": len(gaps),
            "median": statistics.median(gaps) if gaps else None,
            "p95": sorted(gaps)[int(0.95 * (len(gaps) - 1))] if gaps else None,
            "max": max(gaps) if gaps else None,
        },
        "irreversible_shaped_commands": {
            "total": sum(irreversible.values()),
            "by_shape": dict(irreversible),
        },
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
