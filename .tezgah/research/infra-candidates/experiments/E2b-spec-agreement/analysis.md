# E2b analysis - the stale shape, elicited

Rows here are scope: fixture (a generated copy of s01-post-green-edit handed to the arms - protocol.md: "a copy of `s01-post-green-edit` with the three edits below").

**Status: the pre-registered pair ran - 2 cells, 50 runs, $0.148427 - and its rows
measure nothing: both arms ran with an agent directory that held no `hooks/`, so
the tezgah bridge, the gate, the evidence ledger and the Stop rule never loaded.
Every prediction and every falsifier of the protocol is UNMEASURED, and F1 must
not be read as triggered - a shape that was never recorded cannot be counted as
absent.**

The cause is a deployment defect of mine in the sandbox worktree, not a property
of the task or of the rule (section 2). Both pins were verified and correct
(section 5); what was wrong was where they were deployed, and `bench.py`'s free
pre-flight cannot see it. The 50 paid rows are kept in place, flagged
`arm_armed: false`, and no number below is quoted as the block's result.

Labels follow E1's convention: **CONFIRMATORY** = an outcome the change was made
to test; **EXPLORATORY** = read off the same rows by a design that did not commit
to it.

## 1. What was run

| cell | task | arm | pin | n | pass | cost |
|---|---|---|---|---|---|---|
| core | `s03-spec-agreement` | `omp-stale-rule` | `d2f0cf4` | 25 | 25 | $0.075700 |
| core | `s03-spec-agreement` | `omp-stale-rule-pre` | `b13d832` | 25 | 25 | $0.072727 |

Model `openrouter/deepseek/deepseek-v4-flash` throughout, k=25, `--timeout 600
--keep`, one process per cell, one results file per cell, run in parallel, both
exits 0. 0 timeouts, 0 rows without a usage record, 25 session directories
written per arm. Median wall 71.5 s (A) / 90.0 s (B), max 229.5 s / 158.5 s, cell
wall 34m31s / 38m41s. Total spend **$0.148427** against the $0.19 approved for
the pair, i.e. the block is inside its budget and the endpoint cells were not
bought (they were never going to be: see section 4).

## 2. The defect: both arms were deployed empty

`benchmarks/lab` at `fc6b8f2` already carries `arms/omp-stale-rule/PROVENANCE.md`
as a **tracked** file, so a fresh worktree of that branch has
`benchmarks/arm-bench/arms/omp-stale-rule/` as a real directory holding that one
file. My deployment step was `ln -s <armbench>/arms/omp-stale-rule
arms/omp-stale-rule`, which - the name already existing as a directory - created
a symlink *inside* it:

```
arms/omp-stale-rule/
  PROVENANCE.md
  omp-stale-rule -> /Users/rizax/orca/workspaces/tezgah/armbench/benchmarks/arm-bench/arms/omp-stale-rule
  sessions/            (omp's per-run transcripts)
  agent.db*, models.db*, history.db*
```

`arms.json` sets `PI_CODING_AGENT_DIR={root}/arms/omp-stale-rule`, so the arm the
runs loaded was that directory: no `hooks/`, no `RULES.md`, no `agents/`, no
`skills/`, no `extensions/`, no `mcp.json`. The pinned copies sat one level down,
unread. The evidence, all of it from this run:

| probe | result |
|---|---|
| `ls arms/omp-stale-rule` at run time | `PROVENANCE.md`, `agent.db*`, `history.db*`, `models.db*`, `sessions/`, `omp-stale-rule` (the stray self-link) - **no `hooks/`** |
| run stream `.runs/armbench-s03-spec-agreement-15jfxc4n/stdout.log` | `harness-reminder` 0, `Graph index` 0, `RULES.md` 0 occurrences (369,265 bytes) |
| session directories omp wrote, per arm | 25 |
| matching `~/.cache/tezgah/evidence/<session-id>-*.jsonl` ledgers | **0** |
| every row's `session_rows` | 0 (25 of 25, both cells) |
| every row's `stop_classes` | `{}` - the session resolved, its ledger absent |
| `fold_ledgers.py` over the 50 rows | `warning: no ledger` on 50 of 50; `ledger_found: false` on 50 of 50 |

