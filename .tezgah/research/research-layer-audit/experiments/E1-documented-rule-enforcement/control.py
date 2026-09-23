#!/usr/bin/env python3
"""Control for E1: a line that violates a rule the checker IS known to enforce
must be refused. If this exits 0, the E1 harness is not reading the CLI's
verdict and E1's 0/8 is void.

Two cells, each in its own temp git repo:
  ctrl-A  protocol.md committed AFTER results.jsonl      -> predicted refusal
  ctrl-B  a claim with no falsification criterion        -> predicted refusal
"""
import json
import os
import subprocess
import sys
import tempfile

CLI = sys.argv[1]


def sh(cwd, *args, stdin=None):
    return subprocess.run([CLI] + list(args), cwd=cwd, input=stdin,
                          capture_output=True, text=True)


def repo():
    d = tempfile.mkdtemp(prefix="rlctrl-")
    for cmd in (["init", "-q", d], ["-C", d, "config", "user.email", "c@x"],
                ["-C", d, "config", "user.name", "c"]):
        subprocess.run(["git"] + cmd, check=True)
    return d


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def commit(d, msg):
    subprocess.run(["git", "-C", d, "add", "-A"], check=True)
    subprocess.run(["git", "-C", d, "commit", "-qm", msg], check=True)


out = []

d = repo()
sh(d, "init", "q", "--question", "does x help?")
b = os.path.join(d, ".tezgah", "research", "q")
write(os.path.join(b, "experiments", "E1", "protocol.md"), "x\n")
write(os.path.join(b, "experiments", "E1", "results.jsonl"), '{"v":1}\n')
write(os.path.join(b, "experiments", "E1", "analysis.md"), "x\n")
commit(d, "line with results")
write(os.path.join(b, "experiments", "E1", "protocol.md"), "late\n")
commit(d, "protocol after the results")
p = sh(d, "check")
out.append({"cell": "ctrl-A protocol committed after the results",
            "exit": p.returncode, "refuses": p.returncode != 0,
            "said": p.stdout.strip().splitlines()[:3]})

d = repo()
sh(d, "init", "q", "--question", "does x help?")
p = sh(d, "claim", "q", stdin=json.dumps({
    "id": "C1", "statement": "x holds", "status": "supported",
    "provenance": "ai-executed", "falsification": "",
    "proof": "experiments/E1/results.jsonl"}))
out.append({"cell": "ctrl-B claim with no falsification criterion",
            "exit": p.returncode, "refuses": p.returncode != 0,
            "said": (p.stdout + p.stderr).strip().splitlines()[:3]})

print(json.dumps(out, indent=2))
print("control refused %d of 2" % sum(1 for r in out if r["refuses"]))
