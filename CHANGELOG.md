# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Ledger action identity, trace metrics and the loop guard** (plan 012). Every
  evidence row now carries `id` (a digest of the tool and its canonical
  arguments), `exit`, `out_bytes`, `fail_class` and `workspace`, written by both
  the Python hooks and the opencode plugin. On top of that identity: the
  PreToolUse gate denies a third identical call whose previous attempts exited
  non-zero (two attempts when the last failure was transient), and
  `tezgah-status --counters` prints `steps`, `tool_error_rate`, `claims` and
  `false_completion`. The Stop rule now counts a `verify_ok` as support only when
  the host reported exit 0, a non-empty result and an unmasked command; rows
  written before this change are tolerated so an open session is never blocked on
  its own history. Hook medians moved by less than 2.2 ms
  (`benchmarks/hook-latency/`).
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

### Changed

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