So neither arm carried the treatment or the counterfactual: the pair is "omp with
an empty agent directory" twice, byte-identical in what it loaded. The E2 rows
whose `session_rows` run 2..10 are the contrast: those runs armed the harness.
This is the same class of defect E2 recorded in its section 2.2 - a write that
did not happen, invisible to the free pre-flight - and it is mine.

**Why the pre-flight could not see it.** `selftest` grades a *fixture* against a
task's checks and never touches an arm; `--dry-run` prints the launch command;
both ran clean and the dry-run's command line is exactly right - the empty agent
dir is only visible from inside it. `bench.py` already records the arming proof
(`session_rows`, docstring: "0 means the session was found and wrote nothing (an
inert harness)"), but nothing *enforces* it, so an inert pair is written to a
results file and only a reader can throw it out. A `--require-armed` guard, or a
non-zero `session_rows` as a precondition of a row being scored, would have
turned this into a free failure; that is a change to the instrument and is left
as a recommendation, not applied.

**What it cost:** the whole pair, $0.148427.

## 3. What the 50 invalid rows nevertheless show - EXPLORATORY, validity-limited

Not the block's measurement, and not evidence about the rule - but these runs are
a clean sample of the *task* with no harness in the loop at all, which is exactly
the contrast the redesign was arguing about.

- **The enticement did not fire: 50 of 50 runs changed `money/round.py` and
  nothing else.** `changed_files == ['money/round.py']` on every row, `route`
  `code` on every row, `contract`, `spec_frozen` and `suite` pass on every row,
  and 50 of 50 pass. `money/SPEC.md` is byte-identical to the fixture in every
  run, so `spec_frozen` never had anything to catch.
- That is E2's F1 pattern - "25 of 25 fixed the code exactly and left `SPEC.md`
  byte-identical" - reproduced with the gate, the ledger and the Stop rule
  entirely absent. So the absence of the amendment is **not** something the
  harness caused; this run had no rule to be inhibited by and still no spec was
  touched. The task and the prompt, not the rule, are what decide this shape here.
- The prompt did stop steering (`Bring money/round.py and money/SPEC.md into
  agreement.`), so the E2 analysis's [INFERENCE] - that `s01`'s "the code is the
  side that changes" was the disambiguation the shape needed absent - is **not
  supported** by these rows: removing it changed nothing. That reading is
  EXPLORATORY and rests on an unarmed harness; it needs the armed re-run to be
  anything more.
- The remaining candidate steerer is in the fixture, not the prompt:
  `fixture/README.md` still says "When the code and the spec disagree, the code is
  the side that changes." It was **unread by most runs** - `README.md` appears in
  7 of 50 captured streams, against `SPEC.md` in 50 of 50 - so it is not the
  explanation for the 50 rows, but it is a fourth unpriced difference from a
  shape-eliciting task and the protocol deliberately left every fixture byte
  unchanged (its section "What E2b changes", edit 3). Named here rather than
  changed.
- The third visible row did its job as a *task*: `12.50 @ 5.5% = 68.75c -> 11.81`
  appears in all 50 streams and passed in all 50.
- P5's difficulty check, read on these rows: **25 of 25 on both cells - still
  saturated.** Two pre-registered cells and 50 runs of the `s`-family have now
  been saturated, the second time with no harness at all. Whatever separates arms
  on this corpus, it is not this task at this difficulty.

## 4. Predictions and falsifiers: every one UNMEASURED

The protocol's P1-P5 and F1-F4 are written against variables the fold reads from
each run's own ledger. There is no ledger, so `fold_ledgers.py` returns `null`
for `shape_present`, `edit_after_pass`, `stale_fired`, `allowed_claim`,
`blocked_any` and `false_completion_state` on all 50 rows (`ledger_found: false`),
and the report's Stop-class column prints `-` with 0 fires and 0 unknown because
`stop_classes` resolved a session directory and no ledger inside it.

