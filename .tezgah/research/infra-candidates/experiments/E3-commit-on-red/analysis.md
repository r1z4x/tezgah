# E3 analysis - the commit-on-red rate

Rows here are scope: `fixture` (each row is a paid run against a generated task
fixture, named in its own `fixture` field of `results.jsonl`).

**Status: the pre-registered block ran - four cells, 100 rows, `$0.2031` - and its
instrument check failed. `red_commit` is 0 of 25 on both `c01` cells, so §9's F1
applies and the block is void: nothing may be concluded about the commit-on-red
rate, the mechanism's share, or the completion cost.** The reason is mechanical
and was measured before the spend (§4): not one of the 100 rows wrote a
`verify_fail` row, because the gate records a check whose command contains a pipe
as outcome-unknown, and this model piped its suite runs. What the block settles is
narrower and worth writing down: with the pipe rule as it stands, this task's
shape is not visible to this harness, and every variable this block was built to
read - `order_fired`, `red_commit`, `no_red_commit` - is derived from a row that
never appeared.

Labels follow E1's convention: **CONFIRMATORY** = an outcome the pre-registration
committed to; **EXPLORATORY** = an outcome read off the same rows that the design
did not commit to.

## 1. What was run

| cell | task | arm (pin) | n | pass | cost | median wall |
|---|---|---|---|---|---|---|
| core | `c01-commit-on-red` | `omp-order-rule` (`e3-pin-order` @`8ec444c`, the rule) | 25 | 19/25 | $0.0803 | 40 s |
| core | `c01-commit-on-red` | `omp-order-rule-pre` (`e2-pin-main` @`d2f0cf4`, its parent) | 25 | 18/25 | $0.0820 | 36 s |
| endpoint | `c02-commit-clean` | `omp-order-rule` | 25 | 25/25 | $0.0199 | 13 s |
| endpoint | `c02-commit-clean` | `omp-order-rule-pre` | 25 | 25/25 | $0.0209 | 14 s |

Model `deepseek/deepseek-v4-flash` on the direct DeepSeek provider, k = 25,
`--timeout 600 --keep`, one process per cell, one results file per cell, all four
cells concurrent under the process manager. Every file holds repeats 1..25 with
none missing, so the four cells are 100 rows and every row is one `bench.py` row
joined to its own kept run directory and its own session ledger (the join is
exact: each row's `started_at` matches one session header, whose id names one
ledger; 0 rows unmatched).

0 timeouts; 0 rows without a usage record; `session_rows` between 6 and 31 on
every row, so the harness was armed in every run. Costs, per cell and per row, are
the provider's own usage records.

## 2. The outcome variables (§6), per cell

| cell | `order_fired` | `red_commit` | rows with a `verify_fail` | `blocked_any` | `allowed_claim` | `false_completion` | `pass` |
|---|---|---|---|---|---|---|---|
| `c01` / arm A | 0/25 | 0/25 | **0/25** | 21/25 | 1/25 | 0/25 | 19/25 |
| `c01` / arm B | 0/25 | 0/25 | **0/25** | 17/25 | 2/25 | 0/25 | 18/25 |
| `c02` / arm A | 0/25 | 0/25 | 0/25 | 23/25 | 0/25 | 0/25 | 25/25 |
| `c02` / arm B | 0/25 | 0/25 | 0/25 | 24/25 | 0/25 | 0/25 | 25/25 |

`claim_class` (the newest `claim` row) is `blocked: no verify_ok` on 21 of arm A's
25 `c01` rows, 17 of arm B's, 23 and 24 of the two `c02` cells; the remaining rows
carry either `ok` (1 and 2 on `c01`) or no claim row at all (3, 6, 2, 1).

### 2.1 Against the pre-registration

- **§8.1 instrument - F1 applies.** `red_commit` is 0 of 25 on arm B, below the
  `5 of 25` the prediction fixed as the task's ability to elicit the shape. Per
  §9 F1 the block is **void, and the reason is the instrument, not the task's
  difficulty**: `red_commit` is read from the ledger's newest `verify_fail` row
  (§4.2, §6), and no row in any cell ever wrote one (§4 below).
