#!/usr/bin/env python3
"""E3: the census that decides whether the closure is a result or a report.

Counts, per line, the rows that declare no scope and the fixture rows that do not
name what was generated - the two things this line opened - and the containment
rule's final share, then writes the experiment's results.jsonl.
"""
import glob
import json
import os
import sys

REPO = "/Users/rizax/Projects/tezgah"
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_research as tr  # noqa: E402

RESULT = os.path.join(REPO, ".tezgah/research/provenance-integrity/experiments/"
                             "E3-debt-closure/results.jsonl")
SRC = "every .tezgah/research/*/experiments/*/results.jsonl and claims.jsonl, read with the checker's own helpers"
CMD = "python3 .tezgah/research/provenance-integrity/experiments/E3-debt-closure/probe.py"

rows = []
total = {"rows": 0, "unscoped": 0, "fixture": 0, "fixture_without_description": 0,
         "claims": 0, "contained": 0}
for line_dir in sorted(glob.glob(os.path.join(REPO, ".tezgah", "research", "*"))):
    if not os.path.isdir(line_dir):
        continue
    slug = os.path.basename(line_dir)
    got = {"rows": 0, "unscoped": 0, "fixture": 0, "fixture_without_description": 0,
           "claims": 0, "contained": 0}
    for path in glob.glob(os.path.join(line_dir, "experiments", "*", "results.jsonl")):
        for row in tr._row_objects(path):
            got["rows"] += 1
            scope = row.get("scope")
            if not isinstance(scope, str) or not scope.strip():
                got["unscoped"] += 1
            elif scope == "fixture":
                got["fixture"] += 1
                if not str(row.get("fixture", "")).strip():
                    got["fixture_without_description"] += 1
    for claim in tr._row_objects(os.path.join(line_dir, "claims.jsonl")):
        if not claim.get("proof"):
            continue
        tokens = sorted(set(tr._numbers(tr._comparable(str(claim.get("statement", ""))))))
        if not tokens:
            continue
        text = tr._comparable(tr._artifact_text(claim["proof"], line_dir, REPO))
        if not text:
            continue
        got["claims"] += 1
        missing = [t for t in tokens if t not in text]
        if missing:
            found = tr._beyond_window(missing, claim["proof"], line_dir, REPO)
            missing = [t for t in missing if t not in found]
        if not missing:
            got["contained"] += 1
    rows.append({"experiment": "E3-debt-closure", "line": slug, **got,
                 "source": SRC, "command": CMD, "scope": "real"})
    for k in total:
        total[k] += got[k]
rows.append({"experiment": "E3-debt-closure", "totals": True, **total,
             "source": SRC, "command": CMD, "scope": "real"})
with open(RESULT, "w") as fh:
    for row in rows:
        fh.write(json.dumps(row) + "\n")
print(json.dumps(rows[-1]))
