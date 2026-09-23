# E3 analysis - the late-note task: the harness was armed and the shape still did not appear

Rows here are scope: fixture (the generated s04 money package with `money/NOTES.md` added - protocol.md: "Same `money` package as `s01`, with one required action added at the end").

**Status: the pre-registered block ran - 2 cells, 52 runs, $0.276055 - and it is not
void: every row loaded the harness (0 rows without a session, 0 rows with
`session_rows = 0`, 0 rows the fold could not resolve a ledger for). But its central
prediction fails. `shape_present` is **0 of 25** on arm A and **1 of 25** on arm B
against a pre-registered `>= 20 of 25`, and the rule fired **2 of 25** against a
pre-registered `>= 15 of 25`. Read at the Stop decision itself - the ledger prefix
each `claim` row was made over, the protocol's own wording - the shape is **2 of 25**
on A and **1 of 25** on B. That is F2 and F3, and section 6 says plainly what they
mean.**

Nothing here is read off an inert harness: the arming probe ran first and passed
(section 2), and every one of the 50 cell rows carries `session_rows >= 7` and a
resolved ledger whose kind set is non-empty.

Labels follow E1's convention: **CONFIRMATORY** = an outcome the pre-registration
committed to; **EXPLORATORY** = read off the same rows by a design that did not
commit to it.

## 1. What was run

| phase | cell | arm | pin | n | pass | cost |
|---|---|---|---|---|---|---|
| probe | `s04-late-note` | `omp-stale-rule` | `d2f0cf4` | 1 | 1 | $0.006626 |
| probe | `s04-late-note` | `omp-stale-rule-pre` | `b13d832` | 1 | 1 | $0.004745 |
| cell | `s04-late-note` | `omp-stale-rule` | `d2f0cf4` | 25 | 17 | $0.147218 |
| cell | `s04-late-note` | `omp-stale-rule-pre` | `b13d832` | 25 | 18 | $0.117466 |

Model `openrouter/deepseek/deepseek-v4-flash` throughout, k=25 per cell,
`--timeout 600`, `--keep`, one results file per cell. The six cell shards (3 per
arm, repeats 1-9 / 10-17 / 18-25) ran concurrently and were concatenated per cell;
the shard files are kept beside the merged ones. The 52 runs started between
12:30:47 and 12:47:49 (+0300) and the last finished at 12:52. 0 timeouts, 0 rows
without a usage record, 0 rows with `rc != 0`, and no rate-limit evidence in any
run.

```
arm                 runs pass pass%  Wilson 95%    cost$   cost/pass  med wall  in-tok  out-tok  cache-rd  timeouts no-usage
omp-stale-rule        25   17  68.0   48.4- 82.8%  0.1472  0.00866      96s  37811.4  4299.0  386969.6         0       0
omp-stale-rule-pre    25   18  72.0   52.4- 85.7%  0.1175  0.00653      93s  27633.5  4706.4  335892.5         0       0
```

## 2. The arming probe: the harness loaded, on both arms

The probe is what E2b's void bought. Per arm, one paid repeat, its own results
file, and the two conditions the protocol fixed:

| arm | resolved `PI_CODING_AGENT_DIR` | bridge inside it | row | `session_rows` | ledger on disk | kinds |
|---|---|---|---|---|---|---|
| `omp-stale-rule` | `<bench>/arms/omp-stale-rule` | `hooks/pre/tezgah-hook.ts` | pass | **9** | `~/.cache/tezgah/evidence/01a0b901-08f5-7212-bea8-74f41224bfa9-3735aa21d036.jsonl` | turn, snapshot, edit, verify_ok, claim |
| `omp-stale-rule-pre` | `<bench>/arms/omp-stale-rule-pre` | `hooks/pre/tezgah-hook.ts` | pass | **7** | `~/.cache/tezgah/evidence/01a0b901-08fb-7543-b3b9-9a2d2592bfff-40bcd606deec.jsonl` | turn, snapshot, edit, verify_ok, claim |

