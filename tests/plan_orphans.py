#!/usr/bin/env python3
"""Count the plan records that closed with an Acceptance item still open.

    python3 tests/plan_orphans.py            # the counts, exit 1 on a rise
    python3 tests/plan_orphans.py --json     # the same, as one object

The historical reading counted every record in done/, including discarded 091,
and boxes outside Acceptance. Count only status: done now, using the same
per-item predicate as `tezgah-task close`: each unticked Acceptance item needs
its own `UNMET: <reason>`. Discarded records legitimately skip this check, so
the unaccounted-item baseline is zero. Counts come from the records themselves.
"""
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_task as tt  # noqa: E402

BASELINE = {"open_box_no_unmet": 0}


def census(folder=None):
    """Counts over status: done records, and their unticked Acceptance items."""
    folder = folder or os.path.join(REPO, ".tezgah", "plans", "done")
    done = 0
    rows = []
    for path in sorted(glob.glob(os.path.join(folder, "*.md"))):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if tt.frontmatter(text).get("status") != "done":
            continue
        done += 1
        boxes = sum(not item["checked"] for item in tt.acceptance_items(text))
        unaccounted = len(tt.open_items(text))
        if boxes:
            rows.append({"record": os.path.basename(path), "open_box": boxes,
                         "unmet": boxes - unaccounted, "unaccounted": unaccounted})
    return {"done": done, "open_box": len(rows),
            "open_box_no_unmet": sum(bool(row["unaccounted"]) for row in rows),
            "records": rows}


def main(argv):
    stats = census()
    if "--json" in argv:
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        print("done records: %d; with an unticked Acceptance box: %d; with an "
              "unaccounted item: %d" % (stats["done"], stats["open_box"],
                                       stats["open_box_no_unmet"]))
        for row in stats["records"]:
            if row["unaccounted"]:
                print("  unaccounted - %s (%d of %d open item(s))"
                      % (row["record"], row["unaccounted"], row["open_box"]))
    if stats["open_box_no_unmet"] > BASELINE["open_box_no_unmet"]:
        print("FAIL: %d record(s) closed over an item nobody accounted for, "
              "against the %d read on 2026-10-16"
              % (stats["open_box_no_unmet"], BASELINE["open_box_no_unmet"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
