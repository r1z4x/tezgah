# E6 — do `explorer` and `order` refuse when their own shape is issued?

## The change under measurement
None. This drives the shipped gate (`hooks/tezgah_gate.decision`) in a throwaway
HOME and root and issues each rule's own shape.

## Why this experiment exists
E2/E2b folded every ledger on this machine and found two of the gate's thirteen
deny labels with zero rows: `explorer` (`EXPLORE_DENY`, `hooks/tezgah_gate.py:409`)
and `order` (`ORDER_DENY`, `hooks/tezgah_gate.py:1426`), in 1613 ledgers holding
556 refusals over six days. The report read that as three fine outcomes -
reachable and useful, reachable and useless, unreachable - and then withdrew
"record as unreachable": a zero count cannot separate "the traffic never offered
this shape" from "the rule cannot match". The report's own acceptance names the
next step: a probe that issues the shape and either produces a refusal or records
the shape's absence.

## What it predicts
The report's reading of the two zero counts is that each rule may be unreachable
- its text and code sit on the hot path and have never produced a deny row. A
second opinion withdrew that reading as unprovable from a count and left the
question undecided. This probe tests the half of the reading a run can decide:
**each rule refuses when the shape it matches is issued deliberately.**

1. `explorer`: a subagent call whose `subagent_type` is `explore` or `explorer`
   is refused with `EXPLORE_DENY`, and a `deny` row labelled `explorer` lands in
   the ledger.
2. `order`: a `git commit` in a session whose newest ledger check failed is
   refused with `ORDER_DENY` naming that check, and a `deny` row labelled `order`
   lands. The same commit in a session whose newest check passed, or which ran no
   check at all, passes - the rule is a commit-over-a-failing-check rule and not
   a commit rule.

## What would falsify it
- A shape above returns None while the control - the `shortcut` rule on a
  `--no-verify` commit under the same throwaway environment - returns a refusal.
  That would leave the rule unreachable for the shape issued.
- The control itself returns None. Every row is then void: the probe never
  reached the gate, so the run says nothing about either rule.
- A shape refuses but leaves no `deny` row under its label, which would keep the
  E2 fold counting it zero even after it fires.

## What this cannot show
That either rule is unreachable. The probe enumerates shapes; a None means only
that no shape listed here triggers the label, never that none could.

## Method
- A throwaway HOME and a `Projects` root inside it, set in the environment
  before `hooks/tezgah_paths.py` is imported, so the ledger this probe writes
  lives under a temp dir and the user's own state is untouched.
- Import the shipped `hooks/tezgah_gate.py` from the checkout and call
  `decision(tool, input, cwd, session_id)` for each case.
- Seed the state `order` reads through `hooks/tezgah_integrity.note_tool`, the
  same writer a host's PostToolUse hook uses: a `verify_fail` row (the fold's
  `fail`) for the refusal case, a `verify_ok` row (the fold's `ok`) for the
  passed-check negative, nothing for the no-check negative.
- After each case, read the session ledger back and record the label on the
  newest `deny` row, so the row shows the label E2's fold counts and not only the
  reason text.
- Record one `results.jsonl` object per case from the observed return value, plus
  one control that refuses under the same environment, plus a totals row.

## Reported rows
One object per case: `rule`, `case`, `shape`, `expect_refusal`, `refused`,
`reason`, `reason_label` (from the ledger), `check` (what was seeded), `session`,
`source`, `command`. Plus one totals row.
