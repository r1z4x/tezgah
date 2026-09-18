#!/usr/bin/env python3
"""Score the E6 ask block the way PREREGISTRATION-E6.md says it must be scored.

Usage: python3 analyze_e6.py results/e6/*.jsonl
       python3 analyze_e6.py results/e6
       python3 analyze_e6.py results/e6/omp+tezgah.jsonl results/e6/rerun.jsonl

Later files win, as `analyze.py` does: a re-run replaces the row it re-runs.

The endpoint of `u01-ask-before-writing` is the route, not the diff. The third
check, `surfaces_the_open_dimension`, is true exactly when the run asked about
the dimension the prompt left open before writing; `pass` is the conjunction of
all three checks, so a run can implement a defensible endpoint and still fail
the task. That is the design, and it is why every rate here is printed with the
counts it divides and the per-repeat section exists: one lucky repeat must stay
visible instead of being averaged into a rate that hides it.

Endpoints, in the pre-registered order:
  primary    asked rate with a Wilson 95% interval, always with k and n
  co-primary the literal rate and the task pass rate, in the same shape
  cost       CPS = arm cost / passes, and the median run cost, with its counts
  paired     per arm against `omp-bare` on the same (host, task, repeat), so a
             between-cell difference cannot be read as an arm effect
  exact      McNemar's exact test on the discordant pairs, through `bench.py`'s
             own `exact_binomial_p` rather than a second copy of the statistic
  missing    timeouts and rows with no check are counted, never dropped
"""
import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

# The statistic is the runner's, not the analyzer's: importing it keeps one
# definition of the exact test in the tree instead of a copy that can drift.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench import exact_binomial_p  # noqa: E402

ASKED = "surfaces_the_open_dimension"
LITERAL = "literal_list"
SUITE = "suite"
REFERENCE = "omp-bare"


def load(paths):
    """Every row of every target, later files winning over earlier ones.

    A target may be a results file, a directory of `*.jsonl` files or a glob,
    which is how one block's per-arm files are scored as one table.
    """
    rows = {}
    for target in paths:
        path = Path(target)
        if path.is_dir():
            found = sorted(path.glob("*.jsonl"))
        elif path.exists():
            found = [path]
        else:
            found = [Path(one) for one in sorted(glob.glob(target))]
        for one in found:
            if not one.is_file():
                continue
            for line in one.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                rows[(row["arm"], row["task"], row["repeat"])] = row
    return list(rows.values())


def check(row, name):
    """A check's own `passed` field, or None when the row carries no such check.

    None is not False: a timed-out row is graded with `checks: []`, and calling
    that a measured non-ask would price an absence as a verdict. The unknown
    lands in its own column, so the rate's denominator stays visible.
    """
    for entry in row.get("checks") or []:
        if entry.get("name") == name:
            return bool(entry.get("passed"))
    return None


def asked(row):
    """The route endpoint: the reply asked rather than assumed."""
    return check(row, ASKED) is True


