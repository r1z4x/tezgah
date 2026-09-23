#!/usr/bin/env python3
"""E7 cells: each spec item's acceptance sentence, executed.

Run from the repository root:  python3 <this> [--repo /path/to/tezgah]
Prints one row per cell and exits 1 if any cell fails.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = "/Users/rizax/Projects/tezgah"
if "--repo" in sys.argv:
    REPO = sys.argv[sys.argv.index("--repo") + 1]
CLI = os.path.join(REPO, "bin", "tezgah-research")
ROWS = []


def env():
    e = dict(os.environ)
    e["TEZGAH_ORX_BIN"] = "/nonexistent-orx"          # deterministic: no orx in temp cells
    e["TEZGAH_CBM_BIN"] = "/nonexistent-cbm"
    return e


def run(cwd, *args, stdin=None, env_=None):
    return subprocess.run(list(args), cwd=cwd, input=stdin, env=env_ or env(),
                          capture_output=True, text=True)


def cli(cwd, *args, stdin=None):
    return run(cwd, CLI, *args, stdin=stdin)


def repo(ignore_tezgah=True):
    d = tempfile.mkdtemp(prefix="e7-")
    run(d, "git", "init", "-q", ".")
    run(d, "git", "config", "user.email", "e@x")
    run(d, "git", "config", "user.name", "e")
    if ignore_tezgah:
        with open(os.path.join(d, ".gitignore"), "w") as fh:
            fh.write("/.tezgah/\n")
        run(d, "git", "add", ".gitignore")
        run(d, "git", "commit", "-qm", "base")
    return d


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def line(d, slug="q", question="does x help?"):
    cli(d, "init", slug, "--question", question)
    return os.path.join(d, ".tezgah", "research", slug)


def state(base, **kw):
    p = os.path.join(base, "state.json")
    s = json.load(open(p))
    s.update(kw)
    json.dump(s, open(p, "w"), indent=2)


def locked(base):
    """A state.json that satisfies every rule except the one under test, so a
    cell isolates its own behaviour instead of tripping the evaluation rule."""
    state(base, evaluation={"metric": "refusals", "baseline": "8/8",
                            "locked_at": "2026-09-20", "environment": {"model": "x"}},
          hypotheses=["h1"])
    return base


def said(p):
    return p.stdout + p.stderr


def cell(item, name, ok, observed):
    ROWS.append({"item": item, "cell": name, "pass": bool(ok), "observed": observed})
    print("%-4s %-42s %s\n     %s" % (item, name, "PASS" if ok else "FAIL", observed))


# ---------------------------------------------------------------- I1
d = repo()
p = cli(d, "init", "q", "--question", "does x help?")
out = p.stdout + p.stderr
cell("I1", "init names the negation on an ignored path", "!" in out,
     "exit=%d, negation in output=%s" % (p.returncode, "!" in out))
b = os.path.join(d, ".tezgah", "research", "q")
# the rule probes the protocol/results pair, not the line directory (a directory
# can be matched by an ignore rule while the files the order rule needs are
# tracked), so the cell builds the pair it is about
write(os.path.join(b, "experiments", "E1", "protocol.md"), "predicts x\n")
write(os.path.join(b, "experiments", "E1", "results.jsonl"), '{"source": "x"}\n')
write(os.path.join(b, "experiments", "E1", "analysis.md"), "x\n")
p = cli(d, "check", "q")
cell("I1", "check names the ignore rule and the exact add command",
     p.returncode == 0 and re.search(r"ignor", p.stdout + p.stderr, re.I)
     and "git add -f" in (p.stdout + p.stderr),
     "exit=%d, warn=%r" % (p.returncode, (p.stdout or p.stderr).strip().splitlines()[:1]))
p = cli(d, "check", "q", "--strict")
cell("I1", "check --strict refuses it", p.returncode != 0,
     "exit=%d" % p.returncode)
d2 = repo(ignore_tezgah=False)
cli(d2, "init", "q", "--question", "does x help?")
p = cli(d2, "check", "q")
cell("I1", "a tracked line passes without the ignore warning",
     p.returncode == 0 and not re.search(r"ignor", p.stdout, re.I),
     "exit=%d, out=%r" % (p.returncode, p.stdout.strip().splitlines()))

# ---------------------------------------------------------------- I2
d = repo()
b = line(d)
state(b, phase="inner", evaluation={"metric": "", "baseline": "", "locked_at": ""})
p = cli(d, "check", "q")
cell("I2", "empty evaluation at phase=inner fails", p.returncode == 1,
     "exit=%d, first=%r" % (p.returncode, p.stdout.strip().splitlines()[:1]))
state(b, phase="bootstrap")
p = cli(d, "check", "q")
cell("I2", "the same at bootstrap only warns", p.returncode == 0,
     "exit=%d" % p.returncode)
state(b, phase="inner", evaluation={"metric": "m", "baseline": "b", "locked_at": "2026-09-20"},
      sessions=[{"tag": "not-a-tag", "date": "", "what": ""}])
p = cli(d, "check", "q")
cell("I2", "a sessions entry with a bad tag fails", p.returncode == 1,
     "exit=%d, first=%r" % (p.returncode, p.stdout.strip().splitlines()[:1]))

# ---------------------------------------------------------------- I3
d = repo()
b = line(d)
p = cli(d, "claim", "q", stdin=json.dumps({
    "id": "C1", "statement": "x", "status": "supported", "provenance": "ai-executed",
    "falsification": "y", "proof": "verified by hand", "kind": "evidence"}))
cell("I3", "a proof with no path token is refused",
     p.returncode == 1 and "C1" in (p.stdout + p.stderr),
     "exit=%d, said=%r" % (p.returncode, (p.stdout + p.stderr).strip().splitlines()[:1]))
write(os.path.join(b, "experiments", "E1", "protocol.md"), "x\n")
open(os.path.join(b, "experiments", "E1", "results.jsonl"), "w").close()
write(os.path.join(b, "experiments", "E1", "analysis.md"), "x\n")
locked(b)
p = cli(d, "claim", "q", stdin=json.dumps({
    "id": "C2", "statement": "x", "status": "supported", "provenance": "ai-executed",
    "falsification": "y", "proof": "experiments/E1/results.jsonl", "kind": "evidence"}))
cell("I3", "the write path accepts a row-less evidence file (check will warn)",
     p.returncode == 0, "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
p = cli(d, "check", "q")
cell("I3", "check warns about the empty evidence file",
     p.returncode == 0 and re.search(r"holds no row|no row", said(p), re.I) is not None,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
p = cli(d, "check", "q", "--strict")
cell("I3", "check --strict refuses it", p.returncode != 0, "exit=%d" % p.returncode)

# ---------------------------------------------------------------- I4
d = repo()
b = line(d)
write(os.path.join(b, "experiments", "E1", "protocol.md"), "x\n")
write(os.path.join(b, "experiments", "E1", "results.jsonl"), '{"v": 1}\n')
write(os.path.join(b, "experiments", "E1", "analysis.md"), "x\n")
locked(b)
p = cli(d, "check", "q")
cell("I4", "a results row with no source warns (amended class)",
     p.returncode == 0 and re.search(r"source", said(p), re.I) is not None,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
p = cli(d, "check", "q", "--strict")
cell("I4", "check --strict refuses the row with no source", p.returncode != 0,
     "exit=%d" % p.returncode)
write(os.path.join(b, "experiments", "E1", "results.jsonl"), '{"source": "", "v": 1}\n')
p = cli(d, "check", "q")
cell("I4", "a source present but empty fails", p.returncode == 1,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
write(os.path.join(b, "experiments", "E1", "results.jsonl"),
      '{"source": "manual", "v": 1}\nnot json\n')
p = cli(d, "check", "q")
cell("I4", "a results file that does not parse per line fails", p.returncode == 1,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
p = cli(d, "source", "q", "E1", "--run", "abc123")
cell("I4", "source --run without orx exits 2", p.returncode == 2,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))

# ---------------------------------------------------------------- I5
d = repo()
b = line(d)
locked(b)
write(os.path.join(b, "literature", "a-note.md"), "# A\n\n- id: arxiv:1234.5678\n")
p = cli(d, "check", "q")
cell("I5", "a note without an INDEX row fails",
     p.returncode == 1 and "INDEX" in said(p),
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
write(os.path.join(b, "literature", "INDEX.jsonl"), json.dumps({
    "note": "a-note.md", "id": "arxiv:1234.5678", "class": "blog",
    "source": "x", "inclusion": "y", "verified": ["a", "b"]}) + "\n")
p = cli(d, "check", "q")
cell("I5", "a class outside the enum fails",
     p.returncode == 1 and "class" in said(p),
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
write(os.path.join(b, "literature", "INDEX.jsonl"), json.dumps({
    "note": "a-note.md", "id": "arxiv:1234.5678", "class": "grey",
    "source": "blog", "inclusion": "y", "verified": ["blog"]}) + "\n")
p = cli(d, "check", "q")
cell("I5", "grey without quality, one verifier: warns",
     p.returncode == 0 and re.search(r"quality|verified", said(p), re.I) is not None,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:2]))

# ---------------------------------------------------------------- I6
d = repo()
b = line(d)
locked(b)
state(b, phase="concluded")
p = cli(d, "check", "q")
cell("I6", "phase=concluded without review.json warns (amended class)",
     p.returncode == 0 and re.search(r"review", said(p), re.I) is not None,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
p = cli(d, "check", "q", "--strict")
cell("I6", "check --strict refuses the missing review", p.returncode != 0,
     "exit=%d" % p.returncode)
write(os.path.join(b, "to_human", "report.md"), "the numbers are 0 of 8\n")
review = {"dimensions": {k: 5 for k in ("evidence_relevance", "falsifiability",
          "scope_calibration", "argument_coherence", "exploration_integrity",
          "methodological_rigour")},
          "findings": [{"severity": "critical", "target": "to_human/report.md",
                        "quote": "0 of 8"}]}
review["dimensions"]["scope_calibration"] = 7
write(os.path.join(b, "to_human", "review.json"), json.dumps(review))
p = cli(d, "check", "q")
cell("I6", "a dimension outside 1-5 fails",
     p.returncode == 1 and "scope_calibration" in said(p),
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))
review["dimensions"]["scope_calibration"] = 4
review["findings"][0]["quote"] = "this sentence is nowhere in the target"
write(os.path.join(b, "to_human", "review.json"), json.dumps(review))
p = cli(d, "check", "q")
cell("I6", "a quote not verbatim in its target fails",
     p.returncode == 1 and re.search(r"quote|verbatim", said(p), re.I) is not None,
     "exit=%d, said=%r" % (p.returncode, said(p).strip().splitlines()[:1]))

# ---------------------------------------------------------------- I7

p = run(REPO, os.path.join(REPO, "bin", "tezgah-docs"), "research")
cell("I7", "bin/tezgah-docs research resolves to a page",
     p.returncode == 0 and "nothing matches" not in (p.stdout + p.stderr),
     "exit=%d, out=%r" % (p.returncode, (p.stdout + p.stderr).strip().splitlines()[:2]))
kind = run(REPO, os.path.join(REPO, "bin", "tezgah-context"), "kind", "tezgah-research check")
cell("I7", "the layer's own CLI classifies as the research kind",
     "research" in (kind.stdout + kind.stderr),
     "exit=%d, said=%r" % (kind.returncode, (kind.stdout + kind.stderr).strip()[:80]))
stale = []
for f in ("bin/tezgah-setup", "docs/skills.md"):
    text = open(os.path.join(REPO, f)).read()
    if "no prompt-time injection point" in text:
        stale.append(f)
cell("I7", "the two opencode statements are corrected", not stale,
     "still claiming no injection: %r" % stale)

# ---------------------------------------------------------------- I8
p = run(REPO, sys.executable, "-m", "unittest", "discover", "-s", "tests",
        "-p", "test_research.py")
cell("I8", "the research suite is green (discover form; tests/ has no __init__)",
     p.returncode == 0,
     "exit=%d, tail=%r" % (p.returncode, (p.stderr or p.stdout).strip().splitlines()[-2:]))

# ---------------------------------------------------------------- gate
p = cli(REPO, "check")
cell("gate", "check (no flags) passes all six existing lines", p.returncode == 0,
     "exit=%d, last=%r" % (p.returncode, p.stdout.strip().splitlines()[-1:]))
p = cli(REPO, "check", "--strict")
cell("gate", "check --strict refuses the unverifiable class here", p.returncode != 0,
     "exit=%d" % p.returncode)

passed = sum(1 for r in ROWS if r["pass"])
print("\n%d of %d cells passed" % (passed, len(ROWS)))
json.dump(ROWS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "raw-results.json"), "w"), indent=2)
sys.exit(0 if passed == len(ROWS) else 1)
