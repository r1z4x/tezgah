#!/usr/bin/env python3
"""Harness benchmark: tezgah+opencode vs omp-bare vs omp+tezgah-port.

3 arms x 6 tasks, same model (openrouter/deepseek/deepseek-v4-flash), fresh
fixture copy per run, hidden tests injected only at check time.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIXTURE = BASE / "fixture"
HIDDEN = BASE / "hidden"
TASKS = BASE / "tasks"
RESULTS = BASE / "results"
RESULTS.mkdir(exist_ok=True)

MODEL = "openrouter/deepseek/deepseek-v4-flash"
OMP = str(Path.home() / ".local" / "bin" / "omp")
CONTRACT = Path.home() / ".config" / "tezgah" / "opencode-contract.md"

ARMS = {
    "tezgah+opencode": "A",
    "omp-bare": "B",
    "omp+tezgah-port": "C",
}

HIDDEN_FOR = {"t1": "t1", "t2": "t2", "t3": "t3", "t5": "t5", "t6": "t6"}

BANNED = [
    "co-authored-by", "generated with", "made with", "built by", "assisted by",
    "authored by", "claude", "anthropic", "openai", "chatgpt", "gpt",
    "codex", "gemini", "cursor", "copilot", "deepseek", "\U0001f916",
]

TR_MARKERS = [
    "ve", "için", "bir", "bu", "olarak", "ile", "değil", "var", "fonksiyon",
    "fonksiyonlar", "toplam", "indirim", "döndürür", "liste", "fiyat", "işe",
    "yarar", "yapıyor", "kullanılır", "hesaplar", "verir",
]
EN_MARKERS = [
    "the", "and", "for", "with", "this", "that", "returns", "return",
    "function", "functions", "list", "sum", "price", "discount", "used",
    "contains", "calculates", "provides",
]


def word_hits(text, words):
    low = text.lower()
    n = 0
    for w in words:
        n += len(re.findall(r"(?<![\wçğıöşü])" + re.escape(w) + r"(?![\wçğıöşü])", low))
    return n


def parse_omp(stdout):
    usage = {"input": 0, "output": 0, "cache_read": 0, "total": 0, "cost": 0.0}
    tool_calls = 0
    final = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "agent_end":
            for m in ev.get("messages", []):
                if m.get("role") != "assistant":
                    continue
                u = m.get("usage") or {}
                c = u.get("cost") or {}
                usage["input"] += u.get("input", 0) or 0
                usage["output"] += u.get("output", 0) or 0
                usage["cache_read"] += u.get("cacheRead", 0) or 0
                usage["total"] += u.get("totalTokens", 0) or 0
                if isinstance(c, dict):
                    usage["cost"] += c.get("total", 0) or 0
                for part in m.get("content", []):
                    if part.get("type") == "text":
                        final = part.get("text", "") or final
        elif ev.get("type") == "tool_execution_start":
            tool_calls += 1
    return usage, tool_calls, final


def parse_opencode(stdout):
    usage = {"input": 0, "output": 0, "cache_read": 0, "total": 0, "cost": 0.0}
    tool_calls = 0
    texts = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        part = ev.get("part") or {}
        if t == "step_finish":
            tok = part.get("tokens") or {}
            usage["input"] += tok.get("input", 0) or 0
            usage["output"] += tok.get("output", 0) or 0
            usage["total"] += tok.get("total", 0) or 0
            usage["cache_read"] += ((tok.get("cache") or {}).get("read", 0)) or 0
            usage["cost"] += part.get("cost", 0) or 0
        elif t == "tool_use":
            tool_calls += 1
        elif t == "text":
            texts.append(part.get("text", "") or "")
    return usage, tool_calls, "\n".join(texts)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def run_visible(repo):
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=repo, capture_output=True, text=True, timeout=120,
    )
    return r.returncode == 0


def run_hidden(repo, task):
    pattern = f"test_hidden_{task}.py"
    shutil.copy(HIDDEN / pattern, repo / "tests" / pattern)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern],
            cwd=repo, capture_output=True, text=True, timeout=120,
        )
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    finally:
        (repo / "tests" / pattern).unlink(missing_ok=True)


def check(task, repo, final_text):
    reasons = []
    ok = True
    src = "\n".join(p.read_text() for p in repo.rglob("*.py") if ".git" not in p.parts)

    if task != "t4":
        if not run_visible(repo):
            ok = False
            reasons.append("visible tests failed")

    if task in HIDDEN_FOR:
        hid_ok, out = run_hidden(repo, task)
        if not hid_ok:
            ok = False
            reasons.append(f"hidden {task} failed: {out.strip().splitlines()[-1] if out.strip() else '?'}")

    if task == "t3":
        if "calc_total" in src:
            ok = False
            reasons.append("calc_total still present")
        core = (repo / "inventory" / "core.py").read_text()
        rep = (repo / "inventory" / "report.py").read_text()
        if "compute_total" not in core or "compute_total" not in rep:
            ok = False
            reasons.append("compute_total missing in core/report")
        log = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=repo,
                             capture_output=True, text=True).stdout
        if not log.strip():
            ok = False
            reasons.append("no commit created")
        else:
            for b in BANNED:
                if b in log.lower():
                    ok = False
                    reasons.append(f"banned attribution in commit: {b}")

    if task == "t6":
        for rel in ["inventory/core.py", "inventory/parsing.py", "inventory/pricing.py"]:
            if sha(repo / rel) != sha(FIXTURE / rel):
                ok = False
                reasons.append(f"touched sentinel {rel}")
        pristine = {p.name for p in (FIXTURE / "inventory").glob("*.py")}
        now = {p.name for p in (repo / "inventory").glob("*.py")}
        if now - pristine:
            ok = False
            reasons.append(f"new files: {sorted(now - pristine)}")

    if task == "t4":
        tr = word_hits(final_text, TR_MARKERS)
        en = word_hits(final_text, EN_MARKERS)
        if not (tr >= 3 and tr > en):
            ok = False
            reasons.append(f"not Turkish (tr={tr}, en={en})")

    return ok, reasons


def build_cmd(arm, repo, prompt):
    if arm == "tezgah+opencode":
        return ["opencode", "run", "--dir", str(repo), "--format", "json",
                "--auto", "-m", MODEL, prompt]
    return [OMP, "-p", "--no-session", "--auto-approve", "--no-extensions",
            "--mode", "json", "--model", MODEL, "--cwd", str(repo), prompt]


def fixture_manifest():
    out = {}
    for p in FIXTURE.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts:
            out[str(p.relative_to(FIXTURE))] = sha(p)
    return out


def run_one(task, arm):
    before = fixture_manifest()
    repo = RESULTS / f"{task}__{arm.replace('+', '_')}" / "repo"
    if repo.parent.exists():
        shutil.rmtree(repo.parent)
    repo.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, repo)

    if arm == "omp+tezgah-port":
        shutil.copy(CONTRACT, repo / "AGENTS.md")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "bench init"], cwd=repo, capture_output=True)

    prompt = (TASKS / f"{task}.txt").read_text().strip()
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / ".local" / "bin") + ":" + env.get("PATH", "")
    env["PWD"] = str(repo)
    cmd = build_cmd(arm, repo, prompt)

    t0 = time.time()
    timed_out = False
    out_path = repo.parent / "stdout.log"
    err_path = repo.parent / "stderr.log"
    with open(out_path, "w") as of, open(err_path, "w") as ef:
        p = subprocess.Popen(cmd, cwd=repo, stdout=of, stderr=ef, env=env,
                             start_new_session=True)
        try:
            rc = p.wait(timeout=600)
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = -1
        finally:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
    wall = time.time() - t0
    stdout = out_path.read_text(errors="replace")
    stderr = err_path.read_text(errors="replace")

    after = fixture_manifest()
    dirty = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if dirty:
        raise RuntimeError(f"PRISTINE FIXTURE MUTATED by {arm}/{task}: {dirty}")

    if "opencode" in arm:
        usage, calls, final = parse_opencode(stdout)
    else:
        usage, calls, final = parse_omp(stdout)

    ok, reasons = check(task, repo, final)
    row = {
        "task": task, "arm": arm, "pass": ok, "reasons": reasons,
        "wall_s": round(wall, 1), "rc": rc, "timed_out": timed_out,
        "tokens": usage, "tool_calls": calls,
        "final_text_len": len(final),
        "final_text": final[:2000],
    }
    return row


def main():
    only = sys.argv[1:] or None
    rows = []
    for task in ["t1", "t2", "t3", "t4", "t5", "t6"]:
        for arm in ARMS:
            if only and task not in only:
                continue
            print(f"--- {task} | {arm} ---", flush=True)
            try:
                row = run_one(task, arm)
            except Exception as e:
                row = {"task": task, "arm": arm, "pass": False,
                       "reasons": [f"runner error: {type(e).__name__}: {e}"],
                       "wall_s": 0, "tokens": {}, "tool_calls": 0}
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("task", "arm", "pass", "wall_s", "reasons")}),
                  flush=True)
            with open(RESULTS / "results.jsonl", "a") as f:
                f.write(json.dumps(row) + "\n")

    print("\n=== SUMMARY ===")
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        p = sum(1 for r in sub if r["pass"])
        cost = sum((r.get("tokens") or {}).get("cost", 0) for r in sub)
        w = sum(r.get("wall_s", 0) for r in sub)
        tc = sum(r.get("tool_calls", 0) for r in sub)
        print(f"{arm:20} pass {p}/{len(sub)}  cost ${cost:.4f}  wall {w:.0f}s  tools {tc}")


if __name__ == "__main__":
    main()
