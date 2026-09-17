# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The domain library ships with tezgah, as one skill.** `skills/ai-research/`
  carries Orchestra Research's `AI-research-SKILLs` (98 skills, 23 categories,
  MIT, revision `773a529`) in the upstream layout, reached as the single
  `ai-research` skill - one metadata entry on every host instead of 98 - with a
  generated stage index (`index/1-frame.md` … `index/6-write.md`) and the flags
  that mark thin or stale bodies. `bin/tezgah-import-ai-research` regenerates the
  tree from a pinned checkout and `--check` verifies every digest without one;
  `SOURCE` names the revision, the drop list and the one modification. The
  research rule, the `research` skill and the generated `tezgah-researcher` agent
  all point at it, so a research line reaches the domain knowledge on all six
  hosts rather than only where an external clone happened to be installed.
- `tezgah-research check` refuses a claim whose proof names a path the line does
  not have - the fabricated-evidence failure - and the `research` skill gains the
  1-5 review anchors with their grade mapping, the claim-type/evidence table, the
  finding record, the citation-verification rule, the evidence-fidelity rules
  (exact numbers, derived views labelled, a source on every row), the deeper
  ideation moves (hidden constraints, kill criteria) and the figure rules.
- **Ledger action identity, trace metrics and the loop guard** (plan 012). Every
  evidence row now carries `id` (a digest of the tool and its canonical
  arguments) and `workspace`, plus whichever of `exit`, `out_bytes` and
  `fail_class` the host actually reports - `note()` drops a field nobody
  reported rather than writing a zero - written by both the Python hooks and the
  opencode plugin. On top of that identity: the
  PreToolUse gate refuses the third identical call whose previous attempts
  failed - one ceiling for every failure class, reset per user turn, with
  `fail_class` kept as a metric only - and `tezgah-status --counters` prints
  `steps`, `tool_error_rate`, `claims` and `false_completion`. The opencode
  plugin writes the rows that guard reads but has no PreToolUse half, so the
  ceiling is not enforced there. The Stop rule now counts a `verify_ok` as
  support only when the host reported exit 0, the command was not masked by a
  pipe, and - when the host supplies a result size - that size is non-zero; rows
  written before this change are tolerated so an open session is never blocked on
  its own history. Hook medians moved by less than 1 ms against the committed
  baseline (`benchmarks/hook-latency/plan012-after.json`).
- The research workspace: `bin/tezgah-research` (`init`, `check`, `status`) and
  the `research` skill. A research line lives in `<repo>/.tezgah/research/<slug>/`
  and holds the question and locked evaluation, the decision log, the findings,
  the claims with their falsification criteria, provenance and evidence, and one
  directory per experiment whose `protocol.md` is committed before its
  `results.jsonl`. `check` fails on the rules a session skips - a protocol
  committed after the run (a protocol written after the results is not a
  prediction), a claim with no falsification criterion or evidence, results with
  no analysis, a findings file that answers none of its four questions - and the
  session context names the first structural one at session start (the order rule
  needs git history, so it stays a `check`-time rule). The skill carries the
  two-loop rhythm, the ideation step, the six-dimension claim review and the
  provenance tags; execution stays on the OpenResearch CLI.
- `tezgah-setup --mcp-schemas` measures the one context band the installer
  could not see: it performs an `initialize` + `tools/list` handshake with each
  MCP server it registers over stdio and prints the tool count and schema bytes.
  On a machine with the graph server installed that band is 15 tools /
  24,508 bytes, several times the always-on contract, and it rides every
  request.
- `tezgah-status --counters` aggregates one session's evidence ledger: gate
  denials by rule, nudges, fan-out, consult and codegen use, and codegen
  fallbacks. The gate now records its own refusals and the ledger carries an
  exit marker on non-verify events, so a rule that never fires is distinguishable
  from a rule that is wrong.
- The reviewer output gains a severity ladder with written definitions, a
  verbatim evidence span per finding, a `kept`/`violated` line for every
  constraint the task stated, and the recorded read order.
