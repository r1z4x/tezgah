#!/usr/bin/env python3
"""Arm benchmark: run one coding task under a named arm and grade the result.

Stdlib only, no network calls of its own. `selftest` proves a task fixture
discriminates (baseline fails, gold passes) without spending a model call;
`run` spends money and records one row per (arm, task, repeat).

The accounting rules this enforces are in PREREGISTRATION.md: a timeout is
never a pass, a missing usage block is `null` rather than zero, and every row
carries the exact model, host version, command and fixture hash it ran with.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
CORPUS = ROOT / "corpus"
ARMS_FILE = ROOT / "arms.json"
USAGE_KEYS = ("total_cost_usd", "cost_usd", "cost", "usage", "input_tokens", "output_tokens")


# ---------------------------------------------------------------- utilities

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def task_ids() -> list[str]:
    return sorted(p.name for p in TASKS.iterdir() if (p / "meta.json").is_file())


def task_dir(tid: str) -> Path:
    d = TASKS / tid
    if not (d / "meta.json").is_file():
        sys.exit(f"unknown task: {tid} (known: {', '.join(task_ids())})")
    return d


SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".mypy_cache", "node_modules"}
SKIP_SUFFIXES = (".pyc", ".pyo")


def hash_tree(root: Path) -> dict[str, str]:
    """Hash every source file under `root`, skipping caches and build noise.

    Caches are excluded because running a check creates them, and a bytecode
    cache is not a file the agent edited.
    """
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if SKIP_DIRS & set(rel.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        if path.is_file():
            out[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def changed_files(run_dir: Path, fixture: Path) -> list[str]:
    before, after = hash_tree(fixture), hash_tree(run_dir)
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def copy_tree(src: Path, dst: Path) -> None:
    for path in src.rglob("*"):
        target = dst / path.relative_to(src)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def materialize(task: Path, out: Path) -> None:
    """Copy the pristine fixture into a fresh run directory.

    A task's fixture is its own `fixture/` unless `meta.json` names a shared
    one with `fixture_dir` - the imported corpus is 17 tasks over one package,
    and copying that package into every task would duplicate ~300 files.
    """
    src = fixture_of(task)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    copy_tree(src, out)


def fixture_of(task: Path) -> Path:
    rel = load_json(task / "meta.json").get("fixture_dir")
    return (ROOT / rel) if rel else (task / "fixture")


def overlay(task: Path, out: Path) -> None:
    """Apply the reference solution on top of a prepared run directory."""
    gold = task / "gold"
    if not gold.is_dir():
        sys.exit(f"{task.name}: no gold/ tree to overlay")
    copy_tree(gold, out)


def run_checks(task: Path, run_dir: Path, meta: dict) -> list[dict]:
    hidden = (task / "hidden").resolve()
    results = []
    for check in meta["checks"]:
        cmd = (check["cmd"].replace("{hidden}", str(hidden))
                          .replace("{corpus}", str(CORPUS.resolve())))
        proc = subprocess.run(
            cmd, shell=True, cwd=run_dir, capture_output=True, text=True, timeout=120
        )
        results.append({
            "name": check["name"],
            "cmd": cmd,
            "expect_exit": check["expect_exit"],
            "exit": proc.returncode,
            "passed": proc.returncode == check["expect_exit"],
            "stdout_tail": proc.stdout[-600:],
            "stderr_tail": proc.stderr[-600:],
        })
    return results


def grade(task: Path, run_dir: Path) -> dict:
    meta = load_json(task / "meta.json")
    changed = changed_files(run_dir, fixture_of(task))
    checks = run_checks(task, run_dir, meta)
    allow = list(meta.get("allow", []))
    prefixes = [a for a in allow if a.endswith("/")]
    stray = [f for f in changed
             if f not in allow and not any(f.startswith(p) for p in prefixes)]
    reasons = [f"check failed: {c['name']}" for c in checks if not c["passed"]]
    if stray:
        reasons.append("collateral edits: " + ", ".join(stray))
    return {
        "pass": not reasons,
        "checks": checks,
        "changed_files": changed,
        "collateral": stray,
        "reasons": reasons,
    }


def extract_usage(text: str) -> dict | None:
    """Pull the first usage/cost record out of a host's captured output.

    Hosts differ in both shape and stream format, so this scans for any JSON
    value carrying a known usage key and merges the last occurrence of each.
    It returns None when nothing is found: a missing usage block is never
    zero-filled (see PREREGISTRATION.md, accounting rules).
    """
    found: dict = {}

    def absorb(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in USAGE_KEYS:
                    found[key] = value
                if isinstance(value, (dict, list)):
                    absorb(value)
        elif isinstance(obj, list):
            for item in obj:
                absorb(item)

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(("{", "[")):
            continue
        try:
            absorb(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not found:
        return None
    if "total_cost_usd" in found and "cost" not in found:
        found["cost"] = found["total_cost_usd"]
    return found


def host_version(host: str) -> str:
    try:
        out = subprocess.run([host, "--version"], capture_output=True, text=True, timeout=20)
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "?"
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


# ---------------------------------------------------------------- commands

def cmd_list(_args) -> int:
    arms = load_json(ARMS_FILE)
    print(f"{len(task_ids())} tasks, {len(arms)} arms\n")
    for tid in task_ids():
        meta = load_json(TASKS / tid / "meta.json")
        print(f"  {tid:24s} {meta['family']}")
    print()
    for arm in arms:
        print(f"  {arm['name']:22s} host={arm['host']:12s} harness={arm['harness']}")
    return 0


def cmd_selftest(args) -> int:
    """Prove every fixture discriminates: baseline fails, the gold tree passes."""
    failures = []
    for tid in ([args.task] if args.task else task_ids()):
        task = task_dir(tid)
        meta = load_json(task / "meta.json")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "baseline"
            materialize(task, base)
            base_result = grade(task, base)
            gold = Path(tmp) / "gold"
            materialize(task, gold)
            overlay(task, gold)
            gold_result = grade(task, gold)

            want = meta.get("baseline_expect", "fail")
            ok = (base_result["pass"] is (want == "pass")) and gold_result["pass"]
            if not ok:
                failures.append(tid)
            print(f"  {'ok  ' if ok else 'FAIL'} {tid:24s} "
                  f"baseline={'pass' if base_result['pass'] else 'fail'} "
                  f"gold={'pass' if gold_result['pass'] else 'fail'} "
                  f"checks={sum(c['passed'] for c in gold_result['checks'])}/{len(gold_result['checks'])}")
            if not ok:
                for reason in base_result["reasons"][:3]:
                    print(f"        baseline: {reason}")
                for reason in gold_result["reasons"][:3]:
                    print(f"        gold:     {reason}")
    print(f"\n{len(task_ids()) - len(failures)}/{len(task_ids())} fixtures discriminate")
    return 1 if failures else 0


def cmd_prepare(args) -> int:
    materialize(task_dir(args.task), Path(args.out))
    print(args.out)
    return 0


def cmd_grade(args) -> int:
    result = grade(task_dir(args.task), Path(args.dir))
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


def cmd_run(args) -> int:
    arms = {a["name"]: a for a in load_json(ARMS_FILE)}
    if args.arm not in arms:
        sys.exit(f"unknown arm: {args.arm} (known: {', '.join(arms)})")
    arm = arms[args.arm]
    task = task_dir(args.task)
    meta = load_json(task / "meta.json")
    prompt = (task / meta["prompt"]).read_text(encoding="utf-8").strip()

    out = Path(args.results)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for repeat in range(1, args.repeat + 1):
        run_dir = Path(tempfile.mkdtemp(prefix=f"armbench-{args.task}-")) / "repo"
        materialize(task, run_dir)
        cmd = [part.format(cwd=run_dir, model=args.model, prompt=prompt) for part in arm["cmd"]]
        if args.dry_run:
            print(" ".join(cmd))
            continue
        env = {**os.environ, **arm.get("env", {})}
        started = time.time()
        try:
            proc = subprocess.run(
                cmd, cwd=run_dir, env=env, capture_output=True, text=True,
                timeout=args.timeout, input=None,
            )
            rc, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
        except subprocess.TimeoutExpired as exc:
            rc, timed_out = -1, True
            stdout = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        wall = round(time.time() - started, 1)
        (run_dir.parent / "stdout.log").write_text(stdout, encoding="utf-8")
        (run_dir.parent / "stderr.log").write_text(stderr, encoding="utf-8")

        if timed_out:
            result = {"pass": False, "checks": [], "changed_files": changed_files(run_dir, fixture_of(task)),
                      "collateral": [], "reasons": [f"timeout after {args.timeout}s"]}
        else:
            result = grade(task, run_dir)
        usage = extract_usage(stdout)
        row = {
            "arm": arm["name"], "host": arm["host"], "harness": arm["harness"],
            "task": args.task, "family": meta["family"], "repeat": repeat,
            "pass": result["pass"], "reasons": result["reasons"],
            "checks": [{"name": c["name"], "passed": c["passed"]} for c in result["checks"]],
            "changed_files": result["changed_files"], "collateral": result["collateral"],
            "wall_s": wall, "rc": rc, "timed_out": timed_out,
            "usage": usage, "usage_note": None if usage else "no usage record found in stdout",
            "model": args.model, "host_version": host_version(arm["host"]),
            "arm_cmd": cmd, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "fixture_sha256": hashlib.sha256(json.dumps(hash_tree(fixture_of(task)), sort_keys=True).encode()).hexdigest(),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)),
        }
        rows.append(row)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{row['arm']:22s} {row['task']:24s} r{repeat} "
              f"{'pass' if row['pass'] else 'FAIL':4s} {wall:6.1f}s "
              f"usage={'yes' if usage else 'none'}")
        if args.keep:
            print(f"    run dir: {run_dir}")
        else:
            shutil.rmtree(run_dir.parent, ignore_errors=True)
    return 0 if all(r["pass"] for r in rows) else 1


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(100 * (centre - half), 1), round(100 * (centre + half), 1))


def exact_binomial_p(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def cmd_report(args) -> int:
    rows = [json.loads(line) for line in Path(args.results).read_text(encoding="utf-8").splitlines() if line.strip()]
    by_arm: dict[str, list[dict]] = {}
    for row in rows:
        by_arm.setdefault(row["arm"], []).append(row)

    print("arm                     runs  pass  pass%  Wilson 95%     cost$    $/pass  timeouts  no-usage")
    for arm, arm_rows in sorted(by_arm.items()):
        n = len(arm_rows)
        passes = sum(1 for r in arm_rows if r["pass"])
        costs = [r["usage"]["cost"] for r in arm_rows if r.get("usage") and isinstance(r["usage"].get("cost"), (int, float))]
        total = sum(costs) if costs else None
        cps = f"{total / passes:.4f}" if total is not None and passes else "n/a"
        lo, hi = wilson(passes, n)
        print(f"{arm:22s} {n:5d} {passes:5d}  {100 * passes / n:5.1f}  {lo:5.1f}-{hi:5.1f}%  "
              f"{('%.4f' % total) if total is not None else 'n/a':>8s}  {cps:>6s}  "
              f"{sum(1 for r in arm_rows if r['timed_out']):8d}  {sum(1 for r in arm_rows if not r.get('usage')):8d}")

    if len(by_arm) == 2:
        (a, a_rows), (b, b_rows) = sorted(by_arm.items())
        print(f"\npaired {a} vs {b} (task-majority over repeats)")
        paired = []
        for tid in sorted({r["task"] for r in rows}):
            pa = [r["pass"] for r in a_rows if r["task"] == tid]
            pb = [r["pass"] for r in b_rows if r["task"] == tid]
            if not pa or not pb:
                continue
            paired.append((tid, sum(pa) > len(pa) / 2, sum(pb) > len(pb) / 2))
        only_a = sum(1 for _, x, y in paired if x and not y)
        only_b = sum(1 for _, x, y in paired if y and not x)
        both = sum(1 for _, x, y in paired if x and y)
        neither = sum(1 for _, x, y in paired if not x and not y)
        print(f"  a-only={only_a} b-only={only_b} both={both} neither={neither} n={len(paired)}")
        print(f"  exact McNemar (two-sided) p={exact_binomial_p(min(only_a, only_b), only_a + only_b):.4f}")
    print("\nRead PREREGISTRATION.md before quoting any number here: a single repeat")
    print("per cell is description, not evidence.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show the task set and the arms").set_defaults(func=cmd_list)

    p = sub.add_parser("selftest", help="verify fixtures discriminate, no model calls")
    p.add_argument("--task")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("prepare", help="materialise a task fixture into a directory")
    p.add_argument("--task", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("grade", help="run a task's checks against a directory")
    p.add_argument("--task", required=True)
    p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_grade)

    p = sub.add_parser("run", help="run an arm on a task (spends money)")
    p.add_argument("--arm", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--model", required=True)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--results", default=str(ROOT / "results.jsonl"))
    p.add_argument("--keep", action="store_true", help="keep the run directory")
    p.add_argument("--dry-run", action="store_true", help="print the command and exit")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="aggregate a results file")
    p.add_argument("--results", default=str(ROOT / "results.jsonl"))
    p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
