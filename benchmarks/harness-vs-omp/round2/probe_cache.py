#!/usr/bin/env python3
"""Isolate the cause of the omp+tezgah-port prompt-cache miss on t18.

Variants remove one port component at a time; each variant runs twice so the
second run shows warm-cache behaviour. Prints per-step (input, cacheRead).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIXTURE = BASE / "fixture"
PORT = BASE / "port" / "omp"
OUT = BASE / "probe"
OUT.mkdir(exist_ok=True)
MODEL = os.environ.get("BENCH_MODEL", "openrouter/deepseek/deepseek-v4-flash")
OMP = str(Path.home() / ".local" / "bin" / "omp")
PROMPT = (BASE / "tasks" / "t18.txt").read_text().strip()


def setup(repo, variant):
    if variant == "graph":
        (repo / ".omp").mkdir(exist_ok=True)
        shutil.copy(PORT / ".omp" / "mcp.json", repo / ".omp" / "mcp.json")
        return
    shutil.copy(PORT / "AGENTS.md", repo / "AGENTS.md")
    if variant == "agents_only":
        shutil.copy(PORT / "AGENTS.md", repo / "AGENTS.md")
        return
    shutil.copytree(PORT / ".omp", repo / ".omp", dirs_exist_ok=True)
    if variant == "no_hook":
        shutil.rmtree(repo / ".omp" / "hooks", ignore_errors=True)
    elif variant == "no_mcp":
        (repo / ".omp" / "mcp.json").unlink(missing_ok=True)
    elif variant == "no_skills_agents":
        shutil.rmtree(repo / ".omp" / "skills", ignore_errors=True)
        shutil.rmtree(repo / ".omp" / "agents", ignore_errors=True)
    elif variant == "no_agents":
        shutil.rmtree(repo / ".omp" / "agents", ignore_errors=True)
    elif variant == "no_skills":
        shutil.rmtree(repo / ".omp" / "skills", ignore_errors=True)


def steps(path):
    out = []
    for line in open(path):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "agent_end":
            for m in ev.get("messages", []):
                if m.get("role") == "assistant":
                    u = m.get("usage") or {}
                    out.append(((u.get("input", 0) or 0), (u.get("cacheRead", 0) or 0)))
    return out


def run(variant, rep):
    repo = OUT / f"{variant}_{rep}" / "repo"
    if repo.parent.exists():
        shutil.rmtree(repo.parent)
    repo.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, repo)
    setup(repo, variant)
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, capture_output=True)
    cmd = [OMP, "-p", "--no-session", "--auto-approve", "--mode", "json",
           "--model", MODEL, "--cwd", str(repo), PROMPT]
    with open(repo.parent / "out.log", "w") as f:
        subprocess.run(cmd, cwd=repo, stdout=f, stderr=subprocess.DEVNULL, timeout=300)
    st = steps(repo.parent / "out.log")
    inp = sum(a for a, _ in st)
    cachemax = max((b for _, b in st), default=0)
    print(f"{variant:18} run{rep}  steps={len(st)} input={inp:>7} maxCache={cachemax:>7}  per-step={st}", flush=True)


if __name__ == "__main__":
    variants = sys.argv[1:] or ["graph", "full", "no_hook", "no_mcp",
                                "no_skills_agents", "no_agents", "no_skills"]
    for v in variants:
        for rep in (1, 2):
            try:
                run(v, rep)
            except Exception as exc:
                print(f"{v:18} run{rep}  ERROR {type(exc).__name__}: {exc}", flush=True)
