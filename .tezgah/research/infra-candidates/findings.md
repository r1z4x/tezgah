# Findings

## What we know

- The layer already implements the runtime-contract shape the literature argues
  for: preventive rules (gate), an evidential ledger, an evidence-gated Stop rule
  on four hosts, and a snapshot store. The candidates were therefore *gaps in an
  existing design*, not missing subsystems.
- **Closed on 2026-09-19** (each with its own evidence; the open ones keep their
  measurements):
  - the Stop rule's pass branch was position-blind and session-wide - it now
    requires the newest passing check to be newer than the newest write the gate
    saw change the tree, and names the files (`stale evidence`; E0 before, E1
    after, through four host adapters);
  - `passing_check`'s legacy tolerance for a `verify_ok` row with no `exit` key is
    gone, on its own stated removal condition;
  - `rsync` was classified by the wrong end of the command - the destination
    decides now, and the opencode mirror agrees on nine forms;
  - `powershell` could not be gated on any Python host and `pwsh` was gated
    nowhere - the matchers carry the spellings and both halves carry `pwsh`;
  - the consent lease is bound to the workspace the ask recorded, and an outcome
    row of any step kind spends it on every host;
  - the `idx` mark has an honest fourth state for a comparison it cannot make;
  - the reminder's merge authority no longer swallows itself;
  - the subagent brief carries the on-demand pointer and the kill switches;
  - the lessons digest is taken over the text actually shown;
  - the headline ratio is readable over the whole corpus
    (`tezgah-status --counters --all`).