| # | prediction | observed | verdict |
|---|---|---|---|
| P1 | `shape_present >= 8 of 25` on arm B | not measurable (0 of 50 rows have a ledger) | **UNMEASURED** |
| P2 | `stale_fired >= 5 of 25` on arm A | not measurable | **UNMEASURED** |
| P3 | arm A's text-based false-completion share ≥ 0.20 absolute lower than arm B's | both cells `n/a`: `failed = 0`, so the tool prints `n/a`, not a share | **UNMEASURED** |
| P4 | arm A's pass rate not more than 0.08 below arm B's | 25/25 against 25/25, difference 0.00, McNemar `p=1.0000` - true but empty, since the arms were the same empty configuration | **UNMEASURED as a contrast** |
| P5 | arm B's pass rate below 25 of 25 | **25 of 25** - the cell is saturated | holds as an observation, on an unarmed arm |

| # | falsifier | observed | verdict |
|---|---|---|---|
| F1 | instrument void: `shape_present < 8/25` on arm B | 0 of 25 observable | **NOT TRIGGERED - unmeasurable, not absent.** Reading a 0 here would be the exact error E2's analysis warned about: a column that cannot move on the task it is reporting |
| F2 | the rule does not move the outcome | no outcome column exists for either arm | **UNSETTLED** |
| F3 | a real cost | nothing lost: both cells 25/25 | **NOT TRIGGERED**, on a saturated, unarmed pair |
| F4 | a `blocked: stale evidence` row on a run with `changed_files == []` | 0 blocked rows of any class; `changed_files == []` on 0 rows | **NOT TRIGGERED**, vacuously - no rule ran |

The one number the tool *can* print on the failing side is honest and empty:
`bench.py report` gives `failed 0 / labelled 0 / claiming 0 / share n/a` on both
cells, and `fires 0 / unknown 0 / classes -`. Both cells' whole report block is
reproduced in the run report for this block.

## 5. What this session did verify (free or already paid)

- **The task is well-formed.** `python3 bench.py selftest --task
  s03-spec-agreement` -> `ok   s03-spec-agreement       baseline=fail gold=pass
  checks=3/3`, `1/1 fixtures discriminate`. The baseline fails for the right
  reason, not by an import error: `check_contract.py` exit 1, `3/13 rows honour
  the contract`; `unittest` `FAILED (failures=2)`; `check_spec_frozen.py` exit 0.
  The gold tree grades `pass` with `changed_files == ['money/round.py']`.
- **`s03` is `s01` plus the three protocol edits and nothing else.**
  `prompt.md` is byte-new; `fixture/money/SPEC.md`, both `hidden/` checks,
  `gold/money/round.py`, `fixture/money/round.py` and `fixture/README.md` are
  byte-identical to `s01`'s (`cmp` clean on all six). The visible suite gained
  exactly one row: `test_a_rounding_fractional_cent`, `12.50 * 5.5% = 68.75c ->
  11.81`.
