#!/usr/bin/env python3
"""Run one slice of the pilot block.

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
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import bench  # noqa: E402

ARMS = ("opencode+tezgah", "opencode-bare")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", type=int, default=0)
    ap.add_argument("--groups", type=int, default=1)
    ap.add_argument("--model", default="openrouter/deepseek/deepseek-v4-flash")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", default="results/pilot")
    args = ap.parse_args()

    tasks = bench.task_ids()[args.group::args.groups]
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    results = str(out / ("g%d.jsonl" % args.group))
    for task in tasks:
        for arm in ARMS:
            subprocess.run(
                [sys.executable, str(ROOT / "bench.py"), "run", "--arm", arm,
                 "--task", task, "--repeat", str(args.repeats),
                 "--model", args.model, "--results", results,
                 "--timeout", str(args.timeout)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
