#!/usr/bin/env python3
"""Score an arm block the way PREREGISTRATION.md says it must be scored.

Usage: python3 analyze.py results/pilot-block.jsonl results/oc-new.jsonl results/omp-block/*.jsonl

Endpoints, in the pre-registered order:
  primary    CPS = arm cost / passes, always printed with the counts it divides
  co-primary pass rate with a Wilson 95% interval, always with k and n
  secondary  turns proxy (wall), output, fresh input, cache read, collateral,
             timeouts and no-usage rows (counted, never dropped)
  paired     tezgah - bare within a host, per task, so the host factor cannot
             leak into the harness comparison
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def load(paths):
    """Later files win: a re-run replaces the row it re-runs."""
    rows = {}
    for pattern in paths:
        for path in sorted(Path(".").glob(pattern)) if "*" in pattern else [Path(pattern)]:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                rows[(row["arm"], row["task"], row["repeat"])] = row
    return list(rows.values())


def wilson(passes, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def usage_of(row, key):
    return (row.get("usage") or {}).get(key)


def median(values):
    values = sorted(values)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2:
        return float(values[mid])
    return (values[mid - 1] + values[mid]) / 2


def arms_table(rows):
    by_arm = defaultdict(list)
    for row in rows:
        by_arm[row["arm"]].append(row)
    print("| arm | n | pass | pass rate (Wilson 95%) | CPS | median cost | median in | median out | median cache | timeouts | no-usage | collateral |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for arm, group in sorted(by_arm.items()):
        n = len(group)
        passes = sum(1 for r in group if r["pass"])
        low, high = wilson(passes, n)
        cost = sum((usage_of(r, "cost") or 0) for r in group)
        cps = ("$%.4f" % (cost / passes)) if passes else "n/a"
        costs = [usage_of(r, "cost") or 0 for r in group]
        ins = [usage_of(r, "input") or 0 for r in group]
        outs = [usage_of(r, "output") or 0 for r in group]
        caches = [usage_of(r, "cache_read") or 0 for r in group]
        timeouts = sum(1 for r in group if r.get("timed_out"))
        nousage = sum(1 for r in group if not r.get("usage"))
        collateral = sum(1 for r in group if r.get("collateral"))
        print("| %s | %d | %d | %.2f (%.2f-%.2f) | %s | $%.4f | %s | %s | %s | %d | %d | %d |" % (
            arm, n, passes, passes / n, low, high, cps, median(costs),
            int(median(ins)), int(median(outs)), int(median(caches)),
            timeouts, nousage, collateral))
    print("| **total** | %d | %d | | **$%.4f** spent | | | | | | | |" % (
        len(rows), sum(1 for r in rows if r["pass"]),
        sum((usage_of(r, "cost") or 0) for r in rows)))


def paired(rows):
    """tezgah minus bare, per task, inside one host: the harness effect with the
    host held fixed."""
    label = {"tezgah": "tezgah", "none": "bare"}
    by = defaultdict(dict)
    for row in rows:
        by[(row["host"], row["task"])].setdefault(label.get(row["harness"], row["harness"]), []).append(row)
    ks = {len(g) for arms in by.values() for g in arms.values()}
    print("\nper-task pass rate, tezgah vs bare (k=%s):" % (sorted(ks) or "?"))
    print("| host | task | tezgah | bare | delta |")
    print("|---|---|---|---|---|")
    deltas = defaultdict(list)
    for (host, task), arms in sorted(by.items()):
        if "tezgah" not in arms or "bare" not in arms:
            continue
        t = sum(1 for r in arms["tezgah"] if r["pass"]) / len(arms["tezgah"])
        b = sum(1 for r in arms["bare"] if r["pass"]) / len(arms["bare"])
        deltas[host].append(t - b)
        print("| %s | %s | %.2f | %.2f | %+.2f |" % (host, task, t, b, t - b))
    for host, ds in sorted(deltas.items()):
        wins = sum(1 for d in ds if d > 0)
        losses = sum(1 for d in ds if d < 0)
        print("\n%s: %d tasks, %d favour tezgah, %d favour bare, mean delta %+.3f" % (
            host, len(ds), wins, losses, sum(ds) / len(ds)))
        if wins + losses:
            n = wins + losses
            upper = sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n
            lower = sum(math.comb(n, i) for i in range(0, wins + 1)) / 2 ** n
            print("  sign test p=%.3f (two-sided, exact binomial)" % min(1.0, 2 * min(upper, lower)))


def by_family(rows):
    print("\nper family (passes / n, mean cost):")
    by = defaultdict(list)
    for row in rows:
        by[(row.get("family") or "?", row["arm"])].append(row)
    families = sorted({f for f, _ in by})
    header = "| family | " + " | ".join(sorted({a for _, a in by})) + " |"
    print(header)
    print("|---" * (len(by) and (len({a for _, a in by}) + 1)) + "|")
    for family in families:
        cells = []
        for arm in sorted({a for _, a in by}):
            group = by.get((family, arm), [])
            if not group:
                cells.append("-")
                continue
            passes = sum(1 for r in group if r["pass"])
            cells.append("%d/%d ($%.4f)" % (passes, len(group),
                                            sum((usage_of(r, "cost") or 0) for r in group) / len(group)))
        print("| %s | %s |" % (family, " | ".join(cells)))


def per_check(rows):
    """Pass counts per check, per arm: how far an arm got on a sweep task whose
    findings are scored one by one, rather than only whether it finished."""
    by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in rows:
        for check in row.get("checks") or []:
            cell = by[check["name"]][row["arm"]]
            cell[0] += 1
            cell[1] += 1 if check["passed"] else 0
    if not by:
        return
    arms = sorted({row["arm"] for row in rows})
    print("\nper check (passed / run):")
    print("| check | " + " | ".join(arms) + " |")
    print("|---" * (len(arms) + 1) + "|")
    for name in sorted(by):
        cells = []
        for arm in arms:
            total, passed = by[name].get(arm, [0, 0])
            cells.append("%d/%d" % (passed, total) if total else "-")
        print("| %s | %s |" % (name, " | ".join(cells)))


def main():
    paths = sys.argv[1:] or ["results/pilot-block.jsonl"]
    rows = load(paths)
    if not rows:
        sys.exit("no rows in %s" % paths)
    counts = defaultdict(int)
    for row in rows:
        counts[(row["host"], row["harness"])] += 1
    print("rows: %d  cells: %s  model(s): %s" % (
        len(rows), dict(counts), sorted({r["model"] for r in rows})))
    reps = sorted({r["repeat"] for r in rows})
    print("k = %d (repeats %s), tasks = %d\n" % (
        len(reps), reps, len({r["task"] for r in rows})))
    arms_table(rows)
    per_check(rows)
    paired(rows)
    by_family(rows)
    flagged = [r for r in rows if r.get("usage_note")]
    if flagged:
        print("\nrows with a usage note (%d):" % len(flagged))
        for row in flagged[:10]:
            print("  %s %s r%d: %s" % (row["arm"], row["task"], row["repeat"], row["usage_note"]))
    failed = [(r["arm"], r["task"], r["reasons"]) for r in rows if not r["pass"]]
    print("\nfailures (%d):" % len(failed))
    for arm, task, reasons in failed:
        print("  %-18s %-30s %s" % (arm, task, "; ".join(reasons)[:110]))


if __name__ == "__main__":
    main()