def wilson(passes, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def cell(passes, n):
    """`k/n rate (lo-hi)`: a rate never travels without its interval here."""
    low, high = wilson(passes, n)
    rate = passes / n if n else 0.0
    return f"{passes}/{n} {rate:.2f} ({low:.2f}-{high:.2f})"


def usage_of(row, key):
    return (row.get("usage") or {}).get(key)


def median(values):
    """Median of the reported values; rows that reported none are not zero."""
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return float(values[mid])
    return (values[mid - 1] + values[mid]) / 2


def arms_table(rows):
    by_arm = defaultdict(list)
    for row in rows:
        by_arm[row["arm"]].append(row)
    print("per arm (asked = the third check; pass = suite AND literal AND asked):")
    print("| arm | n | asked | literal | pass | CPS | median cost | timeouts | no-check | no-usage |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for arm, group in sorted(by_arm.items()):
        n = len(group)
        asks = sum(1 for r in group if asked(r))
        literals = [check(r, LITERAL) for r in group]
        passes = sum(1 for r in group if r["pass"])
        cost = sum((usage_of(r, "cost") or 0) for r in group)
        costs = [usage_of(r, "cost") for r in group if usage_of(r, "cost") is not None]
        median_cost = median(costs)
        cps = f"${cost / passes:.4f}" if passes else "n/a"
        print(
            f"| {arm} | {n} | {cell(asks, n)} | {cell(sum(1 for x in literals if x), n)} "
            f"| {cell(passes, n)} | {cps} | "
            f"{'n/a' if median_cost is None else f'${median_cost:.4f}'} | "
            f"{sum(1 for r in group if r.get('timed_out'))} | "
            f"{sum(1 for x in literals if x is None)} | "
            f"{sum(1 for r in group if not r.get('usage'))} |"
        )
    print(f"| **total** | {len(rows)} | {sum(1 for r in rows if asked(r))} asked "
          f"| | {sum(1 for r in rows if r['pass'])} passed "
          f"| **${sum((usage_of(r, 'cost') or 0) for r in rows):.4f}** "
          f"| | {sum(1 for r in rows if r.get('timed_out'))} | "
          f"{sum(1 for r in rows if check(r, LITERAL) is None)} "
          f"| {sum(1 for r in rows if not r.get('usage'))} |")


def shape_table(rows):
    """How the conjunction broke, per arm.

    `implemented, asked nothing` is the block's own failure mode - the literal
    contract held and the open dimension never reached the user - so it is a
    count of its own rather than something the pass rate folds away.
    """
    by_arm = defaultdict(list)
    for row in rows:
        by_arm[row["arm"]].append(row)
    print("\nendpoint shape (the two halves of `pass`, kept apart):")
    print("| arm | asked and implemented | implemented, asked nothing | literal broken | no check ran |")
    print("|---|---|---|---|---|")
    for arm, group in sorted(by_arm.items()):
        both = sum(1 for r in group if asked(r) and check(r, LITERAL) is True)
        silent = sum(1 for r in group if not asked(r) and check(r, LITERAL) is True)
        broken = sum(1 for r in group if check(r, LITERAL) is False)
        unknown = sum(1 for r in group if check(r, LITERAL) is None)
        print(f"| {arm} | {both} | {silent} | {broken} | {unknown} |")


def paired(rows):
    """Each arm against `omp-bare`, on the same host, task and repeat.

    Rows are paired inside one cell: the arm effect is read on the repeats both
    arms ran, so a cell that ran more repeats cannot move the comparison.
    """
    reference = {(r["host"], r["task"], r["repeat"]): r for r in rows if r["arm"] == REFERENCE}
    if not reference:
        print(f"\nno {REFERENCE} rows: the paired section needs the reference arm, skipped.")
        return
    print(f"\npaired against {REFERENCE} (same host, task and repeat):")
    print("| arm | pairs | asked: arm only | bare only | both | neither | asked delta "
          "| exact McNemar p | pass delta | p |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for arm in sorted({r["arm"] for r in rows} - {REFERENCE}):
        pairs = []
        for row in rows:
            if row["arm"] != arm:
                continue
            mate = reference.get((row["host"], row["task"], row["repeat"]))
            if mate is not None:
                pairs.append((row, mate))
        if not pairs:
            print(f"| {arm} | 0 (no {REFERENCE} row on this host) | | | | | | | | |")
            continue
        only_arm = sum(1 for a, b in pairs if asked(a) and not asked(b))
        only_bare = sum(1 for a, b in pairs if asked(b) and not asked(a))
        both = sum(1 for a, b in pairs if asked(a) and asked(b))
        neither = sum(1 for a, b in pairs if not asked(a) and not asked(b))
        pass_only_arm = sum(1 for a, b in pairs if a["pass"] and not b["pass"])
        pass_only_bare = sum(1 for a, b in pairs if b["pass"] and not a["pass"])
        delta = (only_arm - only_bare) / len(pairs)
        pass_delta = (pass_only_arm - pass_only_bare) / len(pairs)
        print(f"| {arm} | {len(pairs)} | {only_arm} | {only_bare} | {both} | {neither} "
              f"| {delta:+.3f} | {mcnemar(only_arm, only_bare)} "
              f"| {pass_delta:+.3f} | {mcnemar(pass_only_arm, pass_only_bare)} |")
    print("  delta is (arm-only - bare-only) / pairs; the discordant pairs are the "
          "only evidence in it.")


def mcnemar(only_arm, only_bare):
    """Exact McNemar over the discordant pairs, or a refusal when there are none.

    No discordant pair means the comparison carries no information at all; a
    printed p of 1.0 there would read as a tested null instead of an untested
    one, so it is named rather than printed.
    """
    if only_arm + only_bare == 0:
        return "n/a (no discordant pair)"
    return f"{exact_binomial_p(min(only_arm, only_bare), only_arm + only_bare):.4f}"


def mark(value):
    """T/F for a check's verdict, `?` when the row never produced one."""
    return {True: "T", False: "F", None: "?"}[value]


def per_repeat(rows):
    """One line per repeat, per task: the shape behind a single block average."""
    print("\nper repeat (a single lucky repeat must stay visible):")
    for task in sorted({r["task"] for r in rows}):
        task_rows = [r for r in rows if r["task"] == task]
        print(f"  {task}")
        for repeat in sorted({r["repeat"] for r in task_rows}):
            cells = []
            for arm in sorted({r["arm"] for r in task_rows}):
                row = next((r for r in task_rows
                            if r["arm"] == arm and r["repeat"] == repeat), None)
                if row is None:
                    continue
                cells.append(f"{arm} asked={mark(check(row, ASKED))} "
                             f"lit={mark(check(row, LITERAL))} "
                             f"pass={mark(bool(row['pass']))}")
            print(f"    r{repeat}  " + " | ".join(cells))
        print(f"    asked: {sum(1 for r in task_rows if asked(r))}/{len(task_rows)} "
              f"of {len({r['repeat'] for r in task_rows})} repeat(s) x "
              f"{len({r['arm'] for r in task_rows})} arms")


def failures(rows):
    print(f"\nfailures ({sum(1 for r in rows if not r['pass'])}):")
    for row in [r for r in rows if not r["pass"]]:
        print(f"  {row['arm']:<18} {row['task']:<24} r{row['repeat']} "
              f"{'; '.join(row.get('reasons') or [])[:110]}")


def main():
    paths = sys.argv[1:] or ["results/e6/*.jsonl"]
    rows = load(paths)
    if not rows:
        sys.exit(f"no rows in {paths}")
    counts = defaultdict(int)
    for row in rows:
        counts[(row["host"], row["harness"])] += 1
    print(f"rows: {len(rows)}  cells: {dict(counts)}  model(s): {sorted({r['model'] for r in rows})}")
    reps = sorted({r["repeat"] for r in rows})
    print(f"k = {len(reps)} (repeats {reps}), tasks = {len({r['task'] for r in rows})}\n")
    arms_table(rows)
    shape_table(rows)
    paired(rows)
    per_repeat(rows)
    failures(rows)


if __name__ == "__main__":
    main()