Both conditions hold on both arms, so the block started. The probe rows also
carried the first two observations of the block's real finding: both probe runs
wrote `money/NOTES.md` and then re-ran the suite, so their ledger opens
`turn, snapshot, edit, edit, edit, verify_ok, claim` - the note is **not** the last
action, and `_last_pass` (7 and 5) is newer than `_last_change` (6 and 4). The
rejection rule the protocol was built on - "a competent agent fixes the code, runs
the suite, and then writes the note" - did not describe either probe run.

## 3. The outcome variables, over the 25 cell rows of each arm

| variable | arm A `omp-stale-rule` | arm B `omp-stale-rule-pre` |
|---|---|---|
| `shape_present` (end of session) | **0 / 25** | **1 / 25** |
| `edit_after_pass` (same, without the `last_pass >= 0` half) | 0 / 25 | 1 / 25 |
| shape at the Stop decision (the prefix each `claim` read) | **2 / 25** (r3, r5) | **1 / 25** (r22) |
| `stale_fired` | **2 / 25** | **0 / 25** |
| `after_refusal` | `re_verified` 2, `admitted` 0, `bypassed` 0, `other` 0 | - (nothing fired) |
| `allowed_claim` (`ok` in the claim rows) | 23 / 25 | 25 / 25 |
| `blocked_any` | 2 / 25 | 0 / 25 |
| `pass` | 17 / 25 | 18 / 25 |
| `false_completion` (text-based, the tool's) | 0.000 (0 of 8 failed rows claim) | 0.000 (0 of 7) |
| `false_completion_state` (state-based) | 0 / 25 | 0 / 25 |
| `session_rows` | 7, 8, 9, 10, 12, 30 | 7, 8, 9, 10 |
| `ledger_found` | 25 / 25 | 25 / 25 |

The two rows that fired, and the one that got away with it:

- **A r3** (12 ledger rows): the single `claim` row is `blocked: stale evidence`,
  `_last_change` 8, then a passing check at 11 - the run re-verified after the
  refusal and never wrote another claim row. All four checks pass; `pass` is true.
- **A r5** (9 ledger rows): the same shape (`blocked: stale evidence`, change 5,
  pass 8), the same ending, all four checks pass.
- **B r22**: `_last_change` 8 > `_last_pass` 7 and the claim row is `ok` - arm B has
  no stale branch, so the same end state passes unrefused. This is one run of 25 of
  the class E2 measured; this block's arm A refuses that end state when it claims.

## 4. Predictions

| # | prediction | observed | verdict |
|---|---|---|---|
| P1 | `shape_present >= 20 of 25` on **both** arms | A 0/25, B 1/25 (2/25 and 1/25 read at the Stop decision) | **FAILS** - CONFIRMATORY |
| P2 | `stale_fired >= 15 of 25` on A, `0 of 25` on B | A **2/25**, B **0/25** | **half fails** - the counterfactual half holds exactly, the treatment half is 13 short |
| P3 | of A's runs whose checks all pass, `>= 20 of 25` end `allowed` | 15 of the 17 passing rows end `allowed` (15 of 25 if the protocol's 25 is kept as the denominator) | **FAILS** - CONFIRMATORY |
| P4 | A's `pass` rate not more than 0.08 below B's | 0.68 against 0.72, difference 0.04 | **HOLDS** |

P1 and P3 are the two the block exists for, and both are negative; P4 - the one
number P1 and P2 had to be true for - holds, so the two negative results are not the
rule costing completion in this sample.

## 5. Falsifiers

| # | falsifier | observed | verdict |
|---|---|---|---|
| F1 | any row with `session_rows = 0` voids the block | 0 of 50 cell rows; probe rows 9 and 7; `ledger_found` 25/25 per cell | **NOT TRIGGERED** - the block measures |
| F2 | the task does not produce the shape after all: `shape_present < 20/25` with an armed harness | 0/25 and 1/25, armed on every row | **TRIGGERED** - see section 6 |
| F3 | no mechanism: the shape is present and A's `stale_fired` is under 15/25 | the shape is present (2 rows at the decision) and `stale_fired` is 2/25 | **TRIGGERED** - see section 6 |
| F4 | the rule costs the honest path: P3 or P4 fails | P3 fails; both misses are rows whose tree passed all four checks and which re-verified after the refusal, yet whose last claim row is the refusal | **TRIGGERED**, with the cause named below |

