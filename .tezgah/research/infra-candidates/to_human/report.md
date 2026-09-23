# infra-candidates — which candidate additions to tezgah's infrastructure earn their weight

## Answer, in one paragraph

The line answered its question in a list and failed to answer it in a number, and the
difference is the report. As a **candidate list** it stands: `to_human/candidates.md`
ranks the gaps observed in this checkout on 2026-09-19, every candidate carrying a
`path:line`, a probe command and the change it implies, and the user picked P1 (fresh
evidence) from it - it landed as `d2f0cf4`, followed by a second batch (`8ec444c`) and
the round-2 verdicts. As a **measured outcome** it does not stand: the rate the line was
opened to move - whether the stale-evidence rule lowers the false-completion number, and
at what completion cost - is **unmeasured after four pre-registered blocks and $1.09 of
model spend**. E2 was void by its own F1 (the task did not elicit the shape), E2b was
void on a deployment boundary (the arms loaded no harness at all), E3-late-note was
armed on every row and its central prediction still failed (47 of 50 runs ended with
their newest accepted check *newer* than their newest changed write), and
E3-commit-on-red is void on an instrument boundary (no row in any cell ever wrote
`verify_fail`, because the gate records a check whose command contains a pipe as
outcome-unseen). What the line does hold is a mechanism verified through the real hook
on four adapters, a cost-to-completion comparison that showed no difference (17/25
against 18/25, inside the pre-registered 0.08 floor), one **free** field base rate from
the ledger corpus - 27 of 554 completion claims (4.9%) were allowed to end while the
stale shape was present - and the calibrated finding that the behaviour the rule
enforces is already a competent model's default, which is why the shape is hard to
elicit as well as hard to measure.

## What was established

- **The mechanism works, through the real hook.** E1 drives `hooks/projects-stop.py` and
  the omp, codex and cursor adapters with a seeded stale state: all four block with the
  `stale evidence` class, the verified tree and the no-op write are allowed, and the
  admission escape still works. That is a measured claim about reachability across four
  hosts, not a structural one (`experiments/E1-stale-evidence/analysis.md`).
- **The shape is not hypothetical.** Counted over the rows *before* each claim with the
  shipped `_last_pass` / `_last_change` / `_changed_write` predicates, over 1332 ledgers
  and the 554 completion claims in them: 31 claims were decided while a write that
  changed the tree sat after the newest passing check, and 27 of those were allowed to
  end - **4.9% of all completion claims**; 11 ledgers (0.83%) end in the shape (C32).
  This fold cost nothing and is the number the paid blocks could not produce.
- **The armed block measured, and its endpoints failed.** E3-late-note, 52 runs
  (2 probe + 50 cell), $0.276055, armed on every row (0 rows with `session_rows = 0`,
  a ledger for 25 of 25 rows per cell): the shape appeared in 0 of 25 runs on the arm
  carrying the rule and 1 of 25 on its parent against a pre-registered 20 of 25, and the
  rule fired 2 of 25 against 0 of 25 - both fires correct, both over a genuinely stale
  tree (C35).
- **The rule costs no measurable completion, in the one block that measured it.** 17 of
  25 against 18 of 25 pass (0.68 against 0.72), a 0.04 gap inside the pre-registered
  0.08 floor; E2's armed core cells were 25/25 against 25/25 (C36). This is "no
  difference shown", not equality - see the limits.
- **Why three blocks could not elicit the shape is behavioural, not instrumental.** In
  47 of the 50 armed runs the newest accepted check was newer than the newest changed
  write, because the models wrote the file and then re-ran the suite (C37).
- **E3-commit-on-red is void, and its void is itself the finding.** Four cells, 100 paid
  rows, $0.2031: `red_commit` is 0 of 25 on both `c01` cells and `order_fired` is 0 of 25
  on the armed arm, so F1 applies and nothing may be concluded about the commit-on-red
  rate. The cause is the gate's pipe rule - 1432 of the lab's 1684 `verify` rows are
  piped, and this model piped its suite runs, so the state the block measures was never
  written into the ledger (C40).
- **E2b bought the arming guard.** All 50 rows carry `session_rows = 0` and the fold
  found no ledger for 50 of 50 runs, so no bridge, gate, ledger or Stop rule loaded and
  `shape_present` is unmeasurable rather than zero (C33). The guard that refuses a block
  before spending on an unarmed arm was then verified against a reproduction of that
  state, and it found the same defect latent in a shipped arm (`orx-no-ponytail`) that
  had never run in this line (C38).
