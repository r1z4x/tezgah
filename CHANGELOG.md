# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **The task rule's refusals no longer print the command that lifts them, and a
  session can no longer move the boundary it is held to.** Rule 10
  (`hooks/tezgah_gate.py`) ended both of its refusals with the exact
  `tezgah-task` invocation that clears the phase or widens the allowlist, and the
  E7 block measured what that printed unlock costs: across the armed arm's 25
  runs the boundary came down every time - 24 of them moved the record into a
  write phase, the 25th cleared it and wrote anyway - and no run obeyed the
  refusal (rows under `benchmarks/arm-bench/results/e7/` on the
  `benchmarks/lab` branch, designed in `PREREGISTRATION-E7.md` there). A refusal
  is a boundary or an instruction, and it cannot be both, so no refusal in this
  rule names a command now: each names what it refused, and says the phase and
  the allowlist are the user's to move. Two refusals close the ways a session
  could move that record itself - a write whose target IS the record, refused
  whatever the phase and whatever the globs say, and a shell command that would
  change it through the CLI (`start`, `phase`, `allow`, `stop`), matched on the
  masked command so a grep over the docs or a commit message naming the CLI still
  passes. `task-off` removes all three.

- **`--help` no longer costs a paid call on `consult`, and no longer runs the
  work on `tezgah-agents` and `tezgah-index`.** None of the three had a help
  arm, so the flag landed in the positional argument. `consult --help` sent the
  flag text to the panel as an engineering question and printed no usage;
  `tezgah-agents --help` read it as a PATH and regenerated the repo's subagent
  set (or printed nothing when that path did not resolve); `tezgah-index --help`
  printed the index status and spawned the auto-index worker. All three answer
  `-h`/`--help` with the usage in their docstring now, and one test per tool
  holds it.

- **`tezgah-setup --mcp-schemas` measures every server tezgah registers.** It
  reported the graph server alone while its docstring promised every server, so
  the band it printed (15 tools / 24,508 bytes / ~6.1k tokens) left out the two
  app-analysis servers that ride every request in the Claude, Codex, Cursor and
  opencode configs. Measured on this machine the band is 73 tools / 74,390 bytes
  / ~18.6k tokens; a server that cannot start is reported as not measured.

- **The status line's own renderers separate the mark groups.** opencode's TUI
  plugin and dsh's Web status line build their line from `tezgah-status --json`,
  which carried no group, so both drew every mark with the same spacing and
  dropped the `  ·  ` that `render_line()` puts between the always-on switches,
  the on-demand capabilities and the per-repo facts. Each segment carries its
  `group` now and both renderers use it, so the four surfaces read the same.

### Changed

- **A `rm -rf` under a temp root no longer needs the user's approval.** The
  consent rule asked about any recursive force delete outside the run directory,
  including the session's own fixtures in `$TMPDIR`/`/tmp` - where nothing is
  irreversible and the ask protected nothing, so clearing scratch cost a round
  trip through `bin/tezgah-consent`. Every target is now resolved and tested
  against `SCRATCH_ROOTS` (`hooks/tezgah_gate.py`): a path under one is scratch
  and passes, while the temp root itself (`rm -rf /tmp`), a path that escapes it
  (`/tmp/../etc`), an unresolved `$VAR`/`~` target, and any second target outside
  it still ask. Only the ask is skipped: the untrusted-content rule reads the
  class conservatively, so a scratch delete in a turn that read a fetched page or
  an MCP answer is still refused. opencode's own gate
  (`hosts/opencode/plugins/tezgah.js`) mirrors the floor. Accepted risk, named:
  `/tmp` is shared per-user space, so this
  also lets a delete reach another process's disposable state there.

- **`tezgah-setup --report` no longer claims the local plugin manifest is
  present.** The row read "present and consistent" while its predicate also
  passes on an absent pair - the manifest is the maintainer's untracked file, so
  absence is normal. It reads "consistent when present".

- **`hooks/projects-posttooluse.py` and `hooks/projects-stop.py` are executable
  like the other two hook scripts.** Both manifests invoke every hook as `python3
  "<path>"`, so no wiring was broken; only the file mode was wrong.

