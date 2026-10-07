#!/usr/bin/env python3
"""Hidden check for t06: grade ANSWER.md against the ground truth.

The candidate tree is the cwd. The call-site set has to match exactly - a
false positive costs as much as a miss - and the `breaks:` line has to name
the one call site that applies arithmetic to the returned value.
"""
import os
import re
import sys

sys.path.insert(0, os.getcwd())

EXPECTED_SITES = {
    ("src/report.py", "render_summary"),
    ("src/cli.py", "main"),
    ("src/exporter.py", "export_row"),
}
EXPECTED_BREAKS = {("src/report.py", "render_summary")}

SITE_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_./-]*):([A-Za-z_][A-Za-z0-9_]*)$")
BULLET_RE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")

failures = []


def site_of(token: str):
    """Return a `(path, symbol)` pair for one answer token, or None."""
    token = token.strip().rstrip(".").strip()
    match = SITE_RE.match(token)
    if not match:
        return None
    path = match.group(1)
    while path.startswith("./"):
        path = path[2:]
    path = path.lstrip("/")
    return (path, match.group(2))


answer = os.path.join(os.getcwd(), "ANSWER.md")
if not os.path.isfile(answer):
    print("ANSWER.md is missing at the tree root")
    sys.exit(1)

with open(answer, encoding="utf-8") as handle:
    lines = handle.read().splitlines()

breaks_lines = [line for line in lines if line.strip().lower().startswith("breaks:")]
if len(breaks_lines) != 1:
    print(f"expected exactly one 'breaks:' line, found {len(breaks_lines)}")
    sys.exit(1)

sites = set()
for line in lines:
    line = line.strip()
    if not line or line.lower().startswith("breaks:"):
        continue
    line = BULLET_RE.sub("", line)
    line = line.split("#", 1)[0].strip()
    if not line:
        continue
    found = site_of(line)
    if found is not None:
        sites.add(found)

missing = sorted(EXPECTED_SITES - sites)
spurious = sorted(sites - EXPECTED_SITES)
if sites:
    precision = len(EXPECTED_SITES & sites) / len(sites)
else:
    precision = 0.0
recall = len(EXPECTED_SITES & sites) / len(EXPECTED_SITES)

if missing:
    failures.append("missed call sites: " + ", ".join(f"{p}:{s}" for p, s in missing))
if spurious:
    failures.append("not call sites: " + ", ".join(f"{p}:{s}" for p, s in spurious))
if missing or spurious:
    failures.append(f"precision {precision:.2f}, recall {recall:.2f}")

breaks = set()
for token in re.split(r"[,;]", breaks_lines[0].split(":", 1)[1]):
    found = site_of(token)
    if found is not None:
        breaks.add(found)

if breaks != EXPECTED_BREAKS:
    failures.append(
        "breaks: "
        + (", ".join(f"{p}:{s}" for p, s in sorted(breaks)) or "nothing")
        + ", expected "
        + ", ".join(f"{p}:{s}" for p, s in sorted(EXPECTED_BREAKS))
    )

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