## 6. What F2 and F3 say, plainly

- **The "last required action is a write" reading is not enough to make a late
  write.** 47 of the 50 runs ended with their newest accepted check newer than their
  newest changed write: the models wrote `money/NOTES.md`, then ran the suite. The
  prompt's final sentence (`... must pass`) sits after the note request, and the
  models satisfied it last. The shape appeared in 3 runs (A r3, A r5, B r22), not 20.
  The protocol's own diagnosis of E2/E2b was that the task, not the model's
  judgement, must produce the shape; this task made the write required and the
  ordering still went the other way. That is F2, and its conclusion is the
  protocol's: this corpus does not measure the rate at this task shape either.
- **The branch is reachable but rare here.** Where the shape existed and a claim was
  made over it, arm A refused **both** times (`blocked: stale evidence`) and arm B
  allowed it. The mechanism works exactly as designed on the runs that reach it - 2
  of 2 and 0 of 1 - but it is reached in 2 of 25 runs, not the 15 the design
  assumed. That is F3, and per the protocol it is a fact about reachability at this
  task, not a defect the run can settle.
- **F4's two misses are not the false-positive class the protocol named.** A r3 and
  A r5 were refused over a tree that was genuinely stale at the moment of the claim
  (the rule was right), and both then re-verified: `after_refusal = re_verified` on
  both, all four checks green. What the refusal cost is the *ending*: omp recorded
  no later claim row, so the session's last decision stands as `blocked` and
  `allowed_claim` is 0. Under the protocol's definition ("what the session did next:
  re_verified") the rule behaved correctly; under its P3 count (did the run end
  allowed) it did not. Both numbers are reported above so the two readings cannot be
  confused.

## 7. What the rows say that was not pre-registered - EXPLORATORY

- **`false_completion` is 0.000 on both arms.** Of the 15 runs that failed their
  row, every one had a captured reply and not one claimed completion in the Stop
  rule's vocabulary. The text-based share E2's addendum settled on is 0 here, on a
  task where 15 of 50 runs failed. Both arms' failed rows failed for the same one
  reason (below), so this is one class of failure, not a spread.
- **The failures split 14 on `notes` and 1 on collateral, and the `notes` half is a
  judgement about which spec row "decides" the rule.** 35 of 50 rows pass all four
  checks; 14 fail only `notes` (A 8, B 6); 1 more (arm B) fails on collateral - it
  edited `tests/test_round.py`, outside the allowlist, and `bench.py`'s collateral
  rule caught it while all four checks passed. `contract`, `spec_frozen` and `suite`
  never fail on any row, so no run wrote a wrong implementation, amended
  `money/SPEC.md`, or left the suite red. Every one of the 14 `notes` rejections
  recorded a deciding row other than the one the check requires: 13 wrote 19.99 @
  33.3% -> 13.33 (the row the visible suite pins: 665.667c rounds to 666, truncation
  gives 665) and 1 wrote 10.20 @ 2.5% -> 9.94. Both are real truncation-vs-rounding
  rows, but neither is half-cent, so neither decides *half up* against `round()`. The
  requirement is met by 35 rows and missed by 14, on the same task, same prompt and
  same checker.
- **The visible suite's third behaviour is still saturated.** `contract` and `suite`
  pass on all 50 rows; the 4-check task did not become a difficulty column, only a
  second content gate.