### Added

- **An open plan can be the session's active task, and the gate enforces it.**
  The record is the plan file itself - no `task.json`, no second file: two
  optional frontmatter keys, `phase:` (`discovery`, `implementation` or
  `verification`) and `allowed_paths:` (a `- glob` list relative to the repo
  root), and at most one open plan carries a phase because `start` clears it
  from the others. Rule 10 of the tool gate (`hooks/tezgah_gate.py`) refuses a
  write in `discovery`, or one outside the globs, naming the phase or the file
  and no command that lifts either (see `Fixed` above); a path that resolves
  outside the repo root never matches a `**` pattern.
  `bin/tezgah-task start|phase|allow|stop|status` is the only writer and the
  user runs it - the agent never does - so what the gate refuses on is a
  boundary the user set in advance, and `task-off` removes the rule's refusals.
  Where the record is missing, unreadable or out of phase vocabulary the rule
  fails open, and an empty allowlist reads as "any path in the repo" rather than
  "nothing allowed": a gate that refused every write until a record appeared
  would have the whole session as its blast radius. The phase also rides every
  user turn as one line (`hooks/tezgah_context.py`), so a session meets the
  boundary before a write meets the refusal. opencode does not mirror the rule:
  its plugin puts each write to `bin/tezgah-gate check`, which prints the core's
  own decision and nothing else, because the JS mirror is documented as
  incomplete and divergent.

## [0.10.0] - 2026-09-18

### Changed

- **The benchmark moved to its own branch.** `benchmarks/` - the arms, the
  fixtures, the pre-registrations and `bench.py` - is no longer on `main`; it
  lives on `benchmarks/lab`, cut before the removal so the tree is intact there.
  `main` keeps the results: every README's benchmark section still carries its
  block table and findings, and now says where the instrument is instead of
  pointing at a directory this branch does not have. Three things went with the
  tree because their subject left: the test that pinned
  `benchmarks/harness-vs-omp/README.md` against the installer's live budget
  report, the arm-bench entries in `.gitignore`, and the fixture excludes in
  `pyproject.toml`. The `opencode-bare` arm needs its dependencies installed
  again on that branch before it can run.

- **Three README translations are gone, and the benchmark paragraph now points
  somewhere a reader can reach.** Brazilian Portuguese, Chinese and Japanese are
  removed, leaving English, German, Spanish, French and Turkish, and every
  remaining language switcher dropped the three links. The benchmark section no
  longer cites `docs/research/2026-09-16-tezgah-quality.md` - a local note that
  was never in the repository, so the published README pointed at a file nobody
  could open - and names the OpenResearch project `tezgah-harness-research`
  instead. The local notes themselves and the prepared `opencode-bare` fixture's
  `node_modules` left the working tree with them; the study is archived outside
  the repository, and that benchmark arm needs its dependencies installed again
  before it can run.

