---
id: 003
title: the layer's recorded gaps, closed or decided - citations first
status: open
branch: plan/003-layer-gaps-and-citation-audit
pr:
created: 2026-09-19
updated: 2026-09-19
---
## Goal
Make the layer's record true: land what this session verified but left
uncommitted, and settle the items the research lines left open so nothing stays
claimed-but-unchecked. The docs citations come first - they are the layer's own
promise that every non-obvious claim is openable - then the seats nobody has
measured.

## Acceptance
- [x] `python3 -m unittest discover -s tests` prints `OK` **unpiped**: a piped run
      records as "ran", never as "passed", which is why the first green report this
      session could not support a done claim. (`Ran 922 tests in 129.175s`, `OK`.)
- [x] `bin/tezgah-docs --citations` exits 0 with `0` citations outside the symbol
      they name.
- [ ] the delivered work is committed, and `git status --short` afterwards shows
      only the unrelated work-in-progress this plan does not own.
- [ ] every item the research lines recorded as open (`C5`, the local-form deletes,
      `consult`'s deadline, `I*`, `O*`) is at HEAD either shown closed with the
      reproduction that closes it, or written into `docs/` as a deliberate decision
      with its rationale.
- [ ] the 575 citations the audit cannot judge are named as the standing residue in
      `docs/README.md`: they are the next audit's work list, not a claim of
      cleanliness.
- [ ] the one seat no research line examined - a Jev-shaped classifier in the Stop
      rule's claim detector - is measured against the corpus or parked with its
      reason in `docs/gate.md`.
- [ ] `plans/README.md`'s table carries this plan with its real status.

## State
One caveat on the numbers below, and it is why the audit exists: the rebased
citations are measured against the **working tree**, which carries the
uncommitted `Inception` edit to `hooks/tezgah_policy.py` - that edit replaces six
lines with seven inside `NO_CONSULT`, so `CORE` sits at 487 in the tree and 486 at
`HEAD`, and the four `tezgah_policy.py` numbers this session wrote (`CORE`,
`CONDITIONAL_KEYS`, `POINTERS`, `CONTRACT`) are one line lower if that edit is
dropped rather than committed. `bin/tezgah-docs --citations` is the command that
says so; nothing else will.

Measured 2026-09-19 at HEAD `24936bd`, all unpiped and with the output seen:

- The three checks are green: `compileall` exit 0; `ruff check .` -> "All checks
  passed!"; `python3 -m unittest discover -s tests` -> `Ran 922 tests in
  129.133s`, `OK`. The first unpiped run also caught `HANDBOOK.md` stale (the pages
  moved after the last regeneration); regenerated, and `bin/tezgah-docs --bundle`
  now diffs clean against it.
- The citation audit is new: `bin/tezgah-docs --citations` resolves the symbol named
  beside a citation and reports the ranges outside that symbol's body - **243
  judged, 0 outside, 575 not judgeable** (no single symbol beside them). Reaching
  zero corrected **81 numbers across six pages** (the evidence page worst, 49), and
  two stale numbers in `docs/evidence.md` with them (`out_bytes` 0 of 1224 across
  1162 ledgers -> 6 of 1423 across 1454; `false_completion / claims` 0.271 over 1166
  -> 0.224 over 1454). Both of the resolver's own failure modes were found and fixed
  before its output was trusted: a multi-line contract string read as a definition
  (which mis-spanned `CORE`), and a same-named symbol resolved in the wrong file. A
  deliberately reverted number is caught, and the file comes back byte-identical.
- The research lines' open list reproduces as already closed or deliberately
  documented: `I10`, `I1`, `I6`, `I15`, `I17`, `O1`, `O3`, `O10` are fixed at HEAD
  with pinning tests; `C1`, `C2`, `C3`, `C7`, `C10`-`C15` are closed; the gate's
  17-command table leaves 9 silent forms, five of them on `docs/gate.md`'s written
  non-goal list; `gh pr create` / `gh pr edit` now ask (the hole the
  `jev-classifier` line handed over); `benchmarks/arm-bench/.runs` is empty;
  `consult`'s `os._exit` guard names the 18-minute hang it answers.
- The Jev question is closed on the earlier line's own numbers: precision **0.167**
  (12 of 20), **768.832 ms** per call (15.09x the pre-tool path's 50.965 ms), and
  **0 triggers in 147** sampled calls; the line's `state.json` carries it as `H6`,
  NEGATIVE PRIOR. Its seam map rejected the prompt-arming seat too, and left the
  Stop rule's claim detector unexamined.
- Committed on `main`: the citation work as `f2b6527` (`bin/tezgah-docs`,
  `docs/README.md`, `docs/{architecture,contract,evidence,gate,glossary,hosts}.md`,
  `HANDBOOK.md`, `CHANGELOG.md`) and this plan as `7fd483e`, `a8f69ac` - explicit
  paths only, so the unrelated work-in-progress stayed unstaged. That WIP is an
  `Inception` provider for `consult` (`README*`, `bin/consult`, `bin/codegen`,
  `bin/tezgah-setup`, `hooks/tezgah_paths.py`, `tests/test_{paths,providers,setup}.py`,
  `docs/status-line.md`): this plan does not own it and must not commit it.
  Nothing is pushed.

## Next
Measure the one seat no research line examined - a Jev-shaped classifier in the
Stop rule's claim detector - against the 1436-ledger corpus, or park it with its
reason in `docs/gate.md` beside the empty gate seat that was.
