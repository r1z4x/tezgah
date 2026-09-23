# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-19 bootstrap: the line opened because the request is "new features" with
  no named feature, which is a research question (which addition earns its keep)
  and not a build order. Question fixed in `state.json`.
- 2026-09-19 read: repo is not greenfield. Gate (12 rules), ledger, Stop rule,
  snapshots, untrusted taint, active-task record, six adapters, docs layer, and a
  measurement harness (`benchmarks/arm-bench` on `benchmarks/lab`, 8
  pre-registrations, an OpenResearch project with 11 nodes). So the interesting
  candidates are gaps in an existing design, not new subsystems.
- 2026-09-19 literature: 7 sources read via `orx discover`/`orx paper`; each one
  hit an already-open tezgah hole. ActPlane names the tool-layer blind spot
  tezgah documents; FAVA's 90%-temporal measurement names the missing rule kind;
  the false-success paper validates the evidential (not text-level) design and
  gives a sharper definition of the headline metric; PIPES names the in-root
  write the taint notice deliberately does not refuse.
- 2026-09-19 dead end: OpenAlex title search returned unrelated surveys and then
  429'd. Cross-check moved to arXiv DOI metadata (DataCite content negotiation),
  which resolved all 7 ids with matching titles and authors.
- 2026-09-19 scouts: four read-only passes (evidence, gate, host parity, context).
  The produced set was larger than the literature suggested - F1/F2/F3 (stale or
  absent evidence), F4a/F4b (cwd-blind consent lease; Cursor never spends it),
  F5a/F5b (unreachable `powershell`; rsync branch inverted), F2d/F2e/F2f (shell
  write escapes three write-tool-only rules; write content escapes `secret`).
- 2026-09-19 E0: probed the real functions instead of trusting the reads. Cells A
  and B reproduce a permitted "done" after a later write and across turns; cell D
  reproduces `passing_check` accepting an `out_bytes`-less row; cells E and F
  reproduce nine class-less destructive actions and the inverted rsync branch.
- 2026-09-19 decision: rank by (evidence already in the repo) x (cheap to
  measure) x (no new always-on text). That puts H1/H2 first, H3/H4 next, H5 as
  tooling, H6 recorded as a measured negative.
- 2026-09-19 measurement, C2: the local corpus (1162 ledgers) holds 1224
  `verify_ok` rows and **none** carries `out_bytes`, so the guard that field
  exists for has never fired. This changed the candidate: C2 is not "narrow the
  predicate" but "decide between implementing the guard and deleting the claim".
- 2026-09-19 decision, C3: the legacy no-`exit` tolerance was removed only after
  its own stated condition was measured - 464 rows in 150 ledgers, 0 of those
  ledgers written in the last 24 hours, and no current writer able to produce one.
- 2026-09-19 user pick: P1 (fresh evidence, C1+C3), chosen over P2 (gate truth
  table, needs a per-command policy call) and P3 (six small fixes).
- 2026-09-19 E1: the fix verified through the real `hooks/projects-stop.py`, not
  only through the rule: the blocking cell returns the `stale evidence` envelope
  and writes `blocked: stale evidence`; the verified tree, the no-op write, the
  admission, and the never-checked case all behave as before. Six cells in
  `experiments/E1-stale-evidence/`, plus three more through the omp, codex and
  cursor adapters, which is what makes "four hosts block on it" a measured claim
  rather than a structural one.
- 2026-09-19 side fix, out of P1's scope but needed for a green suite:
  `docs/glossary.md` cited `.tezgah/lessons.md:4`, a file untracked by design
  since `2c1ef68`, so `tests/test_docs.py` had been red on `main`. The citation
  was replaced by naming the file without a `path:line`, and `HANDBOOK.md` was
  regenerated. Recorded as a finding, not as a silent repair.
