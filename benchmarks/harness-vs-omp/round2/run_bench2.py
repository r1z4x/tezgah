#!/usr/bin/env python3
"""Round-2 harness benchmark: tezgah+opencode vs omp+graph vs omp+tezgah-port.

20 tasks x 3 arms, same model, fresh fixture copy per run, hidden tests
injected only at check time. Arm A runs sequentially (shared opencode DB);
arms B/C run through a small worker pool.
"""
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIXTURE = BASE / "fixture"
HIDDEN = BASE / "hidden"
TASKS = BASE / "tasks"
PORT = BASE / "port"
RESULTS = BASE / "results"
RESULTS.mkdir(exist_ok=True)

MODEL = "openrouter/deepseek/deepseek-v4-flash"
OMP = str(Path.home() / ".local" / "bin" / "omp")
CBM = str(Path.home() / ".local" / "bin" / "codebase-memory-mcp")
OVERLAY = str(PORT / "opencode-overlay.jsonc")

ARMS = ["tezgah+opencode", "omp+graph", "omp+tezgah-port"]
ALL_TASKS = [f"t{i}" for i in range(1, 21)]
HIDDEN_TASKS = [f"t{i}" for i in [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]]
RENAME_TASKS = {"t3": ("calc_total", "compute_total"), "t10": ("find_item", "lookup_item")}
GRAPH_TASKS = {
    "t19": {"inventory/core.py", "inventory/report.py", "tests/test_core.py"},
    "t20": {"inventory/parsing.py", "inventory/report.py"},
}
READ_ONLY = {"t4", "t19", "t20"}
TIMEOUT = 240

BANNED = [
    "co-authored-by", "generated with", "made with", "built by", "assisted by",
    "authored by", "claude", "anthropic", "openai", "chatgpt", "gpt", "codex",
    "gemini", "cursor", "copilot", "deepseek", "\U0001f916",
]
TR_MARKERS = ["ve", "için", "bir", "bu", "olarak", "ile", "değil", "var",
              "fonksiyon", "fonksiyonlar", "döndürür", "liste", "yapıyor", "kullanılır"]
EN_MARKERS = ["the", "and", "for", "with", "this", "that", "returns", "return",
              "function", "functions", "list", "used", "contains", "is"]
GRAPH_TOOLS = ["search_graph", "trace_path", "search_code", "get_architecture",
               "detect_changes", "check_index_coverage", "query_graph",
               "index_repository", "get_code_snippet"]

_oc_lock = threading.Lock()
_print_lock = threading.Lock()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def fixture_manifest():
    out = {}
    for p in FIXTURE.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts:
            out[str(p.relative_to(FIXTURE))] = sha(p)
    return out


def word_hits(text, words):
    low = text.lower()
    return sum(len(re.findall(r"(?<![\wçğıöşü])" + re.escape(w) + r"(?![\wçğıöşü])", low))
               for w in words)


def parse_omp(stdout):
    usage = {"input": 0, "output": 0, "cache_read": 0, "total": 0, "cost": 0.0}
    calls, final, graph = 0, "", 0
    tool_names = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "tool_execution_start":
            calls += 1
            nm = str(ev.get("toolName") or ev.get("name") or ev.get("tool") or "")
            tool_names.append(nm)
            if any(g in nm for g in GRAPH_TOOLS):
                graph += 1
        elif ev.get("type") == "agent_end":
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
    return usage, calls, final, graph, tool_names


def parse_opencode(stdout):
    usage = {"input": 0, "output": 0, "cache_read": 0, "total": 0, "cost": 0.0}
    calls, texts, graph = 0, [], 0
    tool_names = []
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
            calls += 1
            nm = str(part.get("tool") or "")
            tool_names.append(nm)
            if any(g in nm for g in GRAPH_TOOLS):
                graph += 1
        elif t == "text":
            texts.append(part.get("text", "") or "")
    return usage, calls, "\n".join(texts), graph, tool_names


def run_visible(repo):
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                       cwd=repo, capture_output=True, text=True, timeout=180)
    return r.returncode == 0


def run_hidden(repo, task):
    pattern = f"test_hidden_{task}.py"
    shutil.copy(HIDDEN / pattern, repo / "tests" / pattern)
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern],
                           cwd=repo, capture_output=True, text=True, timeout=180)
        return r.returncode == 0
    finally:
        (repo / "tests" / pattern).unlink(missing_ok=True)


def check(task, repo, final_text, tool_names):
    ok, reasons = True, []

    if task not in READ_ONLY and not run_visible(repo):
        ok = False
        reasons.append("visible tests failed")

    if task in HIDDEN_TASKS and not run_hidden(repo, task):
        ok = False
        reasons.append(f"hidden {task} failed")

    if task in RENAME_TASKS:
        old, new = RENAME_TASKS[task]
        src = "\n".join(p.read_text() for p in repo.rglob("*.py") if ".git" not in p.parts)
        if old in src:
            ok = False
            reasons.append(f"{old} still present")
        if new not in (repo / "inventory" / "core.py").read_text() or new not in (repo / "inventory" / "report.py").read_text():
            ok = False
            reasons.append(f"{new} missing in core/report")
        log = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=repo,
                             capture_output=True, text=True).stdout
        if not log.strip():
            ok = False
            reasons.append("no commit")
        else:
            for b in BANNED:
                if b in log.lower():
                    ok = False
                    reasons.append(f"banned attribution: {b}")

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
        tr, en = word_hits(final_text, TR_MARKERS), word_hits(final_text, EN_MARKERS)
        if not (tr >= 3 and tr > en):
            ok = False
            reasons.append(f"not Turkish (tr={tr}, en={en})")

    if task in GRAPH_TASKS:
        found = set()
        for m in re.finditer(r"FILE:\s*(\S+)", final_text):
            p = m.group(1).strip().lstrip("./")
            if p.endswith(".py"):
                found.add(p)
        if found != GRAPH_TASKS[task]:
            ok = False
            reasons.append(f"FILE set {sorted(found)} != {sorted(GRAPH_TASKS[task])}")

    return ok, reasons


