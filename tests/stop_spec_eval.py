#!/usr/bin/env python3
"""The bet's measurements for plan 063: the temporal Stop spec against the
imperative fold.

    python3 tests/stop_spec_eval.py --replay        # GO 2: plan 055's replayed Stop events
    python3 tests/stop_spec_eval.py --shadow-rows   # GO 2: the live `stop_spec` rows
    python3 tests/stop_spec_eval.py --timing        # GO 3: perf_counter, in-process
    python3 tests/stop_spec_eval.py --mutants       # generated table mutants

`--replay` builds plan 055's corpus in this process (`tezgah_replay.build_corpus`:
the real ledgers, read-only) and judges every joined Stop item twice over the same
session prefix, once per fold, the way the replay child does (`_replay_one`).
`--timing` times the same items. `--mutants` draws seeded mutants of the formula
table and runs the in-process Stop test classes of `tests/test_integrity.py` with
the mutant standing in for `_evidence_block` - the switch-over, simulated; a
mutant no test notices survives. The hook tests that run a Stop hook in a
subprocess do not see an in-process mutant, so they are not part of that oracle.

Every result is written under `~/.cache/tezgah/replay/` (owner only) and printed.
Exit 0 when the run completed; the bars are read off the output, not the status.
"""
import argparse
import inspect
import json
import os
import random
import statistics
import subprocess
import sys
import time
import unittest
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, HERE)
import tezgah_integrity as ti  # noqa: E402
import tezgah_replay as tr  # noqa: E402
import tezgah_stopspec as ss  # noqa: E402

SEED = 63
MUTANTS = 24


def _out(name, data):
    os.makedirs(tr.replay_root(), mode=0o700, exist_ok=True)
    path = os.path.join(tr.replay_root(), "stopspec-%s-%s.json"
                        % (name, time.strftime("%Y%m%dT%H%M%S")))
    tr._owner_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("written: %s" % path)


def stop_events():
    """(item, prefix, turn) per joined Stop item of plan 055's corpus."""
    items, stream, _counts, _parents, _folds = tr.build_corpus(int(time.time()))
    by = {it["i"]: it for it in items}
    rows_of = defaultdict(list)
    out = []
    for _ts, fname, _sid, row in stream:
        at = row.pop("_item", None)
        it = by.get(at) if at is not None else None
        if it is not None and it["kind"] == "claim" and it.get("text") is not None:
            prefix = [r for r in rows_of[fname] if not (
                r.get("kind") in ("shape", ss.ROW_KIND) and r.get("id") == it["id"])]
            out.append((it, prefix, prefix[ti._turn_start(prefix):]))
        rows_of[fname].append(row)
    return out


def _judge(it, prefix, turn, fold):
    live_events = ti.events
    ti.events = lambda _sid, tail=None: prefix[-tail:] if tail else list(prefix)
    try:
        return ti._stop_block(it["text"], it["sid"], rows=turn, cwd=it["cwd"],
                              fold=fold)[0]
    finally:
        ti.events = live_events


def _spec_fold(rows, worked, external, where="this turn"):
    return ss.fold(rows, worked, external, where)


def replay():
    events = stop_events()
    rows, moved = [], Counter()
    for it, prefix, turn in events:
        try:
            imp = _judge(it, prefix, turn, ti._evidence_block)
            spec = _judge(it, prefix, turn, _spec_fold)
        except Exception as exc:  # a crash is a result, never an agreement
            imp, spec = "error", "%s: %s" % (type(exc).__name__, exc)
        rows.append({"i": it["i"], "sid": it["sid"], "ts": it["ts"], "live": it["live"],
                     "live_rule": it["live_rule"], "imperative": imp, "spec": spec,
                     "turn_rows": len(turn)})
        moved["%s -> %s" % (imp or "ok", spec or "ok")] += 1
    agree = sum(1 for r in rows if r["imperative"] == r["spec"])
    evidence = [r for r in rows if r["imperative"] not in ti.SHAPE_BLOCKS]
    agree_ev = sum(1 for r in evidence if r["imperative"] == r["spec"])
    summary = {"n": len(rows), "agree": agree,
               "agreement": round(100.0 * agree / len(rows), 3) if rows else None,
               "n_evidence_judged": len(evidence), "agree_evidence_judged": agree_ev,
               "classes": dict(moved),
               "disagreements": [r for r in rows if r["imperative"] != r["spec"]]}
    print("replayed Stop events: n=%d agree=%d (%s%%); not refused on shape: n=%d agree=%d"
          % (summary["n"], agree, summary["agreement"], len(evidence), agree_ev))
    for key, count in sorted(moved.items(), key=lambda kv: -kv[1]):
        print("  %5d  %s" % (count, key))
    for r in summary["disagreements"]:
        print("  DISAGREE i=%s sid=%s imperative=%s spec=%s" % (
            r["i"], r["sid"], r["imperative"], r["spec"]))
    _out("replay", summary)
    return summary


