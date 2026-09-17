#!/usr/bin/env python3
"""Run the project's fixed block and print its evidence.

This is what `orx-run.sh` calls, and it is the same on every node: the only
thing a node changes is the committed configuration (`arms.json` and the
contract variant its arms point at). The task set is the instrument and is
pinned in `orx-tasks.txt`; a node that edits it is measuring something else.

Prints, at the end of the log:

    Summary {json}

with per-arm passes, the pass rate, the Wilson interval, cost, and the paired
delta of every harness arm against the bare anchor on the same tasks.
"""
import json
import math
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = "openrouter/deepseek/deepseek-v4-flash"
REPEATS = 50
TIMEOUT = 300
PARALLEL = 10
CHUNK = 5
ANCHOR = "omp-bare"


def wilson(passes: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 1.0)
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def main() -> int:
    arms = [a for a in json.loads((ROOT / "arms.json").read_text(encoding="utf-8"))
            if a.get("orx")]
    tasks = [t.strip() for t in (ROOT / "orx-tasks.txt").read_text().splitlines() if t.strip()]
    if not arms:
        sys.exit("no arm carries \"orx\": true - nothing to run")
    commit_id = commit()
    out = ROOT / "results" / "orx" / commit_id
    out.mkdir(parents=True, exist_ok=True)

    print("commit   %s" % commit_id)
    print("model    %s" % MODEL)
    print("repeats  %d   timeout %ds" % (REPEATS, TIMEOUT))
    print("tasks    %s" % ", ".join(tasks))
    for arm in arms:
        print("arm      %-19s harness=%-8s toggle=%s"
              % (arm["name"], arm["harness"], arm.get("toggle", "")[:110]))

    jobs = [(task, arm["name"], lo)
            for task in tasks for arm in arms
            for lo in range(1, REPEATS + 1, CHUNK)]
    print("cells    %d (%d tasks x %d arms), %d jobs of %d repeats, %d in parallel"
          % (len(tasks) * len(arms), len(tasks), len(arms), len(jobs), CHUNK,
             min(PARALLEL, len(jobs))))

    def run(job):
        task, arm, lo = job
        hi = min(lo + CHUNK - 1, REPEATS)
        results = str(out / ("%s.%s.r%d-%d.jsonl" % (task, arm, lo, hi)))
        proc = subprocess.run(
            [sys.executable, str(ROOT / "bench.py"), "run", "--arm", arm,
             "--task", task, "--repeat", str(hi), "--repeat-from", str(lo),
             "--model", MODEL, "--results", results, "--timeout", str(TIMEOUT)],
            cwd=ROOT, capture_output=True, text=True)
        return task, arm, proc.returncode, proc.stdout.strip().splitlines()[-1:] or [""]

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        for task, arm, rc, tail in pool.map(run, jobs):
            print("  %-30s %-19s rc=%d %s" % (task, arm, rc, tail[0][:80]))

    rows = []
    for path in sorted(out.glob("*.jsonl")):
        rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    deduped = {}
    for row in rows:
        deduped[(row["arm"], row["task"], row["repeat"], row["model"])] = row
    rows = list(deduped.values())

    per_arm, per_task = {}, {}
    for row in rows:
        cell = per_arm.setdefault(row["arm"], {"n": 0, "pass": 0, "cost": 0.0})
        cell["n"] += 1
        cell["pass"] += 1 if row["pass"] else 0
        cell["cost"] += (row.get("usage") or {}).get("cost") or 0
        per_task.setdefault(row["task"], {}).setdefault(
            row["arm"], []).append(1 if row["pass"] else 0)

    summary = {"commit": commit_id, "model": MODEL, "repeats": REPEATS,
               "cells": len(jobs), "runs": len(rows), "arms": {}}
    print("\nper arm")
    for arm, cell in sorted(per_arm.items()):
        low, high = wilson(cell["pass"], cell["n"])
        cps = cell["cost"] / cell["pass"] if cell["pass"] else None
        summary["arms"][arm] = {"n": cell["n"], "pass": cell["pass"],
                                "rate": round(cell["pass"] / cell["n"], 4),
                                "wilson": [round(low, 4), round(high, 4)],
                                "cost": round(cell["cost"], 4),
                                "cps": round(cps, 5) if cps else None}
        print("  %-19s %2d/%2d  %.2f (%.2f-%.2f)  $%.4f  cps=%s"
              % (arm, cell["pass"], cell["n"], cell["pass"] / cell["n"], low, high,
                 cell["cost"], ("$%.5f" % cps) if cps else "n/a"))

    print("\nper task (passes / repeats)")
    header = "  %-30s %s" % ("task", "  ".join("%-19s" % a for a in sorted(per_arm)))
    print(header)
    for task in sorted(per_task):
        cells = []
        for arm in sorted(per_arm):
            got = per_task[task].get(arm)
            cells.append("%d/%d" % (sum(got), len(got)) if got else "-")
        print("  %-30s %s" % (task, "  ".join("%-19s" % c for c in cells)))

    print("\npaired against %s (harness minus anchor, mean over tasks)" % ANCHOR)
    for arm in sorted(per_arm):
        if arm == ANCHOR:
            continue
        deltas = []
        for task, by_arm in per_task.items():
            if arm in by_arm and ANCHOR in by_arm:
                deltas.append(sum(by_arm[arm]) / len(by_arm[arm])
                              - sum(by_arm[ANCHOR]) / len(by_arm[ANCHOR]))
        if deltas:
            mean = sum(deltas) / len(deltas)
            summary["arms"][arm]["delta_vs_anchor"] = round(mean, 4)
            print("  %-19s %+.3f over %d tasks" % (arm, mean, len(deltas)))

    print("\nSummary " + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
