#!/usr/bin/env python3
"""Count the plan records that closed with an Acceptance item still open.

    python3 tests/plan_orphans.py            # the counts, exit 1 on a rise
    python3 tests/plan_orphans.py --json     # the same, as one object

The bar is the 2026-10-16 reading the lifecycle plan (108) was written from: 50
of 103 done records held an unticked `[ ]` box, and one of them - `091` - carried
no `UNMET:`. An `UNMET: <reason, who accepted it>` item is the sanctioned form
(`tezgah-task close` refuses an unticked item without one), so only the second
class is a rise: a record that closed over an item nobody accounted for. The
counts are read from the records themselves, never from a stored number.
"""
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
BASELINE = {"done": 103, "open_box": 50, "open_box_no_unmet": 1}
BOX = re.compile(r"^\s*-\s*\[ \]", re.M)
UNMET = re.compile(r"UNMET:")


def census(folder=None):
    """The counts over `.tezgah/plans/done/`, and the rows that carry a box."""
    folder = folder or os.path.join(REPO, ".tezgah", "plans", "done")
    done = sorted(glob.glob(os.path.join(folder, "*.md")))
    rows = []
    for path in done:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        boxes = len(BOX.findall(text))
        if boxes:
            rows.append({"record": os.path.basename(path), "open_box": boxes,
                         "unmet": len(UNMET.findall(text))})
    return {"done": len(done), "open_box": len(rows),
            "open_box_no_unmet": sum(1 for row in rows if not row["unmet"]),
            "records": rows}


def main(argv):
    stats = census()
    if "--json" in argv:
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        print("done records: %d; with an unticked box: %d; of those without "
              "`UNMET:`: %d" % (stats["done"], stats["open_box"],
                                stats["open_box_no_unmet"]))
        for row in stats["records"]:
            if not row["unmet"]:
                print("  no `UNMET:` - %s (%d open item(s))"
                      % (row["record"], row["open_box"]))
    if stats["open_box_no_unmet"] > BASELINE["open_box_no_unmet"]:
        print("FAIL: %d record(s) closed over an item nobody accounted for, "
              "against the %d read on 2026-10-16"
              % (stats["open_box_no_unmet"], BASELINE["open_box_no_unmet"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
