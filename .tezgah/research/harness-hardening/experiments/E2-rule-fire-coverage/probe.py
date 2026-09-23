#!/usr/bin/env python3
"""E2 probe: per-rule refusal coverage over the whole ledger corpus.

Folds every ~/.cache/tezgah/evidence/*.jsonl and groups the deny rows by the
rule label `_deny` writes (the text before the first colon of `detail`). Prints
one JSON object per rule plus a totals object.

Usage: python3 hh-rules.py [--cache DIR]
"""
import collections
import glob
import json
import os
import sys
import time


def main():
    cache = os.path.expanduser("~/.cache/tezgah")
    if "--cache" in sys.argv:
        cache = sys.argv[sys.argv.index("--cache") + 1]
    files = sorted(glob.glob(os.path.join(cache, "evidence", "*.jsonl")))

    rules = collections.defaultdict(lambda: {"fires": 0, "days": set(),
                                             "sessions": set(), "sample": ""})
    kinds = collections.Counter()
    rows = 0
    unparsed = 0
    for path in files:
        slug = os.path.basename(path)[:-len(".jsonl")]
        try:
            fh = open(path)
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    unparsed += 1
                    continue
                rows += 1
                kind = row.get("kind")
                kinds[kind] += 1
                if kind != "deny":
                    continue
                detail = str(row.get("detail", ""))
                label = detail.split(":", 1)[0].strip() or "(no label)"
                ts = row.get("ts") or row.get("at") or row.get("time")
                day = time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else "(no ts)"
                entry = rules[label]
                entry["fires"] += 1
                entry["days"].add(day)
                entry["sessions"].add(slug)
                if not entry["sample"]:
                    entry["sample"] = detail[:120]

    for label in sorted(rules, key=lambda k: -rules[k]["fires"]):
        e = rules[label]
        days = sorted(e["days"])
        print(json.dumps({"rule": label, "fires": e["fires"],
                          "distinct_days": len(days), "first_day": days[0],
                          "last_day": days[-1],
                          "sessions": len(e["sessions"]),
                          "sample": e["sample"], "source": "ledger fold"}))
    print(json.dumps({"totals": True, "ledgers": len(files), "rows": rows,
                      "unparsed": unparsed, "deny_rows": sum(
                          e["fires"] for e in rules.values()),
                      "distinct_rules": len(rules),
                      "kinds": dict(kinds.most_common(14)),
                      "source": "ledger fold"}))


if __name__ == "__main__":
    main()
