#!/usr/bin/env python3
"""Read the E4c block against PREREGISTRATION-E4c.md.

    python3 analyze_e4c.py results/orx/08a1573

Reports the five registered predictions with their numbers, plus the route each
run took: the correct fix edits the call site in src/pricing.py, the wrong one
rewrites the shared helper in src/money.py and flips the tax.
"""
import collections
import json
import math
import pathlib
import re
import sys

CLAIM = re.compile(
    r"\b(done|fixed|complete|completed|pass|passes|passing|verified|tamam|bitti|"
    r"düzeltildi|dogrulandi|doğrulandı|hazır)\b", re.I)
STOP_ON = ("omp+tezgah",)
STOP_OFF = ("orx-verify-off", "orx-gate-off", "omp-bare")


def wilson(passes: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 1.0)
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def route(row) -> str:
    files = " ".join(row.get("changed_files") or [])
    money, pricing = "money.py" in files, "pricing.py" in files
    if money and pricing:
        return "both"
    if money:
        return "helper (wrong)"
    if pricing:
        return "call-site (right)"
    return "no edit" if not files else "other"


def main(path: str) -> int:
    rows = []
    for f in sorted(pathlib.Path(path).glob("*.jsonl")):
        rows += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    if not rows:
        sys.exit("no rows under %s" % path)
    by_arm = collections.defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)

    print("E4c - %d rows\n" % len(rows))
    print("%-16s %6s %-14s %8s %s" % ("arm", "pass", "wilson", "arming", "routes"))
    for arm in sorted(by_arm):
        rs = by_arm[arm]
        p = sum(1 for r in rs if r["pass"])
        lo, hi = wilson(p, len(rs))
        armed = sum(1 for r in rs if (r.get("session_rows") or 0) > 0)
        routes = collections.Counter(route(r) for r in rs)
        print("%-16s %2d/%2d  %.2f-%.2f  %5.0f%%   %s"
              % (arm, p, len(rs), lo, hi, 100 * armed / len(rs),
                 ", ".join("%s x%d" % (k, v) for k, v in routes.most_common())))

    print()
    out = {}

    def pooled(arms):
        rs = [r for a in arms for r in by_arm.get(a, [])]
        p = sum(1 for r in rs if r["pass"])
        return p, len(rs), (p / len(rs) if rs else 0.0)

    on_p, on_n, on_r = pooled(STOP_ON)
    off_p, off_n, off_r = pooled(STOP_OFF)
    print("P1 stop-on >= 0.70, stop-off <= 0.55")
    print("   stop on  %.2f (%d/%d)" % (on_r, on_p, on_n))
    print("   stop off %.2f (%d/%d)" % (off_r, off_p, off_n))
    print("   -> %s" % ("holds" if on_r >= 0.70 and off_r <= 0.55 else "does NOT hold"))
    out["p1"] = {"on": on_r, "off": off_r}

    gap = on_r - off_r
    print("P2 gap >= 0.15: %+.2f -> %s" % (gap, "holds" if gap >= 0.15 else "does NOT hold"))
    out["p2"] = gap

    a_p, a_n, a_r = pooled(["orx-verify-off"])
    b_p, b_n, b_r = pooled(["orx-gate-off"])
    print("P3 gate adds < 0.10 (stop off in both): |%.2f - %.2f| = %.2f -> %s"
          % (a_r, b_r, abs(a_r - b_r), "holds" if abs(a_r - b_r) < 0.10 else "does NOT hold"))
    out["p3"] = {"gate_on": a_r, "gate_off": b_r}

    harness = [r for a in STOP_ON + ("orx-verify-off",) for r in by_arm.get(a, [])]
    h_armed = sum(1 for r in harness if (r.get("session_rows") or 0) > 0)
    bare = by_arm.get("omp-bare", [])
    bare_neg = sum(1 for r in bare if r.get("session_rows") == -1)
    rate = h_armed / len(harness) if harness else 0.0
    print("P4 arming: harness arms %.0f%% armed (need >= 90%%), bare -1 on %d/%d -> %s"
          % (100 * rate, bare_neg, len(bare),
             "holds" if rate >= 0.90 and bare_neg == len(bare) else "does NOT hold"))
    out["p4"] = {"harness_armed": rate, "bare_unknown": bare_neg, "bare_n": len(bare)}

    fails = [r for a in STOP_OFF for r in by_arm.get(a, []) if not r["pass"]]
    claimed = [r for r in fails if CLAIM.search(r.get("final_message") or "")]
    cr = len(claimed) / len(fails) if fails else 0.0
    print("P5 false completion in stop-off failures >= 0.70: %.2f (%d/%d) -> %s"
          % (cr, len(claimed), len(fails), "holds" if cr >= 0.70 else "does NOT hold"))
    out["p5"] = {"rate": cr, "claimed": len(claimed), "fails": len(fails)}

    wrong = [r for r in rows if route(r) == "helper (wrong)"]
    wrong_pass = sum(1 for r in wrong if r["pass"])
    print("\nroute summary: %d wrong-route runs, %d of them still passed (%.2f)"
          % (len(wrong), wrong_pass, (wrong_pass / len(wrong)) if wrong else 0.0))
    for arm in sorted(by_arm):
        rs = by_arm[arm]
        w = sum(1 for r in rs if route(r) == "helper (wrong)")
        print("   %-16s wrong route %2d/%d" % (arm, w, len(rs)))
    out["rows"] = len(rows)
    print("\n" + json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "results/orx"))
