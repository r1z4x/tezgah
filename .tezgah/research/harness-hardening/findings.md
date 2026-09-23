# Findings — the harness's mechanical half

Question: *which parts of tezgah's harness are measurably load-bearing, which are dead weight
or unstable, and what change to the harness improves a named metric without breaking a
measured invariant?*

## What we know

- **A session's injected text is 9150 B against a 12000 B budget at `session_start` (76.2%),
  and 8081 B of that is the always-on core.** The live-state half — lessons, plans, graph
  glance, pointer, subagent note — is 1069 B combined (C01).
- **The live half does not grow with the repository.** Multiplying the lessons file and the
  open-plan set 5x moved neither block (C02). That is why the budget has only ever bound at
  `subagent_start`, where 4028 of 4400 B is spent (C01).
- **One gated call costs 61.0 ms p50, and the rules are not the cost**: the cascade is
  0.427 ms (C05). Importing `tezgah_gate` alone is 61.4 ms — the same number — so the price
  of every tool call is interpreter start plus import, and adding a rule to the gate is
  free at this scale.
- **~12 ms of that 61 ms buys nothing for the call in hand**: `tezgah_paths` imports
  `sqlite3` (4.5 ms), `shutil` (3.9 ms) and `tempfile` (3.7 ms) at module level for
  capabilities (bin resolution, the temp fallback, the omp `agent.db` read) that most calls
  never ask for (C06).
- **The gate does not slow down as the machine's history grows**: p50 0.430 ms with 1
  ledger and 0.430 ms with 20, because its ledger read is tail-bounded (C07).
- **Two of thirteen refusal rules have never fired on this machine**: `explorer` and
  `order`, across 1613 ledgers and 556 refusals over six days (C03). Three rules live on a
  single day each — `task` (168 fires, the day it shipped), `race` (8), `lang` (1) — and the
  most frequent is `drift` (181 fires, 143 sessions) (C04).
- **The opencode host's language rule was absent when E4 read it** — no `lang` code exists in
  the plugin, and it has none today: it asks the core instead (`hooks/tezgah_gate.lang_reason`),
  which is the change that closed the gap (C26) — and its delegated write path still fails
  open: a missing CLI, a non-zero exit or a broken pipe allows the call, with one `delegation`
  ledger row recording that it did (C08, C18).
- **No host entry point guarded the call into the core when E5 mapped it**, and the map's
  own reading is scoped to that tree: omp converted one crash or one 10 s timeout into a
  session-wide disable (gate, ledger and status line) and opencode's awaited spawn of the core
  had no timeout. Both were fixed afterwards — the guard at seven entry points and a 10 s
  deadline on the plugin's spawns (C14, C25) — and **the re-take was taken (E5b, C27): the
  guard holds at all seven entry points and every core ask in the plugin carries the
  deadline**, so the `guarded` half of H5 is closed for today's tree.
- **One hot-path read was unbounded**: `turn_channel` scanned the whole ledger on every
  effectful call — 2.928 ms at the then-largest ledger (925 rows), linear in session length,
  where the gate's own read is tail-bounded (C10). It was bounded afterwards by the
  turn-scoped reader (C24). **`stop_reason`'s whole-ledger read was the same shape, and it
  was measured and bounded after the re-take (E5b, C27)**: 2.638 ms of parse against 0.185 ms
  for the turn's rows at the largest ledger on this machine (1112 rows), with the bound
  landing in `turn_rows`. The two reads that remain unbounded are `used()` (the session
  store, kinds only) and `_hash_file` (a file hashed to EOF by design), and no run has timed
  either.
- **The behavioural effect of the harness is unresolved by this repository's own instrument**:
  pooled over two model families the armed and bare omp arms and armed opencode all land on
  40/50, the delta flips sign between models, and 22 of 25 pilot tasks are saturated; the one
  family that isolates a rule is `reporting-language` (C13, restated as C22).

## Patterns

- **The harness's cost is in import and I/O, its value is in a few specific rules** [C05] [C13] — 61 ms
  per call against a 0.43 ms cascade, while the only measured behavioural wins are on
  families that isolate one artifact-producing rule. A change should therefore buy a
  measured cost or a measured behaviour, never a rule count.
- **Rules and their reach drift apart in both directions** [C03] [C04]
  [literature/2608.28795-verification-surface-reach.md] — two rules have never met their
  shape while the one rule that fires most, `drift`, fires on long turns whether or not
  anything is drifting, and it fired three times while this experiment was written. The
  published yardstick is the same one: a verification tool is worth what its reach covers.
