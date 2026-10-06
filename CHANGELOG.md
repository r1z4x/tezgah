# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`tezgah-gate replay` measures the gate against its own history.** It
  replays this machine's real ledgers through the unmodified dry-run gate and
  the Stop rule. It runs in a sandbox HOME, with the clock frozen at each call.
  It prints the corpus size, the join rate and every exclusion with its count.
  Per stratum, it prints how often the replayed verdict equals the recorded
  one. Every figure names its cutoff. `replay --sheet` draws a blind label
  sample that shows no verdict. `replay --report --labels <file>` turns two
  raters' labels into per-rule false-block rates and Stop error rates. Each
  rate carries a Wilson 95% interval, and the report adds Cohen's kappa. It
  also folds the denial budget: runs of 3 consecutive denies per rule in one
  turn, and sessions with 20 or more. Nothing leaves `~/.cache/tezgah/replay`,
  and no gate behaviour changes. `tezgah-taste`'s transcript walkers can now
  read subagent files and tool inputs. `mine` reads what it read before.

- **Opt-in taste capture, and a miner for the corrections already on disk.**
  Arm it with `~/.config/tezgah/taste-on`. A repository with a `.tezgah/`
  directory then gets `.tezgah/taste/signals.jsonl`. It holds each prompt,
  each landed edit's old and new text, and a snapshot of the bytes the write
  left. Redaction and a length cut apply to the text. A `.no-taste` mark turns it off per
  repository. `tezgah-taste mine` counts and extracts the prompts that
  followed a writing turn in omp and Claude transcripts. `tezgah-taste
  measure` and `tezgah-taste rate` sort them with the judge seam into
  preference, defect or none. This phase learns and injects nothing.

- **The Stop hook now records the reply after a block.** On Claude, Codex and
  omp the hook skipped the reply that answers a block. It now judges that
  reply in record-only mode and writes one `after_block` row. The row says
  whether the rule would refuse the reply, let a claim through, or found no
  claim. It never blocks a second time and never counts as a claim or as a
  reply. A block from another Stop hook leaves no row. Cursor stays unwired:
  nobody has checked its stop payload yet.
- **A subagent's end leaves a record-only verdict.** Claude's SubagentStop
  (a new hook row) and Cursor's subagentStop now judge the subagent's last
  reply. They read the evidence half of the Stop rule and write one
  `subagent_end`
  row. It never blocks and never counts as a claim. Every Stop adapter names
  its re-ask budget as `STOP_REASKS = 1`. On Claude a subagent's tool rows
  still sit in the parent's ledger, so the row judges the parent's turn until
  the agent key lands.
- **Lessons keep their rule when injected.** A lesson line is now written rule
  first: `<rule> - <incident>`. The rule sits in the first 120 characters, so
  the 200-character cut keeps it. The session block says how many of its lines
  do not open with their rule. A line ending `|| enforced_by: <rule|test>` leaves
  the injected blocks while that gate rule or test is on. A test counts only
  while the repository still defines it. A switched-off rule brings the line
  back. `tezgah-lessons` proposes rule-first rewrites, merges of duplicate lines
  and those retirements. It never writes the ledger. On this repository's
  47-line ledger the session block grows from 1266 to 1352 bytes. omp's
  `RULES.md` lessons line grows from 230 to 270 bytes. The always-on core
  shrinks by 23 bytes.
- **The per-turn lessons block shrinks before the budget drops it.** Over budget
  it keeps its first lesson. The session remembers only the lessons it shows. The
  drop log records this as `kind=truncated`. Each injected lesson leaves a
  `lesson` ledger row with its key and block, and that row is not gate evidence.
- **A wider citation audit.** `bin/tezgah-docs --citations` now judges a bare file
  name and a symbol written after its citation. It also reads the comments and docstrings of the Python code. A
  `path:N` it cannot read counts as unjudged. The tree reads 524 judged and 1022
  unjudged, up from 429 judged. A file whose unjudged count is above or below its
  entry in `docs/citations-baseline.json` fails the check. `--citations --update`
  rewrites that file. The same pass reads all ten Stop classes by AST. It also checks the
  gate's rule order and switches, the judge's callers and the kill-switch names.
  `tests/neuter_matrix.py` generates one mutant per gate rule.