- Every generated subagent body now names the tools it may use, and nothing
  else.
- The contract gains three rules: an exogenous acceptance boundary (the
  deciding check is invisible to the executor and the reviewer did not write the
  change), a cohesion gate on fan-out, and an always-on loop-discipline
  invariant (no re-running a passed check, no repeating an identical failing
  command, three attempts is the ceiling).
- The contract also gains an always-on **session scope** rule: tezgah's own
  installation and its optional tools are the user's to maintain, never the
  session's - no install, upgrade, restart, kill or upstream issue mid-session,
  and a missing capability is one line plus the documented fallback. The
  full-contract skill carries the same section, and its two "no code graph" /
  "no consult key" variants are now labelled appendixes that apply only on a
  machine that lacks them.
- `bin/consult` gains a second stage: after the independent parallel answers it
  spends one more call on a referee that names where the panel disagreed, what
  every answer assumed, what would change the recommendation and what evidence
  it still wants, instead of leaving the caller to diff two answers alone.
  `--judge` picks the referee model, `--no-referee` keeps the old one-shot
  behaviour, the footer classes each failure (`http-500`, `empty`, `timeout`,
  ...) and names the single variable to change on a retry, a dead referee is
  disclosed as an unjudged panel rather than hidden, and the question - a packet
  is often several KB - can be piped in with `consult -` instead of argued
  through argv.

### Changed

- The consult rule is checkable and de-anchored: it names five triggers instead
  of "non-trivial", requires the raw artifact and the acceptance criteria rather
  than the author's own summary or conclusion, and requires reading the
  referee's named fields back rather than a paraphrase, which is where the
  minority view gets dropped. The reviewer body carries the same raw-artifact
  rule. The spec rule asks for one genuinely different option beyond A/B/A+B,
  the smallest reversible experiment that separates them, and the evidence that
  would flip the choice. The armed-by-task-class band grows 758 bytes, to 2,989,
  and the always-on pointer line grows 45 characters, taking the core band to
  6,032 - the cost of the rule being visible in every session rather than only
  when it is armed.

- The status line colors the whole `name✓` chip by state (green in force, yellow
  on demand, red off, dim when a mark carries no state) instead of the glyph
  alone, and dims the separators. omp draws it through `ctx.ui.setWidget`,
  because `setStatus` - its other surface - strips ANSI/VT sequences; the
  `setStatus` path stays as the fallback for a build without the widget surface,
  and `NO_COLOR` / `TEZGAH_STATUS_COLOR=0` still force plain text everywhere.

### Fixed

- The attribution ban now covers file contents, not only shell commands: a
  write or edit whose payload carries a credit line on its own line is denied on
  every host, which is what the rule always claimed. Prose that names the ban is
  not a credit, so the documentation that describes the rule is not denied by
  it.
- opencode's plugin state (evidence ledger, first-grep nudge, used marks) falls
  back to a writable directory when the global cache is not writable, matching
  the Python half; previously every write was swallowed and the state vanished.
- `bin/consult` rejects a flag whose value is missing instead of treating the
  flag text as the question and spending a paid request on it.
- The README no longer hand-quotes context-budget figures that move with the
  policy; it points at the command that measures them. The benchmark README's
  embedded report is regenerated and pinned by a test, and the nine translated
  READMEs carry the measured values instead of three mutually contradictory
  stale ones.
- The benchmark no longer publishes a timeout as a pass: `omp+graph` is 19/20
  and `omp+tezgah-port` 18/20 on the column to quote.
- A session start no longer edits a repo's tracked `.gitignore`: the generated
  agent dirs are ignored through the clone's own `.git/info/exclude`, so a
  project that has nothing to do with tezgah is not handed back with a modified
  file. Reproduced before the fix: `bin/tezgah-agents` in a scratch repo left
  ` M .gitignore`, and two of the user's repos carried that uncommitted or
  committed block. `--uninstall` still clears the block from a `.gitignore` an
  older install edited.
