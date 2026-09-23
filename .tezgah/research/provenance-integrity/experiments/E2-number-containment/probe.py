#!/usr/bin/env python3
"""E2, second pass: the containment rule measured with the tokenizer it ships with.

The first pass used a loose `\\d+`, which counted a metric name (`p95`) as an
asserted number and so inflated the miss rate. This pass calls the checker's own
`NUMBER` and `_artifact_text` - the rule under measurement, not a copy of it - so
the number below is what the rule does, not what a probe did.

Appends rows labelled `pass: refined-tokenizer` to the experiment's results.jsonl.
"""
import json
import os
import sys

REPO = "/Users/rizax/Projects/tezgah"
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_research as tr  # noqa: E402

RESULT = os.path.join(REPO, ".tezgah/research/provenance-integrity/experiments/"
                             "E2-number-containment/results.jsonl")
rows, numeric, full = [], 0, 0
for line_dir in sorted(__import__("glob").glob(os.path.join(REPO, ".tezgah", "research", "*"))):
    if not os.path.isdir(line_dir):
        continue
    slug = os.path.basename(line_dir)
    for claim in tr._row_objects(os.path.join(line_dir, "claims.jsonl")):
        tokens = sorted(set(tr.NUMBER.findall(str(claim.get("statement", "")))))
        if not tokens or not claim.get("proof"):
            continue
        text = tr._artifact_text(claim["proof"], line_dir, REPO)
        if not text:
            continue
        numeric += 1
        missing = [t for t in tokens if t not in text]
        if not missing:
            full += 1
        rows.append({"experiment": "E2-number-containment", "pass": "refined-tokenizer",
                     "line": slug, "claim": claim.get("id"), "tokens": len(tokens),
                     "contained": len(tokens) - len(missing), "missing": missing[:4],
                     "verdict": "contained" if not missing else "missing",
                     "source": "the checker's own NUMBER and _artifact_text, over claims.jsonl",
                     "command": "python3 /tmp/hh-containment-refined.py", "scope": "real"})
rows.append({"experiment": "E2-number-containment", "pass": "refined-tokenizer",
             "totals": True, "numeric_claims": numeric, "fully_contained": full,
             "share_pct": "{:.0f}".format(100.0 * full / numeric) if numeric else "n/a",
             "source": "the checker's own NUMBER and _artifact_text, over claims.jsonl",
             "command": "python3 /tmp/hh-containment-refined.py", "scope": "real"})
with open(RESULT, "a") as fh:
    for row in rows:
        fh.write(json.dumps(row) + "\n")
print(json.dumps({k: v for k, v in rows[-1].items() if k != "source"}))