def shadow_rows():
    count, bad = Counter(), []
    for path in ti.ledgers():
        for row in ti._foreign_rows(path):
            if row.get("kind") != ss.ROW_KIND:
                continue
            detail = str(row.get("detail") or "")
            count[detail.split(":", 1)[0]] += 1
            if not detail.startswith("agree"):
                bad.append({"ledger": os.path.basename(path), "ts": row.get("ts"),
                            "detail": detail})
    n = sum(count.values())
    summary = {"n": n, "min_n": ss.MIN_LIVE_N, "counts": dict(count),
               "agreement": round(100.0 * count["agree"] / n, 3) if n else None,
               "readable": n >= ss.MIN_LIVE_N, "disagreements": bad}
    print("live stop_spec rows: n=%d (pre-registered minimum %d, %s) %s" % (
        n, ss.MIN_LIVE_N, "readable" if summary["readable"] else "NOT readable",
        dict(count)))
    for r in bad:
        print("  %s %s %s" % (r["ledger"], r["ts"], r["detail"]))
    _out("shadow-rows", summary)
    return summary


def _p(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else None


def timing(reps=7):
    """Per item, the best of `reps` interleaved runs of each fold alone (the
    selector is shared, so the post-switch delta is the fold's) and of the whole
    second decision the shadow adds while both run. The load average is printed
    beside it: on a loaded machine the tail is the machine's."""
    spent = [0.0]

    def timed(fold):
        def run(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fold(*args, **kwargs)
            finally:
                spent[0] += time.perf_counter() - t0
        return run

    folds = (timed(ti._evidence_block), timed(_spec_fold))
    imp_ms, spec_ms, delta, whole = [], [], [], []
    for it, prefix, turn in stop_events():
        best = [float("inf")] * 3
        for _ in range(reps):
            for k, fold in enumerate(folds):
                spent[0] = 0.0
                t0 = time.perf_counter()
                try:
                    _judge(it, prefix, turn, fold)
                except Exception:
                    pass
                total = (time.perf_counter() - t0) * 1000
                best[k] = min(best[k], spent[0] * 1000)
                if k == 1:
                    best[2] = min(best[2], total)
        imp_ms.append(best[0])
        spec_ms.append(best[1])
        delta.append(best[1] - best[0])
        whole.append(best[2])
    summary = {"n": len(delta), "reps": reps, "loadavg": os.getloadavg(),
               "imperative_fold_ms": {"p50": _p(imp_ms, .5), "p95": _p(imp_ms, .95)},
               "spec_fold_ms": {"p50": _p(spec_ms, .5), "p95": _p(spec_ms, .95)},
               "post_switch_delta_ms": {"p50": _p(delta, .5), "p95": _p(delta, .95),
                                        "mean": statistics.fmean(delta) if delta else None},
               "shadow_added_ms": {"p50": _p(whole, .5), "p95": _p(whole, .95)}}
    print(json.dumps(summary, indent=2))
    _out("timing", summary)
    return summary


# --------------------------------------------------------------- mutants --

def _paths(f, at=()):
    yield at, f
    if isinstance(f, tuple):
        for k, arg in enumerate(f[1:], 1):
            yield from _paths(arg, at + (k,))


def _put(f, at, new):
    if not at:
        return new
    k = at[0]
    return f[:k] + (_put(f[k], at[1:], new),) + f[k + 1:]


def _mutate(f, rng):
    """One seeded mutation of one formula, or None when the draw was a no-op."""
    at, node = rng.choice(list(_paths(f)))
    atoms = ss.ROW_ATOMS + ss.SCOPE_ATOMS + ("Pb",)
    if isinstance(node, str):
        op = rng.choice(("negate", "swap-atom"))
        new = ("not", node) if op == "negate" else rng.choice(
            [a for a in atoms if a != node])
    elif node[0] == "S":
        op = rng.choice(("swap-since", "since-to-once", "drop-guard"))
        new = {"swap-since": ("S", node[2], node[1]),
               "since-to-once": ("O", node[2]),
               "drop-guard": node[2]}[op]
    elif node[0] in ("and", "or"):
        op = rng.choice(("flip-junction", "drop-operand"))
        new = (("or" if node[0] == "and" else "and",) + node[1:] if op == "flip-junction"
               else node[1 + rng.randrange(len(node) - 1)])
    elif node[0] == "not":
        op, new = "drop-not", node[1]
    else:  # O
        op, new = "once-to-atom", node[1]
    return (op, at, new) if new != node else None


def mutants(n=MUTANTS, seed=SEED):
    rng = random.Random(seed)
    out, seen = [], set()
    while len(out) < n:
        name = rng.choice(sorted(ss.FORMULAS))
        drawn = _mutate(ss.FORMULAS[name], rng)
        if drawn is None:
            continue
        op, at, new = drawn
        key = (name, at, repr(new))
        if key in seen:
            continue
        seen.add(key)
        out.append({"formula": name, "op": op, "at": list(at),
                    "table": {k: (_put(f, at, new) if k == name else f)
                              for k, f in ss.FORMULAS.items()}})
    return out


def _stop_classes():
    """The in-process test classes of test_integrity that reach the Stop fold."""
    import test_integrity
    out = []
    for name, cls in inspect.getmembers(test_integrity, inspect.isclass):
        if issubclass(cls, unittest.TestCase) and cls.__module__ == test_integrity.__name__:
            src = inspect.getsource(cls)
            if "_stop_block" in src or "stop_reason" in src or "_evidence_block" in src:
                out.append(name)
    return sorted(out)


def _to_tuple(f):
    return tuple(_to_tuple(x) for x in f) if isinstance(f, list) else f


def mutant_child(table_json):
    """Run the Stop test classes with `table_json` standing in for the fold; exit
    status 0 means the mutant survived."""
    table = ss.compile_table({k: _to_tuple(v) for k, v in json.loads(table_json).items()})
    live = ti._evidence_block

    def switched(rows, worked, external, where="this turn"):
        cls = ss.fold(rows, worked, external, where, table)[0]
        imp = live(rows, worked, external, where)
        # the text follows the class: the imperative one when the classes agree
        return (cls, imp[1] if imp[0] == cls else cls) if cls else (None, None)

    ti._evidence_block = switched
    import test_integrity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(getattr(test_integrity, c))
                               for c in _stop_classes())
    result = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
    first = (result.failures + result.errors)[:1]
    print(json.dumps({"run": result.testsRun, "failed": len(result.failures),
                      "errors": len(result.errors),
                      "first": first[0][0].id() if first else None}))
    return 0 if result.wasSuccessful() else 1


def run_mutants(n=MUTANTS, workers=3):
    import concurrent.futures
    env = {k: v for k, v in os.environ.items() if k != ss.STRICT}
    cases = [{"formula": "control", "op": "none", "at": [], "table": ss.FORMULAS}] \
        + mutants(n)

    def one(m):
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--mutant-child",
                               json.dumps(m["table"])], capture_output=True, text=True,
                              env=env, cwd=REPO, stdin=subprocess.DEVNULL)
        last = (proc.stdout.strip().splitlines() or ["{}"])[-1]
        try:
            info = json.loads(last)
        except ValueError:
            info = {"crash": proc.stderr[-400:]}
        return dict(m, status=proc.returncode, result=info)

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(one, cases))
    control, rest = results[0], results[1:]
    survivors = [r for r in rest if r["status"] == 0]
    print("control: %s %s" % ("green" if control["status"] == 0 else "RED",
                              control["result"]))
    for r in rest:
        print("%-8s %-16s %-14s at %-10s %s" % (
            "SURVIVED" if r["status"] == 0 else "killed", r["formula"], r["op"],
            r["at"], r["result"].get("first") or ""))
    print("%d generated mutant(s), %d killed, %d survived (seed %d)" % (
        len(rest), len(rest) - len(survivors), len(survivors), SEED))
    _out("mutants", {"seed": SEED, "control": control, "mutants": rest,
                     "survived": len(survivors)})
    return 0 if control["status"] == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--shadow-rows", action="store_true")
    ap.add_argument("--timing", action="store_true")
    ap.add_argument("--mutants", action="store_true")
    ap.add_argument("--mutant-child")
    args = ap.parse_args(argv)
    if args.mutant_child:
        return mutant_child(args.mutant_child)
    if not (args.replay or args.shadow_rows or args.timing or args.mutants):
        ap.error("name at least one of --replay, --shadow-rows, --timing, --mutants")
    status = 0
    if args.replay:
        replay()
    if args.shadow_rows:
        shadow_rows()
    if args.timing:
        timing()
    if args.mutants:
        status = run_mutants()
    return status


if __name__ == "__main__":
    sys.exit(main())
