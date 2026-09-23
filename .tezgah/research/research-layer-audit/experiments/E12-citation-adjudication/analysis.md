# E12 analysis — 974 citations judged, the audit at 0 outside

Raw: `raw/pass.txt` (the three page-owners' reports and the parent's final audit
reading).

**974 citations across twelve pages** were read at their targets and judged
against their sentences: 348 by one owner, 473 by another, 153 by the third. The
corrections come in two shapes, and the split matters:

- **content drift** - the cited line no longer shows what the sentence claims
  (80 + 159 + 51, plus 3 bare citations given the path they meant and 5 prose
  corrections where the *meaning* had moved rather than the number);
- **mechanical re-anchor** - the number moved because a writer inserted lines
  above it, and the content did not change (163 for the gate's +131 insert, 99 for
  the tree's final state).

The audit reads **355 judged, 0 outside the symbol they name, 755 not judgeable**.
The residue went from 748 to 755 - it grew, because the writers added citations
while the pass ran - and it is named as the next audit's work list rather than
claimed clean. That is the same disposition the earlier citation audit (plan 003)
recorded for its own 575.

## What this does not show

- The 755 that remain were not adjudicated by this pass. A citation that names no
  symbol cannot be judged mechanically, and this pass did not cover them.
- "Confirmed" is a reading, not a proof: one owner flagged a single row it could
  not decide from the code (two `tezgah.js` twin numbers in `docs/gate.md`), and it
  is recorded as undecided rather than guessed.
- The two owners' masking checks show no prose moved, which is a strong signal and
  not the same as a byte-identical diff against HEAD for every page (the pages did
  legitimately change citations).

Rows here are scope: real (this repository's docs pages and the citation audit that reads them).