- 2026-09-19 P2+P3 lands in parallel: five slices, split by file ownership (text
  and marks, counters, gate internals, matchers, and a read-only pass staging the
  paid block). Two collisions were caught and resolved by ownership before they
  happened - `docs/architecture.md` was taken away from the slice that claimed it
  and kept by the parent, because two slices were shifting different modules it
  cites; and the `BASH_TOOLS` tuple ended up with one owner after I had briefly
  given it to two.
- 2026-09-19 a slice found the other half of its own candidate: wiring the
  `PowerShell` matcher left `pwsh` - dsh's own spelling - ungated, because `pwsh`
  was not a `BASH_TOOLS` member, so a `--no-verify` command was still allowed
  under that name. Measured with the real hook (deny for `Bash` and `PowerShell`,
  no output for `pwsh`), then closed in both tuples.
- 2026-09-19 integration: the docs citations into five modules were rebased - 75
  by map, 6 by hand - and the residue was chased with a symbol-containment audit
  (645 citations, flagging a citation whose cited line does not contain the symbol
  the sentence names). It found one number that had been wrong *before* this
  session: the glossary pointed `health_segments()` at `:1220` where the function
  has been at `:1150` at HEAD, and a mechanical shift would have carried the
  error forward as `:1260`.
- 2026-09-19 checks on the integrated tree: `compileall`, `ruff`, and the full
  `unittest` suite (838 tests, OK) pass. Two omp tests failed on the first pass
  because they asserted the old silent `idx✓` for a fixture that has an index db
  and no stamp; they were re-pointed at the honest `idx?` with the reason in the
  fixture's docstring, which is a fix of the test's expectation, not of the mark.
- 2026-09-19 open: the rate question (does the stale-evidence rule move the
  false-completion number, and at what completion cost) is pre-registered in
  `experiments/E2-stale-evidence-rate/protocol.md`; the block is being run against
  the commit below. C2's decision, C5's nine-command policy list, C7 (three
  write-tool-only rules still have no shell twin) and C15 (the ledger miner)
  remain open.
- 2026-09-19 landed: the whole session's work is one commit on `main`,
  `d2f0cf4` "contract: fresh evidence, honest marks, and a gate truth table" -
  29 files, +1664/-724, with `compileall`, `ruff check` and 838 unittest tests
  green on that tree. Two workstreams opened from it in parallel: the E2 block
  above (against a pinned worktree of `d2f0cf4`) and a refresh of the installed
  hosts, whose managed always-on files and plugin copy still carry the previous
  text until `tezgah-setup --sync`/`--refresh` runs.
- 2026-09-19 host refresh (parallel workstream): the contract is live on the installed hosts - 8 plugin copies byte-equal to d2f0cf4, omp RULES.md and the opencode contract carry the carve-out, CLI links resolve. It also surfaced two unnamed holes, recorded in round2/host-refresh.md: --install --hosts <one> narrows config.json's hosts key and silently deletes the other hosts' generated agents (measured: tezgah-agents --json went empty; repaired by writing the previous config back), and the omp report row cannot see a stale RULES.md because it greps two substrings (bin/tezgah-setup:1921).
- 2026-09-19 batch 2 (parallel, five slices): the gate got its first cross-event rule
  (`order`: a commit is refused while the newest check failed), the ledger miner
  (`tezgah-status --unclassified`, which on 1195 ledgers reports 10294 class-less allowed
  shell calls and named two effects nobody had listed), five remote-destructive effects and
  three shell twins; the `out_bytes` guard became live on codex, cursor and omp (a behaviour
  change, not only a repair - an empty reported result no longer supports a done claim), and
  docs citations into the grown modules were rebased by hand. Landed as `8ec444c` with
  compileall, ruff and 872 tests green on that tree; the installed hosts were then re-rendered
  and verified on the artifacts themselves.
