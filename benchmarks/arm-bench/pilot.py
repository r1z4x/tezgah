#!/usr/bin/env python3
"""Run one slice of a benchmark block.

    python3 pilot.py --group 0 --groups 10

Every task x both arms x N repeats, one model, one provider. Each group writes
its own results file, so parallel groups never interleave their rows. The arms
and their toggles are in `arms.json`; both were verified before the run (see
README.md, "Status").

k=3 by default makes this a PILOT, not the k>=5 block PREREGISTRATION.md asks
for: it bounds the pass-rate question, not the per-cell cost variance. The
report says which it is.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import bench  # noqa: E402

ARMS = ("opencode+tezgah", "opencode-bare", "omp+tezgah", "omp-bare")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", type=int, default=0)
    ap.add_argument("--groups", type=int, default=1)
    ap.add_argument("--arms", default=",".join(ARMS),
                    help="comma-separated arm names from arms.json")
    ap.add_argument("--tasks", default="",
                    help="comma-separated task ids or globs (default: every task, "
                         "e.g. --tasks 'h*' for the hard family)")
    ap.add_argument("--model", default="openrouter/deepseek/deepseek-v4-flash")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", default="results/pilot")
    ap.add_argument("--force", action="store_true",
                    help="re-run repeats already recorded (default: resume, so a "
                         "re-run of the same command only fills the gaps)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the runs the block would make, spend nothing: the "
                         "way to see what a resume still owes")
    ap.add_argument("--split", choices=("task", "cell"), default="task",
                    help="parallelism unit: 'task' gives each group one task and "
                         "runs its arms in sequence (results/<out>/g<N>.jsonl); "
                         "'cell' gives each group one (task, arm) cell, which is "
                         "how a hard family with long runs stays parallel "
                         "(results/<out>/<task>.<arm>.jsonl)")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    known = {a["name"]: a for a in json.loads(bench.ARMS_FILE.read_text())}
    for name in arms:
        if name not in known:
            sys.exit("unknown arm: %s" % name)
        if not known[name].get("flag_verified"):
            sys.exit("arm %s has flag_verified: false - prove its toggle before "
                     "scoring it" % name)
    every = bench.task_ids()
    wanted = [t.strip() for t in args.tasks.split(",") if t.strip()]
    if wanted:
        missing = [w for w in wanted if not any(fnmatch.fnmatch(t, w) for t in every)]
        if missing:
            sys.exit("no task matches: %s" % ", ".join(missing))
        every = [t for t in every if any(fnmatch.fnmatch(t, w) for w in wanted)]
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, str(ROOT / "bench.py"), "run", "--model", args.model,
            "--repeat", str(args.repeats), "--timeout", str(args.timeout)]
    if args.force:
        base.append("--force")
    if args.dry_run:
        base.append("--dry-run")

    if args.split == "cell":
        # one process per (task, arm), so a cell is the unit of parallelism and of
        # resume: a long task no longer holds three other arms behind it. The
        # group slices the cells, never the task list - slicing both would leave
        # most of the block unrun.
        cells = [(task, arm) for arm in arms for task in every]
        mine = cells[args.group::args.groups]
        print("group %d/%d: %d of %d cells" % (args.group, args.groups, len(mine), len(cells)))
        for task, arm in mine:
            results = str(out / ("%s.%s.jsonl" % (task, arm)))
            subprocess.run(base + ["--arm", arm, "--task", task, "--results", results],
                           check=False)
        return 0

    tasks = every[args.group::args.groups]
    results = str(out / ("g%d.jsonl" % args.group))
    print("group %d/%d: %d of %d tasks x %d arms"
          % (args.group, args.groups, len(tasks), len(every), len(arms)))
    for task in tasks:
        for arm in arms:
            subprocess.run(base + ["--arm", arm, "--task", task, "--results", results],
                           check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
