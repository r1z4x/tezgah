# E11 analysis — used once in 30,750 rows, and the cost is one line

Raw: `raw/audit.txt` (the delegated audit's numbers, persisted by the parent).

## Answer to the first half: not at full capacity - essentially not used

- **1 row in the whole 30,750-row ledger reads a vendored entry body**, and it is
  this session's own read while building a citation note. Three rows list a stage
  index. **26 rows read the same material from the upstream clone** instead.
- **0 of 6 research lines cite a library entry** anywhere in their literature,
  claims, findings or log.
- 22 tests guard the tree and the importer; **none guard adoption**, so nothing
  would notice if the count went from 1 to 0.

**The instrument's limit is part of the finding**: the ledger records shell and
edit rows, not host file reads, so this shows that the library is not reached
through shell commands and not cited as evidence - it cannot show that no session
ever opened an entry with a read tool. The number that would settle it (a
`skill_read_kind` prefix for `skills/ai-research/`) is a small change to the
router/mark machinery, and it is the one item from this audit the parent did not
implement, because it changes the status line's public measure set.

## Answer to the second half: the cost is one line, and the complexity is in maintenance

| cost | measured |
|---|---|
| always-on context | one 217-byte line in a 4.3 KB router file (the collapsed buckets beside it are 45 and 25 bytes) |
| per research prompt | the RESEARCH paragraph's 7 lines naming the library (~470 B) |
| repository | 374 files, ~4.34 MB of content, a 111.6 KB manifest, a 439-line importer, 22 tests, a `SOURCE` and a `NOTICE` row |
| drift | the comment beside `RESEARCH_SKILLS` said the opposite of the code (fixed) |

So: the *context* cost is negligible and the *maintenance* cost is real but
bounded. It is not complexity in the sense of "hard to reason about" - the read
path is three steps and documented - it is complexity in the sense of "4.34 MB of
material nobody reaches, with an importer and 22 tests that keep it honest".

## Options, ranked, with what each costs

1. **Do nothing.** 217 B always-on, 4.34 MB per clone, breaks nothing. Defensible
   because the copy is the only offline domain material the loop can quote.
2. **Fix the drifts and name the read path in `docs/research.md`.** ~3 lines and a
   paragraph; breaks nothing. The comment is already fixed; the page names it.
3. **Make adoption measurable.** One prefix rule in `skill_read_kind`/
   `SKILL_MARKS` mirrored across the hosts, plus a measure in the status line and
   its legend - ~15 lines and tests. This is what turns "unused" from an
   inference into a number, and it is the prerequisite for option 4.
4. **Trim to what a line can reach.** Drops the stages no line has entered; breaks
   the manifest counts, the stage map, `SOURCE`'s drop list and six tree-side
   tests. Its justification is zero recorded usage - which option 3 would have to
   confirm first, since the instrument is blind to host reads.
5. **Delete the tree.** -4.34 MB, -217 B always-on, -22 tests, -439-line importer,
   -3456-line manifest, and ten cut sites; it changes what every research session
   is told, not only what sits on disk.

The parent implemented 2, left 3 for the user's call, and did not touch 4 or 5 -
cutting material on an instrument known to be blind would be acting on silence.

Rows here are scope: real (this repository's vendored tree, its ledger and its installed router file).
