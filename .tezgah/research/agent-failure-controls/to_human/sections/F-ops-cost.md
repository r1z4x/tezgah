# F. Operations, cost and observability

Group F of the agent-failure taxonomy. Anchors read this session on
`research/agent-failure-controls`.

### 1. Runaway cost / token blow-up — `Runaway cost / token patlaması`
- **Today**: absent — no live cost or token meter. Usage is measured offline only:
  `benchmarks/arm-bench/bench.py:410-421` writes `usage`
  (input/output/total/cost/cache/reasoning) plus `usage_note` when nothing parsed,
  via the shape-driven `extract_usage` (`bench.py:162-260`), scored as CPS =
  cost/passes (`benchmarks/arm-bench/analyze.py:1-11`, `:64-84`) under "A missing
  usage block is `null`, never `0.0`" (`benchmarks/arm-bench/PREREGISTRATION.md:57-61`).
  Live ceilings are per-process: `bin/codegen:136-137` (300 s, `max_tokens` unset),
  `bin/consult:105,149` (120 s), `bench.py:558` (600 s). Check run:
  `grep -ni 'token|cost|budget' hooks/tezgah_policy.py` returns prose only (`:126`,
  `:243`, `:285`): no numeric budget exists. `E3` measured every injected block as
  static or capped, so the unbounded part is host history, tool output and schemas.
- **Evidence**: `agent://EvidenceCost` §1 (per-run vs per-session); `bench.py:410-421`,
  `bin/codegen:136-137`, `bin/consult:105,149` read directly.
- **Control**: a per-session cost ledger — the arm-bench row applied live — as the
  second ledger over the same execution, `dual ledgers` [2608.26195].
- **Where**: PostToolUse ledger (record) + Stop gate (threshold); ceiling stated at SessionStart.
- **Design**: signal = cumulative cost/tokens and cost per completed unit of work. New
  data is required: no host payload carries usage, so reuse `extract_usage`
  (`bench.py:162-260`) over the host's own record (`payload["transcript_path"]` on
  Claude/Cursor, `agent_end.messages` on omp, `bench.py:246-260`), ledgered as a `cost`
  kind under the "null, never 0.0" rule. Rule: at Stop, a cost above the ceiling blocks
  quoting the figure and the delta; below it, one line and pass. It fails honestly when
  no host exposes usage — "cost unmeasured", never a silent pass. Test: replay a
  transcript with its usage block deleted; assert unmeasured, never zero.
- **Cost**: one extra transcript read per turn (statusline already parses that file,
  `statusline.py:56-98`); false positives only if a pricing object is counted as tokens,
  the defect `bench.py:165-177` guards.

### 2. Endless planning with no execution — `Sonsuz planlama, hiç execution yapmama`
- **Today**: partial, prose only. The loop-discipline clause governs re-running
  *checks*, not planning — "Three attempts on one failure is the ceiling"
  (`hooks/tezgah_policy.py:451-455`) — text with no runtime reader. The Stop gate cannot
  see the mode: `stop_reason` computes `worked = ev & {"edit", "verify", "verify_fail",
  "run"}` and returns `None` when that set is empty (`hooks/tezgah_integrity.py:369-403`).
- **Evidence**: `hooks/tezgah_policy.py:451-455`, `hooks/tezgah_integrity.py:369-403` read
  directly; `E1` (`experiments/E1-write-path-coverage/results.jsonl`): 7/7 write-time
  refused, 12/12 trajectory-time (`p1`-`p12`) allowed.
- **Control**: a plan-to-execution ratio with a hard revision bound — the bounded
  critic-refiner loop, `a maximum of three rounds (R=3)` [2608.24361].
- **Where**: PostToolUse ledger + Stop gate.
- **Design**: signal = consecutive turns whose only recorded evidence is a plan artifact
  (a `plans/`-scoped edit or a plan heading) versus turns carrying an executed action.
  Data: the ledger separates `edit` from `run`/`verify` (`tezgah_integrity.py:306-315`), so
  only a turn index and plan flag are new. Rule: after N revisions of one plan path with
  zero `run`/`verify` between them the Stop gate blocks naming the path and count; N is the
  three the contract already uses, so one number governs both loops. It fails on design work
  with no code to run, so any `run` entry clears it and the count is per-plan-path. Test:
  three plan edits with no `run` block on the fourth; with one `run` interleaved they pass.
