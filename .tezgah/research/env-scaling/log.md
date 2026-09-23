# Log

Newest last. One line per decision, dead end or pivot, with the evidence that drove it.

- 2026-09-20 bootstrap. `bin/tezgah-research init env-scaling --question 'What does post-training
  environment scaling mean in 2026...'`. No `--tracked`: the line's own rule is temporal only for
  an experiment pair, and this line runs nothing, so nothing needs the protocol order to be
  decidable. The init printed the TRACKING note; left as it stands.
- 2026-09-20 read before searching, as the contract asks: `docs/research.md` (the layout, the
  refusal and warn lists, the exact shape of a claim and an INDEX row), `plans/open/004` (the
  repository's own failure-shape numbers), and the notes under `.tezgah/research/*/literature/`
  (2608.19880, 2604.25850, 2606.10106, 2609.11677, 2609.20519, 2609.20804, 2609.00069,
  benchmarks/arm-bench). Decision: cite them and do not re-derive; the only note re-written here
  is EnvHarness, because 2608.19880 is this line's central source and the other line's note is
  read for the boundary argument it was written for.
- 2026-09-20 dead end: `orx discover openalex "environment scaling post-training language model
  agents"` returned ChatGPT/USMLE/survey papers, not the line of work. Decision: OpenAlex
  discovery is not usable for this term in 2026; alphaXiv keyword discovery found every source
  that mattered, and `orx paper <id>` plus the arXiv abs page gave the record for each.
- 2026-09-20 dead end: the fourth required source class was expected to be editorial - a position
  piece arguing quality over count. It is not: 2608.03571 measures the non-monotonicity (30
  selected environments beating 170), 2608.22631 measures the corpus defect rate (over 60%
  defective), 2607.28074 measures depth against count on the same domains, and ReAgent measures
  the construction bias. Decision: the counter-argument is filed as four measured sources.
- 2026-09-20 source set closed at 13 (12 papers plus the repository's own arm-bench README as the
  grey practice source). ReAgent is the one source with no arXiv or OpenAlex record: the
  alphaXiv listing gives the full report and preprints.org lists the same title as manuscript
  202608.1575, which returned HTTP 403 from this machine. It is filed grey with that stated.
- 2026-09-20 no node, no run. `orx` is installed and its manual was loaded first (`orx skill`);
  a literature screen has no run command, so nothing was created through `orx create-experiment`
  and `researcher`'s experiment-tree rules have nothing to apply to. The empty `experiments/`
  directory `init` scaffolded was removed again (`rmdir`), the assignment being explicit that no
  run happened and none should be implied; `check` handles its absence (`_check_experiments`
  returns on the OSError). `predictions.jsonl` was not created: a prediction row has to name a
  metric and a value to move, and this line moved no number.
- 2026-09-20 evaluation locked to the screening discipline rather than to a behavioural metric:
  the line has no model, no run and no node, so the honest criterion is "13 notes, 13 INDEX rows,
  zero refusals under --strict". Recorded in `state.json` with the environment naming no model.
- 2026-09-20 claims filed through `bin/tezgah-research claim`, not by hand: 15 rows, ids C01-C15,
  kinds literature/12, code/2, derivation/1, and every row declares `scope: derived` because no
  row here rests on a run in this line. The writer accepted all 15; the first attempt was refused
  for a missing `provenance`/`status`, which is the write path agreeing with the checker.
- 2026-09-20 the read that changed the answer: EnvHarness's own scaling curve (47.67% to 54.79%
  for reshaped environments while original and generated ones flatten) and Agent-World's count
  curve (18.4% to 38.5% over 1978 environments, elbow at a few hundred). Both were expected to be
  absent from the literature; both are measured. That is why findings.md states the relation as
  positive but saturating instead of as unmeasured.
- 2026-09-20 closed. `check env-scaling` and `check env-scaling --strict` both exit 0; the only
  warning the strict pass closes is the one a line with no experiment cannot avoid, and none
  remains. Report written to `to_human/report.md` with its limits section, and the six-dimension
  review to `to_human/review.json`.

- 2026-09-22 close-out pass, the line already concluded: the report's limits section now names the
  adaptation half as **unrun**, with the branch reason spelled out - both halves of the answer are
  design, not execution, and the environment half's target `benchmarks/arm-bench` is not in this
  tree at all: it lives on branch `benchmarks/lab`, while this branch holds only
  `benchmarks/codegraph-bench`, so the task corpus, its pre-registrations and its attribution gate
  are absent here and there was no artifact for a run to act on. The session-side half is reachable
  without a run and was still not exercised in this line. Evidence: `git ls-tree -r benchmarks/lab`
  names `benchmarks/arm-bench/PREREGISTRATION-E4c.md` etc.; `git ls-files benchmarks` on this
  branch names only `benchmarks/codegraph-bench/probe.py`.
