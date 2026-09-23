#!/usr/bin/env python3
"""E5b's instrument: the re-take's one measurement.

Read-only over this machine's own ledger corpus (`~/.cache/tezgah/evidence`,
overridable with a path argument): it times the two readers `stop_reason` could
use on the largest ledger present - the whole-ledger read `events` it did use,
and the turn-scoped `turn_rows` the fix routes through - plus the raw read the
two share. Every number is printed as JSON on one line; nothing is written.

    python3 probe.py [ledger-glob-dir]

Rows are `scope: real`: the corpus is this machine's running history, not a
generated input. No provider, no network, no cost.
"""
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import tezgah_integrity as ti  # noqa: E402

REPEATS = 7


def timed(fn):
    """(the best of REPEATS runs in ms, the median of them).

    The best is the run least disturbed by the rest of the machine, which is
    what a reader comparing two readers wants; the median is there so a number
    that only exists in one lucky run is visible as a gap between the two."""
    got = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        fn()
        got.append((time.perf_counter() - start) * 1000.0)
    got.sort()
    return round(got[0], 3), round(got[len(got) // 2], 3)


def main():
    where = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.expanduser("~"), ".cache", "tezgah", "evidence")
    files = [(os.path.getsize(p), p) for p in glob.glob(os.path.join(where, "*.jsonl"))]
    if not files:
        print(json.dumps({"error": "no ledger under %s" % where}))
        return 1
    files.sort()
    size, path = files[-1]
    whole = ti.events_path(path)
    ti._path = lambda session: path          # the reader's own path hook, patched
    turn = ti.turn_rows("probe")

    def raw_read():
        with open(path) as fh:
            fh.readlines()

    raw_best, raw_med = timed(raw_read)
    rows_best, rows_med = timed(lambda: ti.events("probe"))
    turn_best, turn_med = timed(lambda: ti.turn_rows("probe"))
    print(json.dumps({
        "experiment": "E5b-h5-retake",
        "kind": "measurement",
        "what": "whole-ledger read vs turn-scoped read on this machine's largest ledger",
        "corpus": where,
        "ledgers": len(files),
        "largest_ledger_bytes": size,
        "largest_ledger": os.path.basename(path),
        "largest_ledger_rows": len(whole),
        "turn_rows": len(turn),
        "read_lines_ms": raw_best,
        "read_lines_median_ms": raw_med,
        "events_ms": rows_best,
        "events_median_ms": rows_med,
        "turn_rows_ms": turn_best,
        "turn_rows_median_ms": turn_med,
        "repeats": REPEATS,
        "source": "in-process timer over %s (probe.py, best of %d)" % (where, REPEATS),
        "verification": "measured",
        "scope": "real",
    }))


if __name__ == "__main__":
    sys.exit(main())
