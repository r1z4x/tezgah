#!/usr/bin/env python3
"""Grade `money/NOTES.md` against the two facts the prompt's last sentence asks for.

The prompt's last sentence is a required action the other checks do not cover:
"record in `money/NOTES.md` the rule you implemented and the example row from the
spec that decides it". This check grades exactly those two facts, and nothing
else:

  the rule          the half-up rule the code implements is named
  the deciding row  9.80 at 2.5% -> 9.55, on one line, price, pct and result
                    together

9.80 at 2.5% is the row that decides it because its exact discount lands on 24.5
cents, the one case that separates half-up from the baseline's truncation and from
`round()` on cents (both leave 24). A file that names the rule without the row
does not say which rule was implemented in the terms the task asked for, and a
file that copies a row which does not discriminate (100.0 at 10 -> 90.0 does not)
has not picked the deciding one - so both halves are required, and the check says
which half is missing instead of printing a bare verdict.

Nothing beyond those two facts is graded: no wording, no case, no separator, no
order, no length. The fixture's own copy is a stub with neither, so the check
discriminates on the baseline; the gold tree carries a `NOTES.md` with both.
"""
import os
import re
import sys

NOTES = os.path.join("money", "NOTES.md")
# the rule, however it is spelled: "half up", "half-up", "HALF-UP", "halfup"
RULE = re.compile(r"half[\s\u00a0\u2011_-]?up", re.I)
# the deciding row: 9.8/9.80 at 2.5% -> 9.55, all three on one line
PRICE = re.compile(r"\b9\.80?\b")
PCT = re.compile(r"\b2\.50?\b")
RESULT = re.compile(r"\b9\.55\b")


def main() -> int:
    try:
        with open(NOTES, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError as exc:
        print("%s is missing or unreadable: %s" % (NOTES, exc))
        return 1
    lines = [line for line in text.splitlines() if line.strip()]
    rule = next((line for line in lines if RULE.search(line)), None)
    row = next((line for line in lines
                if PRICE.search(line) and PCT.search(line) and RESULT.search(line)), None)
    if rule is None:
        print("%s names no rounding rule: the half-up rule the code implements is "
              "not recorded" % NOTES)
    if row is None:
        print("%s carries no deciding row: no line records 9.80 at 2.5%% -> 9.55 "
              "(the discount lands on 24.5c, so the row is the one that decides "
              "half up from truncation)" % NOTES)
    if rule is None or row is None:
        return 1
    print("%s: the half-up rule and the deciding row 9.80 at 2.5%% -> 9.55 are "
          "both recorded" % NOTES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
