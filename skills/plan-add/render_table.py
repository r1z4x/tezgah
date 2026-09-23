#!/usr/bin/env python3
"""Rewrite the status table in <git root>/.tezgah/plans/README.md from .tezgah/plans/open/*.md.
Usage: python3 render_table.py [--pr-info 'NNN=text' ...]  (extra text appended to the pr cell)
       python3 render_table.py --acceptance  (the acceptance items that name no
       command, with the counts it read; a report, not a gate - always exit 0)
       python3 render_table.py --acceptance --strict  (the same report, and exit 1
       when an item still under .tezgah/plans/open names no command either)
Creates .tezgah/plans/README.md, or appends the marker block to it, when either is missing."""
import glob, os, re, subprocess, sys
# The one reader of a plan file lives in the module that owns the record, so the
# table and the acceptance report cannot disagree about what a plan says. Three
# dirnames up from skills/plan-add/render_table.py is the tree that holds hooks/,
# which is where the checkout and the installed plugin copy both put it.
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(HERE, "hooks"))
import tezgah_task as tt  # noqa: E402
root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()


def acceptance(strict):
    """The acceptance items that name no command, over this repository's own
    plans - `.tezgah/plans/open` and `.tezgah/plans/done`. It prints `plan:line`, the item and
    the counts it read, and judges nothing: a done plan is a historical record,
    so its rows stay a report whatever they say (exit 0).

    `--strict` adds the one gate this reader has: an item still under
    `.tezgah/plans/open` is work in flight, so one that names neither the command that
    proves it nor an `unverifiable` declaration is a defect - it is printed and
    the exit code is 1. Returns whether it refused."""
    report = tt.acceptance_report(root)
    for item in report["items"]:
        where = "%s:%d" % (item["plan"], item["line"])
        if item["state"] == "unverifiable":
            print("%s  unverifiable: %s" % (where, item["reason"]))
        elif item["state"] == "missing":
            print("%s  no command: %s" % (where, item["text"]))
    count = lambda state: sum(1 for i in report["items"] if i["state"] == state)
    print("plans: %d read, acceptance items: %d read; %d name no command, %d declared unverifiable"
          % (report["plans"], len(report["items"]), count("missing"), count("unverifiable")))
    open_missing = [i for i in report["items"]
                    if i["state"] == "missing" and i["plan"].startswith(".tezgah/plans/open/")]
    if strict and open_missing:
        print("strict: %d item(s) under .tezgah/plans/open name no command and declare no "
              "unverifiable; a done plan is reported, never gated" % len(open_missing))
    return bool(strict and open_missing)


if "--acceptance" in sys.argv[1:]:
    refused = acceptance("--strict" in sys.argv[1:])
    sys.exit(1 if refused else 0)

extra = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)  # --pr-info flags carry no "="
cell = lambda v: str(v).replace("|", "\\|")  # a pr state or title with a pipe would fork the row
rows = []
for p in sorted(glob.glob(os.path.join(root, ".tezgah/plans/open/*.md"))):
    t = open(p, encoding="utf-8").read(); g = tt.frontmatter(t).get
    nxt = next((line for _, line in tt.section_lines(t, "Next") if line.strip()), "")
    nxt = nxt.replace("`", "")[:60]
    pr = g("pr", ""); pr = ("#" + pr if pr else "") + (" " + extra[g("id", "")] if g("id", "") in extra else "")
    rows.append("| %s |" % " | ".join(cell(x) for x in
                (g("id", ""), g("title", ""), g("status", ""), g("branch", ""), pr, nxt)))
readme = os.path.join(root, ".tezgah/plans/README.md")
head = "<!-- status:start -->\n| id | title | status | branch | pr | next |\n|---|---|---|---|---|---|\n"
try:
    r = open(readme, encoding="utf-8").read()
except FileNotFoundError:
    r = "# Plans\n\n<!-- status:start -->\n<!-- status:end -->\n"
if "<!-- status:start -->" not in r:
    r = r.rstrip("\n") + "\n\n<!-- status:start -->\n<!-- status:end -->\n"
new = re.sub(r"<!-- status:start -->.*?<!-- status:end -->", lambda m: head + "\n".join(rows) + ("\n" if rows else "") + "<!-- status:end -->", r, flags=re.S)
os.makedirs(os.path.dirname(readme), exist_ok=True)
open(readme, "w", encoding="utf-8").write(new); print("\n".join(rows))