- **The public repository no longer carries the local state.** `.tezgah/` (the
  lessons ledger and the research lines) and `.claude-plugin/` (the plugin
  manifest, whose marketplace path is a personal one) are gitignored and
  untracked: they stay on the maintainer's machine and a clone stops carrying
  them. The READMEs' Claude install line is `bin/tezgah-setup --install --hosts
  claude` like every other host, the manifest note in the READMEs and
  `RELEASING.md` says it is local, `bin/tezgah-setup --version` falls back to the
  newest `CHANGELOG.md` heading when the manifest is absent, and `--status`
  reports an absent local manifest as normal rather than as a failure. What this
  costs, named rather than implied: Claude's skills, agents, output style and
  hooks were installed by the plugin channel, so a fresh clone can no longer arm
  Claude - the maintainer's checkout keeps them through the untracked manifest,
  and wiring those four through `bin/tezgah-setup` is the follow-up.

- **The README translations are reduced to six languages plus Turkish** -
  English, 简体中文, Deutsch, Español, Français, 日本語, Português (Brasil), Türkçe -
  and every remaining file's language switcher lists exactly that set. The
  eleven dropped translations (বাংলা, Bosanski, Dansk, Italiano, 한국어, Norsk, Polski,
  Русский, ไทย, Українська, 繁體中文) stay in git history; English is still the
  source of truth. The one sentence each translation carries about the shipped
  library was re-read through `consult --online`: the French, Spanish, Italian
  and Brazilian Portuguese lines no longer carry a "vendored" loan word, and the
  Chinese line says 仓库内置的 rather than an inline English term.
- A copy of the plugin (the tree Claude Code actually runs) now syncs past a
  path that is deleted in the working tree but not yet staged in the index;
  `ls-files` still lists it, and copying it crashed `--sync` and `--install`
  (hit while the README translations were reduced).

### Added

- **A research claim is recorded under a lock.** `bin/tezgah-research claim
  <slug>` reads one claim as a JSON object on stdin, applies the same rules
  `check` applies to a row, and appends it to the line's `claims.jsonl` under an
  exclusive `flock` on that file, refusing with the reason and writing nothing
  when the claim breaks a rule or the file is another writer's. Recording a claim
  used to mean editing the file: an unlocked read-modify-write of the one file
  every claim of a line lives in, guarded only by the gate's `race` rule - whose
  own comments name two ways a writer escapes it (`hooks/tezgah_gate.py:805` and
  `:828`) - so two sessions recording at the same moment could lose a claim
  silently or leave a line that does not parse, which `check` reports as `does
  not parse` rather than as a race. Exit codes follow the rest of the CLI (0
  recorded, 1 refused, 2 misuse), and refusing rather than falling back to an
  unlocked append is the one place this path deliberately differs from the
  ledger's `_append`.

- **The user's half of the consent rule is a command.** `bin/tezgah-consent
  <digest>` records that the user approved the action the gate asked about, and
  `tezgah-consent --last` approves the newest ask no grant answers yet, so a
  digest never has to be copied by hand. Both write
  `{"kind": "grant", "detail": "cli", "id": <digest>}` into the ledger that
  carries the ask - the session the gate reads the approval from - through the
  same appender the hooks write their rows with. The ask, the approval and a
  repeat the gate allowed stay three rows in that ledger (`consent`, `grant`,
  `repeat-allowed`) instead of one row meaning all three, and the contract says
  what to put in front of the user when the gate refuses.
- **A declared effect can only make the gate stricter.** A command that names its
  own class with `tezgah:effect=<class>` (outward, publish, deploy, schema,
  destructive) is held to it when it stands at or above the class the command
  text derives, which is how an effect no pattern can see still gets asked about.
  A declaration that would stand below it is ignored and named in the refusal, so
  no command can talk its own class down: a declaration that can loosen the gate
  reading it is a bypass of that gate.
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
- **Two opencode wiring gaps the first live host turn exposed.** The generated
  router now names tezgah's own on-demand skills in the always-on section
  (`research (tezgah's own)`), because a library a session is never told about is
  one it answers from memory instead: on a research prompt `opencode run` globbed
  the project, found nothing, and reported estimates. And the installer grants
  `external_directory` read for the two directories tezgah installs
  (`<checkout>/skills/**` and `~/.config/tezgah/bin/**`) - a skill body and
  tezgah's own CLIs live outside the session's project, and opencode auto-rejects
  a permission prompt nobody can answer in a non-interactive run (the same turn's
  attempt to open `skills/ai-research/` was denied). A user's explicit global
  `external_directory` action is left alone, and `--uninstall` removes the grants.
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
  plugin writes the rows that guard reads and enforces the same ceilings from its
  own before-hook. The Stop rule now counts a `verify_ok` as
  support only when the host reported exit 0, the command was not masked by a
  pipe, and - when the host supplies a result size - that size is non-zero; rows
  written before this change are tolerated so an open session is never blocked on
  its own history. Hook medians moved by less than 1 ms against the committed
  baseline (`benchmarks/hook-latency/plan012-after.json`).
- The research workspace: `bin/tezgah-research` (`init`, `check`, `status`; the
  locked `claim` append is a later entry above) and the `research` skill. A
  research line lives in `<repo>/.tezgah/research/<slug>/`
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

[0.10.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.10.0
[0.9.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.9.0