- **What the line's own work changed in the tree, each with its measurement.** The
  Stop rule's pass branch now requires the newest passing check to be newer than the
  newest changed write (`d2f0cf4`); the `rsync` direction, the `powershell`/`pwsh`
  matchers, the consent lease's workspace binding, the legacy `exit` tolerance and the
  `idx` fourth state are closed with their own before/after evidence; batch 2 added the
  first cross-event rule (`order`), the ledger miner (`tezgah-status --unclassified`,
  which named two effects nobody had listed), five remote-destructive effects, three
  shell twins and a live `out_bytes` (`8ec444c`); round 2 sized the three structural
  answers rather than guessing them (`round2/`).

## What the line does not show

- **The rate this line was opened to measure does not exist.** Four pre-registered
  blocks ran at it and none produced a usable numerator: E2 and E3-late-note could not
  elicit the shape at the pre-registered rate, E2b's arms were inert, and
  E3-commit-on-red's instrument never wrote the row it reads. No number in this report
  is a false-completion rate this line moved, and the $1.09 of model spend bought
  mechanism, base rate and calibration - not an effect size.
- **E3-commit-on-red's void is an instrument boundary, not a task result.** Because
  `hooks/tezgah_integrity.note_tool` records a piped check as outcome-unseen, no row
  carries `verify_fail`, and every variable the block was built to read (`order_fired`,
  `red_commit`, `no_red_commit`) is derived from a row that never appeared. With the
  pipe rule as it stands the commit-on-red shape is not visible to this harness at all;
  a re-run with the same design would be void again.
- **Every arm-bench row here is `fixture`.** The paid rows are runs against generated
  task fixtures (the `c01`/`c02`/`s01`/`s03`/`s04` tasks, named in each row's own
  `fixture` field) on real providers; they are evidence about the code path, never a
  property of a user's running tezgah. The only `real`-scope numbers are the two ledger
  folds (C02, C32) and both are counts of this machine's own traffic, not measurements
  of the change.
- **One model, one provider, one task shape, one prompt wording per block.** The
  provider also moved mid-line: the OpenRouter account held no credit, so
  E3-commit-on-red ran `deepseek/deepseek-v4-flash` on the direct provider, and a
  *level* is not comparable across the two routes (the arm-pair comparison was inside
  one route). The pass rates are not separated - Wilson intervals overlap almost
  completely (48.4-82.8% against 52.4-85.7%) - so the cost result is "no difference
  shown", not equality, and the `notes` checker is arm-symmetric but the arms are not
  balanced on it (A failed it 8 times, B 6).
- **The arms are the installed host at 04:40 with one line changed.** The `result_len`
  drift against today's installed host is a stated limit, and the reasoning that it
  cannot move this block's endpoints is an inference from the two pins' code, not a
  measurement. Whether omp loads the bridge from `PI_CODING_AGENT_DIR` is read at one
  remove: the rows' own `session_rows` and resolved ledgers.
- **Cost overran where the cap inherited a void.** E3-late-note spent $0.276055 against
  a pre-registered ~$0.16 estimate and the parent's $0.25 hard stop - the estimate came
  from E2b's own unarmed rows, an unarmed measurement read as a measurement, and the
  overrun is reported as an overrun. E2's six cell-runs cost $0.458764 of $0.63, E2b
  $0.148427 of $0.19, E3-commit-on-red $0.2031 of $1.00.
- **One row count in the line's own summary is wrong.** `findings.md` states E2b's rows
  as "All 100 rows" and `claims.jsonl`'s C33 repeats the 100;
  `experiments/E2b-spec-agreement/results.jsonl` holds 50 rows, all with
  `session_rows = 0` (the analysis says 2 cells, 50 runs). The arming fact and the void
  are unaffected; the count is not, and it is recorded in `to_human/review.json` rather
  than silently repaired. The same file's Open questions section still reads E2 as
  unrun.
- **H2-H6 stay open or negative.** The `out_bytes` decision (implement the guard or
  delete the claim), the nine class-less destructive commands' per-command policy call
  (two closed since, with tests; the local-only forms still ask nobody deliberately), the
  shell-parity gap's remaining shapes, the cross-session counters reader, and the
  declined indirect-action classifier (measured precision 0.167) are recorded with their
  numbers in `state.json` and `findings.md`. P2 and P3 were ranked in
  `to_human/candidates.md` and the user has not picked a second package; nothing in this
  report decides them.

## Where the artifacts are

`state.json` (question, phase, direction, the locked evaluation, H1-H6),
`log.md` (the decision timeline, the OpenRouter refusal, the E3 voids),
`findings.md` (the four sections, the round-2 summary, the verdict on the rule),
`claims.jsonl` (40 rows, every arm claim `scope: fixture`),
`literature/` (7 notes + `INDEX.jsonl`), `experiments/E0`-`E3-late-note`,
`round2/` (30 findings and three sized verdicts), `to_human/candidates.md` (the ranked
list the user picks from) and this report with its `to_human/review.json`.