- **Still open, with their numbers:**
  - C5 - nine destructive/outward commands derive no effect class, and none is on
    the documented non-goal list. A per-command policy call, not a bug list. Two
    of the nine closed since, with tests: `ssh host cmd` is the send class beside
    `scp`, and `gh run delete`/`gh cache delete` are destructive (`f76c87f`). The
    local-only forms (`git reset --hard`, `git tag -d`, `docker compose down -v`,
    `chmod -R 000`, a plain `git push origin main`) still ask nobody, deliberately,
    for the maintainer's call.
  - the harness's own scratch cannot be cleaned by an agent: `benchmarks/
    arm-bench/.runs/` is gitignored and held 263 directories / 52 MB on
    2026-09-19, while `rm -rf` outside `SCRATCH_ROOTS` is an effect on every host -
    so each cleanup costs a user approval and the directory grows instead. The
    narrow fix is a repo-published scratch list; a general "gitignored means
    scratch" rule is wrong, because `.env`, a local database and
    `.tezgah/research/` are gitignored too.
  - closed since, each with the measurement that closed it: C2 (the codex, cursor
    and omp adapters now send a result size, so `out_bytes` has data to reject
    on), C7 (`SKIP_TEST`, the attribution line and the secret scan gained shell
    twins - E7c's route), C15 (`tezgah-status --unclassified` reads the blind spot
    from the ledger; its first run named two effects nobody had listed).
- The `false_completion / claims` ratio over the local corpus is 134 / 612
  (0.219) across 1400 ledgers as of 2026-09-19
  (`bin/tezgah-status --counters --all`). It read 108 / 399 (0.271) across 1166
  ledgers earlier the same day: the denominator moved because the corpus grew, not
  because the rule changed - the number every future change to the Stop rule
  should move, measured the same way. Four ledgers from this session's own
  end-to-end probe runs are inside that count (session ids beginning
  `zzz-e2e-probe`, ~35 rows including 2 claim rows and one deliberate refusal);
  a fold that wants the untouched corpus should drop that prefix.

## Patterns

- **The evidence/rule boundary is not the tool/effect boundary** ([C26],
  literature/2606.25189-actplane.md). Three independently-found holes (shell
  writes escaping `SKIP_TEST`, `ATTRIB_LINE` and the secret scan) come from one
  structural fact: `WRITE_TOOLS` and `BASH_TOOLS` are disjoint. The literature
  names this class as the structural limit of tool-layer guardrails (ActPlane),
  and E7c measured it as the route an agent takes once the write tools are
  refused.
- **Every rule is a per-call predicate** ([C24], [C28],
  literature/2607.27267-fava.md, literature/2606.25189-actplane.md). None
  asserts an ordering between two different actions, while the field's own
  measurements put temporal obligations at 90% of real instruction files (FAVA)
  and cross-event policies at 16% (ActPlane).
- **What is recorded and what is read drift apart** ([C11], [C18], [C22],
  [C25], [C31]). Three of this line's fixes were "read the row you already
  write" (`changed`, `hash`, the denied-call counts) rather than "record more",
  and the same shape recurs in C15 and C16.
- **A duplicated rule is a rule that drifts** ([C15], [C16], [C17], [C24],
  [C26]). Every candidate that had to land in two halves (the gate and its JS
  mirror) needed the same change twice, and only a test kept them honest. The
  consent-lease fix is the clearest case: the scope and the spend predicate both
  had to move in step.

## Lessons

- A read-only audit cannot execute, and that is where its claims break: two of
  them changed under execution (the `rsync` direction and its behaviour with a
  flag). Every claim promoted to the report was re-run in-process first.
- A rule added to the Stop path must be checked against the *control* cases as
  hard as against the fix - the same branch that closes a hole is the one that can
  block an honest turn, and the admission escape (`doğrulanmadı`) is what keeps
  that from being a false positive.
- A test fixture that "makes the mark resolvable" is not the same as one that
  makes it *fresh*: two omp tests asserted the old silent fallback and had to be
  re-pointed at the honest glyph when the fallback became a real state.
- Parallel slices need file ownership decided before they start, not after: two
  slices claimed `docs/architecture.md`, and a line-number-only change in one
  module invalidates citations that a different slice owns. The parent has to hold
  the shared pages and rebase them once.
- A number is not a citation. A mechanical line-shift carries a *wrong* number
  forward as faithfully as a right one - the audit found one that had been wrong
  since before this session, and only a symbol-containment check caught it.
- OpenResearch's `orx` was the right tool for the literature pass and the wrong
  one for the measurement: the repo's own `benchmarks/lab` harness is the
  instrument, and the pre-registration for the paid block is a file in this line.

## Open questions

- **Does the stale-evidence rule move the number?** E1 shows the rule refuses the
  shape; the rate and the completion cost need the block pre-registered in
  `experiments/E2-stale-evidence-rate/protocol.md` - unrun, and it needs the change
  committed (the arm pins a checkout) plus about $0.31 of model calls.
- Does `git tag -d` / `docker compose down -v` deserve an ask at all, and is a
  plain `git push origin main` meant to? Two of the nine are local.
- If `out_bytes` is implemented rather than deleted, which host can supply a real
  result size, and what does that cost on the PostToolUse path?
- The gate exists twice (Python and the opencode mirror) and the two halves are
  kept honest by hand-written cases. C-Trace's answer - require two
  implementations to agree on *every* trace in a corpus - would be a stronger
  obligation than case-by-case pinning, and is untested here.

## Round 2 — three areas the first round never probed (2026-09-19)

Each probe is a file in `round2/`, written by a read-only pass over files no first-round
brief touched. Counts are as reported by each pass; the findings themselves are one per
section there, each with `path:line` evidence, a class, a measurable? verdict and a sketch.

- **`round2/installer.md`** - 18 findings, 17 class (c) and 1 class (a), 70 citations, every
  claim reproduced by an in-process call rather than by running the installer. The ones worth
  naming here: `I10` the contract's source list omits `hooks/tezgah_context.py`, which the
  contract is rendered from, so a render can be stale and the list will not say so; `I1` the
  "hooks.json wired" report row passes when any single event is wired, so a host with no Stop
  hook reads as armed; `I6` the plugin-copy freshness check hashes only files that still
  exist, so a file deleted from the copy is invisible; `I15` the failed-index note names a log
  path the worker does not write; `I17` `tezgah-research init` accepts any slug and the line is
  then invisible to `check`/`status`/`claim`.
- **`round2/orchestration.md`** - 10 findings, 8 class (c) and 2 class (b), all probed against a
  local stub with no provider paid. `O1` the referee's five headings are printed without being
  checked (measured: exit 0, "referee: m1", zero headings); `O2` no global deadline, so the
  wall clock is per-model; `O3` codegen's parse guard keys on the `.py` suffix, so a `.tsx`,
  `.js` or extension-less draft is unvouched; `O10` a consult or codegen answer is not an
  untrusted channel while a `curl` to the same URL is.
- **`round2/structural.md`** - the three structural answers sized rather than guessed:
  cross-event obligations **build now** (the rule kind is ~12 lines with no extra ledger I/O);
  two-implementation agreement **build after** a divergence set exists (the two halves share 20
  patterns but only 11 Python rules and 4 mirror rules write a deny row at all, so a corpus
  runner would start red for a reason that is scope, not drift); response-boundary screening
  **do not build** the screen (the measured precision objection stands) - instead a surface-path
  sink list plus one notice sentence. It also measured that an in-root write to `AGENTS.md` or
  `.tezgah/lessons.md` is allowed by every rule, and that no tainted turn in this machine's
  corpus has written to a contract surface (189 edits, 0 of them there).

## The stale shape, counted in real traffic (2026-09-19, free)

The two paid blocks could not elicit the shape; the ledger corpus already
contained it. Over 1332 ledgers (19333 rows) and the 554 completion claims in
them, **31 claims were decided while a write that changed the tree sat after the
newest passing check, and 27 of those were allowed to end** - 4.9% of all
completion claims on this machine. Eleven ledgers (0.83%) end in the shape. The
shape is counted over the rows *before* each claim, with the shipped
`_last_pass`/`_last_change`/`_changed_write` predicates, so it is the state the
Stop decision actually read. Detail in `experiments/E2-stale-evidence-rate/analysis.md`.

## Two paid blocks, two different voids (2026-09-19)

The rate this line was opened to measure is still unmeasured, and the two attempts
failed for different reasons - which is the finding.

- **E2** ($0.458764, six cells): the task did not elicit the shape. 0 of 25 runs on
  both arms amended the frozen document, so its own instrument check falsified the
  premise. What it did establish: 25 of 25 runs passed on both arms (saturated, so
  no cost signal), the rule never fired on a turn that changed nothing (0
  `stale evidence` rows in 150 runs), and the field's false-completion share was
  the same on both arms.
- **E2b** ($0.148427, two cells): the harness was not there at all. All 100 rows
  carry `session_rows = 0` and the fold found no ledger for 50 of 50 runs, so no
  bridge, gate, ledger or Stop rule loaded; `shape_present` is **unmeasurable, not
  zero**. The cause is a deployment defect in the arm's agent directory, and the
  free pre-flight could not see it: `selftest` measures the fixture and `--dry-run`
  prints the command, and neither looks inside the arm - while `bench.py` already
  *records* the arming evidence (`session_rows`) and never enforces it.
- **What E2b still settled, free of the harness**: the task is well-formed and its
  added row discriminates (6 implementations x 3 visible / 13 hidden: two
  plausible-wrong fixes pass the visible suite and fail the hidden one); `s01`
  stayed byte-identical where the protocol said it must; and E2's inference that
  its own prompt caused the absence is **not supported** - the steer was removed
  and the document was still untouched in 50 of 50 runs (a weak reading, since the
  harness was absent).

**The number that did come out of this question is the field base rate** (above):
27 of 554 completion claims were allowed while the shape was present. Two paid
blocks could not add to it; the ledger could, for nothing.

## The verdict on the stale-evidence rule, after three armed attempts (2026-09-19)

Three blocks were run at this question; the third was armed on every row and is
therefore the first whose numbers mean anything.

| what | measured | source |
|---|---|---|
| mechanism | fires correctly: 2 refusals on the arm carrying it, 0 on its parent commit, over 25 armed runs each | E3 |
| cost to completion | none measurable: 17/25 vs 18/25 pass (0.68 against 0.72, inside the pre-registered 0.08 floor); E2's armed s01 pair was 25/25 against 25/25 | E3, E2 |
| reach, fresh traffic | 2 of 25 runs (8%) on the arm carrying it; the shape itself appeared in 0-1 of 25 because the models re-verified | E3 |
| reach, this machine's history | 27 of 554 completion claims (4.9%) were allowed under the shape | field fold |
| why the pre-registered contrast failed three times | 47 of 50 runs ended with their newest accepted check **newer** than their newest changed write - the models wrote the file and then re-ran the suite, so "the last action is a write" does not survive contact with a competent model | E3 |

**The rule stays.** It costs nothing measurable, it fires correctly where the shape
does occur, and the tail it covers is not hypothetical - 4.9% of this machine's
own completion claims and 8% of runs in the armed block. What the three blocks
settle is the *reason* it is hard to measure: the behaviour it enforces is already
a competent model's default, and the rule exists for the runs where it is not.