- The session brief stays silent when the generated agent set is already
  current. `sync_root` returned "N agent(s) current" on every session start, so
  every project session was told about tezgah's own files in it. The explicit
  `tezgah-setup --agents` still reports the steady state, because it answers a
  user's command rather than injecting context.
- `hooks/tezgah_agents.py` writes now fail open as its own docstring promised: a
  read-only `.git`, a path that is a directory, or a full disk costs the
  generated file instead of raising out of the session-start hook.
- `bin/codegen --timeout` now bounds the WHOLE request instead of one socket
  operation, the way `bin/consult` already did: a response that trickles bytes
  resets urllib's per-recv clock and used to hold the process open indefinitely
  (observed live: an ESTABLISHED connection for over three minutes under
  `--timeout 90`). A stalled request now exits 2 for the router to fall back on,
  and `CODEGEN_URL` overrides the endpoint. A test drives a local trickling
  server that never ends its body.
- The `tezgah-contract` skill no longer ships a copy of the per-turn
  `<harness-reminder>` block: 2 KB of injected reminder text had been committed
  into the skill file, where it is neither the skill nor the reminder.
- The no-graph contract text no longer tells the session to install
  `codebase-memory-mcp`, and the omp hook-failure notice no longer tells the
  model to run tezgah's own diagnostics mid-session: both now report the gap and
  leave tezgah's maintenance to the user.

- `benchmarks/arm-bench/`: a runnable harness/factor benchmark with a frozen
  pre-registration, eight host arms, and 25 task fixtures that each fail before
  their reference fix and pass after it (`bench.py selftest`). Seventeen tasks
  are imported from the historical round-2 corpus, sharing one fixture; the
  rename tasks grade the rename itself, which their hidden test alone could not.
- `tezgah-setup --hosts omp` reports whether each app-analysis MCP command is a
  single executable, the shape omp spawns.

### Changed

- The status line colors the whole `name✓` chip by state (green in force, yellow
  on demand, red off, dim when a mark carries no state) instead of the glyph
  alone, and dims the separators. omp draws it through `ctx.ui.setWidget`,
  because `setStatus` - its other surface - strips ANSI/VT sequences; the
  `setStatus` path stays as the fallback for a build without the widget surface,
  and `NO_COLOR` / `TEZGAH_STATUS_COLOR=0` still force plain text everywhere.

### Fixed

- omp's `mcp.json` app-analysis servers are written as `command` + `args`: the
  whole argv in `command` made omp spawn the comma-joined string and fail with
  `ENOENT`, so `playwright` and `mobile-mcp` never connected. Re-running the
  installer repairs an entry an earlier release wrote and keeps the user's other
  keys in it.

## [0.9.0] - 2026-09-16

First tagged release: one shared working contract for Claude Code, Codex,
Cursor, opencode, dsh and omp.

### Added

- Task-class arming: the advisory rules (spec-first, second-opinion consult,
  OpenResearch routing, code-graph-first) are expanded per prompt from the
  per-turn hook, wired for Claude, Codex, Cursor and dsh. Their invariants and
  the irreversible-actions safety rule stay always-on, every advisory rule keeps
  an actionable one-line pointer, and the per-prompt decision is audited to
  `~/.cache/tezgah/classify.log` (armed set and prompt length, no text).
- `omp` (oh-my-pi) host: `~/.omp/agent` gets a managed `RULES.md` always-on
  block, skills, generated subagents, an `mcp.json` and a `hooks/pre` gate.
- Always-on context-budget report from `tezgah-setup`.
- tezgah-vs-oh-my-pi harness benchmark under `benchmarks/`.
- README translations and a logo, plus the community-health files.

### Changed

- opencode's generated skill router keeps only the coding buckets always-on and
  points at `opencode-skills.full.md` for the rest: about 20.5 KB → 7 KB of
  instructions per session.

[0.9.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.9.0
