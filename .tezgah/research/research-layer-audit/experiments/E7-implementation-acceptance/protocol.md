# E7 protocol — the implementation's acceptance, item by item

Frozen 2026-09-20, before wave 1's changes land (baseline: `1021 tests, OK` at
HEAD with the tree clean of tracked edits). Written from
`to_human/implementation-spec.md`; the run happens after the writers stop.

## Question

Does each of the eight items behave as the spec states, on the real repository
and on throwaway repositories, and does the default (non-strict) path still pass
all six existing lines?

## Locked evaluation

- **Metric**: items whose acceptance test passes / 8, plus a hard gate:
  `bin/tezgah-research check` (no flags) must exit 0 for all six lines in this
  repository. A single item failing means the deliverable is incomplete, whatever
  the other seven do.
- **Baseline**: 8/8 predicted, and the gate green, because the spec is what the
  writers implement. A baseline of "some items pass" is not a result, it is a
  defect list.
- **Threshold**: 8/8 with the gate green. Anything less is reported as the exact
  failing item with its observed output.

## Cells and predictions

| cell | item | predicted |
|---|---|---|
| I1 | `init` on a gitignored path prints the negation; `check` warns with the reason; `check --strict` exits 1; a tracked line passes both | as stated |
| I2 | empty `evaluation.metric` at `phase=inner` -> FAIL; the same at `bootstrap` -> warn; a sessions entry with a bad tag -> FAIL | as stated |
| I3 | a proof with no path token -> FAIL for every kind; `evidence` citing a row-less `results.jsonl` -> warn, and FAIL under `--strict` | as stated |
| I4 | a `results.jsonl` row with no `source`, or a file that does not parse per line -> FAIL; `source --run` writes the log and the row; no orx -> exit 2 | as stated |
| I5 | a note absent from `INDEX.jsonl` -> FAIL; an INDEX row naming no note -> FAIL; a `class` outside the enum -> FAIL; grey without `quality` -> warn; `verified` of 1 -> warn | as stated |
| I6 | `phase=concluded` without `review.json` -> FAIL; a dimension outside 1-5 -> FAIL; a `quote` not verbatim in its target -> FAIL; an unsourced Patterns bullet -> warn | as stated |
| I7 | a shell command running `tezgah-research` records the `research` kind and flips the mark; `bin/tezgah-docs research` resolves; the two opencode statements match the code | as stated |
| I8 | the pinned behaviours in `experiments/E6-coverage-gap-list/results.jsonl` have tests | as stated |
| gate | `bin/tezgah-research check` on the six existing lines | exit 0 |

## What would falsify

- Any cell failing, with its output recorded verbatim.
- A rule that only works because a test was written to match the implementation
  rather than the spec's wording: the cell's command must be the spec's own
  acceptance sentence, not a paraphrase of the code.
- The gate red: the change broke an existing line, and the item that caused it is
  named.
- `check --strict` passing on this repository's own six lines: strict exists to
  refuse the unverifiable class, and this repository's lines are the population
  that has the most of it, so a green strict run here would mean the class is
  empty - which E1-E4 measured as false.
