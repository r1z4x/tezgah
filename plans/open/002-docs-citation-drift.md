---
id: 002
title: finish the docs citation rebase
status: open
branch: main
pr:
created: 2026-09-19
updated: 2026-09-19
---
## Goal
The docs layer's promise is that every non-obvious claim carries a `path:line`
you can open. The code moved under the pages, so most of those citations pointed
at the wrong line. A page-by-page audit against HEAD was run and 414 of its
corrections are applied; this plan finishes the rest and keeps the layer from
rotting the same way again.

## What is already done
- Ten read-only audits, one per page, each resolving every citation against HEAD
  (`docs/architecture.md` … `docs/glossary.md`). Raw reports:
  `.tezgah/research/jev-classifier/tmp/reports/*.raw` (local only - the research
  workspace is gitignored), plus `reports/gate.jsonl` and
  `reports/opencode-js.jsonl` in machine-readable form.
- **414 corrections applied** to the ten pages and to `HANDBOOK.md`, each one
  verified before it was written: the evidence recorded by the audit had to sit
  at the corrected range in the cited file.
- `tests/test_docs.py::test_every_citation_points_into_a_file_that_has_that_line`
  now checks the half a script can: the cited file exists and the line is inside
  it. It catches a renamed or deleted file and a line past EOF; it cannot catch
  "the line no longer shows the thing the sentence names".

## Acceptance
- [ ] The 61 remaining stale citations are corrected and verified (see State for
      the per-page counts)
- [ ] A second audit pass over the ten pages returns an empty correction list
- [ ] `HANDBOOK.md` is regenerated and `bin/tezgah-docs --bundle` output matches
- [ ] `python3 -m unittest discover -s tests` green

## State
Started 2026-09-19. 61 citations resisted the mechanical pass, in two groups:

1. **57 whose correction could not be verified** - the audit's evidence was
   truncated at an escaped quote, or recorded for a neighbouring line, so the
   write was refused rather than guessed. They are the safe half of the residue:
   the correction is probably right and needs one reader's eye each.
2. **4 whose `old` string is not literally on the page** - citation text written
   with a file-name prefix the report spelled differently, or with a descriptive
   suffix.
3. Plus the deferred set from this session's own change: every citation into
   `hosts/opencode/plugins/tezgah.js` was invalidated by the `send`-class fix and
   re-derived separately (23 applied, 1 by hand).

Per page, as of this commit (`docs/gate.md` 4, `docs/operations.md` 11,
`docs/status-line.md` 12, `docs/hosts.md` 9, `docs/architecture.md` 7,
`docs/glossary.md` 7, `docs/skills.md` 6, `docs/contract.md` 4,
`docs/evidence.md` 1).

Instruments, local only: `.tezgah/research/jev-classifier/tmp/extract.py` (reports
→ pairs), `apply.py` (apply + verify, `--write` to write), `apply_js.py`.

## Why the drift happened, and what would stop it
Nothing regenerates a `path:line`: it is prose. Two options, neither free:
- keep the audit-and-repair cycle, now with the cheap test as the floor;
- or replace bare line numbers with symbol names plus a lookup (`def decision`),
  which survives a move but needs a resolver and a docs-layer policy change.
This plan is the first option; the second is worth a decision of its own.
