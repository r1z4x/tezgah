#!/usr/bin/env python3
"""Read the E5 block against PREREGISTRATION-E5.md.

Wrong route is task-specific: `e01` reaches it by editing `src/money.py` (route
`helper`) instead of the call site, `e05` by editing only the reported site
(route `one-site`).

    python3 analyze_e5.py results/orx/3c2e39e
"""
import collections
import json
import math
import pathlib
import sys

WRONG = {"e01-silent-one-liner": "helper", "e05-three-call-sites": "one-site"}
HARNESS = ("omp+tezgah", "orx-verify-off", "orx-gate-off")
STOP_OFF = ("orx-verify-off", "orx-gate-off", "omp-bare")


def wilson(p, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    ph = p / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def wrong(r):
    return r.get("route") == WRONG.get(r["task"])


def main(path):
    src = pathlib.Path(path)
    files = [src] if src.is_file() else sorted(src.glob("*.jsonl"))
    rows = [json.loads(l) for f in files for l in f.read_text().splitlines() if l.strip()]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)

    print("E5 - %d rows\n" % len(rows))
    print("%-16s %8s %-14s %10s %8s %9s" % ("arm", "pass", "wilson", "wrong route", "armed", "fires>0"))
    for a in sorted(by):
        rs = by[a]
        p = sum(1 for r in rs if r["pass"])
        lo, hi = wilson(p, len(rs))
        w = sum(1 for r in rs if wrong(r))
        armed = sum(1 for r in rs if (r.get("session_rows") or 0) > 0)
        fires = sum(1 for r in rs if (r.get("stop_fires") or 0) > 0)
        print("%-16s %3d/%3d  %.2f-%.2f  %4d/%3d (%4.0f%%)  %6.0f%% %9d"
              % (a, p, len(rs), lo, hi, w, len(rs), 100 * w / len(rs),
                 100 * armed / len(rs), fires))

    out = {}
    on = by.get("omp+tezgah", [])
    on_w = sum(1 for r in on if wrong(r)) / len(on)
    off = [r for a in STOP_OFF for r in by.get(a, [])]
    off_w = sum(1 for r in off if wrong(r)) / len(off)
    p1 = on_w <= 0.12 and off_w >= 0.22
    print("\nP1 wrong route: omp+tezgah <= 12%%, pooled Stop-off >= 22%%")
    print("   %-16s %.3f (%d/%d)" % ("omp+tezgah", on_w, sum(1 for r in on if wrong(r)), len(on)))
    print("   %-16s %.3f (%d/%d)" % ("pooled stop-off", off_w, sum(1 for r in off if wrong(r)), len(off)))
    print("   -> %s" % ("holds" if p1 else "does NOT hold"))
    out["p1"] = {"on": on_w, "off": off_w, "gap": on_w - off_w}

    on_fires = sum(1 for r in on if (r.get("stop_fires") or 0) > 0)
    off_fires = sum(1 for a in STOP_OFF for r in by.get(a, []) if (r.get("stop_fires") or 0) > 0)
    p2 = on_fires >= 5 and off_fires == 0
    print("P2 >= 5 fires on omp+tezgah and 0 across the other 300: %d and %d -> %s"
          % (on_fires, off_fires, "holds" if p2 else "does NOT hold"))
    out["p2"] = {"on_fires": on_fires, "off_fires": off_fires}

    fired = [r for r in on if (r.get("stop_fires") or 0) > 0]
    notfired = [r for r in on if not (r.get("stop_fires") or 0) > 0]
    fr = sum(1 for r in fired if r["pass"]) / len(fired) if fired else 0.0
    nr = sum(1 for r in notfired if r["pass"]) / len(notfired) if notfired else 0.0
    p3 = fr > nr
    print("P3 fired rows pass more often: %.2f (%d/%d) vs %.2f (%d/%d) -> %s"
          % (fr, sum(1 for r in fired if r["pass"]), len(fired), nr,
             sum(1 for r in notfired if r["pass"]), len(notfired),
             "holds" if p3 else "does NOT hold"))
    out["p3"] = {"fired_rate": fr, "not_fired_rate": nr}

    def rate(a):
        rs = by.get(a, [])
        return sum(1 for r in rs if r["pass"]) / len(rs) if rs else 0.0
    seq = [rate("omp+tezgah"), rate("orx-verify-off"), rate("orx-gate-off")]
    p4 = seq[0] >= seq[1] >= seq[2]
    print("P4 pass ordering %s -> %s" % (["%.3f" % x for x in seq], "holds" if p4 else "does NOT hold"))
    out["p4"] = seq

    harness = [r for a in HARNESS for r in by.get(a, [])]
    armed = sum(1 for r in harness if (r.get("session_rows") or 0) > 0) / len(harness)
    bare_ok = all((r.get("session_rows") == -1) for r in by.get("omp-bare", []))
    routed = sum(1 for r in rows if r.get("route"))
    p5 = armed >= 0.90 and bare_ok and routed == len(rows)
    print("P5 arming %.0f%% (>=90%%), bare all -1: %s, route %d/%d -> %s"
          % (100 * armed, bare_ok, routed, len(rows), "holds" if p5 else "does NOT hold"))
    out["p5"] = {"armed": armed, "bare_ok": bare_ok, "routed": routed}

    print("\nper task")
    for t in sorted({r["task"] for r in rows}):
        line = []
        for a in sorted(by):
            rs = [r for r in by[a] if r["task"] == t]
            if rs:
                line.append("%s %d/%d wrong %d" % (a, sum(1 for r in rs if r["pass"]), len(rs),
                                                   sum(1 for r in rs if wrong(r))))
        print("  %-24s %s" % (t, " | ".join(line)))
    out["rows"] = len(rows)
    print("\n" + json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "results/orx"))