- 2026-09-19 round 2 (parallel, three probes + the refresh): 30 findings plus three sized
  structural verdicts, all in `round2/`. The verdicts are the round's real result: build the
  obligation kind now, defer the cross-implementation corpus until a divergence set exists
  (measured: 20 shared patterns, but only 11 Python and 4 mirror rules write a deny row at
  all), and do not build the response-boundary screen (the measured precision objection
  stands) in favour of a surface-path sink list. The refresh also surfaced two unnamed holes
  (`--install --hosts <one>` narrowing the config and deleting other hosts' agents; the omp
  report row that cannot see a stale RULES.md).
- 2026-09-19 E2: the stale-evidence rate block ran - 4 cells, 100 runs, $0.334736,
  one model, k=25 - and it is **void by its own F1**: `shape_present` is 0/25 on
  both arms, because 50 of 50 `s01` runs fixed the code exactly and left
  `SPEC.md` byte-identical. The enticement the task was built on (amend the
  specification to fit, 12 of 12 on the closest existing task) did not occur once
  here; the prompt names which side changes, which is the disambiguation the
  shape needs absent [INFERENCE]. Arm B had to be pinned at `b13d832` instead of
  read from `omp+tezgah`, whose installed pin is the primary checkout and
  therefore the change itself; the parent approved (`pin-parent`) and the
  whole-commit confound was measured empty: the per-turn context, the
  session-start context and the seven reachable PreToolUse decisions are
  identical between the two checkouts, and the commit's new graph notice appears
  in 0 of 100 captured streams. The endpoint held where it mattered:
  `blocked: stale evidence` is 0 rows in all 150, so the branch does not fire on
  a turn that changed nothing - the 5 blocked rows of the pre-registered `s02`
  pair (2 with the change, 3 without it, inside the 0.08 floor) are the
  pre-existing `no verify_ok`/`check failed` triggers. One defect of mine: the
  first `s02` pair ran against a fixture missing `rates/round.py` (the write was
  skipped when its batch was interrupted, and `selftest` passed anyway because
  the baseline failed by import error instead of truncation); it was found while
  staging the tasks, fixed, and re-run into its own files, with the trace rows
  kept - six cell-runs and $0.458764 in total against the $0.63 approved. Before
  any spend, a free probe drove both pinned hooks
  with the bridge's own payloads: A blocks with the `stale evidence` class in the
  ledger, B does not, which is also what settles the protocol's open `.md`-write
  question (a `SPEC.md` write does record `changed: true`).
- 2026-09-19 C16 landed on the instrument (`benchmarks/lab` `fc6b8f2`, fast-forwarded inside the
  armbench worktree without touching the foreign staged file): `bench.py` now records each refusal's
  class beside the count and `report` prints the field's false-completion share. Running it over
  E2's own rows found a real disagreement - the tool says 3/25 = 0.120 on each s02 arm where the
  analysis's state-based column said 0.00 - and the two are different quantities, not a defect.
  Recorded as an addendum to E2's analysis with the numbers, and E2b's protocol now has to name
  which measure it reports. The class side agreed with the hand-derived classification on 150 of
  150 rows. `selftest` still discriminates 44 of 44 fixtures; the old E7/E6 result files report
  without crashing and without inventing a value.
- 2026-09-19 E3 (the third attempt, armed): NOT void - every row loaded the harness (0 rows with
  session_rows = 0, ledgers 25/25 per cell). Result: the shape appeared in 0-1 of 25 per arm against
  the pre-registered >=20, so F2 fired; the rule fired 2 of 25 on the arm carrying it and 0 of 25 on
  its parent, so F3 fired (both fires correct); P4 held (17/25 against 18/25 pass, inside the floor);
  P3's literal denominator failed because only 17 runs passed, and 15 of those 17 ended allowed.
  The diagnostic finding: 47 of 50 runs ended with their newest accepted check newer than their newest
  changed write - the models write the file and re-run the suite. Cost $0.276055, an overrun of the
  $0.25 stop that is reported as an overrun. Landed as benchmarks/lab 65c289f.