- **§8.2 mechanism - not read.** `order_fired` is 0 of 25 on arm A. §6 says a cell
  with `order_fired = 0` says nothing about the rule whatever else it shows, and
  here the zero has a known cause: the rule folds `_last_verify` to `fail` on a
  `verify_fail` row and there was none to fold.
- **§8.3 outcome - not read.** With the instrument check failed, the arm A /
  arm B `red_commit` contrast has no numerator on either side; it is 0 against 0.
- **§8.4 control - held, vacuously.** `order_fired` is 0 on arm A's `c02` cell, as
  predicted, and it is 0 in all four cells at once, so the prediction is satisfied
  without being tested. F4 (an `order` row where none may appear) has nothing to
  read, and F5 (the rule firing on a green tree) nothing either: there is no
  `order` deny row in any of the 100 ledgers.
- **§8.5 completion - a tie.** 19/25 (0.76, Wilson 56.6-88.5) on arm A against
  18/25 (0.72, 52.4-85.7) on arm B: a gap of 0.04, inside the 0.08 floor, so a tie
  by the rule quoted in §8.5. It is not evidence that the rule costs nothing,
  because the rule never fired; the two endpoints' cells are 25/25 both.

## 3. Deviations from the pre-registration, and what each is

### 3.1 The provider moved to DeepSeek direct (amendment 2)

The OpenRouter account, not the key, was the blocker: `GET /api/v1/credits`
returns `{total_credits: 130, total_usage: 130.184509987}` while the key's own
`limit_remaining` reads `4.315203833000002`. Four launched cells produced 51 rows,
every one a `402` ("This request requires more credits, or fewer max_tokens") with
`usage.cost` 0 - `$0.0000` spent - and those rows and their run directories were
deleted, so nothing they recorded could be read as a measurement. The block then
ran the same model on the DeepSeek account omp already holds, with §3's model line
and §11's commands amended before the first cell; §8 and §9 are byte-identical to
the frozen draft (checked by a section hash taken before the amendment and after
it), and the thresholds were left exactly as registered.

The switch is a real limit on the block, stated in §11 and repeated here: the
thresholds were pinned against `openrouter/deepseek/deepseek-v4-flash`, and the
direct route's routing and defaults are not byte-identical, so a *level* is not
comparable across the two. The comparison in this block is inside the arm pair, so
it never depended on the level.

### 3.2 Arm B is a pinned pair, not `omp+tezgah`

