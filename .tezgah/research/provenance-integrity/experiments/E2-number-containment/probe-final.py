#!/usr/bin/env python3
"""E2, third pass: the containment rule as it finally ships.

The first pass measured a probe that walked whole directories with a loose
tokenizer; the second measured the rule then in the tree. This pass calls the
checker's own helpers - NUMBER and _comparable (the rule's own statement reading), ISO_DATE, _artifact_text,
_beyond_window - over every line's claims, so the share below is what the shipped
rule does after the six refinements another session made against real artifacts.

Appends rows labelled `pass: final-rule` to the experiment's results.jsonl.
"""
import glob
import json
import os
import sys

REPO = "/Users/rizax/Projects/tezgah"
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_research as tr  # noqa: E402

RESULT = os.path.join(REPO, ".tezgah/research/provenance-integrity/experiments/"
                             "E2-number-containment/results.jsonl")
rows, contained = [], 0
for line_dir in sorted(glob.glob(os.path.join(REPO, ".tezgah", "research", "*"))):
    if not os.path.isdir(line_dir):
        continue
    slug = os.path.basename(line_dir)
    for claim in tr._row_objects(os.path.join(line_dir, "claims.jsonl")):
        if not claim.get("proof"):
            continue
        tokens = sorted(set(tr._numbers(tr._comparable(str(claim.get("statement", ""))))))
        if not tokens:
            continue
        text = tr._comparable(tr._artifact_text(claim["proof"], line_dir, REPO))
        if not text:
            continue
        missing = [t for t in tokens if t not in text]
        if missing:
            found = tr._beyond_window(missing, claim["proof"], line_dir, REPO)
            missing = [t for t in missing if t not in found]
        if not missing:
            contained += 1
        rows.append({"experiment": "E2-number-containment", "pass": "final-rule",
                     "line": slug, "claim": claim.get("id"), "tokens": len(tokens),
                     "contained": len(tokens) - len(missing), "missing": missing[:4],
                     "verdict": "contained" if not missing else "missing",
                     "source": "the checker's own NUMBER/THOUSANDS/ISO_DATE/_artifact_text/_beyond_window over claims.jsonl",
                     "command": "python3 .tezgah/research/provenance-integrity/experiments/E2-number-containment/probe-final.py",
                     "scope": "real"})
rows.append({"experiment": "E2-number-containment", "pass": "final-rule",
             "totals": True, "numeric_claims": len(rows), "fully_contained": contained,
             "share_pct": "{:.0f}".format(100.0 * contained / len(rows)) if rows else "n/a",
             "source": "the checker's own NUMBER/THOUSANDS/ISO_DATE/_artifact_text/_beyond_window over claims.jsonl",
             "command": "python3 .tezgah/research/provenance-integrity/experiments/E2-number-containment/probe-final.py",
             "scope": "real"})
with open(RESULT, "a") as fh:
    for row in rows:
        fh.write(json.dumps(row) + "\n")
print(json.dumps(rows[-1]))
