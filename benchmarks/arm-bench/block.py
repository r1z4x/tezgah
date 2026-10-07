#!/usr/bin/env python3
"""Run one pre-registered block of plan 062: every (arm, task, repeat) once.

    ARMBENCH_LAB=<lab> python3 block.py --config <block.json>

The config is the protocol's own numbers, committed with it: `arms`, `tasks`,
`repeats`, `model`, `timeout`, `parallel`, `results`, `cap_usd`, `row_meta`.
Each cell is one `bench.py run --repeat-from r --repeat r`, so a stopped block
resumes where it stopped (bench skips repeats already in `results`). Spend is
read back from the results file and its excluded file (runs a provider error
kept out of the results, bench.py `record_row`) after every run; once it passes
`cap_usd` no new run starts, the runs in flight finish, and the block exits 3
naming the cap. A run that exits QUOTA_RC (a provider spend limit) stops the
block the same way and the block exits 4: every later run would fail alike.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUOTA_RC = 4  # bench.py QUOTA_RC; tests/test_arm_bench.py pins the two together


def spent(results: Path) -> float:
    total = 0.0
    for path in (results, results.with_name(results.stem + ".excluded.jsonl")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                usage = json.loads(line).get("usage") or {}
                total += usage.get("cost") or 0.0
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    if not os.environ.get("ARMBENCH_LAB"):
        sys.exit("ARMBENCH_LAB is not set: the lab arms run from its HOMEs")
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    results = Path(cfg["results"]).resolve()
    jobs = [(arm, task, r) for r in range(1, cfg["repeats"] + 1)
            for task in cfg["tasks"] for arm in cfg["arms"]]
    stop, quota = threading.Event(), threading.Event()
    lock = threading.Lock()
    print("block: %d runs (%d arms x %d tasks x k=%d), model %s, cap $%.2f, %d in parallel"
          % (len(jobs), len(cfg["arms"]), len(cfg["tasks"]), cfg["repeats"], cfg["model"],
             cfg["cap_usd"], cfg["parallel"]), flush=True)

    def run(job):
        arm, task, repeat = job
        if stop.is_set():
            return job, None, "skipped: block stopped"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "bench.py"), "run", "--arm", arm, "--task", task,
             "--repeat-from", str(repeat), "--repeat", str(repeat), "--model", cfg["model"],
             "--timeout", str(cfg["timeout"]), "--results", str(results),
             "--row-meta", json.dumps(cfg.get("row_meta", {}))],
            capture_output=True, text=True)
        with lock:
            cost = spent(results)
            if cost > cfg["cap_usd"]:
                stop.set()
            if proc.returncode == QUOTA_RC:
                quota.set()
                stop.set()
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(arm)]
        return job, proc.returncode, (lines[-1] if lines else proc.stdout.strip()[-200:]) + \
            "  [spent $%.4f]" % cost

    with ThreadPoolExecutor(max_workers=cfg["parallel"]) as pool:
        for (arm, task, repeat), rc, tail in pool.map(run, jobs):
            print("  %-16s %-26s r%-2d rc=%s %s" % (arm, task, repeat, rc, tail), flush=True)
    total = spent(results)
    if quota.is_set():
        print("block done: $%.4f spent - PROVIDER QUOTA REACHED, block stopped; raise the "
              "key limit and re-run the same command" % total)
        return QUOTA_RC
    print("block done: $%.4f spent%s" % (total, " - CAP REACHED, block stopped" if stop.is_set() else ""))
    return 3 if stop.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
