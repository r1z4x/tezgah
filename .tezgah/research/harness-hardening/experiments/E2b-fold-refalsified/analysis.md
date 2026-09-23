# E2b analysis — the fold re-read with a findable falsifier

## What was read
`results.jsonl` (5 rows): the same fold as E2 over the same corpus, re-run.

Rows here are scope: real (protocol.md: "The same fold of the same corpus").

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | the corrected run reaches E2's counts | `explorer` 0, `order` 0, `drift` highest, `task` on one day | **holds** |
| 2 | totals differ only by corpus growth | +1 refusal, +43 rows, same 1613 ledgers (this session's own traffic while both folds ran) | **holds** |

## What the numbers say
- The finding is reproducible and not an artifact of the first read: two
  independent folds over the same corpus agree on both zero-count rules.
- The corpus grows *while* it is measured — this session's own refusals are in
  the second fold — which is worth stating: a per-rule count from a live ledger
  is a moving number, and a claim about it carries the date it was read.

## What this does not show
- Anything E2 did not: a zero count still cannot separate "never offered this
  shape" from "cannot match this shape".
