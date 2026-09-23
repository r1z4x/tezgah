#!/usr/bin/env python3
"""E1/E2 probe: audit every research line for fixture data presented as real.

E1 classifies each results row's input scope from the row's own fields and flags
claims whose wording asserts a property of the running system while every row in
their proof is fixture-scoped. E2 measures whether the numbers a claim asserts
appear in the artifact it cites.

Usage: python3 hh-provenance-audit.py [--root <repo>]
Prints one JSON object per (claim) plus per-line totals, on stdout.
"""
import glob
import json
import os
import re
import sys

REPO = "/Users/rizax/Projects/tezgah"
if "--root" in sys.argv:
    REPO = sys.argv[sys.argv.index("--root") + 1]
LINES = os.path.join(REPO, ".tezgah", "research")

# One stated rule, as the protocol says: the row's own fields decide its scope.
FIXTURE = re.compile(r"tmp|/T/|tempfile|fixture|synthetic|probe|tests/|_probe", re.I)
REAL = re.compile(r"~/.cache/tezgah/evidence|\.tezgah/research|/Users/rizax/Projects/tezgah"
                  r"|openrouter|consult|money|corpus|ledger fold", re.I)
DERIVED = re.compile(r"derived|fold|table", re.I)
REAL_WORDS = re.compile(r"\b(the machine|a session|this machine|the gate|a host|every session"
                        r"|this repository|the corpus|per call|per tool call)\b", re.I)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def row_scope(row):
    text = " ".join(str(row.get(k, "")) for k in ("command", "source", "note", "call"))
    if DERIVED.search(text) and not FIXTURE.search(text):
        return "derived"
    if FIXTURE.search(text):
        return "fixture"
    if REAL.search(text):
        return "real"
    return "unknown"


def rows_of(path):
    out = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def resolve(line_dir, ref):
    """A proof ref is line-relative or repository-relative (the CLI accepts both).

    Bounded on purpose: a ref that resolves to a directory is walked only a few
    levels deep, keeps at most 200 files and never enters `.git`, a cache or a
    virtualenv - an unbounded walk here is how this probe hung on its first run."""
    for cand in (os.path.join(line_dir, ref), os.path.join(REPO, ref)):
        if os.path.isfile(cand):
            return [cand]
        if os.path.isdir(cand):
            out = []
            for root, dirs, files in os.walk(cand):
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")
                           and not d.startswith(".")]
                if root[len(cand):].count(os.sep) > 3:
                    dirs[:] = []
                    continue
                out += [os.path.join(root, f) for f in files]
                if len(out) > 200:
                    return out[:200]
            return out
    return []


def proof_text(files):
    out = []
    for f in files:
        if os.path.isfile(f) and os.path.getsize(f) < 2_000_000:
            try:
                out.append(open(f, errors="replace").read())
            except OSError:
                pass
    return "\n".join(out)


totals = {"lines": 0, "rows": 0, "claims": 0, "flagged": 0, "scopes": {}}
for line_dir in sorted(glob.glob(os.path.join(LINES, "*"))):
    if not os.path.isdir(line_dir):
        continue
    slug = os.path.basename(line_dir)
    totals["lines"] += 1
    row_scopes = {}
    for path in glob.glob(os.path.join(line_dir, "experiments", "*", "results.jsonl")):
        rows = rows_of(path)
        scopes = [row_scope(r) for r in rows]
        totals["rows"] += len(rows)
        for s in scopes:
            totals["scopes"][s] = totals["scopes"].get(s, 0) + 1
        row_scopes[os.path.relpath(path, line_dir)] = scopes
    claims_path = os.path.join(line_dir, "claims.jsonl")
    if not os.path.exists(claims_path):
        continue
    for claim in rows_of(claims_path):
        totals["claims"] += 1
        files, scopes = [], []
        for ref in claim.get("proof") or []:
            got = resolve(line_dir, ref)
            files += got
            for f in got:
                scopes.append(row_scope({"source": f}))
        text = proof_text(files)
        statement = str(claim.get("statement", ""))
        tokens = sorted(set(NUMBER.findall(statement)))
        contained = [t for t in tokens if t in text]
        missing = [t for t in tokens if t not in text]
        fixture_only = bool(scopes) and all(s == "fixture" for s in scopes)
        flagged = bool(fixture_only and REAL_WORDS.search(statement))
        if flagged:
            totals["flagged"] += 1
        print(json.dumps({
            "experiment": "E1-scope-audit", "line": slug, "claim": claim.get("id"),
            "proofs": claim.get("proof"), "scopes": sorted(set(scopes)),
            "flagged_fixture_as_real": flagged,
            "why": "every proof row is fixture-scoped while the statement names the running system"
                   if flagged else "",
            "e2_tokens": len(tokens), "e2_contained": len(contained), "e2_missing": missing[:4],
            "source": "python3 /tmp/hh-provenance-audit.py",
            "command": "python3 /tmp/hh-provenance-audit.py",
        }))
print(json.dumps({"experiment": "E1-scope-audit", "totals": True, **totals,
                  "source": "python3 /tmp/hh-provenance-audit.py",
                  "command": "python3 /tmp/hh-provenance-audit.py"}))