- **Cost**: Stop-time, ledger-only, no per-call cost; false positives on pure-design
  sessions, bounded by the accept-any-run escape.

### 3. Silent quality degradation — `Sessiz kalite düşüşü`
- **Today**: absent live, partial offline. Live: the ledger records no size, count or
  shape — `classify` returns only `edit`/`run`/`verify` (`hooks/tezgah_integrity.py:306-315`)
  and the Stop rule is a vocabulary match with no length or structure term
  (`tezgah_integrity.py:338-341`, `:369-403`). Offline: `grade()` counts `collateral`
  stray edits against an `allow` list (`benchmarks/arm-bench/bench.py:138-153`) and
  `analyze.py:64-84` prints median in/out/cache tokens plus timeout and no-usage counts —
  after a whole block, per arm, never per turn.
- **Evidence**: `hooks/tezgah_integrity.py:306-315, 338-341, 369-403` read directly (no
  size or shape term in any); `bench.py:138-153`, `analyze.py:64-84` read directly; `E2` —
  8/10 explicit claims refused, 0/10 implicit
  (`experiments/E2-completion-claim-coverage/analysis.md`).
- **Control**: an in-session structural-divergence monitor — the finding that
  `successful traces followed a focused path through 9 of 25 states, while failures spanned all 25 states with more chaotic exploration` [2608.23670].
- **Where**: PostToolUse ledger + Stop gate.
- **Design**: signal = per-turn output shape: reply bytes, tool calls by kind, distinct
  files touched, verify runs, the prose-to-evidence share, all from the Stop payload's
  `last_assistant_message` and the ledger (`hooks/tezgah_integrity.py:317-336`). Rule: over a
  k-turn window, a turn whose shape collapses (reply bytes and distinct-file count both below
  the median margin) while still claiming completion raises a Stop-gate warning naming both
  numbers, and a strictly monotone decay over k turns blocks. It fails on a small edit after a
  large refactor, so the block requires decay *and* claim, never one low turn. Test: a
  five-turn ledger with shrinking evidence and a closing claim blocks; without it, passes.
- **Cost**: O(1) per turn over a k-turn window; the false-positive risk is the whole design
  constraint, which is why two conditions are required.

### 4. Missing observability — `Observability eksikliği`
- **Today**: partial. The ledger is append-only, one JSONL line per event with `kind`,
  `ts` and `detail` truncated to 200 chars (`hooks/tezgah_integrity.py:113-125`, `:127-136`);
  `counters()` aggregates denies-by-rule, nudges, fanout and `codegen_failed` (`:153-180`),
  surfaced by `tezgah-status --counters` (`bin/tezgah-status:38-56`); the status line
  reports armed/used state (`statusline.py:56-102`, `hooks/tezgah_context.py:759-808`);
  the classifier logs one prompt line to a 64 KB ring (`tezgah_context.py:302-305`).
  Missing is the causal link: no turn or step index, no tool-call id, no prompt or reply
  hash; the host outcome marker `[exit!=0]` is free text nothing parses
  (`tezgah_integrity.py:150`). The benchmark row has all of it — `prompt_sha256`,
  `fixture_sha256`, `arm_cmd`, `host_version`, `model`, `started_at`
  (`benchmarks/arm-bench/bench.py:418-421`) — and the live ledger none.
- **Evidence**: `hooks/tezgah_integrity.py:113-125, 127-136, 150, 153-180`,
  `bin/tezgah-status:38-56`, `statusline.py:56-102`,
  `hooks/tezgah_context.py:302-305, 759-808`, `bench.py:418-421` read directly.
- **Control**: a provenance link on every ledger entry, on the requirement that
  `reliable causal attribution requires explicit decision-to-provenance links` [2608.07899].
- **Where**: PostToolUse ledger.
- **Design**: signal = the ledger line P1 (`to_human/synthesis.md`: one schema, extended once),
  so a failure walks back to the step that introduced it. Data: `turn`/`step` countable from the
  host payload in the hook process (omp's statusline already carries a per-event `idx` glyph,
  `hosts/omp/hook.py:59-93`), `tool_call_id` host-provided, the hash
  `sha256(last_assistant_message)`. Recording, not denying: an entry missing any field is
  written with an explicit `unlinked` marker and counted, so an unlinked event is never read as
  a linked one. It fails when a host provides no step identity — the marker must be honest.
  Test: replay one session's events; assert every entry is linked or `unlinked` per `--counters`.
