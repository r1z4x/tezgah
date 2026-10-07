#!/usr/bin/env python3
"""Plan 067's measure: the Stop rule's claim reader (`tezgah_integrity.claims`)
against hand labels.

    python3 tests/claim_reader_eval.py --set e4        # dev: plan 062's 60 E4 labels
    python3 tests/claim_reader_eval.py --set heldout   # the blind held-out sample

A row is read as a claim when `any(claims(text))`, the reading plan 062's
`false_done` used. Precision and recall are on `claims_done` rows. A borderline
row is counted both ways: once as `claims_done`, once as `honest`; under
`as labelled` an E4 borderline keeps its written label and a held-out row the
raters split on is left out. The sets live in the gitignored workspace
(`.tezgah/`), so a checkout without it reports that and exits 2.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
import tezgah_integrity as ti  # noqa: E402

LIVE = "/Users/rizax/Projects/tezgah/.tezgah"
DIR = os.path.join(LIVE, "analysis", "claim-reader-heldout-2026-10")
E4 = os.path.join(LIVE, "research", "done", "paired-outcome-arm", "experiments",
                  "E4-falsedone-labels")


def _jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def e4_rows():
    """(id, text, label, borderline): dev.jsonl's text, E4's labels and flags."""
    text = {r["id"]: r["text"] for r in _jsonl(os.path.join(DIR, "dev.jsonl"))}
    return [(r["id"], text[r["id"]], r["label"], bool(r["borderline"]))
            for r in _jsonl(os.path.join(E4, "results.jsonl"))]


def heldout_rows():
    """blind.jsonl's text joined with labels.jsonl; `borderline` = raters split."""
    text = {r["id"]: r["text"] for r in _jsonl(os.path.join(DIR, "blind.jsonl"))}
    return [(r["id"], text[r["id"]], r["label"], r["label"] == "borderline")
            for r in _jsonl(os.path.join(DIR, "labels.jsonl"))]


def score(rows, mode):
    tp = fp = fn = 0
    for _id, text, label, borderline in rows:
        if borderline and mode != "as labelled":
            label = mode
        if label == "borderline":
            continue
        said = any(ti.claims(text))
        tp += said and label == "claims_done"
        fp += said and label != "claims_done"
        fn += not said and label == "claims_done"
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return dict(mode=mode, flagged=tp + fp, claims_done=tp + fn, tp=tp,
                precision=round(p, 3), recall=round(r, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("e4", "heldout"), required=True)
    args = ap.parse_args()
    try:
        rows = e4_rows() if args.set == "e4" else heldout_rows()
    except OSError as exc:
        print("set unavailable: %s" % exc)
        return 2
    print("rows: %d, borderline: %d" % (len(rows), sum(r[3] for r in rows)))
    for mode in ("as labelled", "claims_done", "honest"):
        print(json.dumps(score(rows, mode)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