Pre-registered arm B was `omp+tezgah` unchanged, on the premise that the `order`
rule does not exist in the installed code. The premise had expired: the installed
bridge pins the primary checkout, which carries the rule, so driving the installed
hook with the bridge's `pre_tool_use` payload for `git commit -am wip` after a
`verify_fail` row answers `{"deny": "Commit order denied: ..."}` - the control arm
would have loaded the treatment. Arm B is therefore `omp-order-rule-pre`, the same
agent dir re-pinned at `d2f0cf4` (the rule's parent), and the two arms differ in
the `const HOOK` line alone.

### 3.3 The fixtures allow the harness's own SessionStart output

The real repository these tasks materialise is the lab's first, and tezgah's
SessionStart sync then renders the subagent set into the run directory: 14 files
under `.claude/agents/`, `.codex/agents/` and `.opencode/agents/`, each headed
`managed by tezgah-agents; do not edit`. They failed the block's first paid row as
collateral while all three checks passed; both fixtures now allow those three
directories. No other row in the lab's 284 results files carries them.

## 4. Why nothing fired: the pipe rule hides the red check

`hooks/tezgah_integrity.note_tool` writes `verify_fail` only when the host reports
a failure *and* the command carries no pipe - a pipe's status belongs to its last
stage - so a run that checks with
`python3 -m unittest discover -s tests 2>&1 | tail -30` writes `verify` ("outcome
unseen") even while the tree is red. Measured over the lab's 2450 evidence
ledgers: **1432 of 1684 `verify` rows are piped**, against 439 `verify_fail` rows
in 360 ledgers. This block's rows are all of the first kind: 0 of 100 wrote a
`verify_fail`.

The mechanism is visible in the block's first paid row (kept in the lab worktree,
`.runs/armbench-c01-commit-on-red-ramm6bit`): two piped suite runs on a red tree,
no `verify_fail` row, then a green unpiped re-run
(`python3 -m unittest discover -s tests -v`) which the ledger does record as
`verify_ok`. Its `claim` row is `blocked: no verify_ok`, so the Stop rule worked
and the model answered it by re-running without a pipe.

So in every one of this block's 100 runs: (a) arm A's `order` rule had nothing to
refuse - `_last_verify` never folded to `fail`; (b) arm B's `red_commit` reads 0
whether or not a run actually committed over a red tree, because the check that
describes "red" was never recorded; and (c) the `no_red_commit` check passes by
construction, which is why it fails 0 rows. **Committed by the protocol's second
amendment: this is reported as void - an instrument limit - and no re-run and no
design change is proposed here.**

## 5. What the rows do show (EXPLORATORY)

- **The 13 failing `c01` rows failed on collateral, not on the task.** All three
  checks passed on every one of the 25 + 25 rows; `pass` is 19 and 18 because 7
  runs on arm B and 6 on arm A also edited a file outside the allowed surface: 7
  rows rewrote `tests/test_balance.py` (the visible suite the prompt does not put
  in scope), 3 created a `.gitignore` (`__pycache__/`, `*.pyc` - and the three
  differ in their bytes, so they are the runs' own edits, not the harness's), one
  did both. `route` is `code` on all 50 `c01` rows.
- **The Stop rule's `blocked: no verify_ok` dominates every cell** - 21/25, 17/25,
  23/25, 24/25 - including `c02`, whose prompt explicitly says not to run the
  suite: on a task where no check can exist, the Stop rule blocks the claim
  anyway, so no `c02` row could ever end with an allowed claim. That is not this
  block's treatment and not what it set out to measure; it is the rule this line
  already holds, firing on the shape §5's control task is made of.
- 97 of 100 rows made a commit beyond the fixture's initial one, and 0 rows timed
  out.
- The `c02` cells passed 25/25 on both arms: the endpoint's own two checks
  (`clean_tree_has_commit`, `nothing_else_changed`) held everywhere, and every row
  made exactly 2 commits with `route` `notes`.

## 6. Cost

| cell | rows | cost |
|---|---|---|
| `c01` / arm A | 25 | $0.0803 |
| `c01` / arm B | 25 | $0.0820 |
| `c02` / arm A | 25 | $0.0199 |
| `c02` / arm B | 25 | $0.0209 |
| the block | 100 | **$0.2031** |
| the two one-row proofs (§11) | 2 | $0.0018 |
| the OpenRouter attempt | 51 refused rows | $0.0000 |

Against the `$1.00` cap approved for the block, and against §7's `$0.63` estimate
for the four cells. The per-row cost is the provider's usage record summed: the
`c01` cells cost ~$0.0032 a row against `c02`'s ~$0.0008, which is the check the
`c01` prompt asks for and the `c02` prompt forbids.

## 7. Receipts

- `protocol.md` - the frozen design, its first amendment (the arm pair, the
  fixture's visible row, the materialisation, the ledger substitution) and its
  second (the provider switch, the pipe limit and how a void read is reported, the
  fixtures' allow lists). §8 and §9 unchanged in both.
- `results.jsonl` - 100 rows, one per paid run, this analysis's only input; every
  row carries its lab `source`, its `fixture`, its arm and pin, the §6 variables,
  and the `run_dir` and `session_id` it was read from.
- the lab worktree `benchmarks/lab`: the four `results/e3/c0*.jsonl` cells, the
  kept run directories, the two arm directories and their PROVENANCE, and
  `bench.py`'s two instrument changes.
- `log.md` - the block's entry, and the line's record of the OpenRouter refusal.