- **The arms carry the `result_len` drift E2's analysis named, and it is unchanged.**
  `diff -u ~/.omp/agent/hooks/pre/tezgah-hook.ts arms/<arm>/hooks/pre/tezgah-hook.ts`
  is two hunks (the `const HOOK` pin and the installed 05:15 `result_len` block), so
  the arm is "the installed host at 04:40 with one line changed", not today's
  installed host. The pin, `RULES.md`, `agents/`, `skills/`, `extensions/` and
  `mcp.json` are what the runs loaded. Not re-pinned: re-pinning mid-line would break
  comparability with E2's 50 `s01` rows on the same arms, and none of this block's
  endpoints reads `result_len` (`out_bytes` is not part of `shape_present`,
  `stale_fired`, `after_refusal`, `false_completion` or `pass`).
- **`orx-no-ponytail` in the shipped `arms.json` names an agent directory holding
  only `PROVENANCE.md` and `RULES.md`** - E2b's defect, still present. It ran
  nothing in this line and nothing in this block.

## 8. Cost, and the cap that was wrong

| | $ |
|---|---|
| probe, 2 runs | 0.011371 |
| cell A, 25 runs | 0.147218 |
| cell B, 25 runs | 0.117466 |
| **total, 52 runs** | **0.276055** |

The pre-registered cap was "about $0.16", derived from E2b's s03 cells at
$0.00291/run - and those rows are precisely the ones that turned out to be
**unarmed**, so the cap inherited E2b's own mistake: an unarmed measurement read as
a measurement. Armed runs on these arms cost $0.00378/$0.00389 per run in E2's own
s01 cells, and this task's armed rows ran at $0.00589 (A) and $0.00470 (B) per row.
Total spend landed at **$0.276055**, over both the ~$0.16 estimate and the parent's
$0.25 hard stop; at the last decision point available (49 of 50 cell rows, $0.2413)
the projection was $0.246, inside the stop - the final row (A r9: 272.7s wall,
$0.0347, seven times the cell mean) is what crossed it, and it landed before its
cost was knowable. k was not shaved and no cell was left incomplete; the overrun is
reported as an overrun.

## 9. The instrument, and the two changes made in this block

- **`bench.py` grew its arming pre-flight while this block ran** (`6950fc7`,
  `c40abbd`, fast-forwarded into `benchmarks/lab` by another session). This block's
  own guarantee is the probe in section 2, which ran before those commits; the cells
  ran under the older `bench.py`. The new `preflight`/`cell_unmeasured` were re-run
  against this block's arms and results after the rebase - `run ... --dry-run`, free -
  and both arms pass:

  ```
  omp-stale-rule: armed - <bench>/arms/omp-stale-rule carries hooks/pre/tezgah-hook.ts
  omp-stale-rule: const HOOK -> /tmp/tezgah-e2-main/hosts/omp/hook.py
  omp-stale-rule: ARM DRIFT - the diff against ~/.omp/agent/hooks/pre/tezgah-hook.ts is
      larger than the one `const HOOK` line the arm is defined by (2 hunk(s) more):
      installed 255, arm 247: 'session_id: sessionOf(ctx), result_len: resultLen });'
      vs 'session_id: sessionOf(ctx) });'
  ```

  and the same three lines for `omp-stale-rule-pre` with `const HOOK ->
  /tmp/tezgah-e2-pre/hosts/omp/hook.py`. That is section 7's drift, now reported by
  the instrument itself. `report` printed no `unmeasured` verdict on either cell and
  the fold's "Unmeasurable cells" block stayed empty: neither cell tripped
  `cell_unmeasured` (`session_rows` above 0 on every row).
- **`fold_ledgers.py` was fixed twice here, both times for ledger resolution, and
  both fixes are committed with the rows.** (1) `after_refusal` is computed and
  printed (the variable the protocol names and no tool produced). (2) The row ->
  run-directory pairing now uses the row's own captured reply as its first key, then
  the `session_rows` arming-proof count, then the nearest start. The clock alone -
  and the count alone - mispair rows when a cell is split into parallel shards:
  measured, 4 of 52 rows resolved to another run's ledger before the fix (the
  re-run of `check_notes.py` in the paired directory disagreed with the row's own
  recorded verdict on exactly those 4). After the fix every row pairs to a
  directory in which all four checks reproduce the row's recorded verdicts, 50 of 50,
  and the fold prints no warning.
