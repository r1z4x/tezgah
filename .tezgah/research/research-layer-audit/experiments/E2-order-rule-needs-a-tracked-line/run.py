#!/usr/bin/env python3
"""E2 cells A and B: the order rule in a tracked layout versus an untracked one.

  A  line tracked, protocol committed before results        -> predicted clean
  B  line never committed (what a gitignored .tezgah/ gives) -> predicted warning
"""
import json
import os
import subprocess
import sys
import tempfile

CLI = sys.argv[1]


def run(cwd, *args, **kw):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, **kw)


def repo():
    d = tempfile.mkdtemp(prefix="rlorder-")
    for cmd in (["init", "-q", d], ["-C", d, "config", "user.email", "o@x"],
                ["-C", d, "config", "user.name", "o"]):
        run(d, "git", *cmd)
    return d


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def commit(d, msg):
    run(d, "git", "-C", d, "add", "-A")
    run(d, "git", "-C", d, "commit", "-qm", msg)


out = []

for cell, tracked in (("A", True), ("B", False)):
    d = repo()
    write(os.path.join(d, "README.md"), "base\n")
    commit(d, "base")
    subprocess.run([CLI, "init", "q", "--question", "does x help?"],
                   cwd=d, capture_output=True, text=True)
    b = os.path.join(d, ".tezgah", "research", "q")
    write(os.path.join(b, "experiments", "E1", "protocol.md"), "predicts x\n")
    write(os.path.join(b, "experiments", "E1", "analysis.md"), "x\n")
    if tracked:
        commit(d, "protocol")
    write(os.path.join(b, "experiments", "E1", "results.jsonl"), '{"v":1}\n')
    if tracked:
        commit(d, "results")
    p = subprocess.run([CLI, "check"], cwd=d, capture_output=True, text=True)
    out.append({"cell": cell, "tracked": tracked, "exit": p.returncode,
                "refuses": p.returncode != 0,
                "said": p.stdout.strip().splitlines()})

print(json.dumps(out, indent=2))
