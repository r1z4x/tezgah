# E1 — the scope audit: fixture numbers presented as real ones

## The change under measurement
None. This audits the repository's own research lines for the failure class the
user named: **data produced by a fixture, a stand-in or a synthetic input, and
then presented as a property of the running system.**

## Why this line exists, stated honestly
The accusation is concrete and it is about a pattern, not one incident: a demo on
fabricated data was presented as progress, and the layer permitted it. This
repository's own recent work is the corpus, and the audit starts with the line
this session wrote: `harness-hardening`'s E1 rows were produced against a
**synthetic** root (a temp HOME, a generated repo of 40 files, a fabricated
`lessons.md`), while its report presents 9150 B of 12000 as what a session pays
at `session_start`. That sentence may be true of the real system too - but the
measurement does not show it, and nothing in the layer says so.

## What it predicts
1. **At least one claim in this repository asserts a property of the running
   system while every artifact in its proof is fixture-scoped** (predicted: C01 of
   `harness-hardening`, whose proof is a synthetic-root row).
2. **No existing control reads a row's input scope**: neither the Stop rule
   (`hooks/tezgah_integrity.py`) nor the research checker
   (`hooks/tezgah_research.py`) has a field, a rule or a refusal that separates a
   fixture row from a real one.
3. **The majority of rows across the lines are real-corpus** (files under
   `~/.cache/tezgah/evidence`, the repository itself) rather than fixture rows, so
   the class is rare in count but decisive where it lands.

## Falsification
This reading is wrong if (a) every claim's proof rows are in the same scope as
the claim's own wording, or (b) some control already refuses a fixture-scoped
artifact presented as a real one - named with its `path:line`.

## Method
- Enumerate every `results.jsonl` under `.tezgah/research/*/experiments/*/`.
- Classify each row's scope from its own fields by one stated rule:
  `fixture` when the row's `command`, `source` or `note` names a temporary
  directory, `fixture`, `probe`, `synthetic` or a `tests/` path; `real` when it
  names the machine's own ledger corpus, the repository's files or a paid run;
  `derived` when it names a file another row produced; `unknown` otherwise.
- For every claim in every line, resolve its `proof` entries, take the scopes of
  the rows they contain, and flag a claim whose statement uses real-system
  vocabulary (`the machine`, `a session`, `the gate`, `this repository`) while
  every proof row is `fixture`-scoped.
- Report the counts, with the flagged claims named.

## Reported rows
One object per claim (`line`, `claim`, `proofs`, `scopes`, `flagged`, `why`) and
one totals row per line. `source` and `command` on every row.
