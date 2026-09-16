#!/usr/bin/env python3
"""Rewrite the status table in <git root>/plans/README.md from plans/open/*.md.
Usage: python3 render_table.py [--pr-info 'NNN=text' ...]  (extra text appended to the pr cell)
Creates plans/README.md, or appends the marker block to it, when either is missing."""
import glob, os, re, subprocess, sys
root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
extra = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)  # --pr-info flags carry no "="
cell = lambda v: str(v).replace("|", "\\|")  # a pr state or title with a pipe would fork the row
rows = []
for p in sorted(glob.glob(os.path.join(root, "plans/open/*.md"))):
    t = open(p).read(); fm = t.split("---", 2)[1]
    g = lambda k: (re.search(r"^%s:[ \t]*(.*)$" % k, fm, re.M) or [None, ""])[1].strip()
    tail = t.split("## Next", 1)[1] if "## Next" in t else ""
    nxt = (tail.strip().splitlines() or [""])[0].replace("`", "")[:60]
    pr = g("pr"); pr = ("#" + pr if pr else "") + (" " + extra[g("id")] if g("id") in extra else "")
    rows.append("| %s |" % " | ".join(cell(x) for x in
                (g("id"), g("title"), g("status"), g("branch"), pr, nxt)))
readme = os.path.join(root, "plans/README.md")
head = "<!-- status:start -->\n| id | title | status | branch | pr | next |\n|---|---|---|---|---|---|\n"
try:
    r = open(readme).read()
except FileNotFoundError:
    r = "# Plans\n\n<!-- status:start -->\n<!-- status:end -->\n"
if "<!-- status:start -->" not in r:
    r = r.rstrip("\n") + "\n\n<!-- status:start -->\n<!-- status:end -->\n"
new = re.sub(r"<!-- status:start -->.*?<!-- status:end -->", lambda m: head + "\n".join(rows) + ("\n" if rows else "") + "<!-- status:end -->", r, flags=re.S)
os.makedirs(os.path.dirname(readme), exist_ok=True)
open(readme, "w").write(new); print("\n".join(rows))
