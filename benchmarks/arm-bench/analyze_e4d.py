#!/usr/bin/env python3
"""Read the E4d block against PREREGISTRATION-E4d.md (section 2b sizing).

    python3 analyze_e4d.py results/orx/6ff5446
"""
import collections
import glob
import json
import math
import pathlib
import sys

STOP_ON = ("omp+tezgah",)
STOP_OFF = ("orx-verify-off", "orx-gate-off", "omp-bare")


def wilson(p, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    ph = p / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main(path):
    src = pathlib.Path(path)
    files = [src] if src.is_file() else sorted(src.glob("*.jsonl"))
    rows = [json.loads(l) for f in files for l in f.read_text().splitlines() if l.strip()]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)

    print("E4d - %d rows\n" % len(rows))
    print("%-16s %6s %-14s %8s %8s %9s" % ("arm", "pass", "wilson", "helper", "armed", "fires>0"))
    for a in sorted(by):
        rs = by[a]
        p = sum(1 for r in rs if r["pass"])
        lo, hi = wilson(p, len(rs))
        h = sum(1 for r in rs if r.get("route") == "helper")
        armed = sum(1 for r in rs if (r.get("session_rows") or 0) > 0)
        fires = sum(1 for r in rs if (r.get("stop_fires") or 0) > 0)
        print("%-16s %2d/%2d  %.2f-%.2f  %3d/%2d  %6.0f%% %9d"
              % (a, p, len(rs), lo, hi, h, len(rs), 100 * armed / len(rs), fires))

    out = {}
    go = by.get("orx-gate-off", [])
    go_h = sum(1 for r in go if r.get("route") == "helper")
    others = [r for a in ("omp+tezgah", "orx-verify-off", "omp-bare") for r in by.get(a, [])]
    o_h = sum(1 for r in others if r.get("route") == "helper")
    p1 = go_h <= 4 and o_h >= 24
    print("\nP1 gate-off helper <= 4/50 and pooled others >= 24/150")
    print("   gate-off %d/%d, pooled %d/%d -> %s" % (go_h, len(go), o_h, len(others),
                                                     "holds" if p1 else "does NOT hold"))
    out["p1"] = {"gate_off_helper": go_h, "gate_off_n": len(go), "pooled_helper": o_h}

    counts = {a: sum(1 for r in by[a] if r.get("route") == "helper") for a in sorted(by)}
    fewest = min(counts, key=lambda a: counts[a])
    p2 = fewest == "orx-gate-off" and list(counts.values()).count(counts["orx-gate-off"]) == 1
    print("P2 gate-off has strictly the fewest helper runs: %s -> %s"
          % (counts, "holds" if p2 else "does NOT hold"))
    out["p2"] = counts

    on_fires = sum(1 for r in by.get("omp+tezgah", []) if (r.get("stop_fires") or 0) > 0)
    off_fires = sum(1 for a in STOP_OFF for r in by.get(a, []) if (r.get("stop_fires") or 0) > 0)
    p3 = on_fires >= 10 and off_fires == 0
    print("P3 >= 10 omp+tezgah rows fire and 0 across the other 150: %d and %d -> %s"
          % (on_fires, off_fires, "holds" if p3 else "does NOT hold"))
    out["p3"] = {"on_fires": on_fires, "off_fires": off_fires}

    def rate(a):
        rs = by.get(a, [])
        return sum(1 for r in rs if r["pass"]) / len(rs) if rs else 0
    gap = abs(rate("omp+tezgah") - rate("orx-verify-off"))
    print("P4 |pass(omp+tezgah) - pass(orx-verify-off)| <= 0.10: %.3f -> %s"
          % (gap, "holds" if gap <= 0.10 else "does NOT hold"))
    out["p4"] = gap

    harness = [r for a in STOP_ON + ("orx-verify-off", "orx-gate-off") for r in by.get(a, [])]
    armed = sum(1 for r in harness if (r.get("session_rows") or 0) > 0) / len(harness)
    bare_ok = all((r.get("session_rows") == -1) for r in by.get("omp-bare", []))
    routed = sum(1 for r in rows if r.get("route"))
    p5 = armed >= 0.90 and bare_ok and routed == len(rows)
    print("P5 arming: harness %.0f%% armed (>=90%%), bare all -1: %s, route on %d/%d -> %s"
          % (100 * armed, bare_ok, routed, len(rows), "holds" if p5 else "does NOT hold"))
    out["p5"] = {"armed": armed, "bare_ok": bare_ok, "routed": routed}

    print("\npass rate by arm: %s" % {a: round(rate(a), 3) for a in sorted(by)})
    print("\n" + json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "results/orx"))