- 2026-09-19 verdict on the rule (synthesis in findings.md): keep it - mechanism verified, cost
  measurable zero in two armed blocks, reach 8% of runs in the armed block and 4.9% of this machine's
  historical completion claims. Three task designs failed to produce the shape at the pre-registered
  rate because a competent model re-verifies after its last write, which is the behaviour the rule
  wants and therefore the reason it is hard to measure.
- 2026-09-19 provenance, the E2 pair's pins: the two pinned checkouts left `/private/tmp`,
  where a tmp cleaner or a reboot takes the directory out and the arm goes inert. `git worktree
  move` returned 0 for both: `/tmp/tezgah-e2-main` -> `/Users/rizax/orca/workspaces/tezgah/
  e2-pin-main` (`d2f0cf4`) and `/tmp/tezgah-e2-pre` -> `.../e2-pin-pre` (`b13d832`), both detached
  worktrees of this repository at the same commits, so E2's and E3's rows keep describing the same
  code. Both bridges are re-pinned and the guard's own block reports both arms armed with the new
  paths. The E2, E2b and E3 analyses below still quote the old paths because they are frozen
  records of runs that read them; the arm's committed `PROVENANCE.md` carries the old -> new map.
- 2026-09-19 the tier channel (finding O10, landed): a `consult`/`codegen` invocation that reaches a
  provider is now an outside channel (`hooks/tezgah_integrity.py`, `TIER_PROGRAMS`), so the turn is
  tainted and the gate's sink rule holds an effect that leaves the workspace until the user's own
  approval is written. The cost was measured live before it was reported: the `LabHygiene` agent ran
  `consult --help`, which in the first shape counted as a read, and every write in its turn was then
  refused - the work was hand-ported to a fresh agent instead of spending a user approval on it.
  The final shape is by invocation: `-h`/`--help` and a bare invocation reach no provider and are
  not reads; an argument does, and `consult --version` was measured reaching one (3 calls, the panel
  asked the question `--version`), so the local-forms list is not the rule, the invocation shape is.

