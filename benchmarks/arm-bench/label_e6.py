#!/usr/bin/env python3
"""Hand-label the ask detector's verdicts, then read the agreement back.

    python3 label_e6.py worksheet results/e6/*.jsonl --out labels.e6.tsv
    python3 label_e6.py agreement labels.e6.tsv

The detector behind `u01-ask-before-writing`'s third check cannot validate
itself, so this is the two-step every reply-graded check in this bench gets:
`worksheet` writes one TSV line per row - the detector's own verdict beside the
reply it graded, flattened to one line - with an empty `human` column, so the
labelling is done by reading replies rather than by opening JSON. `agreement`
takes that column back, prints the 2x2 it forms with the detector, observed
agreement and Cohen's kappa, and **refuses** the kappa when the sample is
single-sided: with no positive example there is no variance to explain, and a
number printed there would be read as validation of a detector whose sensitivity
was never measured (see `meta.json`'s `detector_validation`).

A row whose detector never ran carries `missing` rather than a verdict, and is
never counted as a negative: a timed-out run has no reply to label.
"""
import argparse
import csv
import glob
import json
import sys
from pathlib import Path

DETECTOR = "surfaces_the_open_dimension"
HEADER = ["task", "repeat", "arm", "detector", "human", "final_message"]
# The vocabulary the worksheet offers; anything else is unlabelable, not a guess.
ASKED, NOT_ASKED = "asked", "not_asked"
LABELS = {ASKED: True, NOT_ASKED: False}


def load(targets):
    """Every row of every target, later files winning over earlier ones."""
    rows = {}
    for target in targets:
        path = Path(target)
        if path.is_dir():
            found = sorted(path.glob("*.jsonl"))
        elif path.exists():
            found = [path]
        else:
            found = [Path(one) for one in sorted(glob.glob(target))]
        for one in found:
            if not one.is_file():
                continue
            for line in one.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                rows[(row["arm"], row["task"], row["repeat"])] = row
    return list(rows.values())


def verdict(row):
    """The check's `passed` field as a label, or `missing` when it never ran."""
    for entry in row.get("checks") or []:
        if entry.get("name") == DETECTOR:
            return ASKED if entry.get("passed") else NOT_ASKED
    return "missing"


def flatten(text):
    """One line, always: a worksheet line must survive grep and a text editor."""
    return " ".join((text or "").split())


def worksheet(args):
    rows = load(args.results)
    if not rows:
        sys.exit(f"no rows in {args.results}")
    out = Path(args.out)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        for row in sorted(rows, key=lambda r: (r["task"], r["arm"], r["repeat"])):
            writer.writerow([row["task"], row["repeat"], row["arm"], verdict(row), "",
                             flatten(row.get("final_message"))])
    missing = sum(1 for r in rows if verdict(r) == "missing")
    print(f"{out}: {len(rows)} rows to label ({missing} carry no detector verdict "
          f"because no check ran). Fill the `human` column with {ASKED} or {NOT_ASKED}, "
          f"then run: python3 label_e6.py agreement {out}")


def read_labels(path):
    """The labelled rows, and why each unlabelled one was dropped."""
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for column in ("detector", "human"):
            if column not in (reader.fieldnames or []):
                sys.exit(f"{path} has no `{column}` column: {reader.fieldnames}")
        kept, dropped = [], []
        for number, row in enumerate(reader, start=2):
            human = (row.get("human") or "").strip().lower().replace(" ", "_")
            detector = (row.get("detector") or "").strip().lower()
            if detector not in LABELS:
                dropped.append((number, f"detector={detector or 'empty'}"))
            elif human not in LABELS:
                dropped.append((number, f"human={human or 'empty'}"))
            else:
                kept.append((row, detector, human))
    if not kept:
        sys.exit(f"{path}: no line carries both a detector verdict and a human label")
    return kept, dropped


def kappa_pe(detector_asked, human_asked, n):
    """Chance agreement from the two marginals, as the README's c04 figures use."""
    p_detector = detector_asked / n
    p_human = human_asked / n
    return p_detector * p_human + (1 - p_detector) * (1 - p_human)


def agreement(args):
    kept, dropped = read_labels(args.labels)
    n = len(kept)
    true_positive = sum(1 for _, d, h in kept if d == ASKED and h == ASKED)
    false_positive = sum(1 for _, d, h in kept if d == ASKED and h == NOT_ASKED)
    false_negative = sum(1 for _, d, h in kept if d == NOT_ASKED and h == ASKED)
    true_negative = sum(1 for _, d, h in kept if d == NOT_ASKED and h == NOT_ASKED)
    observed = (true_positive + true_negative) / n
    print(f"{args.labels}: {n} labelled rows, {len(dropped)} not counted\n")
    print(f"  observed agreement {observed:.3f}")
    print(f"  true positive {true_positive}  false positive {false_positive}  "
          f"false negative {false_negative}  true negative {true_negative}")
    print(f"  detector said {ASKED} in {true_positive + false_positive}/{n}, "
          f"human said {ASKED} in {true_positive + false_negative}/{n}")
    if dropped:
        print(f"\n  not counted ({len(dropped)}): " + ", ".join(
            f"line {line} {why}" for line, why in dropped[:10]))

    sides = []
    if true_positive + false_negative == 0:
        sides.append("no reply was labelled as asking, so there is no positive sample")
    if true_negative + false_positive == 0:
        sides.append("no reply was labelled as not asking, so there is no negative sample")
    if true_positive + false_positive == 0:
        sides.append("the detector never returned a positive verdict")
    if true_positive + false_positive == n:
        sides.append("the detector never returned a negative verdict")
    if sides or kappa_pe(true_positive + false_positive, true_positive + false_negative, n) == 1.0:
        print("\n  kappa: REFUSED - " + "; ".join(sides or ["chance agreement is 1.0"]) + ".")
        print("  A kappa needs both classes present, otherwise chance agreement is 1.0 "
              "and the statistic is 0/0; printing one here would read as validation of "
              "a detector whose sensitivity no run has exercised. The observed agreement "
              "above is all this sample supports - label replies from the asking side and "
              "re-run this mode.")
        return 0
    pe = kappa_pe(true_positive + false_positive, true_positive + false_negative, n)
    print(f"  chance agreement {pe:.3f}")
    print(f"  Cohen's kappa {(observed - pe) / (1 - pe):.3f}")
    if false_positive or false_negative:
        print("\n  disagreements, to read before trusting the number:")
        for row, detector, human in kept:
            if detector != human:
                print(f"    {row.get('arm')} r{row.get('repeat')}: detector={detector} "
                      f"human={human} :: {flatten(row.get('final_message'))[:100]}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    sheet = sub.add_parser("worksheet", help="write the reply beside the detector's verdict")
    sheet.add_argument("results", nargs="+", help="result files, a directory or a glob")
    sheet.add_argument("--out", required=True, help="the TSV to label")
    sheet.set_defaults(func=worksheet)
    read = sub.add_parser("agreement", help="read the human column back and score the detector")
    read.add_argument("labels", help="a worksheet with the human column filled in")
    read.set_defaults(func=agreement)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
