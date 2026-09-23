#!/usr/bin/env python3
"""Probe which documented research-layer rules the checked implementation
actually enforces. Each probe builds the smallest line that violates exactly one
rule from skills/research/SKILL.md, then runs the shipped CLI and prints what it
said.

Usage: python3 probe.py <path-to-bin/tezgah-research>
"""
import json
import os
import subprocess
import sys
import tempfile

CLI = sys.argv[1]

CLAIM = {
    "kind": "evidence",
    "id": "C1",
    "statement": "x holds",
    "status": "supported",
    "provenance": "ai-executed",
    "falsification": "x fails on the rerun",
    "proof": "experiments/E1/results.jsonl",
}

rows = []


def sh(cwd, *args, stdin=None):
    return subprocess.run([CLI] + list(args), cwd=cwd, input=stdin,
                          capture_output=True, text=True)


def repo():
    d = tempfile.mkdtemp(prefix="rlprobe-")
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "p@x"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "p"], check=True)
    return d


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def line(repo, slug="q", question="does x help?"):
    sh(repo, "init", slug, "--question", question)
    return os.path.join(repo, ".tezgah", "research", slug)


def record(name, documented, proc, cwd):
    """Documented = what SKILL.md says check does; observed = what it printed."""
    failed = proc.returncode != 0
    rows.append({
        "probe": name,
        "documented": documented,
        "observed_exit": proc.returncode,
        "observed_line": [line for line in (proc.stdout or "").splitlines() if line.strip()],
        "refuses": failed,
    })
    print("--- %s\n  documented: %s\n  exit=%d refuses=%s\n  out: %s"
          % (name, documented, proc.returncode, failed,
             " | ".join(rows[-1]["observed_line"]) or "(no output)"))
    return rows[-1]


print("tezgah-research:", CLI)
print()

# P1. state.json: the locked evaluation and the hypothesis list are both named in
# the skill ("lock the evaluation before running anything: the metric, the
# baseline, the threshold") but neither appears in the template's checker.
d = repo()
b = line(d)
state = json.load(open(os.path.join(b, "state.json")))
state["evaluation"] = {"metric": "", "baseline": "", "locked_at": ""}
state["phase"] = "inner"
state["hypotheses"] = []
write(os.path.join(b, "state.json"), json.dumps(state))
record("P1 empty evaluation (no metric/baseline) in state.json",
       "skill: lock the metric and baseline before anything runs", sh(d, "check"), d)

# P2. protocol.md content: the skill requires what changes, what it predicts, why
# and what would falsify it. Only its existence and commit time are checked.
d = repo()
b = line(d)
write(os.path.join(b, "experiments", "E1", "protocol.md"), "run it\n")
write(os.path.join(b, "experiments", "E1", "results.jsonl"), '{"v": 1}\n')
write(os.path.join(b, "experiments", "E1", "analysis.md"), "ok\n")
record("P2 protocol.md with no prediction and no falsification criterion",
       "skill: protocol states what changes, predicts, why, what falsifies it",
       sh(d, "check"), d)

# P3. results.jsonl rows: "every result row carries its source" and analysis
# labels CONFIRMATORY/EXPLORATORY. The file is never parsed.
d = repo()
b = line(d)
write(os.path.join(b, "experiments", "E1", "protocol.md"), "x\n")
write(os.path.join(b, "experiments", "E1", "results.jsonl"),
      "this is not even json\n")
write(os.path.join(b, "experiments", "E1", "analysis.md"), "no label\n")
record("P3 results.jsonl that is not JSON, rows with no source, analysis with no label",
       "skill: exact numbers, a source on every row", sh(d, "check"), d)

# P4. claim proof with no path in it at all: "cites no evidence" is decided by
# truthiness, and a prose proof passes with nothing binding it.
d = repo()
b = line(d)
os.remove(os.path.join(b, "claims.jsonl"))
c = dict(CLAIM, proof="verified by hand, I checked it")
p = sh(d, "claim", "q", stdin=json.dumps(c))
record("P4 claim whose proof names no artifact at all",
       "skill: a proof cites the evidence; fabricated evidence must be refused",
       p, d)

# P5. claim proof resolving to an experiment directory with an empty results file.
d = repo()
b = line(d)
write(os.path.join(b, "experiments", "E1", "protocol.md"), "x\n")
open(os.path.join(b, "experiments", "E1", "results.jsonl"), "w").close()
p = subprocess.run([CLI, "claim", "q"], cwd=d, input=json.dumps(CLAIM),
                   capture_output=True, text=True)
record("P5 claim whose proof is an experiment with zero result rows",
       "skill (verbatim): proof resolving to an experiment directory that "
       "actually has results", p, d)

# P6. claim proof resolving to a repository file the line never produced.
d = repo()
b = line(d)
write(os.path.join(d, "src", "unrelated.py"), "# nothing to do with the line\n")
p = subprocess.run([CLI, "claim", "q"], cwd=d,
                   input=json.dumps(dict(CLAIM, proof="src/unrelated.py")),
                   capture_output=True, text=True)
record("P6 claim whose proof is any file in the repository",
       "skill: a path the line never produced is the fabricated-evidence failure",
       p, d)

# P7. state.json.sessions: the skill requires the session record with provenance
# tags; the checker validates neither the field nor its contents.
d = repo()
b = line(d)
state = json.load(open(os.path.join(b, "state.json")))
state["sessions"] = [{"tag": "user-typed-it", "what": ""}]
write(os.path.join(b, "state.json"), json.dumps(state))
record("P7 state.json.sessions entry with an unknown provenance tag",
       "skill: every session event tagged user/ai-suggested/ai-executed/user-revised",
       sh(d, "check"), d)

# P8. literature/: the skill names one note per source and a verification rule
# for every citation; nothing reads the directory.
d = repo()
b = line(d)
write(os.path.join(b, "literature", "ghost.md"),
      "# A Real Paper, 2026\nverified: yes, two sources\n")
write(os.path.join(b, "findings.md"),
      open(os.path.join(b, "findings.md")).read() +
      "\nWe follow (2301.99999, 'A Real Paper', 2026) throughout.\n")
record("P8 a literature note with no identifier, no URL and a source that does not exist",
       "skill: never write a citation from memory; verify against two of Semantic "
       "Scholar, CrossRef, arXiv, OpenAlex", sh(d, "check"), d)

print()
print(json.dumps(rows, indent=2))
enforced = sum(1 for r in rows if r["refuses"])
print("\n%d of %d documented rules refused the violating line" % (enforced, len(rows)))