- **Enforcement is host-shaped, not rule-shaped** [C26] [C25] — the same rule is in-process
  on three hosts, absent on a fourth and delegated-with-a-fail-open on the fifth, and the
  failure *policy* differs as much as the code: omp disables the whole harness, opencode
  hangs.
- **Recovery machinery nobody uses is the literature's named trap** [C13]
  [literature/2609.20804-harness-design-components.md] — the recall tool added complexity
  without accuracy, and the ai-research line measured 1 of 30,750 ledger rows reading an
  entry body.

## Lessons

- A budget measurement is only meaningful with the builder's own blocks, not the returned
  string: wrapping `budgeted` was what made "the live half is bounded by construction"
  visible, and the `--big` variant turned it from a plausible claim into a measured one (C02).
- A rule's zero count is a question, not a verdict: `explorer` and `order` may be wrong or
  merely unreached, and only a probe that issues their shape can tell the two apart (C03).
- The checker's phrase rule has a blind spot worth knowing: a falsifier sentence that follows
  a negation within four words is read as a disclaimer and cut out, which is why this line
  carries E2b — a child with a corrected protocol — instead of an edit of a frozen E2.
- The gate's own drift rule fired at this session three times while the measurement ran; the
  one rule with the highest fire count is also the one whose cost lands on long, careful work.
- A verdict is scoped to the tree it was taken on: three of the four defects H5 named were
  fixed after the map landed, so the refutation is recorded as one against the pre-fix tree
  rather than kept as current or quietly withdrawn (C25), and the claims it rests on carry the
  same scope.
- The re-take is what separated H5's two halves, and only the artifact a reader keeps made it
  happen: the same change that guarded seven entry points left the Stop path parsing the whole
  ledger, and a close-out pass that records "not re-taken" in the log while the findings file
  still reads as current is a debt with an owner, not a settled question (E5b, C27).

## Open questions

- ~~Are `explorer` and `order` unreachable in practice, or unreachable in principle?~~
  **Answered by E6**: both refused when their shape was issued deliberately (a
  `Task` call with `subagent_type=explore`/`explorer`; a `git commit` over a newest
  failing check), with a control that refuses under the same conditions. So the
  zero counts [C03] mean this machine's traffic never offered the shape - not that
  the rule cannot match it. The related open question the probe raises but does not
  answer: whether the shape is rare because it is genuinely uncommon or because the
  hosts name their subagents differently.
- Does the 12 ms of unused import matter to the user's wall clock at all? **Now
  measured [C19]**: the gated call moves 61.0 → 56.8 ms p50, 7%, and the import
  61.4 → 50-55 ms. Small, real, and below what a session can feel per call.
- Which of the remaining import cost is the floor? `site` (7.4-8.9 ms) and the
  modules' own parse remain; nothing further has been separated.
- Would the gate's cost survive being made resident (a daemon per session) rather than
  one-process-per-call, and is that worth the architecture the literature calls the
  highest-regression-risk zone (context/provider changes)?
- Is the literature's conditional reading true of *this* harness? **Settled as untested
  here [C21]**, not answered: the claim is that a mechanical context policy is worth a lot
  under context pressure and about nothing without it, and the repository holds no
  measurement of that axis — E1 measures the pressure side (76.2% of the budget at
  `session_start`) and the lab's pooled null [C22] is taken at one window over a corpus it
  calls saturated. What would settle it: the arm-bench lab re-run with the harness's context
  policy toggled at two window sizes over an un-saturated corpus, which needs model spend on
  the `benchmarks/lab` branch and was therefore not run in this line.
- Is H5 still refuted for today's tree? **Re-taken by E5b [C27]**: the `guarded` half holds —
  every entry point wraps its call into the core and every core ask in the opencode plugin
  carries a deadline — and the `bounded` half failed only at the Stop path, whose
  whole-ledger read was then bounded through `turn_rows` with a test that fails on the
  pre-fix file (4002 lines parsed before, the turn's own after). H5 stays refuted for
  today's tree on the two reads that are unbounded by construction and that no run has
  timed: `used()` and `_hash_file`.
- Which of the four unbounded reads the map found are still unbounded? Two are answered by
  a fix (`turn_channel` → the turn-scoped reader, C24; `stop_reason` / `changed_files` → the
  same reader, E5b/C27). `used()` and `_hash_file` remain unbounded by construction: the
  first walks a kinds-only store (on this machine 286 files, 1.1 MB, the largest 14755 B /
  931 lines) and the second hashes a file to EOF on purpose, and neither has a timing.
