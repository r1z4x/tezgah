---
id: 002
title: finish the docs citation rebase
status: done
branch: main
pr:
created: 2026-09-19
updated: 2026-09-19
---
## Goal
The docs layer's promise is that every non-obvious claim carries a `path:line`
you can open. The code moved under the pages, so most of those citations pointed
at the wrong line. Ten page-by-page audits were run against HEAD and every
citation they flagged is now corrected and verified.

## Acceptance
- [x] The citations the audits flagged are corrected: 414 in the first pass, 60
      that resisted it re-judged by nine fresh readers and all applied (58
      mechanically, 4 compound ones by hand), and 24 in
      `hosts/opencode/plugins/tezgah.js` re-derived after this session's own
      `send` fix moved that file
- [x] A second pass over the residue returned no stale citations (the four the
      detector still reports are its own false positives, matched inside text it
      wrote: `:145` inside `:1453`, `:248` inside `:248-251`, `34-40` inside
      `hosts/cursor/hook.py:34-40`, `10-12` inside the repaired codex citation)
- [x] `HANDBOOK.md` regenerated; `bin/tezgah-docs --bundle` output matches
- [x] `tests/test_docs.py` gains the check a script can make: the cited file
      exists and the line is inside it
- [x] `python3 -m unittest discover -s tests` green

## What the work found, beyond the drift
- **The drift is the norm, not the exception.** 462 of the pages' citations were
  stale (the gate page worst: 130 of 168), because nothing regenerates a
  `path:line`: it is prose. The new test catches a deleted file or a line past
  EOF and nothing finer, so a periodic audit is still the mechanism.
- **Mechanical replacement needs a real verifier.** Two classes of damage were
  introduced and then found: 13 citations doubled (`path:path:NNN`), because a
  bare-number fallback matched inside a longer citation, and 4 spliced
  (`pathApathB:NNN`), because the same bare number existed in two files. Both are
  repaired; the detector for them is in this plan's instruments.
- **This session's own edits invalidated citations twice**: the `send` fix grew
  `tezgah.js`, and the `HANDBOOK.md` note pushed `AGENTS.md` down five lines and
  broke two citations in `docs/testing.md`.

## Instruments (local, gitignored)
`.tezgah/research/jev-classifier/tmp/` - `extract.py` (audit reports -> pairs),
`apply.py` (apply + verify against the cited range), `apply_js.py`,
`apply_residue.py`, `collect_residue.py`, and `reports/*.raw` (the ten audits).
