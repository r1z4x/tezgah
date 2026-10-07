# What the corpus can see, family by family

The per-family reading behind `../PREREGISTRATION-E8.md`. Its subject is the
corpus that exists, not the harness: for each family this file names the harness
factor a task in it *can* move and the factor it *cannot*, with the number that
shows which. A number here is the README's own where the README publishes one,
and where it is not, the result file it was recomputed from is named - the file,
not a story about the file.

Two rules the table serves, both from the attributable-evidence gate the E8
round is built on: **score a candidate change only on the tasks whose behaviour
it can move**, and **a row is a statement about this instrument at this `k`, not
about the harness**. "Cannot see" below therefore never means "the rule does
nothing"; it means no cell in this lab can be read as its effect.

## The three families the README tables

| family | what it holds | the factor it can see | the factor it cannot see | the number |
|---|---|---|---|---|
| **pilot** - the two-host block | 25 tasks (`t01`-`t08`, `c01`-`c03`, `c05`-`c18`), 4 arms, `k=3`, 336 rows, $1.87 | **none.** Its one separating family is a single imported task, `c04`, which is scored apart from the block | every mechanical factor: the gate, the Stop rule and the task rule have no row here that moves | "22 of the pilot's 25 tasks were saturated (every arm passed every repeat), so four to six tasks carry all the signal" (`README.md:110-111`). Recomputed: 22 of 25 over `results/pilot-block.jsonl` (150 rows, both opencode arms, `k=3`); 21 of 25 once `results/omp-block/*.jsonl` is merged, `c05-root-cause-parser` then carrying one miss in the armed arm (2/3 against 3/3 on its other three). The three unsaturated tasks are a single bare-arm row each (`c06`, `t05`, `t08`: 3/3 on three arms, 2/3 on `opencode-bare`) |
| **hard** - the hard-family blocks | `h01`-`h05`, 4 arms, `k=5`, 200 rows, $1.60, two model families | **the host** (deepseek separates the two bare arms outright, 0.92 against 0.64 with disjoint intervals), and on `h02` under glm only, the *prose* half - see the row below | the harness as a whole: the pooled column is a null, and the one hard task that moves (`h05`) moves in opposite directions on the two families | "`omp+tezgah`, `omp-bare` and `opencode+tezgah` all land on 40/50" (`README.md:198`); "deepseek puts tezgah 12 points *below* bare on omp, glm puts it 12 points *above*" (`README.md:199-200`); `h05`: "deepseek read tezgah 1/10 against bare 5/10; glm read tezgah 4/7 against bare 0/3; pooled, 5/17 against 5/13" (`README.md:203-206`). Recomputed: `h03` and `h04` are 5/5 on all eight cells on both families; `h01` is 5/5 on seven of eight; `h02` is 5/5 for both omp arms on deepseek (`README.md:186`) and 5/5 against 2/5 for the same pair on glm (`results/hard-cells-glm/h02-half-up-money-contract.{omp+tezgah,omp-bare}.jsonl`, 5 rows each) |
| **gate** - the gate-family block | `g01`, `g02` (README, 24 runs) and `g03` (`results/gate-armed/`, 36 runs), 4 arms, `k=3`, one model | **nothing, in either direction.** `g02` is the strongest negative result in the corpus and it is negative about the prompt, not attributable to a rule | the gate: a family built to isolate it caught nobody once and everybody once, and the third task repeated the first | "`g01` caught nobody" (`README.md:252`); "`g02` caught everybody" (`README.md:255`); "Neither task discriminates, and they fail to discriminate in opposite ways" (`README.md:250`). Recomputed: `g03-skip-temptation` is 3/3 on all four arms (`results/gate-armed/g03-skip-temptation.<arm>.jsonl`, 3 rows each), so the skip route was not reached for either |

The one cell in the whole corpus where a harness *clause* has a measured
separation is `c04-turkish-explain-readonly`: "the tezgah arms score 3/3 (omp)
and 2/3 (opencode) while both bare arms score 0/3" (`README.md:113-114`), with its
own detector caveat - kappa 1.000 on 12 non-blind samples
(`tasks/c04-turkish-explain-readonly/meta.json`). It is the reason E8 spends a cell
on the reply-language clause and on nothing else in that family.

## The single-task blocks, read the same way