### Changed

- **Docs cite Python code by symbol.** A citation into Python code is now
  `path::name` or `path::Class.method`, not `path:line`. Moving lines no longer
  shifts it. `bin/tezgah-docs --citations` reads the cited file's AST and fails
  on a name it does not define. 961 docs citations moved to the new form. The
  rest kept `path:line`: no single enclosing symbol, a non-Python target, or a
  stale line nobody has re-anchored yet. They stay under the unjudged ratchet.
- **The rule ledger drops its `since` column.** A history rewrite left no
  record of the first commit that carries each rule. The provenance table in
  `docs/gate.md` now has `rule`, `incident`, `evidence` and `pin`.

- **The lessons ranking ignores words that name no lesson.** English and
  Turkish function words no longer rank a line. On a ledger of ten or more
  lines, neither does a word found in more than half of them. "update the
  changelog" used to inject three unrelated lessons and now injects none. The
  docs fallback ranks as before.
- **High-stakes briefs route to frontier by rule.** The override also matches
  destructive data and history operations. It matches keys, certificates,
  bearer and access tokens, and privilege changes too. A 12-brief fixture pins
  it: 8 high-stakes briefs go to frontier, 4 near misses do not.
- **Route rows and the skill hint's cost row name who answered.** Each carries a
  `judge=<provider>/<model>` word, and the model is the one the reply names.
  `via` keeps its name, so `tezgah-route --report` groups history as before.
- **consult's referee reads anonymous answers in a shuffled order.** The output
  maps each label to its member. With no recorded referee, an available member
  outside the panel referees. Otherwise a note says the referee is a panel member.
  consult reads omp's session model only on an omp session.
- **A pass now licenses a claim only when it checked something.**
  `--version`, `--help`, `--list`, `--collect-only`, `make help` and a bare
  `ruff` now record as plain runs. So do formatters in write mode:
  `ruff format`, `ruff check --fix`, `prettier --write` and `eslint --fix`.
  A formatter run after a pass now makes that pass stale. Some checks say
  in their own output that they ran nothing: `collected 0 items`, `no tests
  ran`, `Ran 0 tests`, `No tests found`. Such a run no longer counts as a
  pass. omp's bridge reads
  that from the result and sends only the flag. A pass also has to come from
  the changed file's own repository, so `cd ../other && pytest` no longer
  covers an edit here. The rule now dates a pass from the moment its check
  began, so a write that landed while the check ran makes it stale. The gate
  reads the same list: an information form is not a neutered or piped check,
  and it gets no retry exemption.
- **Honest Stop counters.** A blocked reply that claimed nothing is now a
  `refusal` row, not a `claim`. It has no completion word and no claim about
  an outside system. `false_completion / claims` counts claims only, and
  `counters` adds `refusals`. A `no verify_ok` row says
  whether no check ran or no pass of one showed. Rows are now version 3.
  The docs no longer call that ratio the one number that matters, and no
  longer quote a fixed value for it.
- **A question is not a claim on a turn with no work.** "Testler geçti mi?",
  "is it done?" and "not tested yet" no longer trigger the no-work claim
  check. "Tamamlandı, push edeyim mi?" still does.

### Fixed

- **A host config the installer cannot parse is left alone.** Seven install
  steps read a host's JSON config and then rewrote it. They cover Codex and
  Cursor `hooks.json`, opencode's `opencode.json` and `tui.json`, Cursor's
  `mcp.json` and `cli-config.json`, and omp's `mcp.json`. A trailing comma, a
  `//` comment or a top level that is not an object made the installer write
  its default over the file. `--install` now names that file and the parse
  error, leaves its bytes alone and exits 1.
- **The skill hint can no longer outlive the hook.** It asks once, with a 4 s
  wall-clock deadline, well under omp's 10 s hook kill. The prompt goes out
  redacted and cut at 2,000 characters.
- **A dead judge provider is not paid for on every call.** A 401, 402 or 5xx
  marks it down for five minutes. The mark covers that provider, endpoint and
  key. Until it expires the seam answers with no judgement and sends no request.
- **codegen guards its egress.** It refuses a redirect to another host, a plain
  `http` endpoint off this machine, and a file that carries a credential. Each
  exits 2, so the caller writes the change itself.