- **Cost**: tens of bytes per entry, one hash per turn; no false-positive risk because the
  rule never blocks.

### 5. Missing idempotency — `İdempotency eksikliği`
- **Today**: absent. Check run: `grep -i 'idempot|dedup|operation_?id|op_?id|replay|nonce'`
  over `hooks/`, `hosts/`, `bin/` returns installer-level idempotency only —
  `hooks/tezgah_agents.py:425-427` (one managed `.gitignore` block), `hooks/tezgah_index.py:35`
  (a warm daemon start), `bin/tezgah-setup:24,163,539,1092` (re-running setup) — none keyed
  on an action. The closest identity is the mutable `session_id` slug
  (`hooks/tezgah_integrity.py:105-110`), and the PostToolUse matcher is
  `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell` (`hooks/hooks.json:19-24`), so an
  effect through any other tool is unrecorded.
- **Evidence**: the grep above (named and run this session);
  `hooks/tezgah_integrity.py:105-110`, `hooks/hooks.json:19-24` read directly.
- **Control**: an action key checked before the effect, on the append-only ledger as
  substrate — `an append-only ledger of typed events with byte-offset resume` [2609.01466].
- **Where**: PreToolUse gate.
- **Design**: signal = `key = sha256(tool_name + normalized(target) + normalized(args))` for
  every call the gate classifies as an effect (a write tool, or a shell command matching the
  gate's write patterns, `hooks/tezgah_gate.py:51-55`). Data: PostToolUse already records
  `edit`/`run` with the target in `detail` (`tezgah_integrity.py:317-336`), so the key is
  derivable by replay. Rule: a repeated key in one session window records a `repeat` event
  and, for an outward-facing effect (`git push`, deploy), denies quoting the original detail.
  It fails when a repeat is legitimate, so the deny covers effects whose first attempt recorded
  no failure (`verify_fail` clears it). Test: two identical write calls → one effect, one `repeat`.
- **Cost**: one hash plus one ledger scan per effect call; false positives only on genuine
  repeat work, which is the mode itself.

### 6. Missing circuit breaker and limits — `Circuit breaker ve limit eksikliği`
- **Today**: partial — per-operation ceilings, no breaker. `codegen` never retries and exits
  2 to force a fallback (`bin/codegen:214-220`, contract `:15-27`, router rule
  `hooks/tezgah_policy.py:256-262`); `consult` captures per-model errors without retrying
  (`bin/consult:90-95`), caps at `deadline = timeout + 15` (`:149`) and hard-exits so a hung
  thread cannot wedge the run (`:175-179`); the index worker retries `RETRIES = 5` / 3 s and
  leaves a `<stamp>.failed` marker (`hooks/tezgah_index.py:23-24`, `:41`, `:57-61`); the
  benchmark caps a run at 600 s (`benchmarks/arm-bench/bench.py:558`) and each check at 120 s
  (`:116-136`); the block runner fixes `TIMEOUT = 300`, `PARALLEL = 6`
  (`benchmarks/arm-bench/orx_block.py:25-27`, pool `:82`). Absent: any token or step budget,
  and any cap on host subagents — `counters` counts fanout (`tezgah_integrity.py:178-179`)
  but nothing bounds it; the only pool caps are `ThreadPoolExecutor(len(models))`
  (`bin/consult:150`) and `orx_block.PARALLEL`.
- **Evidence**: the file:line set above, read directly; `agent://EvidenceCost` §2 ("Retry cap
  of 2 for transient errors", "Subagent concurrency cap") and §3 ("Timeout ceilings are
  per-process, not per-turn").
- **Control**: one breaker per loop kind, bounded retries and early termination —
  `bounded retries, and early termination strategies` [2608.26195].
- **Where**: PreToolUse gate + Stop gate.
- **Design**: signal = attempts per `(tool, digest)` and steps per turn. Data:
  retries are visible today only inside each tool; the ledger's `verify_fail` and `[exit!=0]`
  marker (`tezgah_integrity.py:150`) is the natural counter once parsed. Rule: the counter and
  its ceiling are P4 (`to_human/synthesis.md`) — one counter keyed on `(tool, digest)`, ceiling
  2 for a transient `fail_class` and 1 for `unknown`/`permanent`, reset per user turn — and the
  Stop gate blocks a turn that exceeded a step or token ceiling without changing state. It
  fails on a flaky service where the refused attempt would have worked, so the breaker opens on
  *identical* failures only. Test: two `verify_fail` rows for one `(tool, digest)` in a turn,
  then the next identical call is denied; a differing command passes.
- **Cost**: one ledger read per gated call, bounded by the session's own line count; false
  positives concentrated on flaky checks, excluded by the identical-signature condition.

### 7. Schema/API drift — `Schema/API drift`
- **Today**: partial, offline only. Every adapter hardcodes a foreign host's field names with
  no version stamp: `hosts/cursor/hook.py:2` states the adapter exists because "Cursor uses
  its own event names and output schemas"; `hosts/codex/hook.py:82-93` reads the outcome from
  `tool_response.exit_code` and returns `None` when it is absent or not an int. The
  degradation is silent: `note_tool` writes an unknown outcome as `verify` — a check that RAN
  (`hooks/tezgah_integrity.py:317-336`) — correct per record, but a renamed field weakens the
  Stop gate without an error. Offline is the counter-example: `extract_usage` pins per-host
  key names and returns `None` rather than zero (`benchmarks/arm-bench/bench.py:162-177`),
  fixed as PREREGISTRATION rule 2 (`PREREGISTRATION.md:57-61`), and one supply-chain drift is
  guarded by a test that every package runner declares a version
  (`tests/test_setup.py:964-1000`). Check run:
  `grep -i 'schema|schema_version|payload_version|quarantin'` over `hooks/`, `hosts/`, `bin/`,
  `statusline.py` returns host *config* and MCP-tool `$schema` declarations
  (`bin/tezgah-setup:63-64,700,735,976,1565-1570,1598-1633,2160-2162`), that module's own
  schema/budget notes (`:807-808`, `:1541-1543`) and four prose uses
  (`hooks/tezgah_context.py:39`, the classifier's `schema change`;
  `hooks/tezgah_policy.py:237,382`; `bin/consult:90`; `hosts/cursor/hook.py:2`) — no payload
  version, no quarantine path.
- **Evidence**: the grep above; `hosts/codex/hook.py:82-93`,
  `hooks/tezgah_integrity.py:317-336`, `bench.py:162-177`, `PREREGISTRATION.md:57-61`,
  `tests/test_setup.py:964-1000` read directly.
- **Control**: a declared field map per adapter with a required-field check and a quarantine
  counter — the property that `each attribute has a stable name and meaning across executions` [2608.24271].
- **Where**: PostToolUse ledger + host bridge.
- **Design**: signal = the fields an adapter must read per event, declared beside the adapter,
  plus a `schema_drift` ledger kind. Data: the adapter's own required-field list plus the payload
  it already has; the host version is computed in the benchmark (`bench.py:418`). Rule: at
  PostToolUse, a required field missing or of the wrong type writes `schema_drift` naming the
  adapter, the field and the host version, and never writes `verify_ok`; the counter surfaces
  through `--counters` (`bin/tezgah-status:38-56`). It fails on a host that renames a field while
  keeping its meaning: drift is reported until the map is updated — a true positive, the map IS
  stale — so the noise dedupes per session. Test: replay a payload with one field renamed; assert `schema_drift`, no `verify_ok`.
- **Cost**: one field check per PostToolUse call, no network or subprocess; false positives are
  the deduplicated per-session drift entries.

### 8. Model/provider behaviour difference — `Model/provider davranış farkı`
- **Today**: partial. The text is single-sourced — the policy module exists so that "Claude,
  Codex, Cursor, opencode, dsh and omp say exactly the same thing"
  (`hooks/tezgah_policy.py:9-10`), rendered per host by `context_for`
  (`hooks/tezgah_context.py:409-506`). Behaviour is not: one role is encoded four ways by host
  capability (`hooks/tezgah_agents.py:223-273` — `disallowedTools` for Claude/Cursor,
  `readonly` for Cursor, an explicit read-only tool list for omp at `:263`), and the two CLIs
  hold separate provider/model tables (`bin/codegen:37-53` vs `bin/consult:27-43`). The axis
  is recorded per run — `model` and `host_version` in every benchmark row
  (`benchmarks/arm-bench/bench.py:418`) — but nothing compares behaviour across it, and
  `tests/test_providers.py:1-40` covers only unknown-provider and missing-key paths.
- **Evidence**: `hooks/tezgah_policy.py:9-10`, `hooks/tezgah_context.py:409-506`,
  `hooks/tezgah_agents.py:223-273`, `bin/codegen:37-53`, `bin/consult:27-43`,
  `benchmarks/arm-bench/bench.py:418`, `tests/test_providers.py:1-40` read directly; `E2`
  (`experiments/E2-completion-claim-coverage/analysis.md`) — the vocabulary carries
  `düzeltildi` and misses `giderildi`.
- **Control**: a per-(host, model, version) conformance record, on the finding that behaviour
  is `largely dictated by the deployment harness (tools, system prompt) rather than the specific LLM` [2608.23670].
- **Where**: SessionStart context + CLI.
- **Design**: signal = the pass rate of a small in-repo conformance corpus per (host, model):
  does the model call the tool the contract names, write in the required language, emit the
  evidence line, and refrain from retrying when told to. Data: the benchmark already measures
  the offline half (`bench.py:410-421` records `model` and `host_version` per row,
  `analyze.py:64-84` scores it), so the control promotes those two fields into a declared
  capability record read at SessionStart and fails loudly when the session's model has no entry.
  It fails when a provider silently re-points a model id: the record is then wrong and the brief
  must name the observed id, not the configured one. Test: a missing entry yields an explicit "unverified model" line.
- **Cost**: one extra SessionStart line plus a benchmark block per new model; no per-call cost.
  False positives only if the corpus is model-specific rather than contract-specific.

## Group summary

| mode | today | control | where | effort |
|---|---|---|---|---|
| 1. Runaway cost / token blow-up | absent | per-session cost ledger vs a configured ceiling, "null never 0.0" | PostToolUse ledger + Stop gate | M |
| 2. Endless planning, no execution | partial (prose) | plan-to-execution ratio with the three-revision bound | PostToolUse ledger + Stop gate | S |
| 3. Silent quality degradation | absent (proxy offline only) | rolling output-shape decay over k turns | PostToolUse ledger + Stop gate | M |
| 4. Missing observability | partial | `(turn, step, tool_call_id, reply_sha256)` per entry | PostToolUse ledger | S |
| 5. Missing idempotency | absent | action key `sha256(tool+target+args)` checked before outward effects | PreToolUse gate | M |
| 6. Missing circuit breaker and limits | partial | breaker on identical failure signatures + step/token ceiling | PreToolUse gate + Stop gate | M |
| 7. Schema/API drift | partial (offline only) | declared adapter field map + `schema_drift` quarantine counter | PostToolUse ledger + host bridge | S |
| 8. Model/provider behaviour difference | partial | declared `(host, model, version)` conformance record at session start | SessionStart context + CLI | M |

For mode 3 no mechanical control can decide quality: every in-session signal is a proxy (reply
size, distinct files, evidence density), and a proxy can flag a decay but cannot call a shorter
answer worse. The honest form is the one the repository already uses offline — an acceptance
artifact the executor cannot see or edit, `grade()`'s hidden checks and `allow` list
(`benchmarks/arm-bench/bench.py:116-153`) — so the block above is a decay detector, not a
quality test. Mode 8 is the same shape for another reason: a behavioural difference between two
models cannot be removed by a hook at all, only declared, probed and surfaced, which is why its
control is a record rather than a rule. Mode 1 has a data gap, not a design gap: the usage a
budget needs is absent from the tool payload on every host and lives only in a transcript whose
path is exposed on Claude and Cursor and nowhere else, so on omp, dsh and opencode the control
can report "unmeasured" — still a control, because a silent pass is the defect. Two assigned
literature ids, `2608.29646` and `2608.25920`, were not in `literature/` when the
sections were drafted — the index says they were fetched after the briefs named
them, "before they existed here" — so they are cited nowhere above; the count in
that draft sentence is stale, because `ls` now lists 41 report ids plus `INDEX.md`,
which records 38 fetched in the main retrieval loop and those two plus
`2605.05403` afterwards (`literature/INDEX.md:5-8,48,51`). The earlier absence is
reported, not hidden.
