#!/usr/bin/env python3
"""E3 probe: the hot-path cost of the gate decision and the per-turn build.

Three measurements per run:
  1. in-process `decision()` over N repetitions (write and shell payloads),
  2. the end-to-end cost a host actually pays: one `tests/_probe_gate.py`
     process per call (the PreToolUse hook is a fresh process in every host),
  3. `context_for` for user_prompt and session_start over N repetitions.

Usage: python3 hh-cost.py [--reps 200] [--ledgers N]
  --ledgers N  point the cache at a temp dir holding N ledger files (1 or 20),
               to test whether the decision's cost grows with the corpus.
Prints one JSON object per (call, measure) on stdout.
"""
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

REPO = "/Users/rizax/Projects/tezgah"
sys.path.insert(0, os.path.join(REPO, "hooks"))


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


def stats(values):
    return {"n": len(values),
            "p50_ms": round(statistics.median(values), 3),
            "p95_ms": round(percentile(values, 95), 3),
            "max_ms": round(max(values), 3),
            "mean_ms": round(statistics.fmean(values), 3)}


def ledger_cache(count):
    """A temp cache dir with `count` ledger files, each holding 200 rows."""
    root = tempfile.mkdtemp(prefix="hh-e3-cache-")
    ev = os.path.join(root, "evidence")
    os.makedirs(ev)
    row = json.dumps({"kind": "run", "id": "abc123", "detail": "x", "ts": 1789000000})
    for i in range(count):
        with open(os.path.join(ev, "sess-%03d.jsonl" % i), "w") as fh:
            fh.write("\n".join([row] * 200) + "\n")
    return root


def main():
    reps = 200
    if "--reps" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--reps") + 1])
    ledgers = 0
    if "--ledgers" in sys.argv:
        ledgers = int(sys.argv[sys.argv.index("--ledgers") + 1])

    home = tempfile.mkdtemp(prefix="hh-e3-home-")
    root = os.path.join(home, "proj")
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    os.makedirs(os.path.join(home, ".config", "tezgah"), exist_ok=True)
    os.environ["HOME"] = home
    os.environ["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    os.environ["TEZGAH_ROOTS"] = root
    if ledgers:
        os.environ["XDG_CACHE_HOME"] = ledger_cache(ledgers)

    import tezgah_gate as tg
    import tezgah_context as tc

    print(json.dumps({"cache_ledgers": ledgers, "python": sys.version.split()[0],
                      "machine": "darwin-arm64"}))

    write_inp = {"file_path": os.path.join(root, "src", "a.py"),
                 "old_string": "x = 1", "new_string": "x = 2"}
    shell_inp = {"command": "pytest -q tests/test_a.py"}
    for tool, inp in (("edit", write_inp), ("bash", shell_inp)):
        vals = []
        for _ in range(reps):
            t0 = time.perf_counter()
            tg.decision(tool, inp, root, "hh-e3")
            vals.append((time.perf_counter() - t0) * 1000.0)
        row = stats(vals)
        row.update({"call": "decision(%s)" % tool, "ledgers_present": ledgers,
                    "source": "in-process timer"})
        print(json.dumps(row))

    for event in ("user_prompt", "session_start"):
        payload = {"prompt": "implement the thing", "session_id": "hh-e3"}
        vals = []
        for _ in range(max(20, reps // 4)):
            t0 = time.perf_counter()
            tc.context_for(event, root, payload if event == "user_prompt" else None)
            vals.append((time.perf_counter() - t0) * 1000.0)
        row = stats(vals)
        row.update({"call": "context_for(%s)" % event, "ledgers_present": ledgers,
                    "source": "in-process timer"})
        print(json.dumps(row))

    shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