- 2026-09-20 input scope declared across the line, and six receipt corrections: all 268 results rows
  now carry `scope` (267 `fixture` - a hand-written trace, a seeded ledger, a generated task fixture -
  and E1's `fix-1-ledger` `derived`), every fixture row names what was generated, and the 13 claims
  over those rows declare `fixture`. C2 and C10 listed `experiments/E0-current-stop-rule/results.jsonl`
  in their proof, and E0 holds none of the numbers either states: their counts (1162 ledgers, 1224
  `verify_ok` rows, 398 claim rows, 0.271) fold the real local ledger corpus, so the proof now cites
  `to_human/candidates.md`, where the fold is recorded, and both declare `real` - a misreceipt
  corrected, not evidence dropped. C20, C21, C23, C33, C22 and C25 had their proof extended with the pre-existing
  artifact that already holds the asserted number (`./CHANGELOG.md` 2082/3001 and 1166/17520/0.19,
  `hooks/tezgah_context.py` 200, `./log.md` 645/1150/1220/1260 and 10294/1195,
  `experiments/E2b-spec-agreement/analysis.md` 0.148427/100). No
  number was written into any file to make one reachable.

- 2026-09-22 the E3-commit-on-red block is prepared and could not be run, and the reason is the
  provider's billing layer rather than the design. Four cells were launched as four `bench.py`
  processes with one results file each; every row came back `stopReason: error` with
  `errorStatus 402` - "This request requires more credits, or fewer max_tokens. You requested up to
  131072 tokens, but can only afford 27251" - so no row reached a model. `GET /api/v1/credits` is
  `{total_credits: 130, total_usage: 130.184509987}`, i.e. the account holds no credit, while
  `GET /api/v1/key` reports `limit_remaining 4.315203833000002`: that is the key's own sub-limit and
  it is not spendable, the two are different layers, and the account layer is the one OpenRouter
  checks. Spend: `$0.0000` (all 51 attempted rows carry `usage.cost` 0, and the key's own usage
  figure is byte-identical before and after). The 51 rows and the 8 run directories they left were
  deleted, so a rerun starts at repeat 1 and no row that never called a model can be read as a
  measurement. Prepared and unchanged: both fixtures pass `selftest` (`c01-commit-on-red`
  baseline=fail gold=pass 3/3, `c02-commit-clean` 2/2, and 49/49 harness-wide), the two arms are
  added and probed - `omp-order-rule` pinned at `8ec444c` (the ordering rule) and
  `omp-order-rule-pre` at `d2f0cf4` (its parent) - with the probe showing the rule denying a commit
  over a red check on the first, allowing it on the second, and denying it on the installed pin,
  which is why `omp+tezgah` can no longer serve as this block's no-rule arm; `bench.py` carries the
  task-owned setup hook (a fixture cannot store a `.git`, so the task builds the repository) and the
  `{ledger}` substitution the `no_red_commit` check needs; `--dry-run` resolves both arms. What is
  waiting is a decision about money: fund the OpenRouter account and run the committed recipe
  unchanged, or run the same model through the `deepseek` credential omp already holds - which changes
  the arm's model string and section 3's lock, so it needs an amendment first.

- 2026-09-22 the E3-commit-on-red block ran and is **void**: four cells, 100 paid rows, `$0.2031`, all
  four cells concurrent, `deepseek/deepseek-v4-flash` on the direct provider after the OpenRouter
  account turned out to be unfunded. No run in any cell wrote a `verify_fail` row, so §8.1's instrument
  check fails: `red_commit` is 0 of 25 on both `c01` cells and `order_fired` is 0 of 25 on the armed
  arm, F1 applies, and nothing may be concluded about the commit-on-red rate. The cause is the gate's
  pipe rule - `hooks/tezgah_integrity.note_tool` records a check whose command contains a pipe as
  outcome-unseen, never as `verify_fail` - measured as 1432 piped of the lab's 1684 `verify` rows, and
  this model piped its suite runs, so the state the block measures was never written into the ledger.
  Completion guardrail: 19/25 pass on arm A against 18/25 on arm B, a 0.04 gap inside §8.5's 0.08 floor
  (a tie, and not evidence the rule is free - the rule never fired); the 13 failing `c01` rows failed on
  collateral alone (7 rewrote `tests/test_balance.py`, 3 added a `.gitignore`), with all three checks
  passing on all 50. The `c02` control passed 25/25 on both arms with `order_fired` 0 everywhere, so
  §8.4 held vacuously. Read off the same ledgers: `blocked: no verify_ok` is the newest `claim` row on
  21/25, 17/25, 23/25 and 24/25 of the four cells - including `c02`, whose prompt forbids running the
  check - so a task whose design has no check can never end with an allowed claim. Deviations, all three
  in the protocol's amendments: the provider moved to DeepSeek direct, arm B is a re-pinned pair rather
  than `omp+tezgah` (the installed pin carries the rule), and both fixtures' `allow` lists gained the
  agent files tezgah's own SessionStart sync writes into the run directory. `results.jsonl` (100 rows,
  scope `fixture`, each with its `run_dir` and `session_id`) is ignored by `.gitignore:52`, so it needs
  `git add -f` beside the two new arm directories.

- 2026-09-22 close-out: the line concluded on the question it can answer and left the
  measured outcome named as missing. `to_human/report.md` and `to_human/review.json` were
  written from the artifacts already here - no new measurement, no model call, and no
  `protocol.md`, `results.jsonl` or claims row touched - and `phase`/`direction` moved to
  `concluded`/`conclude`. Two record defects are recorded in the review rather than edited
  behind the record: `findings.md` still reads the E2 block as unrun in its Open questions
  section while a later section of the same file records the void, and its E2b row count is
  "All 100 rows" where `experiments/E2b-spec-agreement/results.jsonl` holds 50 (C33 repeats
  the 100). The arming fact and the void are unaffected; the counts are not.