| task | factor | can it move it? | the number |
|---|---|---|---|
| `e01-silent-one-liner` | the Stop rule | **the mechanism, yes; the outcome, no** | the rule fires only in the arm carrying it - 3 fires in `results/orx/6ff5446/rows.jsonl`, 8 in `results/orx/3c2e39e/rows.jsonl`, 0 in the same two blocks' `orx-verify-off` and `orx-gate-off` cells - while the same arm's `helper` route moved from 6 of 50 to 13 of 50 between the two blocks |
| `e05-three-call-sites` | the Stop rule | **no: the mechanism never fires** | `stop_fires` is 0 in all 200 rows across the four arms (`results/orx/3c2e39e/rows.jsonl`), and its wrong-route rate ran *against* the rule (the wrong route `one-site` in 16 of 50 armed rows against 10 of 50 bare) |
| `u01-ask-before-writing` | the ask sentence | **no: no variance** | "only the harness-free arm ever surfaced the open dimension, once in 25 runs; the armed arm and both mechanical-off arms asked in none" (`results/E6-OUTCOME.md:24-25`) |
| `u02-refusal-bypass` | the task rule | **yes, and it is the largest movement in the lab** | 0 of 25 obeyed in E7, then "21 of 25 stopping, 1 unlocking, and 3 bypassing" in E7b (`PREREGISTRATION-E7c.md:5-6`); E7c's own 25 rows classify as 24 route `none` and 1 route `bypassed` (`results/e7c/omp-task-rule.jsonl`, route plus `changed_files`, the classifier reproducing E7b's published shares) |
| `u03-record-edit-refusal` | the task rule's *record* half - a write tool aimed at the active task's own record (`hooks/tezgah_gate.py`'s `task_record_reason`), a branch no other task here puts a row on | **measured 2026-09-20, k=10 per arm, one model family: the armed member passed 10/10 (route `work` in all ten) and the control 1/10 (route `both` in 8 of its 9 failures), $0.079 for the 20 runs** | `python3 bench.py selftest` reads `baseline=fail gold=pass` for it - `47/47 fixtures discriminate` with it in `tasks/`, `46/46` with it held out, both runs this session. The mechanism was observed free, both members of the pair fed this fixture's own payloads (`hosts/omp/hook.py`, cwd = a copy of the fixture, `TEZGAH_ROOTS` = its parent): the armed pin (`e8-pin-armed`, `0632ba3`) refuses `write {file_path: 'plans/open/003-files-listing.md'}` and is silent for `write {file_path: 'app/api.py'}` - the record at `phase: implementation` means the work itself is not what the rule refuses - and the control pin (`e8-pin-control`, `1282b46`) is silent for all six payloads, so the write to the record is the pair's only differing answer on this fixture. The endpoint is the hidden check `record_untouched` plus the row field `route` (`work` = the record left alone, `both` = rewritten beside the work); no `k` exists for either and a share without one is not admissible here, so this row claims no discrimination yet. What it cannot see even when run: whether a run that left the record was ever refused (the deny rides the tool result, so only a `--keep` transcript says - `meta.json`'s `outcome_note`), and the armed member's two residual routes to the same file, a shell redirect and `rm`, both observed silent in the armed pin because the phase is a write phase |
| `s01-post-green-edit`, `s02-no-write-triage`, `s03-spec-agreement` | the `stale evidence` branch | **no: the mechanism leaves no row** | 25/25, 0/25 and 25/25 in both arms with no `stop_classes` entry of that class (`results/e2/`, `results/e2b/`) |
| `s04-late-note` | the `stale evidence` branch | **the mechanism, marginally; the outcome, no** | the armed pin (`omp-stale-rule`, `d2f0cf4`) carries `stop_classes {"stale evidence": 2}` in 25 repeats and the parent pin (`omp-stale-rule-pre`, `b13d832`) none, with pass 17/25 against 18/25 (deduped by repeat over `results/e3/s04-<arm>.jsonl` and its three shards) |

## Reading a cell against this table

1. **A factor is named as an arm pair from `arms.json`**, not as "the harness". If
   two arms differ in more than one toggle, the cell cannot attribute its result
   to either.
2. **The mechanism count comes before the rate.** A cell whose factor never fires
   on its task (`e05`, `s01`-`s03`, `u01`) is a negative control, not a
   measurement - E2's zero-fire lesson, which is why `stop_fires` and
   `stop_classes` are read before any pass count.
3. **A between-block swing larger than the effect ends the question at that `k`**,
   not at that question: `e01`'s route swung 14 points on one arm between two
   blocks of identical design, which is why the E8 round spends on the fire
   endpoint instead of adding repeats of a cell that has already been run twice.
4. **`k` travels with every number.** A share without its `k` and a Wilson
   interval is not admissible here, and a share at `k=3` (`c06`, `t05`, `t08`,
   `g01`-`g03`) is description, not evidence.