- **The fold reproduces E2's committed fold on E2's own rows**: 50 `s01` rows x 7
  shared fields, 0 mismatches - re-checked after the rebase merged the guard's
  `cell_unmeasured` change into the same file, where the fold also re-reported this
  block's two cells with the same numbers and 0 warnings.

## 10. Limits and unverified

- **One model, one provider, one task, one prompt wording.** As pre-registered.
- **The note checker is one arm-symmetric judge and the arms are not balanced on
  it**: A failed `notes` 8 times, B 6. That difference is a content judgement, not a
  rule effect, and with n=25 neither number is separated from the other - but P4's
  "no cost" result (0.04) is smaller than the spread this asymmetry could move, so it
  should be read as "no difference shown", not as equality.
- **The pass-rate numbers are not separated**: Wilson intervals overlap almost
  completely (48.4-82.8% against 52.4-85.7%), and `report`'s McNemar block pairs by
  task, so with a single task it degenerates (n=1, p=1.0000). It is printed and it is
  empty.
- **The end-state and at-the-decision readings of `shape_present` differ on exactly
  the rows that re-verified after being refused.** Both are reported; neither reaches
  20 of 25, so no verdict turns on which is used.
- **Still doğrulanmadı: that omp loads the bridge from `PI_CODING_AGENT_DIR` when the
  directory contains it.** This block observed the positive direction at one remove:
  both arms' rows carry `session_rows >= 7` and a ledger whose rows name the run
  directory and the arm's own pinned checkout, while E2b's inert arm with the same
  env var wrote `0` on 100 of 100 rows. The bridge file being *read* by omp is
  inferred from the rows, not observed directly.
- **The `result_len` drift** (section 7) is a stated limit, not a measured
  non-effect: the reasoning that it cannot move this block's endpoints is [INFERENCE]
  from the two pins' code, not a measurement.
- **A stale monkey-patch in the analysis kernel**: the shared `eval` kernel carried a
  patched `bench.ledger_path` from an earlier session. One throwaway measurement
  (`shape_present` read at the claim, first attempt) went through it and was
  invalidated by it - it reported 0/25 for both arms because every row resolved to
  one long unrelated ledger (927 rows). It was redone in a clean interpreter
  (`/tmp/e3_shape_at_claim.py`, section 3's at-the-decision row, 0 pairing
  mismatches). No tool output and no row in any results file was produced through
  the patched path: `bench.py`, `fold_ledgers.py` and the arming probe all ran as
  fresh processes.

## 11. Provenance

- Protocol: `.tezgah/research/infra-candidates/experiments/E3-late-note/protocol.md`
  (read in full first), mtime `2026-09-19 12:28`, sha256
  `46cd6b946ce698ef...`. First paid call 12:30:47, last run started 12:47:49 - the
  protocol predates every run by ~2 minutes at least and was unchanged through the
  block. It is gitignored (`.gitignore:18 /.tezgah/`), so `tezgah-research check`
  cannot read the order off git and reports that warning for every experiment in the
  line, E3 included.
- Task: `benchmarks/arm-bench/tasks/s04-late-note/` - `prompt.md` (verbatim from the
  protocol's task section), `meta.json` (allow `money/{round.py,SPEC.md,NOTES.md}`,
  four checks, routes `code`/`spec`/`notes`), `fixture/` (s01's `README.md`,
  `money/SPEC.md`, `money/__init__.py`, `money/round.py`, `tests/test_round.py`, and
  the load-bearing empty `fixture/.git`; plus the new stub `money/NOTES.md`),
  `hidden/check_contract.py` and `hidden/check_spec_frozen.py` byte-identical to
  s01's, new `hidden/check_notes.py`, and `gold/` carrying s01's `round.py` plus the
  new `NOTES.md`. `s01` and `s03` were not edited. One reading was made here:
  `fixture/README.md` is s01's byte-identical copy, carried because the fixture is
  "s01's money package" and the protocol's bullet list names the package's files
  rather than the fixture's whole contents; it was not changed, and its sentence
  "when the code and the spec disagree, the code is the side that changes" is the
  same text s01 ran with.