def prepare(repo, arm):
    if arm == "omp+graph":
        (repo / ".omp").mkdir(exist_ok=True)
        shutil.copy(PORT / "omp" / ".omp" / "mcp.json", repo / ".omp" / "mcp.json")
    elif arm == "omp+tezgah-port":
        shutil.copy(PORT / "omp" / "AGENTS.md", repo / "AGENTS.md")
        shutil.copytree(PORT / "omp" / ".omp", repo / ".omp", dirs_exist_ok=True)


def build_cmd(arm, repo, prompt):
    if arm == "tezgah+opencode":
        return ["opencode", "run", "--dir", str(repo), "--format", "json", "--auto", "-m", MODEL, prompt]
    return [OMP, "-p", "--no-session", "--auto-approve", "--mode", "json",
            "--model", MODEL, "--cwd", str(repo), prompt]


def run_one(task, arm):
    before = fixture_manifest()
    out_dir = RESULTS / f"{task}__{arm.replace('+', '_')}"
    repo = out_dir / "repo"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    shutil.copytree(FIXTURE, repo)
    prepare(repo, arm)
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "bench init"], cwd=repo, capture_output=True)

    if task in GRAPH_TASKS:
        subprocess.run([CBM, "cli", "index_repository", "--repo-path", str(repo), "--mode", "fast"],
                       capture_output=True, text=True, timeout=240)

    prompt = (TASKS / f"{task}.txt").read_text().strip()
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / ".local" / "bin") + ":" + env.get("PATH", "")
    env["PWD"] = str(repo)
    if arm == "tezgah+opencode":
        env["OPENCODE_CONFIG"] = OVERLAY
    cmd = build_cmd(arm, repo, prompt)

    if arm == "tezgah+opencode":
        _oc_lock.acquire()
    try:
        t0 = time.time()
        timed_out = False
        out_path, err_path = out_dir / "stdout.log", out_dir / "stderr.log"
        with open(out_path, "w") as of, open(err_path, "w") as ef:
            p = subprocess.Popen(cmd, cwd=repo, stdout=of, stderr=ef, env=env, start_new_session=True)
            try:
                rc = p.wait(timeout=TIMEOUT)
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
    finally:
        if arm == "tezgah+opencode":
            _oc_lock.release()

    after = fixture_manifest()
    dirty = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if dirty:
        raise RuntimeError(f"PRISTINE FIXTURE MUTATED by {arm}/{task}: {dirty}")

    if arm == "tezgah+opencode":
        usage, calls, final, graph, names = parse_opencode(stdout)
    else:
        usage, calls, final, graph, names = parse_omp(stdout)

    ok, reasons = check(task, repo, final, names)
    row = {"task": task, "arm": arm, "pass": ok, "reasons": reasons,
           "wall_s": round(wall, 1), "rc": rc, "timed_out": timed_out,
           "tokens": usage, "tool_calls": calls, "graph_calls": graph,
           "tool_names": sorted(set(names)), "final_text_len": len(final),
           "final_text": final[:3000]}
    return row


def worker(task, arm):
    try:
        row = run_one(task, arm)
    except Exception as exc:
        row = {"task": task, "arm": arm, "pass": False,
               "reasons": [f"runner error: {type(exc).__name__}: {exc}"],
               "wall_s": 0, "tokens": {}, "tool_calls": 0, "graph_calls": 0}
    with _print_lock:
        print(json.dumps({k: row.get(k) for k in ("task", "arm", "pass", "wall_s", "graph_calls", "reasons")}), flush=True)
        with open(RESULTS / "results.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
    return row


def main():
    only = sys.argv[1:]
    tasks = [t for t in ALL_TASKS if not only or t in only]
    oc_jobs = [(t, a) for t in tasks for a in ARMS if a == "tezgah+opencode"]
    omp_jobs = [(t, a) for t in tasks for a in ARMS if a != "tezgah+opencode"]

    rows = []
    with cf.ThreadPoolExecutor(max_workers=1) as oc_pool, cf.ThreadPoolExecutor(max_workers=4) as omp_pool:
        futs = [oc_pool.submit(worker, t, a) for t, a in oc_jobs]
        futs += [omp_pool.submit(worker, t, a) for t, a in omp_jobs]
        for f in cf.as_completed(futs):
            rows.append(f.result())

    print("\n=== SUMMARY ===")
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        p = sum(1 for r in sub if r["pass"])
        cost = sum((r.get("tokens") or {}).get("cost", 0) for r in sub)
        wall = sum(r.get("wall_s", 0) for r in sub)
        tc = sum(r.get("tool_calls", 0) for r in sub)
        gc = sum(r.get("graph_calls", 0) for r in sub)
        print(f"{arm:20} pass {p}/{len(sub)}  cost ${cost:.4f}  wall {wall:.0f}s  tools {tc}  graph {gc}")


if __name__ == "__main__":
    main()
