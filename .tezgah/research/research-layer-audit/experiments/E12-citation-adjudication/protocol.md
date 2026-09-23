# E12 protocol — the citation residue, adjudicated

**Ordering disclosed.** The audit that motivates this ran first; the pass itself
is a judgement task delegated to the pages' owners, and the numbers here are what
they reported plus the parent's own audit reading at the end.

## Question

`bin/tezgah-docs --citations` judges citations that name a symbol beside them and
leaves the rest - **748 at the start of this pass** - undecided. Does each of
those still show what its sentence claims?

## Metric

- citations examined, per page-owner;
- citations corrected for content drift (the number points at a line that no
  longer shows the claim) versus re-anchored mechanically (the number moved but
  the content did not);
- citations confirmed unchanged;
- the audit's own reading at the end: `judged (N outside the symbol they name)`.

## Method, and the trap it avoids

Each citation was read at its target and judged against its sentence - not
shifted by an arithmetic offset. The reason is in this repository's own ledger: a
`path:line` shift is not find-and-replace, and two earlier passes mis-shifted 479
and then 40 citations by treating it as one. Two of the three passes here used a
content-verified line map (a number may only move through a byte-identical block),
and every changed row was read back afterwards.

## What would falsify

- The audit reporting anything above zero outside the symbol it names.
- A page's prose changing outside a citation: masked citations must leave the page
  byte-identical to the revision it started from.
- A confirmed row that does not in fact show its claim: the parent's spot checks
  are the sample, not the population.