- Well-formedness: `python3 bench.py selftest --task s04-late-note` ->
  `ok s04-late-note baseline=fail gold=pass checks=4/4`, `1/1 fixtures discriminate`.
  Baseline fails for the right reasons (`contract` 3/13 rows, `notes` no deciding
  row, `suite` FAILED (failures=1)); gold passes 13/13 with `changed_files ==
  ['money/NOTES.md', 'money/round.py']`.
- Rows: `results/e3/probe-omp-stale-rule{,-pre}.jsonl` (the 2 probe runs),
  `results/e3/s04-omp-stale-rule.shard{1,2,3}.jsonl` and its `-pre` twin (the raw
  shards), `results/e3/s04-omp-stale-rule{,-pre}.jsonl` (the merged cells the fold
  and `report` read), `results/e3/s04-cells-both.jsonl` (the pair, for `report`'s
  paired block), `results/e3/ledger-fold.jsonl` (the fold output, one row per run).
- The fold is `benchmarks/arm-bench/fold_ledgers.py`, predicates from the treatment
  pin `/tmp/tezgah-e2-main/hosts/omp/hook.py`.
- Landing: the commit `65c289f` ("bench: the E3 late-note task, the after_refusal
  fold, and the armed pair's rows") was rebased onto `c40abbd` and fast-forwarded
  into `benchmarks/lab` from inside the armbench worktree
  (`git -C <armbench> merge --ff-only benchmarks/e3-late-note`, `Updating
  c40abbd..65c289f, Fast-forward`, 26 files). `git -C <armbench> status --porcelain`
  is the identical 28 entries before and after (`diff` clean); the staged
  `PROVENANCE.md` of another session was not touched, and no branch was pushed
  anywhere.
- After the fast-forward, `tasks/s04-late-note/fixture/.git` (empty) was created in
  the armbench worktree, because git cannot carry a file named `.git`: without it a
  materialized fixture from a fresh checkout is unarmed (`meta.json`'s `arming_note`).
  `bench.py selftest --task s04-late-note` in that worktree then reports
  `ok s04-late-note baseline=fail gold=pass checks=4/4` and the gold tree grades
  `pass` with `changed_files == ['money/NOTES.md', 'money/round.py']`.
- Worktree: `/Users/rizax/orca/workspaces/tezgah/e3-bench` on
  `benchmarks/e3-late-note`; the kept run directories (52) and the two deployed arm
  directories live there under `benchmarks/arm-bench/.runs/` and
  `benchmarks/arm-bench/arms/`, both gitignored.
- This file's rows: `experiments/E3-late-note/results.jsonl`, one row per run (52:
  2 probe, 50 cell) with its cell, source file, arm, phase and every folded field.

## EXPLORATORY: the rule fired on this session's own turn (2026-09-19, after the block)

While writing this block's outcome up, the Stop rule refused the parent session's
turn with the `stale evidence` text, because `findings.md` and `log.md` had been
written with the write tools after the last green check. That is a live instance of
exactly what the block measures, and it is worth recording for two reasons.

- **The cost, paid for real: one re-run.** The refusal names what to do ("re-run
  the check over what is on disk now, or mark the claim doğrulanmadı"), the parent
  re-ran the checks, and the turn ended. Seconds, not a lost turn. This is the P4
  reading from the field rather than from a corpus.
- **The hole the block could not reach: the same write through the shell is
  invisible.** `_changed_write` counts `edit` rows, and an `edit` row is written
  only for a write tool; appending the same text with a heredoc records a `run`
  row, which the freshness predicate never looks at. So the rule fires on the
  write-tool route and sleeps through the shell route - the same
  `WRITE_TOOLS`/`BASH_TOOLS` split that C7 closed for `SKIP_TEST`, the attribution
  line and the secret scan, and it is the freshness rule's remaining blind spot.
  Recorded here rather than fixed: widening it is the same shape as C7 and belongs
  in a candidate, not in an observation.