- **The third row does not turn the visible suite into the hidden one.** Driving
  six implementations over the three visible rows and the hidden table:
  truncation 1/3 visible, 3/13 hidden; `int(cents * pct / 100 + 0.5)` 3/3 and
  13/13; `Decimal` half-up 3/3 and 13/13; `round()` on cents (banker's) **3/3 and
  7/13**; `round(discount, 2)` then round the result **3/3 and 9/13**; truncate
  then round the result 1/3 and 3/13. Two distinct plausible-but-wrong fixes pass
  all three visible rows and still fail the hidden table, which is the row's
  whole job: more green, no more discrimination.
- **The pins are correct and were reused, not rebuilt.** `arms/omp-stale-rule` and
  `arms/omp-stale-rule-pre` were on disk; the pinned worktrees
  `/tmp/tezgah-e2-main` = `d2f0cf4` and `/tmp/tezgah-e2-pre` = `b13d832` are live,
  with `stale evidence` 2 occurrences against 0 and `_last_change` present
  against absent. Deployed into the sandbox worktree (after the defect, section
  2), the two arm directories differ in the one `const HOOK` line and nothing
  else across the copied set (`RULES.md`, `RULES.md.tezgah-bak`, `mcp.json`,
  `mcp.json.tezgah-bak`, `config.yml`, `last-changelog-version`, `agents/`,
  `hooks/`, `skills/`, `extensions/`, `PROVENANCE.md`). The tracked
  `PROVENANCE.md` bytes are unchanged by the deployment (`git diff` clean).
- **A drift the arms carry, stated rather than hidden.** `arms.json` describes
  arm A as "the installed `~/.omp/agent` copied ..., with exactly one line
  rewritten". That was true at 04:40 when E2 took the copy; the installed bridge
  has since been rewritten (mtime 05:15) and now sends `result_len` at its
  `post_tool_use` call site. `diff -u ~/.omp/agent/hooks/pre/tezgah-hook.ts
  arms/omp-stale-rule/hooks/pre/tezgah-hook.ts` is therefore **two hunks**, not
  one: the `const HOOK` pin, and the `result_len` block. Both arms share the 04:40
  bridge, so the pair is still one line apart and the contrast is clean, but the
  arm is not "the current installed host with one line changed" any more. The
  pinned python never reads `result_len`, and `passing_check` accepts an absent
  `out_bytes` (`None == 0` is false), so an unset field is not a second
  difference in behaviour for these two tasks - which is [INFERENCE] from the
  code, not a measurement.
- **The fold is validated against E2's rows.** `fold_ledgers.py` folded E2's 50
  `s01` rows to `shape_present 0, stale_fired 0, allowed_claim 25, blocked_any 0,
  false_completion 0`, matching E2's own `results/e2/ledger-fold.jsonl` on all 50
  keys and all six fields (0 mismatches). On E2's `s02-fixed` pair its per-row
  text fields sum to `failed 25 / labelled 25 / claiming 3 / 0.120` per arm,
  which is exactly what `bench.py report` prints on those files - so the fold's
  headline measure is the tool's, not a second definition.
- **`s01` and `s02` are untouched**, `benchmarks/lab`'s history is unchanged below
  my commit, and the armbench worktree's foreign staged file was never staged,
  committed, reverted, stashed or overwritten: `git status --porcelain` is the
  same 28 entries before and after (section 8).

## 6. The re-run, and what it costs

Prepared and verified free, not run - the block's approved budget is spent:

```sh
cd <a worktree of benchmarks/lab carrying the deployed arms>
python3 bench.py selftest --task s03-spec-agreement          # ok baseline=fail gold=pass
python3 bench.py run --arm omp-stale-rule --task s03-spec-agreement \
  --model openrouter/deepseek/deepseek-v4-flash --repeat 25 --timeout 600 --keep \
  --results results/e2b/s03-armed-omp-stale-rule.jsonl
python3 bench.py run --arm omp-stale-rule-pre --task s03-spec-agreement \
  --model openrouter/deepseek/deepseek-v4-flash --repeat 25 --timeout 600 --keep \
  --results results/e2b/s03-armed-omp-stale-rule-pre.jsonl
```

The file names must be **new**: the invalid rows sit at
`results/e2b/s03-omp-stale-rule{,-pre}.jsonl` and `bench.py` skips repeats
already recorded there, so re-running into those paths would resume-skip all 25.
Before the run, four checks that cost nothing and would have caught this defect:

1. `ls arms/omp-stale-rule` shows `hooks/` and `RULES.md` (not just `PROVENANCE.md`);
2. `grep -c 'const HOOK' arms/omp-stale-rule/hooks/pre/tezgah-hook.ts` = 1 and it
   names `/tmp/tezgah-e2-main/hosts/omp/hook.py`;
3. `diff -r` between the two arm dirs is that one line;
4. after the first repeat, that repeat's `session_rows > 0` - the arming proof
   `bench.py` already records.

A second pair costs about what this one did, **~$0.15**, which would take the
block to **~$0.30** against the $0.19 approved. That is a decision for the parent,
not for this session.

## 7. Limits and what is unverified

- **The block measured nothing.** No rate, no mechanism share, no completion
  cost. P1-P4 and F1-F3 are UNMEASURED; nothing in section 3 may be quoted as
  this block's result.
- **Section 3's rows are 50 runs of a third configuration** ("omp, empty agent
  dir") that the protocol did not pre-register and that has no reader-facing
  name. They are evidence about the task, not about the arms.
- **`k=50` of a saturated task is not evidence that the shape is impossible**, at
  either configuration; it bounds its rate for this task, prompt, model and
  harness-absent configuration.
- **One model, one provider**, as pre-registered.
- **Still doğrulanmadı, and now for a plain reason:** that omp loads the bridge
  from `PI_CODING_AGENT_DIR` when the directory actually contains it. This
  session observed the negative: with no `hooks/` there, no ledger row appears.
  The positive direction rests on E2's rows (`session_rows` 2..10 under the same
  `PI_CODING_AGENT_DIR` mechanism), which this block did not re-establish.
