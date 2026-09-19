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
- [x] the delivered work is committed on its own paths, and nothing of the unrelated
      work-in-progress was swept in (that workstream committed its own `4b8d9b2`).
- [x] every item the research lines recorded as open (`C5`, the local-form deletes,
      `consult`'s deadline, `I*`, `O*`) is at HEAD either shown closed with the
      reproduction that closes it, or recorded where its disposition lives: `docs/gate.md`
      for the five local-form deletes (a written non-goal) and for the two classifier
      seats, `bin/consult`'s docstring and its `ponytail:` comment for the per-model
      deadline and the 18-minute hang it answers.
- [x] the 575 citations the audit cannot judge are named as the standing residue in
      `docs/README.md`: they are the next audit's work list, not a claim of
      cleanliness.
- [x] the one seat no research line examined - a Jev-shaped classifier in the Stop
      rule's claim detector - is measured against the corpus and parked with its reason
      in `docs/gate.md`, and the measurement closed a real gap in the vocabulary it
      found (`DONE`, `hooks/tezgah_integrity.py`).
- [x] `plans/README.md`'s table carries this plan with its real status.

## State
One caveat on the numbers below, and it is why the audit exists: the rebased
citations are measured against the **working tree**, which carries the
uncommitted `Inception` edit to `hooks/tezgah_policy.py` - that edit replaces six
lines with seven inside `NO_CONSULT`, so `CORE` sits at 487 in the tree and 486 at
`HEAD`, and the four `tezgah_policy.py` numbers this session wrote (`CORE`,
`CONDITIONAL_KEYS`, `POINTERS`, `CONTRACT`) are one line lower if that edit is
dropped rather than committed. `bin/tezgah-docs --citations` is the command that
says so; nothing else will.

The seat's measurement (2026-09-19, free, offline): the claim vocabulary was
applied to this machine's own 161 final replies from
`~/.omp/agent/sessions/-Projects-tezgah` and to a hand-drawn set of 15 completions
stated as a completed state. It recognised 2 of the 15 and read 34 of the 161
replies as claims. The misses are one shape - the Turkish passive and the English
state predicate - so naming 11 of the 13 closes them in the regex itself: the list
now catches 13 of the 15, reads 39 of the 161, and still claims 0 of 5 control
replies (a question, a plan, an explicit `doğrulanmadı`). The verdict never moved,
which is why the seat stays empty: a turn that recorded work is refused on its
evidence whatever its wording.

That widening grew `hooks/tezgah_integrity.py` by 13 lines and moved every citation
into it; `bin/tezgah-docs --citations` caught all 81 in one command, and the rebase
was re-applied in a single pass after a first attempt carried stale offsets and
corrupted the pages (recovered from `f2b6527`, and the seven pages restored by
explicit path so the other workstream's `docs/status-line.md` was untouched).

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
Resolve the 575 unjudged citations, page by page, from the six read-only passes
running over them; apply what they confirm and re-run `bin/tezgah-docs --citations`
until only the genuinely unjudgeable rows are left.