- 2026-09-22 **no superseding claim was added, decided after reading all 15 rows.** C15 is the only
  claim about "the adaptation" and it asserts capacity, not an executed change ("can act on the 3
  non-saturated pilot tasks", "can move the refusal counts"), declares `scope: derived`, and its
  proof's `findings.md` names the branch the corpus lives on - so no row reads as if the adaptation
  had been established, and the mechanism the layer provides for an established-but-unrun change is
  not the right instrument here. A supersedes link would also have been refused by
  `bin/tezgah-research check env-scaling --strict` by design (the checker flags any supersedes
  relation), which would have falsified this line's own locked evaluation - 13 notes, 13 INDEX rows,
  zero refusals under `--strict` - by editing a criterion after the fact. What was recorded instead
  is the real defect: the review gains a major finding that C15 names `benchmarks/arm-bench` without
  the branch qualification, which lives only in `findings.md`. No claim row, note or INDEX row was
  edited, and nothing new was measured: no model call, no run, no money.
- 2026-09-22 the adaptation half is **built, pre-registered and unrun, blocked on account credit**.
  Read before writing, per the contract: `benchmarks/arm-bench` on branch `benchmarks/lab`
  (`git ls-tree -r benchmarks/lab` for the corpus; `README.md` for the task format, the
  well-formedness rule, the accounting rules, the freeze rule and the hard family's calibration
  lesson; `PREREGISTRATION.md` sections 2-5 for k, accounting and stopping; `PREREGISTRATION-E8.md`
  for the gate a task entering a round must answer, its power table and its cost basis), and the
  branch's own result files for the one cell that sits at the floor. Chosen change, the cheapest
  shape item (a) names: the corpus gains `tasks/h06-exact-split-sum`, a `hidden-invariant` task
  whose hidden check is a **swept property** over the documented split contract - 2,828 cells, one
  failing cell fails the check, the five clauses determine the answer uniquely - with the contract
  in the prompt and the visible suite green before and after (h02's design rule). Free proof, run:
  `selftest --task` ok (`baseline=fail gold=pass checks=2/2`), corpus `48/48` (47/47 before it),
  `preflight` True for the arm, `--dry-run` prints the exact command, and the check's own
  route-separation sweep: five plausible wrong implementations fail 1,239-1,784 of 2,828 cells
  while two correct ones pass every cell. The one cell was fixed at `opencode-bare` (the floor
  member: on deepseek the sibling `h02` reads opencode+tezgah 5/5 against opencode-bare 0/5),
  k=12, `openrouter/deepseek/deepseek-v4-flash`, ~$0.08. **No run happened**: the OpenRouter
  account's credit is exhausted (`total_credits 130` against `total_usage 130.18`; the key's
  visible `limit_remaining 4.3152` is a sub-limit, not account credit), and a sibling session on
  the same account had every row return HTTP 402 with $0 spent. Recorded as C16 (`untested`), one
  line in the report's limits, and the round blocked in section 13 of the lab's
  `PREREGISTRATION-H06.md`. Spent: $0.00. Protocol:
  `experiments/E1-env-adapt-h06/protocol.md` - written, uncommitted, the parent's to commit (the
  order rule needs it in history before any results); the line is therefore open again on its own
  `_open_reasons` rule, which is the honest state.
- 2026-09-22 provider switched to DeepSeek direct for the E1 cell (parent's decision after the
  OpenRouter account ran out: `total_credits 130` / `total_usage 130.18`). Amendment 1 written into
  both files before any scored row: `experiments/E1-env-adapt-h06/protocol.md` section 12 and the
  lab's `PREREGISTRATION-H06.md` section 14. Model identity `openrouter/deepseek/deepseek-v4-flash`
  -> `deepseek/deepseek-v4-flash` (`opencode models deepseek` lists it; the provider is
  authenticated in the host's own store), arm/task/k/endpoints/thresholds unchanged, and the
  comparison stays within the same arm - the provider is a named confound, not a second factor.
  Balances read for the amendment: `api.deepseek.com/user/balance` -> `is_available true`,
  `total_balance 8.00 USD`. Path probe, one row, kept apart from the cell at
  `benchmarks/arm-bench/results/h06/opencode-bare-proof.jsonl` on the lab branch: `pass`, both
  checks green, route `code`, `changed_files == ["inventory/allocate.py"]`, no collateral, 21.2 s,
  `usage.cost` $0.006218, `host_version 1.18.31` - the path works, and it is the first signal
  *against* prediction 1 (the bare arm solved it on the direct provider), which is reported rather
  than folded into the thresholds. Round ceiling now $0.20; spent so far $0.006218 (the probe),
  cell rows 0 of 12.
- 2026-09-22 E1 ran and **refuted both of its own predictions**. The one cell (opencode-bare on
  h06-exact-split-sum, deepseek/deepseek-v4-flash, k=12, $0.20 ceiling) read **12/12 passes**,
  **0 rows** in the green-suite-wrong-contract shape, both checks green on every row, route `code`,
  no collateral, no timeouts, CPS $0.006389, cell spend $0.076672 and $0.082890 for the 13 rows
  filed (12 cell + 1 probe); the protocol's own falsifier (>=7/12 passes -> the task is not a
  discriminator) fired, P1 and P2 are falsified and P3 held. The probe row had already said so
  (1/1 pass), and it was reported at the time rather than folded into a threshold. What the round
  bought: the corpus change did **not** raise the count of tasks that can discriminate - C15's
  number - because on this arm the new task is saturated; and the h02 floor prior (opencode-bare
  0/5 on OpenRouter) did not transfer, with the task's contract shape and the provider (direct
  routing/prompt caching; median 148,032 cache-read tokens per row) confounded and named as such.
  Filed: `experiments/E1-env-adapt-h06/results.jsonl` (13 rows, `scope: real`, `source` = the lab
  files), `analysis.md` (rates, per-row table, the lab analyzer's own output, cost, limits), C17
  appended **superseding C16**. Cost note: the row sum is this round's spend; the provider balance
  moved 8.00 -> 7.68 USD over the same window on an account shared with a sibling session, so the
  delta is not this round's. Consequence recorded rather than repaired: a `supersedes` relation
  makes `check --strict` report one FAIL by design (the shape harness-hardening, judge-positioning
  and product-analysis already carry), so the line's locked "zero refusals under --strict"
  evaluation is affected - the parent instructed the supersede explicitly, and no criterion was
  edited after the fact.