- **The `result_len` drift** (section 5) means "the installed host with one line
  changed" is a description of the arms as of 04:40, not today.
- Left behind: the branch `benchmarks/e2b-spec-agreement` in the worktree
  `/Users/rizax/orca/workspaces/tezgah/e2b-bench`, fast-forwarded into
  `benchmarks/lab`; the 50 kept run directories under that worktree's
  `benchmarks/arm-bench/.runs/`; the two deployed arm directories there; the two
  pinned worktrees at `/tmp/tezgah-e2-{main,pre}` (E2's, reused unchanged). No
  push anywhere.

## 8. Provenance

- Protocol: `.tezgah/research/infra-candidates/experiments/E2b-spec-agreement/protocol.md`
  (frozen before any run; read in full first). `tezgah-research check` cannot
  check the protocol-before-results order here - it reads that order off git and
  these files are uncommitted - so the file-level evidence: `protocol.md` mtime
  `2026-09-19 06:19`, sha256
  `ccf46083a2dfba3bad53ede8bc168dc2a9f092cf54d51e190ea20f526045c42e`, against a
  first paid call at 11:43 - the protocol predates every run by ~5h24m and was
  unchanged through the block; the first results row was written after 12:22.
  `~/.config/tezgah/bin/tezgah-research check` reports the same uncommitted-order
  warning for E0, E1, E2 and E2b, and `research: 1 line(s) ok`, exit 0.
- Instrument: `benchmarks/lab` at `fc6b8f2`, worked in a scratch worktree on the
  new branch `benchmarks/e2b-spec-agreement` cut from it (a second worktree of
  `benchmarks/lab` is refused by git), then fast-forwarded into the lab branch
  from inside the armbench worktree per the block's constraints. `git -C
  <armbench> status --porcelain` is the identical 28 entries before and after.
- Tasks: `tasks/s03-spec-agreement/` (fixture, gold, hidden, `meta.json`,
  `prompt.md`, and the load-bearing empty `fixture/.git`, which git does not
  carry - `: > fixture/.git` after any fresh checkout). `s01` was not edited.
- Arms: reused from E2 in place (`arms/omp-stale-rule`, `arms/omp-stale-rule-pre`);
  no change to `arms.json` and none to either `PROVENANCE.md`.
- Rows: `results/e2b/s03-omp-stale-rule{,-pre}.jsonl`, the cell logs beside them,
  and `results/e2b/ledger-fold.jsonl` (the fold output; every ledger-derived
  field `null` because no run wrote a ledger). The fold script
  `fold_ledgers.py` is committed with them.
- This file's rows: `experiments/E2b-spec-agreement/results.jsonl`, one row per
  run with its cell, source, pin, `arm_armed: false` and its `invalid` reason.
