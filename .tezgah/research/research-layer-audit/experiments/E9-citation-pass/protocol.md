# E9 protocol — the docs citations after the writers' edits

**Ordering disclosed.** The audit ran before this file was written, because the
writers' edits produced the drift and the audit is what located it. This file
records the measurement and the method, not a prediction.

## Question

Do the `path:line` citations in `docs/` still point into the symbol they name
after three writers inserted lines into `hooks/tezgah_policy.py`,
`hooks/tezgah_context.py`, `bin/tezgah-setup` and `tests/test_context.py`, and
after `docs/research.md` was added?

## Metric and the method used

`bin/tezgah-docs --citations` reports citations that resolve outside the symbol
named beside them. Method, and why it is not find-and-replace: the audit itself
states where each named symbol now lives, so the per-file shift is *derived*
(`new_start - old_start`), asserted uniform within each file, and only then
applied to every token in that file - each token keeping its own shape (a range
stays a range, a bare `:N` stays bare). The lesson this follows is written in the
repository's own ledger: a shift is not a search-and-replace, each bare `:N`
anchors to the path that precedes it, and the audit must report zero before the
pass is believed.

## Result

| reading | value |
|---|---|
| before | 36 judged citations outside their symbol, all from the writers' insertions |
| derived shifts | `hooks/tezgah_policy.py` +7, `hooks/tezgah_context.py` +8, `bin/tezgah-setup` +2, `tests/test_context.py` +39, `hooks/tezgah_research.py` a single citation already synced by the writer |
| replacements applied | 33 tokens across 6 pages (three audit rows were substrings already carried by a longer token in the same page) |
| after | **329 judged, 0 outside**, 748 not judgeable |

## What would falsify

- The audit reporting anything above zero after the pass - it reports zero.
- A uniform shift hiding a non-uniform edit: the shifts were derived per file from
  the audit's own rows and every file had exactly one distinct shift (`+7`, `+8`,
  `+2`, `+39`); a second distinct value would have stopped the pass rather than
  guessed.
- A shifted citation naming the right symbol but the wrong statement: not decidable
  by this audit. Spot-checked by reading the shifted sentences in
  `docs/research.md`, `docs/contract.md`, `docs/glossary.md` and `docs/hosts.md`;
  the residual population is the 748 not judgeable citations, which needs the
  page-by-page reading the earlier citation audit (plan 003) did.
