# E1 analysis — the scope audit, and why its method is the finding

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | ≥1 claim asserts a system property while every proof artifact is fixture-scoped | **1 flagged** (`harness-hardening` C15) — and the flag came from the directory name `E6-rule-reach-probe` containing "probe", not from the data | **holds by accident, not by measurement** |
| 2 | no control reads a row's input scope | neither the Stop rule nor the research checker has a scope field or a rule | **holds** |
| 3 | most rows are real-corpus rows | **438 of 520 rows are `unknown`** (79 fixture, 3 real) | **missed** |

## What the audit actually establishes
- **Scope cannot be inferred from a row's own text.** The classifier keyed on
  `command`/`source`/`note`, and 84% of rows carry no path at all ("ledger fold",
  `python3 /tmp/hh-rules.py`), so the `real` count of 3 is an artifact of the rule,
  not a property of the corpus. Any control built on this inference would be a
  guess wearing a check's clothes - the exact failure the gate's own comment names
  for the semantic seat.
- **The class is present in this repository's own artifacts, and nothing records
  it.** `harness-hardening`'s E1 rows were produced against a **synthetic** root:
  `protocol.md` says so ("a temp HOME, a generated repo of 40 files, a fabricated
  `lessons.md`"), and the row's own `command` is `python3 /tmp/hh-budget.py`. The
  line's report then states "9150 B of 12000" as what a session is injected. No
  field on the row, on the claim, or in the report says *fixture*; a reader who
  opens the report alone cannot tell the number came from a generated repository.
- **The audit cannot clear anything either.** Its power is too low to acquit: a
  fixture-run number presented as real is invisible to it unless the directory
  happens to be named "probe". What it convicts is the *method* - which is the
  finding that shapes the control: the scope must be **recorded by the producer**,
  not recovered by a reader.

## What it does not show
- Whether other lines have the same defect. `research-layer-audit` and
  `infra-candidates` were written from real corpora as far as their artifacts say,
  but "as far as their artifacts say" is exactly the thing this audit cannot
  verify.
- Any count of the failure class. One flag, produced by a name, is not a rate.

## Reproducing this

The probe is stored beside these results as `probe.py`; the rows' `command` field
names the throwaway path it was run from, which is what ran and is left as
recorded. Re-running it from this directory prints the same rows.