- **Every changing write keeps its own backup.** A write that changes a file
  copies it to `<file>.<timestamp>.tezgah-bak` first. Before, only the first
  write left a backup. The oldest timestamped copy is always kept, beside the
  newest four. A bare `<file>.tezgah-bak` from an older release stays as is.
  A full uninstall removes the timestamped backups of tezgah's own state too.
- **`--install` fails when a planned host is not armed.** The run printed MISS
  under a host and still exited 0. Now it exits 1 and names the host and row
  under `not armed:`. Only the arming rows count: hooks wired, the contract
  current, and omp's extension row where an omp CLI exists. Codex
  `hooks trusted`, the provider keys and Claude's plugin copy stay out,
  because a correct fresh install leaves them MISS.
- **Codex write rows know where they ran.** The Codex hook was the one host
  that gave the ledger no cwd. Its write rows carried no workspace, and a
  relative path resolved against the hook process instead of the repository.
- **`tezgah-capture` no longer counts as a read of the screen.** It is the
  pre-write file snapshot CLI. A turn could end on a done claim because this
  run stood in for a screen proof or for a passing check.
- **dsh has no Stop rule.** Its bridge drops every call's outcome, so no check
  there can show a pass. The rule could only refuse honest work there. The
  Stop entry leaves `hosts/dsh/hooks.json` until the bridge carries outcomes.

- **A release publishes only after CI passed on its commit.** `release.yml`
  now runs `ci.yml` as its `ci` job. `npm-publish` and `brew-formula` wait for
  it. v0.1.2 reached npm and brew while its own CI run failed.
- **A test run that runs nothing no longer passes.** A docs-only
  `tests/impacted.py --run` matched no test file and passed with 0 tests. It
  now runs the docs modules. A run where nothing maps, and a `--ref` with no
  change, exit 5. It prints a failed module's log, not only its path.
- **The suite stays out of the real ledger.** Importing `tests/support.py`
  gives the process a temp HOME and drops `TEZGAH_SESSION`. `tests/test_models.py`
  does the same for the `tezgah-route` runs it starts.
- **CI shows what it checks.** The plan report step read the gitignored
  `.tezgah/` and could never fail, so it left CI. It stays a local check. The
  docs now take the CI version list from `.github/workflows/ci.yml`.
  `test-sharded` runs `tests/impacted.py --all` on 3.10 and 3.14 as a
  four-week shadow of the four-version matrix. No matrix cancels its other
  legs on a failure.
- **`bin/tezgah-mcp.py` exists**, the `.py` twin every other Python entry
  point in `bin/` has.

- **Docs that disagreed with the code.** `docs/gate.md` listed Secret before Workspace,
  and `decision` checks them the other way. The Language section did not name `lang-off`.
  `docs/judge.md` counted four callers, and `bin/tezgah-taste` is the fifth. The READMEs
  said fourteen kill switches. CORE names sixteen. Forty-one bare-file citations, six in
  code comments, and the repeat-guard anchor in "Adding a rule" pointed at the wrong
  lines.

- **Uninstall sweeps four more legacy switches.** An uninstall now also sweeps
  `workspace-off`, `triage-off`, `docs-judge-off` and `update-check-off` from `~/.claude`.

## [0.1.2] - 2026-10-04

### Added

- **The status line says when a newer release is out, and `tezgah update`
  takes it.** A `↑X.Y.Z` chip sits beside the logo on every surface. A redraw
  reads a cached answer, and a detached check refreshes it at most once a day.
  `tezgah update [--dry-run]` updates through the channel the install came
  from (release prefix, Homebrew, npm or git) and re-arms the hosts. The
  `update-check-off` switch turns the check and the chip off.

### Fixed

- **The Homebrew formula runs.** It copied `tezgah-setup` out of the tree, so
  the copy could not find `hooks/` and died on import. It now links into the
  installed tree, and also installs the command as `tezgah`.

## [0.1.1] - 2026-10-04

### Added

- First public release.

[Unreleased]: https://github.com/r1z4x/tezgah/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/r1z4x/tezgah/releases/tag/v0.1.2
[0.1.1]: https://github.com/r1z4x/tezgah/releases/tag/v0.1.1
