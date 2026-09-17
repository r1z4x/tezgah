#!/usr/bin/env python3
"""Score a mechanical-off block: pass rate, cost per pass, and false completion.

Reads the rows `orx_block.py` wrote under `results/orx/<commit>/` and answers the
question the block was built for: does an enforced control change the work?

  python3 mechanical_off_report.py [<results-dir>]

Three endpoints, all from the same rows:

  pass rate            hidden checks, per arm, with a Wilson 95% interval
  CPS                  total cost / passes, reported with its pass counts
  false completion     the agent's final message claims success and the hidden
                       checks disagree. The claim side is a word list, stated
                       here rather than hidden in the harness: a completion verb
                       in the final message. A row with no recorded message is
                       counted as "no claim", never as a claim.
"""
import json
import math
import pathlib
import re
import sys

CLAIM = re.compile(
    r"\b(?:done|fixed|complete|completed|finished|passes|passing|all tests pass|"
    r"works now|verified|tamamland[ıi]|d[üu]zeltildi|bitti|ge[çc]ti|"
    r"[çc]al[ıi][şs][ıi]yor|haz[ıi]r)\b", re.I)
ARMS = ("omp+tezgah", "orx-verify-off", "orx-gate-off", "omp-bare")


def wilson(passes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def rows(results: pathlib.Path) -> list[dict]:
    out = []
    for path in sorted(results.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def main(argv: list[str]) -> int:
    root = pathlib.Path(__file__).resolve().parent
    results = pathlib.Path(argv[1]) if len(argv) > 1 else (
        root / "results" / "orx" / "latest")
    data = rows(results)
    if not data:
        print("no rows under %s" % results)
        return 1

    arms = [a for a in ARMS if any(r["arm"] == a for r in data)]
    print("%d rows, %d arms, model(s) %s\n"
          % (len(data), len(arms), ", ".join(sorted({r["model"] for r in data}))))

    print("%-16s %8s %10s %12s %14s" % ("arm", "passes", "rate", "wilson95", "cost/pass"))
    for arm in arms:
        sel = [r for r in data if r["arm"] == arm]
        passes = sum(1 for r in sel if r["pass"])
        cost = sum((r.get("usage") or {}).get("cost") or 0.0 for r in sel)
        lo, hi = wilson(passes, len(sel))
        cps = ("$%.4f" % (cost / passes)) if passes else "n/a"
        print("%-16s %5d/%-3d %9.3f %5.2f-%-6.2f %13s"
              % (arm, passes, len(sel), passes / len(sel), lo * 100, hi * 100, cps))

    print("\n%-16s %10s %10s %10s %12s" % ("arm", "falsecomp", "of-claims", "no-claim", "claim-rate"))
    for arm in arms:
        sel = [r for r in data if r["arm"] == arm]
        claimed = [r for r in sel if CLAIM.search(r.get("final_message") or "")]
        false = [r for r in claimed if not r["pass"]]
        print("%-16s %10d %10d %10d %11.2f"
              % (arm, len(false), len(claimed), len(sel) - len(claimed),
                 len(claimed) / len(sel)))

    print("\nper arm, per task (passes/repeats)")
    tasks = sorted({r["task"] for r in data})
    print("%-16s" % "arm" + "".join("%22s" % t[:20] for t in tasks))
    for arm in arms:
        cells = []
        for task in tasks:
            sel = [r for r in data if r["arm"] == arm and r["task"] == task]
            cells.append("%4d/%-3d" % (sum(1 for r in sel if r["pass"]), len(sel)))
        print("%-16s" % arm + "".join("%22s" % c for c in cells))

    timeouts = [r for r in data if r.get("timed_out")]
    no_usage = [r for r in data if not r.get("usage")]
    print("\ntimeouts: %d, rows without usage: %d" % (len(timeouts), len(no_usage)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
