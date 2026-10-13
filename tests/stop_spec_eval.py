#!/usr/bin/env python3
"""Generated mutants of the Stop rule's temporal spec (plan 063).

    python3 tests/stop_spec_eval.py --mutants       # generated table mutants

`--mutants` draws seeded mutants of the formula table and runs the in-process
Stop test classes of `tests/test_integrity.py` with the mutant's table standing
in for the live one (`tezgah_stopspec._TABLE`); a mutant no test notices
survives. The hook tests that run a Stop hook in a subprocess do not see an
in-process mutant, so they are not part of that oracle. The bet's other
measurements (`--replay`, `--shadow-rows`, `--timing`, `--stop-cost`) compared
the spec with the imperative fold; plan 101 deleted that fold, and with it them.

The result is written under `~/.cache/tezgah/replay/` (owner only) and printed.
Exit 0 when the control is green; survivors are read off the output.
"""
import argparse
import inspect
import json
import os
import random
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, HERE)
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
            if "_stop_block" in src or "stop_reason" in src:
                out.append(name)
    return sorted(out)


def _to_tuple(f):
    return tuple(_to_tuple(x) for x in f) if isinstance(f, list) else f


def mutant_child(table_json):
    """Run the Stop test classes with `table_json` as the live table; exit
    status 0 means the mutant survived."""
    ss._TABLE = ss.compile_table({k: _to_tuple(v)
                                  for k, v in json.loads(table_json).items()})
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
    cases = [{"formula": "control", "op": "none", "at": [], "table": ss.FORMULAS}] \
        + mutants(n)

    def one(m):
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--mutant-child",
                               json.dumps(m["table"])], capture_output=True, text=True,
                              cwd=REPO, stdin=subprocess.DEVNULL)
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
    ap.add_argument("--mutants", action="store_true")
    ap.add_argument("--mutant-child")
    args = ap.parse_args(argv)
    if args.mutant_child:
        return mutant_child(args.mutant_child)
    if not args.mutants:
        ap.error("name --mutants")
    return run_mutants()


if __name__ == "__main__":
    sys.exit(main())
