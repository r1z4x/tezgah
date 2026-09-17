#!/usr/bin/env python3
"""Measure the wall time of tezgah's three hook entry points.

    python3 benchmarks/hook-latency/measure.py --n 20 --label plan012-baseline

Each hook is a separate Python process on every event (that is how the hosts
spawn them), so the honest figure is the whole process: interpreter start plus
the hook's own work. The script therefore runs the real entry points the way a
host does - a JSON payload on stdin - and reports the median and p95 of N runs,
next to the floor of an interpreter that does nothing (`python3 -c pass`).

The payload's `cwd` is inside the repo on purpose: outside a configured root
every hook returns before doing its work, which would time the arming check and
nothing else.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS = os.path.join(ROOT, "hooks")

PAYLOADS = {
    "pretooluse": os.path.join(HOOKS, "projects-pretooluse.py"),
    "posttooluse": os.path.join(HOOKS, "projects-posttooluse.py"),
    "stop": os.path.join(HOOKS, "projects-stop.py"),
}


def payload_for(name: str) -> dict:
    base = {"cwd": ROOT, "session_id": "probe-hook-latency",
            "tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    if name == "posttooluse":
        base["hook_event_name"] = "PostToolUse"
        base["tool_response"] = {"stdout": "ok"}
    if name == "stop":
        return {"cwd": ROOT, "session_id": "probe-hook-latency",
                "last_assistant_message": "done"}
    return base


def time_once(cmd: list[str], payload: dict | None) -> float:
    started = time.time()
    subprocess.run(cmd, input=json.dumps(payload) if payload is not None else "",
                   capture_output=True, text=True)
    return (time.time() - started) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--label", default="unlabelled")
    parser.add_argument("--out", help="also write the JSON report to this path, "
                                     "so a committed before/after pair is a run "
                                     "and not a copy-paste")
    args = parser.parse_args()

    floor = [time_once([sys.executable, "-c", "pass"], None) for _ in range(args.n)]
    out = {"label": args.label, "n": args.n, "python_floor_ms": round(statistics.median(floor), 2),
           "hooks": {}}
    for name, path in PAYLOADS.items():
        times = [time_once([sys.executable, path], payload_for(name)) for _ in range(args.n)]
        out["hooks"][name] = {"median_ms": round(statistics.median(times), 2),
                              "p95_ms": round(sorted(times)[int(0.95 * (len(times) - 1))], 2)}
        print("%-12s median %6.2f ms   p95 %6.2f ms" % (name, out["hooks"][name]["median_ms"],
                                                        out["hooks"][name]["p95_ms"]))
    print("python floor  median %6.2f ms" % out["python_floor_ms"])
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
