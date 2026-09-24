# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.17.2] - 2026-09-24

### Changed

- **`--uninstall` removes everything tezgah installed, then proves the
  removal.** A full run — one covering every host `config.json` records as
  armed — takes, beside the per-host wiring: the Claude plugin copy with its
  `installed_plugins.json` rows and a marketplace row sourced from a tezgah
  tree once nothing else installs from it (`remove_plugin_copies()`,
  `bin/tezgah-setup:2143`); the generated `~/.config/tezgah` state and the
  kill switches, the legacy `~/.claude` copies by name
  (`remove_generated_state()`, `bin/tezgah-setup:2219`;
  `sweep_legacy_switches()`, `bin/tezgah-setup:2192`); both state caches; and
  the versioned install tree, every version plus the `current` flip
  (`remove_install_tree()`, `bin/tezgah-setup:2263`). A partial run — some
  armed hosts stay — keeps config.json and the tree for them and says so.
  Kept in every run: the user's own files, `.tezgah-bak` backups outside the
  config dir, `adopted/` and every repo's `.tezgah/` research state. The run
  ends in `verify_uninstall()`, which re-derives the removal from the
  filesystem alone and exits 1 while anything tezgah wrote survives
  (`bin/tezgah-setup:2327`).

### Fixed

- **A full uninstall could still leave tezgah talking.** `~/.codex/bin/consult`
  was written by `install_codex` and read by no uninstaller
  (`bin/tezgah-setup:2552`); Cursor's `statusLine` in `cli-config.json` was
  likewise never unwired (`bin/tezgah-setup:2578`); omp's `mcp.json` was left
  holding the `$schema` and an empty `mcpServers` — the shape that reads as a
  wired-but-empty registration (`bin/tezgah-setup:2613`); and links that hop
  through the farm (`~/.codex/bin/consult` → `~/.config/tezgah/bin/consult` →
  here) read as the user's once the middle link was swept, so
  `is_tezgah_link()` now counts the farm as its own
  (`bin/tezgah-setup:1998`).
- **A predecessor pointer survived the harness it named.** The
  `codex-projects-harness` marker block in a root's `AGENTS.md` points every
  session at a POLICY.md inside `~/.codex/projects-harness`, so after the
  harness moved the block was a standing dead pointer: `predecessors()`
  reports it and `--adopt` retires it, the file moving aside first
  (`bin/tezgah-setup:2749`, `bin/tezgah-setup:2861`).

### Added

- **A container cycle for the uninstall contract.**
  `tests/e2e_docker_cycle.py` installs, uninstalls and reinstalls inside a
  clean `python:3.12-slim` container and scans the leftovers from paths alone,
  importing nothing of tezgah's; `TEZGAH_E2E_DOCKER_DEPS=1` installs node
  first and runs `--install` without `--no-deps`, so the vendor install
  channel (orx, cursor-agent, pnpm, dsh) is exercised over the network.

## [0.16.1] - 2026-09-22

### Added

- **Two gates, when one locked metric is not enough.** `state.json`'s
  `evaluation` may carry `capability_tolerance` - the band the capability metric
  has to stay inside before a result counts - and `counter_metric`, the name of
  the metric the change is supposed to move; a candidate then passes both, and
  survivors are compared on the Pareto frontier instead of by one number's sign.
  Both fields are optional and validated only when written (an absent key is a
  line that locks one metric - every line in this tree does), so nothing here
  fires on their absence (`_check_evaluation`, `hooks/tezgah_research.py`;
  `skills/research/SKILL.md`; `docs/research.md`; `tests/test_research.py`). Two
  things the pair buys, and why they are written down: a candidate cannot buy its
  gain by moving the metric, and the rule stays out of the reach of the loop it
  judges - these fields are read by `check`, which lives in a module the frozen
  set forbids a prediction's commit to touch.

### Fixed

- **A superseded claim row was still read as a live proposal.** `_open_reasons`
  flagged any row whose own status was `hypothesis` or `testing`, so a line whose
  claim had been replaced could never close: C11 in `harness-hardening` and
  C5/C5-R in `typesafe-cost` stayed open with their successors - `untested` and
  `weakened`, both carrying `supersedes` - sitting beside them, which left
  `tezgah-research init` refusing every new line and `--allow-open` as the only
  way in. A row another row names in `supersedes` is now skipped and the
  replacing row decides; the append-only doctrine is untouched
  (`_open_reasons`, `hooks/tezgah_research.py`).
- **The test fixture HOME sat under a scratch root on a runner.** The gate reads
  its scratch exemption from `$TMPDIR or /tmp` in the hook process while
  `tempfile` honours the test process's TMPDIR, so a runner that sets none put
  the fixture under `/tmp` and `rm -rf ../victim` became the session's own
  scratch - held to no ask, inverting the two directory-scope tests that assert
  exactly that ask (`test_gate.Gate`, `test_opencode_plugin`'s lease; the CI
  Python 3.10 job). The fixture is built under `/var/tmp`, which is neither root
  (`TempHome.setUp`, `tests/support.py`).

## [0.16.0] - 2026-09-22

### Added

- **One research line at a time.** A line is open until its work is applied or
  deliberately not and the line is closed: `phase` not `concluded`, a claim left
  at `hypothesis` or `testing`, an experiment with a protocol and no results, a
  missing `to_human/report.md` or `review.json`, or a review finding with no
  status (`open_lines()`, `hooks/tezgah_research.py`). `tezgah-research init`
  refuses while anything is open, prints every open line with its reasons, and
  `--allow-open "<reason>"` is the way past - the reason lands in the new line's
  `log.md`, so a second line is a decision on the record instead of an accident.
  `status` and an unscoped `check` end with the same line, and the armed research
  rule names the open lines and their reason counts on every research turn
  (`open_note`, `hooks/tezgah_policy.py`; `{OPEN_LINES}`,
  `hooks/tezgah_context.py`). The rule the prompt path reads never opens
  `claims.jsonl`, so a line open only because of a live claim is named by `init`
  and not by the note - a cost budget, stated in the rule's own comment. The
  reason it exists: on 2026-09-22 thirteen lines existed, eleven of them carrying
  unfinished work while later lines were opened over them.

### Fixed

- **`generated by <model>` is attribution too.** The credit ban caught
  `generated with` and `co-authored-by:` but not a generator named as the author,
  so a message carrying `This was generated by AI during triage` passed the gate
  while the `Co-Authored-By` control was denied (claim C04 in
  `.tezgah/research/mp-skills-adoption/`). The forms the ban reads now tie the verb
  to a model object - `generated|written|authored|built|assisted by <ai|llm|claude|
  gpt|chatgpt|copilot|codex|cursor|gemini|deepseek|openai|anthropic>` - while
  ordinary prose (`the report was generated by the build script`, `the index is
  built by the gate`) passes, and the opencode plugin's hand-written mirror is the
  same set again with a parity test that fails if the two drift (`ATTRIB`,
  `_CREDIT`, `hooks/tezgah_gate.py`; `hosts/opencode/plugins/tezgah.js`;
  `tests/test_opencode_plugin.py`).
- **The Stop path read the whole session ledger, per turn.** `stop_reason` and
  `changed_files` asked `events()` for every row; both now ask `turn_rows()`,
  which falls back to the whole ledger for a session that writes no `turn` row, so
  nothing changes for those sessions. Measured on a 1112-line ledger: 2.638 ms
  whole-ledger against 0.185 ms turn-scoped (E5b, `.tezgah/research/
  harness-hardening/experiments/E5b-h5-retake/`). `used()` and `_hash_file` stay
  unbounded by construction and are named as such.
- **225 doc citations re-pointed.** The attribution widening, the Stop-path bound,
  the `init` guard and the research rule each moved lines under citations that
  `bin/tezgah-docs --citations` judges; each was shifted through the diff against
  the revision where the audit last read `0 outside`, and the three the shift could
  not place are cited to their symbol's body. The audit reads `324 judged (0
  outside)` again.


## [0.15.0] - 2026-09-21

### Removed

- **`codebase-memory-mcp` is gone; `codegraph` is the graph engine.** There is no
  second engine and no fallback: the `cbm_bin()` resolver, the `TEZGAH_CBM_BIN`
  pin, the `TEZGAH_GRAPH_ENGINE` selector, the `cbm_bin` config key and the
  `~/.cache/codebase-memory-mcp` accounting in `bin/tezgah-doctor` are deleted,
  and the six host rows, the agent briefs, the three graph workflows and the
  conditional rule name codegraph's real surface (`codegraph_explore` over MCP;
  `codegraph callers|callees|impact|affected|node` from a shell). The per-repo
  opt-out is `.no-graph` now - a repository still carrying `.no-cbm` re-arms the
  code-graph rule, which is the one breaking rename here - and the tool-use mark
  is `graph` where it was `cbm`. The index moves inside the repository
  (`<repo>/.codegraph/codegraph.db`) and the repo's root `.gitignore` carries
  `/.codegraph/`; `bin/tezgah-doctor --coverage` is new and reports what the
  engine does not index, which codegraph's own `status` never says. The only
  `cbm` strings left are the older harness's `~/.claude/hooks/cbm-*` filenames
  that `predecessors()` looks for on a user's disk, because those files are what
  `--adopt` retires.

### Added

- **A judgement still happens without a TypeSafe key.** The seam
  (`hooks/tezgah_judge.py`) gained a second provider: when `TYPESAFE_API_KEY` and
  `~/.config/typesafe/key` both resolve nothing, the same batched questions go to
  OpenRouter - `OPENROUTER_API_KEY`, else `~/.config/openrouter/key` - and its
  chat reply is mapped back into the shapes the callers already read
  (`credential()`, `hooks/tezgah_judge.py:150`; `CHAT_SYSTEM`, `:66`;
  `_chat_body()`, `:295`; `_clean_answer()`, `:357`). TypeSafe still wins whenever
  it resolves, so a machine that already judges with Jev does not move. The
  fallback asks `deepseek/deepseek-v4-flash` unless `TEZGAH_JUDGE_MODEL` names
  another chat model, drops any answer whose type does not match its question,
  and reports the model that answered, which the triage's and the docs page's cost
  rows now print (`bin/tezgah-triage:134-138`, `bin/tezgah-docs:188-192`). The
  install report's key probe and the status line's `judge` readiness count the
  fallback's channels (`have_judge_key()`, `hooks/tezgah_paths.py:249`).

## [0.14.0] - 2026-09-20

### Added

- **A feature is audited across its layers, not by its screen.** The new
  `feature-audit` skill fills four matrices before any taste judgement - capability
  (action x layer: surface, route, authorization, service, persistence), field
  contract, flow/step and interaction dependency - where a disagreement between two
  layers is a finding and an agreement is a pass row, and it requires a
  capability-change proposal whenever a fix names a layer that does not exist yet,
  carrying an artifact something other than its author can reject (a spec, permission
  or schema diff a checker can fail on, a flag with a type and an expiry, an ADR with
  a status). Every interface element and every data view is in scope, never only form
  fields. The product rule carries the coherence paragraph and names the skill, and
  `skills/tezgah-contract` mirrors it, so the conditional half pays for it only on a
  matching turn: measured, the product paragraph is 2064 -> 2681 bytes.
- **A feature-level ask reaches that rule.** The `product` hints
  (`hooks/tezgah_context.py:66-83`) now cover a feature named by its surface -
  `ekran`, `arayüz`, `tablo`, `filtre`, `wizard`, `adım`, `crud`, `formu`,
  `kullanıcı listesi`, `admin panel` - which armed nothing before: measured against
  the running classifier, `admin paneldeki users ekranını incele`, `bu filtre
  çalışmıyor`, `bu tabloyu iyileştir` and `kullanıcı listesi ekranında crud var mı`
  arm `product` where they previously returned the empty set, and the code senses the
  lookaheads keep out (`ekran kartı` is a GPU, `adım sayısı` is a count, `form a
  hypothesis` is a verb) arm nothing. The always-on band is unchanged at 8388
  characters: the rule text lives in the conditional paragraph, not in `CORE` or
  `POINTERS`.

## [0.13.0] - 2026-09-20

### Added

- **The status line carries tezgah's name and version.** `tezgah v0.13.0` opens the
  line on every surface - Claude and Cursor through `statusline.py`, omp's widget,
  dsh's Web route and opencode's TUI, all through the same renderer in the core - and
  the JSON form carries it as a field (`{"key": "tezgah", "version": "0.13.0"}`) so a
  program reads it rather than parsing the text. One reader resolves the version (the
  local plugin manifest, else the newest `## [x.y.z]` in `CHANGELOG.md`, reading only
  its head) and `tezgah-setup --version` now calls it, so the two cannot disagree; a
  checkout with no readable version prints the bare name instead of a placeholder.
  Measured: one `render_line` is 0.0038 ms before and 0.0037-0.0040 ms after (the
  chip costs +0.0003 ms), and the always-on contract text is unchanged at 8388
  characters.

## [0.12.1] - 2026-09-20

### Fixed

- **The contract skill carries the code-graph project id rule again.**
  `skills/tezgah-contract/SKILL.md` is a hand-kept CONTRACT source, not a
  generated file, so its code-discovery paragraph still held the older
  sentence after `hooks/tezgah_policy.py`'s rule gained the project id
  derivation and the `list_projects` recovery: the two readings of one rule
  had drifted apart, which is the shape the lessons ledger records. Both are
  aligned now, and `tests/test_skills.py` pins the sentence in the skill and
  in the policy together, so the next edit has to move both.

## [0.12.0] - 2026-09-20


### Added

- **A failure fold over the ledger, so a rule's reach is readable instead of
  argued.** `bin/tezgah-status --failure-shapes [--json]` walks every ledger on
  the machine and reports the refusal shapes that recur in at least five distinct
  sessions, each with its session count, fire count, fires per session and the
  three most common redacted command shapes. It is a report, not a gate (exit 0),
  and it prints the corpus size it read. On this machine: 8 shapes over 1661
  ledgers, `drift` widest at 177 sessions and 1.27 fires per session, `task` 80,
  `consent` 46. The ranking is distinct sessions on purpose - the highest-firing
  rule is also the one that fires on long careful turns.
- **A harness change can now carry a falsifiable prediction, bound to a commit.**
  `bin/tezgah-research predict <slug>` appends a row to a line's
  `predictions.jsonl` (`commit`, `components`, `metric`, `value_before`,
  `value_after`, `falsifier`, and `granted_by` where a human lifted the freeze);
  `tezgah-research check` refuses a row whose commit is not an ancestor of HEAD,
  whose metric or value names no number, or whose commit touched a frozen path
  (`hooks/tezgah_gate.py`, `hooks/tezgah_integrity.py`, `hooks/tezgah_research.py`,
  `tests/`, `benchmarks/`, any experiment's `protocol.md`) without a grant. The
  write path and the checker read the same `prediction_problems`, so they cannot
  disagree.
- **The layer's editable components are one manifest.**
  `hooks/tezgah_components.py` lists all twenty (the sixteen always-on rule labels
  plus `skills`, `subagents`, `memory` and `drift-notice`) with the files each
  lives in, its kill switch or per-repo mark, whether the refinement loop may edit
  it and how a change is reverted, and it carries AHE's seven components as a
  mapping that names the ones this layer does not own and why. A test pins every
  rule label to exactly one entry, every path to disk, every switch to one the
  injection actually reads and every frozen path to `editable: False`.
- **A per-component report.** `bin/tezgah-research components [--json]` prints, for
  each component, the predictions that name it and their state (`unmeasured`,
  `held`, `falsified`) - a report, not a gate.
- **An acceptance item must name the command that proves it.**
  `skills/plan-add/render_table.py --acceptance [--strict]` reports the acceptance
  items that name no command, per `plan:line`, and `--strict` gates the open plans
  (a done plan is a record, reported and never gated). On its first run over this
  repository's own plans: 38 of 48 items named no command.
- **`docs/layers.md`**, and the glossary entries to go with it: the four layers -
  model and MCP transport, agent framework, agent host runtime, tezgah's policy and
  evidence layer - each with what it owns and what it must not, and the boundary
  drawn against host, framework, SDK, IDE plugin, eval harness, orchestrator and
  MCP. The word `harness` carries three senses in this repository; the page and the
  glossary now separate them, and `skills/harness/SKILL.md` names its own.
- **Two CI steps**: the citation audit and the open plans' acceptance gate now run
  in the same job as `compileall`, the suite and `ruff`.

### Changed

- **`drift` is delivered on the tool-result channel instead of as a refusal.** The
  long-turn re-statement is about the turn, not about the call it lands on, so the
  notice rides the result beside the untrusted-content label and `decision()` never
  refuses for it. The text, the 25-work-row threshold and the once-per-turn marker
  row are unchanged. Measured over the 225 refusals in the corpus: 128 of them
  (56.9%) were calls re-issued identically in the same turn, and 97 (43.1%) were
  calls the session composed and never got back.
- **The code-graph rule names the project id it needs.** Sessions were failing
  `search_graph` with "project not found or not indexed" because the rule named no
  id. It now states the derivation (the repo root path with every run of
  non-alphanumerics replaced by `-`) and the recovery (call `list_projects` and pass
  the name it prints). On-demand contract text only: the always-on core is
  unchanged at 8388 characters.

### Fixed

- **A write row records the path it changed.** The row's `detail` was built from a
  narrower set of input keys than the gate's own path reader, so a host dialect that
  names the file under `path` or inside a patch body recorded nothing: **0 of 5308**
  changed write rows carried a path. Both halves now call one reader, the opencode
  mirror included (which was also missing `notebook_path`). Measured after the
  change: **240 of 244** changed write rows carry a path, 98.4%.
- **The drift notice stays once per turn in a very long turn.** `drift_reason` reads
  a 200-row tail and then looks for the turn's start inside it, so a turn longer than
  the window lost both its own marker and its turn marker and re-armed. It now falls
  back to the module's turn-scoped reader when the window holds no turn marker; the
  ordinary path keeps its single tail read.
- **105 citations the drift change shifted were re-anchored**, and
  `bin/tezgah-docs --citations` was run as part of the checks that caught them - the
  suite is green either way, so the audit is now a CI step.
- **The prediction rule's own module is frozen**, so the machinery that decides the
  rule cannot be edited by the loop it judges without a human grant.

- **Three of the mechanical findings the harness audit left open are closed, and one
  of them found a test that proved nothing.** The audit line is
  `.tezgah/research/harness-hardening/`; this lands items I1-I3 of its report.

  *A gated call stops paying for imports it does not use.* `hooks/tezgah_paths.py`
  imported `sqlite3`, `shutil` and `tempfile` at module level, and every hook imports
  it transitively, so ~12 ms of the 61 ms a gated call costs bought capabilities most
  calls never ask for. All three are resolved on use now, and `tezgah_snapshot`'s
  `shutil` with them. Measured over three runs of ten (the number is jittery on a
  loaded machine, so it is given as a range): `import tezgah_gate` falls from
  **61.4 ms to 50-55 ms p50**, `tezgah_paths` itself from 12.7 ms to **0.18 ms**, and
  the end-to-end gated call - what a host pays per tool call - from **61.0 to
  56.8 ms p50** (n=40, idle machine). The one other reader of that constant - the
  concurrent-probe test that patches the two cache candidates - was pointed at the new
  seam.

  *A taint check costs the turn, not the session.* `tezgah_untrusted.turn_channel` read
  and parsed the whole ledger on every effectful call; it now goes through `turn_rows`
  (`hooks/tezgah_integrity.py:483`), which reads every line but parses only the rows
  after the current turn's marker - the same answer over five ledger shapes, and with
  4000 rows ahead of the marker fewer than 400 are parsed.

  *The language rule reaches opencode, and a silent delegation stops being invisible.*
  The plugin carried no language code at all, so a non-English branch name, commit
  subject or PR title was created unchecked there - the one artifact class that
  outlives the session. It now asks the core for the rule (`IDENT_CMD`
  `hosts/opencode/plugins/tezgah.js:408`, call site `:2118`) instead of growing a second
  copy of the word list, and one `delegation` ledger row records the class whenever the
  core could not answer at all (`noteDelegation`
  `hosts/opencode/plugins/tezgah.js:1962-1980`). The fail-open direction is unchanged,
  deliberately.

  *The hung-core test proved nothing until this landed.* Its stand-in CLI was
  `#!/bin/sh` plus `sleep 60`, and the plugin runs that path as `python3 <path>`, so the
  fixture died on its own shebang in 0.02 s and the test never reached the deadline it
  is named for. It is a Python sleeper now, and the test really waits.

- **A crashing hook costs an envelope, never a session.** Every entry point
  decoded its payload defensively and then called into the core unguarded, so a
  fault in the gate, the ledger or the context builder left the session by the
  host's route rather than the hook's: Claude, Codex and Cursor lost one
  envelope, while **omp's bridge turned the same crash - or one 10 s timeout -
  into a session-wide disable of the gate, the ledger and the status line**, and
  opencode awaited a core process with no deadline at all.
  `hooks/tezgah_guard.py` is now the one place that call is caught (`safe`,
  applied at every entry point), it fails open in the direction the rest of the
  layer already chooses - a core that has crashed has refused nothing - and it
  records the caught class as a `crash` ledger row, so a swallowed fault stays
  countable instead of looking like a rule that fired. The opencode plugin's
  five awaited core calls now run through one `collect` helper with a 10 s
  deadline (`SPAWN_DEADLINE_MS`, `hosts/opencode/plugins/tezgah.js:114-147`),
  which answers a hang with the same empty value a missing binary gets.
  `tests/test_guard.py` pins the contract host by host - one process, the
  payload on stdin, the core function replaced by a raiser before the hook
  loads - and **all seven entry points fail it before this change**;
  `tests/test_opencode_plugin.py` pins the deadline with a `tezgah-gate` that
  sleeps 60 s.

## [0.11.0] - 2026-09-20

### Added

- **Turkish no longer reaches an identifier, the research line's last three
  promises are checked, and the flagship rule finally fires.** The follow-up to
  the research-layer audit, in four parts.

  *The rule the layer exists for is decidable now.* `protocol.md` committed before
  `results.jsonl` is decided on the commit graph and `.tezgah/` was excluded
  wholesale, so no line could ever satisfy it - the audit measured 7 of 7
  experiments reporting the order unverifiable while `check` exited 0. The
  protocol side is re-included (`.gitignore`, level by level, because git never
  descends into an excluded directory), this line's nine protocols landed in
  `74370f8` and its nine results in `e632642`, and after that **all nine "the
  order cannot be checked" warnings disappeared** - the rule decided the order for
  the first time in this repository. The results of the earlier lines are
  deliberately left untracked: infra-candidates' E1 protocol states in its own
  text that it was written after its run, and committing those results would have
  git assert an order the file denies. The checker now probes each experiment's
  protocol/results pair rather than the line's directory (which an ignore rule
  still matches, and which produced a false positive until it was asked the right
  question) and prints the exact `git add -f <path>` when a pair cannot be
  verified, because a plain `git add` silently adds nothing there.

  *Three documented rules became rules.* A protocol must answer both a prediction
  and a falsifier (14 of the 17 protocols in the six lines do; the three that do
  not are delegated-map briefs and warn), a concluded line's `to_human/report.md`
  must state what the evidence does not show, and a claim may carry `supersedes`
  naming the claims it revises - a dangling id is refused on both the write path
  and the checker, a valid link is reported, and C34 now records that it revises
  C27, whose number went stale. `migrate` also derives a results row's `source`
  from a field the row already carries when it can (judge-positioning: 18 rows) and
  reports what it cannot instead of inventing one. 18 new tests in
  `tests/test_research.py` (185 there).

  *Turkish in an identifier is refused at the point the command is issued.* A new
  rule in the gate covers a branch (`git checkout -b`, `git switch -c`,
  `git branch`), a commit subject (`git commit -m`/`--message`/`-F`) and a
  `gh pr|issue create --title`: a letter outside ASCII anywhere (any script, not
  only Turkish), or an ASCII-folded Turkish word from a curated list, is refused
  with the English to write instead -
  `plan/004-admin-durum-onarimi` is `plan/004-status-repair`. The detector
  (`hooks/tezgah_lang.py`) folds before it looks a word up, keeps a four-letter
  stem whole-token so `sil` cannot refuse `silent`, and holds the three stems that
  are also prefixes of English words in a `WHOLE` set; measured over 57 Turkish
  and 25 English words it catches **57 of 57** and refuses none of the English, and
  the refusal says plainly that a word list is not a language detector and that the
  user's own term is theirs to settle. `plan-add` states the rule where the slug is
  written, the contract gained `**Identifiers and messages stay English.**` and the
  switch `lang-off`, and the subagent budget moved 4000 -> 4400 bytes because at
  the old bound the new rule silently dropped `consult` - bloat turning into rule
  loss, which is what that budget's own comment warns about.

  *The docs layer's unjudged citations were adjudicated.* `tezgah-docs --citations`
  judges 329 citations against a named symbol and leaves the rest undecided; three
  writers examined **974 of them across twelve pages**, corrected the ones that no
  longer showed what their sentence claimed, and left the numbers they confirmed.
  The judged population is at **0 outside the symbol they name**, with the residue
  named rather than claimed clean.

- **The vendored `ai-research` library is measurably unused, and its cost is one
  line.** An audit of the 98-entry tree (374 files, 4.34 MB of content, a 111 KB
  manifest, a 439-line importer and 22 integrity tests) found exactly **one** row
  in the whole 30,750-row harness ledger that reads a vendored entry body - by the
  audit itself - against 26 rows that read the same material from the upstream
  clone, and no research line cites an entry. Its always-on cost is a 217-byte
  router line in a 4.3 KB file, and the comment claiming it collapses to its
  bucket's count line said the opposite of what the code does; that comment is
  fixed. Keeping it, trimming it and deleting it are three options with their
  measured costs in `.tezgah/research/research-layer-audit/`, and the trimming cut
  rests on zero recorded usage - which the same audit shows is not the same as zero
  use, because a host file read is not something the ledger records.

- **The research layer's checks now reach what its skill promised, and the order
  rule is reachable where the contract puts it.** The layer's own audit
  (`.tezgah/research/research-layer-audit/`, 36 claims and nine experiments)
  measured `tezgah-research check` refusing **0 of 8** frozen probe lines, each
  violating a rule `skills/research/SKILL.md` states as enforced (control: 2 of 2
  refused); the protocol-before-results rule unverifiable for every experiment in
  every line, because the prescribed `.tezgah/` path is gitignored; **68% of 75
  existing claims** naming no artifact the line produced; no claim naming an orx
  run and no tezgah code reading orx; and no non-academic channel or cross-source
  synthesis anywhere. This lands the seven fixes and the coverage pass, each with
  its acceptance test in E7 (**29 of 29** cells, both gate cells included) and the
  frozen probe set re-measured in E8 (**0 of 8 -> 6 of 8** refused, 8 of 8
  predictions matched).

  *The checker reaches the content.* `state.json.evaluation` is a locked metric,
  baseline and timestamp, required once a line leaves `bootstrap`, with an optional
  `environment` block; `sessions[]` entries must carry a provenance tag and a date.
  A claim carries `kind` (`evidence`/`code`/`literature`/`derivation`) with a
  per-kind proof rule: a proof naming no artifact is refused, an `evidence` claim
  must name at least one artifact the line produced, an `evidence` claim whose
  experiment has no rows is warned, and `orx:<runId>` resolves to the run's log.
  `results.jsonl` is parsed - one JSON object per non-blank line with a non-empty
  `source` - and `source --run <id>` files the `orx logs` output as `raw/<id>.log`
  beside the row. `literature/INDEX.jsonl` records each source's class
  (`formal`/`grey`), inclusion reason and verification set. `to_human/review.json`
  makes the six-dimension review an artifact whose findings are checked against the
  quote they claim, and a `## Patterns` bullet must name its source (`[Cnn]`, a
  note path or an `orx:<id>`). `migrate <slug>` derives what those rules require
  from artifacts written before them and reports what it cannot derive instead of
  inventing it.

  *Warnings are not verdicts.* `check --strict` turns the class the checker cannot
  decide - an ignored line path, a claim written before `kind` existed, a results
  row written before `source` did, a grey source with no quality note, an
  unsourced Patterns bullet, a concluded line with no review - into a refusal:
  `check` stays green over the six lines here while `check --strict` refuses 190
  things in them. `check --orx` reads the orx registry and reports the project
  whose run command names a script the tree no longer holds
  (`benchmarks/arm-bench/orx-run.sh`, removed in `5af240b`).

  *The surface sees the layer.* `tezgah-research` is classified as the `research`
  kind, so the mark lights from the layer's own CLI and not only from a shell
  command that ran `orx`; opencode's cheap pre-filter learned the spelling. Two
  statements claiming opencode has no prompt-time injection point
  (`bin/tezgah-setup`, `docs/skills.md`) were corrected against
  `hosts/opencode/plugins/tezgah.js:2209-2230`. `docs/research.md` is the layer's
  first reachable page - `tezgah-docs research` used to answer "nothing matches".

  Three rules landed softer than the spec asked, each with its measurement in the
  spec's amendment table: a results row with no `source` and a concluded line with
  no `review.json` warn rather than refuse, because 71 existing rows carry no
  source and four existing lines carry no review, and no rule may invent a
  provenance it cannot derive. Two defects the acceptance runs found - the write
  path refusing a claim the checker only warns about, and `kind: evidence`
  accepting a proof naming only a repository file - were fixed on both sides and
  re-measured. 86 new tests in `tests/test_research.py` (167 there, 1137 in the
  suite, `OK`) plus 13 across `tests/test_{agents,skills,context}.py`.

- **The judgement seam now says what it costs, shows it on the status line, and
  has a page.** Three surfaces the seam was missing, from its own spec
  (`.tezgah/research/judge-positioning/to_human/spec.md`):

  *Cost.* Each caller records one `judge` ledger row after a successful judgement -
  `tezgah-triage`, `tezgah-docs` and the prompt-path skill picker, so the half no
  shell row can carry is counted too - as `<caller> jev-latest in=<n> out=<n> ms=<n>`.
  `counters()` counts it on the row's KIND and never on a `detail` substring, which
  the consult/codegen rows use and which would count a command that merely mentions
  the tool; `tezgah-status --counters` prints it, `--all` folds through the same
  `_counts`, and `STEP_KINDS` is untouched because a model answer must never be able
  to license a done claim. Measured live: `judge 0` before, `judge 1` after one row,
  and a `run` row whose detail says "judge" counts 0.

  *A mark.* `judge` joined group 1 of the status line, decided from the switch and a
  real used-kind: `ready` with a credential and no use, `on` once a judgement really
  ran, `off` under `judge-off` or without a credential, `info` where `--observable`
  excludes it - and `off` beats `info`, so a surface that cannot write the store
  never claims `ready` forever. `shell_kind` gained its third answer (a program
  position that ran `tezgah-triage` or `tezgah-docs`), and the hosts' cheap
  pre-filters had to learn it: opencode's `/consult|\borx\b/` kept `judge`
  unearnable until it was widened. The mark reads `tezgah_paths.have_judge_key()`
  rather than importing the seam, because the status path is drawn often: measured
  20.1 ms bare against 70.6 ms with `tezgah_judge` imported (urllib alone is
  62.0 ms). dsh's `--observable` literal grew the fifth mark, since dsh wires the
  same PostToolUse hook every other host does - its old comment said otherwise and
  was stale.

  *A page.* `docs/judge.md` (144 lines) with its index entry, so `tezgah-docs judge`
  routes from the keyword index and makes no request at all - proved by pointing the
  endpoint at a dead port and still getting exit 0.

- **One judgement in front of the skill choice, and one line to show for it.** A
  session meets the roster as an index of host-truncated one-liners - 8,018
  characters / ~2,005 tokens for tezgah's 13 skills, cut to 60 characters each - so
  which entry to look at first is the one thing a turn cannot work out for itself.
  `hooks/tezgah_skill_pick.py` asks TypeSafe once per unanswered prompt: a Choice
  over the installed skill names plus `none`, and one Noul asking whether the turn
  wants a skill at all. The winner is appended to the per-turn text as one
  `<skill_relevance>` line that names the skill, says what it is for and says the
  line is a hint to look at first rather than an instruction to load (upstream's own
  recipe over 488 requests: wrong skill loads 16.8% -> 7.3%, needless loads
  9.8% -> 4.0%). It is the fifth injected surface, so it behaves like the others:
  nothing is appended without a credential, on a `none` answer, on a slash command,
  on a refused or stalled call, or with `skill-suggest-off` armed, and nothing is
  asked twice for one prompt in one session. Measured live: 909-915 input tokens,
  0.77-0.81 s, $0.000038 per judgement; 305-317 characters (~78 tokens) for the
  line; a 963 ms first hook turn against 138 ms once the prompt is cached and 140 ms
  with the switch on. The gate question had to be measured rather than inherited:
  the cookbook's own "documented procedure" wording is wrong for a roster of working
  rules, scoring `ponytail` at 0.05-0.24 and losing correct picks on 8 prompts,
  where this wording separates the five that want a skill (0.80-0.98) from the three
  that do not (0.01-0.15). The roster itself is left alone - upstream keeps it so
  the host's prefix cache holds, and on five of the six hosts tezgah does not write
  that text at all. Compacting its 13 entries to name plus one clause would save
  6,063 characters (~1,516 tokens); that is measured and deliberately not done,
  because what a session loses by no longer seeing the full descriptions is
  unmeasured. 14 hermetic tests pin the line, the request, the cache, the failures
  and the switch.

- **The judgement's egress is now pinned, not just documented.** `hooks/tezgah_judge.py`
  sends the state and the questions to `api.typesafe.ai` - for the triage the state
  is the screen's own text, which on an admin table or a mobile view may carry
  personal data - and the module now says so in its own docstring, including that
  the state is deliberately not redacted and that this is why both callers are
  on-demand and `judge-off` is the off button. Five tests hold the wiring in place:
  the body's keys are exactly `state`, `model` and `questions`; the headers are the
  bearer and the content type over urllib's own defaults and nothing more; a
  `TEZGAH_SESSION` in the environment (which opencode's plugin exports into every
  shell) does not appear on the wire; a state carrying an email and an absolute path
  arrives byte-identical, so nobody can add a scrubber without a test going red; and
  a repo-local `.env`, `tezgah.env` or `.tezgah/config.json` cannot repoint the
  endpoint, because `TEZGAH_TYPESAFE_URL` is an environment variable and no dotenv
  loader exists in the tree. The tests were shown to fail by mutation before they
  were trusted.

- **A redirect can no longer carry the credential to another host.** urllib
  re-issues a 302 on a POST and keeps the `Authorization` header while doing it, so
  an endpoint - or an override of `TEZGAH_TYPESAFE_URL` - that answered with a
  `Location` would have handed the key to whatever host it named. Measured on two
  loopback servers: unguarded, the second host received the request with
  `Authorization: Bearer SECRET`; through the module's opener the same request
  raises and the second host receives nothing. `_NoCrossHostRedirect` refuses only
  a hop that leaves the endpoint's network location, and a refusal is already the
  `None` every caller's fallback expects.

- **A TypeSafe (Jev) judgement seam, and its first two callers.** tezgah had one
  TypeSafe reference in the whole tree - a health row that reports whether *omp* can
  resolve a credential - and no call path, because the hook layer has no HTTP client
  at all. `hooks/tezgah_judge.py` is now the single seam: `available()` and one
  batched `ask()`, stdlib only, no SDK, no retry, and every failure a `None` rather
  than an exception, since a hook that raises takes a session down. The credential
  has two channels on purpose - `~/.zshenv` exports the env var for an interactive
  shell, but hooks and bin tools run in a non-interactive one where it is absent
  (measured: interactive length 107, non-interactive unset), so the key file at
  `~/.config/typesafe/key` is the channel that survives. `judge-off` disarms it.
  Two callers ship: `bin/tezgah-triage` flattens a `browser_snapshot` to numbered
  lines and asks which lines matter (`--select`) or which states a component shows
  (`--states`) in ONE request, printing the selected refs, the characters now
  skippable and the arithmetic at $0.042/1M input; `bin/tezgah-docs` falls back to a
  page Choice only when its keyword match found nothing, so the deterministic path is
  untouched. 27 hermetic tests (a loopback endpoint, no network) cover the credential
  order, the request shape, parsing, a 401, a timeout, the kill switch and triage's
  numbering, units and fallbacks. Measured live on a real 356-line admin screen: the
  triage selects 48 of 67 units, skips 21 lines, and costs 7,008 input tokens / 1.3 s
  / $0.000294. The first shape asked one question per LINE and was measured at 69.9%
  recall of the load-bearing controls - refuted before it shipped further - so the
  default is one question per the tree's own UNIT (row, cell, leaf), which reaches
  100% recall of the task's controls at a 94% read on that table and 100% at a 71%
  read on a 31-line detail screen. The tool prints that read-share and says so when a
  task naming a control every row repeats must be read in full: on such a screen the
  units buy coverage, not skipping.

- **A `product` task class, and the `product-analysis` skill behind it.** A
  product question armed nothing: `PROMPT_HINTS` carried `spec`, `consult`,
  `research` and `cbm`, so "ürünle alakalı analiz istiyorum ürünleri daha iyi hale
  getirmek istiyorum" or "which feature should we build next" reached no rule and
  the answer came from the model's priors. The class is armed by its own pattern
  (`product`, `feature`, `roadmap`, `backlog`, `prd`, `retention`, `churn`,
  `onboarding`, `funnel`, `pricing`, `prioriti[sz]e`, `ürün`, ...) with
  `production`, `productivity` and `productive` excluded by lookahead, because
  they are code words that merely share a prefix; the paragraph it injects names
  the two axes - PM value (HEART's Goals -> Signals -> Metrics, with raw counts
  refused) and PE feasibility (a cited `path:line`, documented intent against the
  code that enforces it) - and the four evidence classes a finding may name
  (`user-verbatim`, `behaviour`, `code`, `external`), with a finding that has none
  reported as a question rather than a finding. `research-off` disarms it, since
  it shares the research route. The `product-analysis` skill carries the artifact
  shape and a six-dimension scorecard on the `research` skill's 1-5 anchors, and
  execution runs through the shipped research workspace, so no parallel machinery
  was added. The upstream framework depth (`phuryn/pm-skills`, MIT) is referenced
  by URL rather than vendored. The context-budget test now reads the skill count
  from `SKILLS` instead of a literal, which had made adding any skill a failing
  test about arithmetic.

- **Two product methods vendored offline as `skills/pm-frameworks`.** The
  `product-analysis` skill defers to `intended-vs-implemented` (a gap is a finding
  only when the documented intent and the code that enforces it are both cited)
  and to the Opportunity Solution Tree; both now ship byte-for-byte from
  `phuryn/pm-skills` (MIT) at revision
  `8607e3b077817f89bf4a9b623246219734ac3be0`, so an offline session reads the
  method instead of citing its name. `skills/pm-frameworks/SOURCE` records the
  upstream path and the sha256 of each body, `tests/test_skills.py` holds the
  tree to it and fails on an unlisted directory beside them, and `NOTICE` carries
  the licence. The other 67 skills and the plugin manifest are not copied.

### Fixed

- **`tezgah-triage --states` was answering about the wrong lines, and said so
  without saying when the tree could not answer at all.** The mode asked one Noul
  per state - `Is the component shown in its <state> state?` - over a component's
  subtree, and the wording alone was measured wrong on a driven fixture this round:
  a screen built for the purpose (a button with a real `:hover` and a disabled
  sibling, a textbox with `:focus`, a data view routed to empty, to 500, to 403,
  held in loading, and taken offline), driven through the pinned Playwright MCP,
  ten conditions x five components, 50 live calls, 650 verdicts scored against the
  marker the driven tree itself carries. `disabled` came back 0.49-0.51 for a form
  whose only `[disabled]` sat on a child button, `partial` 0.26-0.30 for a view
  whose row printed a missing amount, `focus` 0.20 for the element the snapshot
  marks `[active]`, and `error` 0.92-0.94 for a view showing the permission or the
  offline copy. Each question now carries the API's own `criteria` - what counts as
  shown, in thirteen short lines: the component's own line is what carries
  `[active]` and `[disabled]`, a disabled child is not a disabled parent, a blank
  field is not an empty data view, a permission or offline copy is neither error
  nor partial, a loading placeholder is not partial. Agreement over the same
  fixture moved 88.8% -> 97.4%, states read as present when they are absent 58 -> 9,
  and the dangerous direction - a state called not-shown that the tree does show -
  12 -> 8. The eight that remain are a class the command was pretending to answer:
  an aria snapshot has no marker for the pointer, `[active]` is the focused element
  rather than a pressed one, a skeleton and a loading placeholder read the same,
  "long" is a rendered width the text does not know, and `default` is the absence
  of the other states - so `--states` now prints one `unmarked:` line naming those
  five, in either direction, and a verdict on them is no longer read as something
  the tree showed. The `--select` path, both fallback paths and their printed
  output are untouched; 2 hermetic cases pin the criteria and the unmarked line
  (1,057 input tokens for a 12-line component, $0.000044).

- **`tezgah-triage --states` asks the interactive pair as one Choice, not two
  Nouls over the same bit.** `focus` and `active` were reading one piece of
  evidence: an aria snapshot marks the element that has focus `[active]` and
  carries no marker for a press, so the two came back high together on the driven
  fixture (0.95 focus beside 0.82 active for the focused searchbox) and `active`
  came back 0.87 for a button held down, which the tree marks only `[active]`. The
  pair is now one Choice over the three readings of that bit - `neither`, `focus`,
  `pressed`, each with the API's own criteria - and the answer's `choice` decides
  both rows; the other eleven states keep their Nouls, and the `unmarked:` line,
  the `--select` path and both fallback paths are untouched. Measured on the same
  driven fixture, re-driven this round through the pinned Playwright MCP
  (10 conditions x 5 components x 13 states, 50 live calls per arm): agreement
  97.7% -> 98.3%, the dangerous direction (a state called not-shown that the tree
  shows) 7 -> 6, states read as present when they are absent 8 -> 5. On the 100
  cells the change moves it is 95.0% -> 99.0%, with 1 -> 0 dangerous and 4 -> 1
  false-positive, while the 550 cells it does not touch swapped 2 wrong for right
  and 2 right for wrong - this model's run-to-run noise floor. It is not free:
  1,096 -> 1,115 input tokens and $0.000046 -> $0.000047 per call. The `pressed`
  option names the marker a press really prints, `[pressed]`, checked against the
  pinned MCP rather than assumed (`aria-pressed` on a button snapshots as
  `[pressed]`), and `active` stays on the `unmarked:` line because a held-down
  button prints only `[active]`. The one false positive left in the pair is the
  form under the held-down export button: the form's span carries a focused child,
  so the span reading says focus, where the fixture's own proxy counts only the
  searchbox. 3 hermetic cases pin the three-option criteria, the reading of
  `choice` and the answer of the wrong shape.

- **A transient upstream failure no longer costs a judgement.** `ask()` sent one
  request and nothing else, so a timeout, a connection error or a 5xx - observed
  once on this path at 2 of 50 `--states` calls, where the same cells answered on
  re-asking - came back as a `None` both callers read as "no judgement was made".
  One extra attempt now fires for exactly that class and no other: a 4xx (a refused
  credential, a rejected body) and a reply that parsed malformed are never retried,
  because the second request would fail identically and only a call that already
  worked must not be billed twice; the ceiling is one, so the normal call is still
  one request against one bill and the worst case is one duplicated request on a
  call that answered nothing anyway. The rate was re-measured before the retry was
  written: 184 live calls (60 at a small payload, 124 at the `--states` shape, 64 of
  those eight-way concurrent, spread over roughly eight minutes of wall clock)
  returned `None` zero times for $0.0105, so the steady rate reads as at or below
  1.6% (95% bound) and the earlier 2 of 50 as a transient epoch rather than a
  per-run rate - the retry is there for the epoch. Three hermetic cases pin the
  recovered 5xx and the never-retried 401 and 422, and the existing timeout and
  malformed-reply cases now pin the retry and its absence; both directions of the
  policy were shown to fail when flipped. The caller contract is unchanged: `None`
  on failure, never an exception, one request per call in the normal case.

- **The docs page fallback picks the topic, not the reader's word.** `bin/tezgah-docs`
  falls back to one TypeSafe Choice over the pages when the keyword index matches
  nothing, and its accuracy was unmeasured. Measured over 39 live queries the index
  could not place (33 paraphrases of the ten pages' own `answers` lines plus the
  queries naming nothing in the layer, run through a loopback recorder so the tokens
  are the tool's own request): 36 right, 0 wrong page, 3 missed, 0 pages picked for a
  query outside the layer, 37,369 input tokens / $0.001569. All three misses were the
  reader's word rather than the page's - a client where the page says host, a bar
  where it says line, "support one more" where it says add - so the question now says
  the reader may name a thing with a different word and to match the topic rather
  than the wording. That recovered one of the three, cost nothing and introduced
  nothing (37 right, 0 wrong page, 0 pages picked for a query outside the layer,
  39,046 tokens / $0.001640); the two that remain are the same vocabulary gap, and
  they stay misses because the layer carries no synonym list to judge them against.
  The deterministic path and both fallback paths are byte-identical; one hermetic
  case pins the question's instruction, the `none` option and every page's material.

### Changed

- **One answer reader for the seam, a switch per caller, and two credential rows
  instead of one.** `hooks/tezgah_judge.py` grew `choice(result, id)` and
  `noul(result, id)` - both total, both `None` on a missing or wrongly-typed
  answer - and all three callers read the reply through them; the triage's own
  `prob()` is gone. `grep` for a direct `.get("choice")`/`.get("noul")` now finds
  only those two bodies. Per-caller switches joined the master: `triage-off` and
  `docs-judge-off`, each checked before any request, so a caller that is off makes
  no call while its neighbour still judges - the pairing is what the new cases
  assert, because a caller that honours the global switch and forgets its own is
  the bug this shape introduces. All three names are in the always-on paragraph and
  the contract's table, with an assertion per name rather than only mirror parity:
  the parity test passes as long as the two copies agree, which is how `judge-off`
  stayed invisible for a round.

- **The installer reports both credential channels, not one.** `have_typesafe_key()`
  answers whether OMP can resolve a TypeSafe key (its env var, or its own login
  store) while the seam's `key()` resolves the env var or
  `~/.config/typesafe/key` - and the two sets diverge in BOTH directions: with the
  key file alone omp silently falls back to a chat model while the seam judges
  (measured: `have_typesafe_key() == False`, `available() == True`), and with an omp
  store row alone omp works while the seam has nothing. One row cannot answer both
  questions without being wrong in one direction whichever way it is written, so the
  installer now prints `judgement seam key resolvable` beside the omp row, from a
  new `tezgah_paths.have_judge_key()`. Simulated in three throwaway HOMEs: env only -
  both rows ok; key file only - omp `MISS`, seam ok; neither - both `MISS`. The
  predicate lives in `tezgah_paths` rather than importing the seam because the
  status mark must not pay urllib, and `tests/test_paths.py` pins both definitions in
  one process so the two cannot drift apart silently again.

- **The skill suggestion is opt-in, because its measured cost had no measured
  benefit.** It shipped armed, and the measurement that followed says it should not
  have: a labelled set of 28 prompts run through an independent chooser
  (`consult`, deepseek-flash, 0 of 88 cells changing between runs) scored 0 of 20
  wrong-load with NO hint at all, so the line cannot improve what is already right
  on this 13-skill roster while it costs about 78 tokens and 0.8 s on every fresh
  prompt - and the vendor's 16.8% -> 7.3% figure that justified it was measured on a
  182-skill roster with a different agent. `skill-suggest-on` in `~/.config/tezgah`
  turns it on, through `tezgah_paths.armed()`, which is `off()`'s opposite and
  exists because a rule a session was never armed with and a rule the user switched
  off must not look the same; an unarmed install makes no request at all, so the
  default costs zero bytes and zero cents. The old `skill-suggest-off` name is gone
  from the kill-switch list in the core text, its output-style mirror and the
  contract skill, `docs/contract.md` states the opt-in with the measurement behind
  it, and the docstring growth moved one citation, which `bin/tezgah-docs
  --citations` caught and the row was rebound to.

- **The product-analysis artifact contract now fails on a silently absent element.**
  The Ustam run satisfied every required section and still shipped with no component
  x state matrix, no screenshot read, no blur or grayscale test, no axe-core sweep and
  no walkthrough, none of them named as skipped - the list named them in prose inside
  one numbered item, and its only rule about absences was section-scoped. The matrix
  is now demanded as output: a table with a row per interactive component and a row per
  data view, each row naming the states checked and each state that does not exist. The
  absence rule now covers every element the list names, not only a section - produced,
  or named with the reason it was not - so a scorecard reported short counts as a
  silently absent element too. The run had the tooling the skips needed (the same
  desktop pass measured tap targets, computed contrast and probed the DOM per route),
  and the one absence the product forced, mobile, was already declared with evidence,
  so the fix is to the contract, not to the standards. The always-on PRODUCT paragraph
  and its contract mirror are unchanged.

- **The usability axis now goes down to component x state, and reads the image as
  well as the tree.** The second real run still stopped at the screen: no state
  matrix, and the rendered screen was never looked at, so hierarchy, rhythm, colour
  and feel sat silently outside the audit. Skill and rule now carry a depth ladder
  (screen -> component -> state -> measured property), a mandatory state set for
  every interactive control (default, hover, focus, active, disabled, loading,
  error) and every data view (empty, loading, skeleton, error, offline, partial,
  long-text, permission-denied) where a state that does not exist is itself a
  finding, and a section on reading the image: one capture per breakpoint, dark
  mode, largest text, plus the blur and grayscale tests, with anything read from
  pixels reported as a `judgement` and repeated twice. Two standards are now named
  and runnable in the page instead of argued about - axe-core (its own figure:
  about 57% of WCAG issues found automatically, with the checks it misses listed by
  name) and the Core Web Vitals thresholds - and `analyze-app` gains the
  screenshot, injection and `PerformanceObserver` recipes. A second inspection
  method joins the heuristics: the cognitive walkthrough's four questions per task
  step. `ui-observed` now records how a screen state was read, and a screenshot
  saved but never read explicitly does not count. The scorecard gains depth and
  image-evidence dimensions.

- **The product rule now covers every axis of a product, not only its code.** The
  first real run of `product-analysis` (a live multi-tenant SaaS) returned findings
  that were 100% `code` class: the product was never run, no competitor was looked
  at, no existing feature got a keep/cut verdict, and no answer existed for "what
  does the best version of this look like". The rule and the skill now carry five
  axes - value (unchanged), **usability** (Nielsen's 10 heuristics with the 0-4
  severity scale, WCAG 2.2 AA with the W3C WCAG2Mobile note for native apps, the
  running app read through `analyze-app` rather than inferred from source),
  feasibility (unchanged), **competition** (a teardown with the comparison basis
  stated before comparing, plus review mining, every competitor fact carrying its
  artifact URL and read date) and **triage** (keep / fix / cut / bet per feature,
  with a kill criterion - metric, failure level, timeframe, pre-decided action -
  wired to a flag and a named owner). One new evidence class, `ui-observed`, holds
  a screen state read from the running app, which previously had to be forced into
  `code` or dropped. A gate precedes all five: if the behaviour is not observable,
  "we cannot see this yet" is the first finding. The artifact gains a required
  section per axis - a missing section reads as a covered one - and the scorecard
  gains axis coverage and decision quality. Sources read this session: NN/g on
  heuristic evaluation and severity, W3C WCAG 2.2 and WCAG2Mobile, Umbrex product
  teardown, Appbot review mining, Mind the Product kill criteria.

- **Playwright MCP now carries the capabilities a product audit needs.** The
  wired command was `@playwright/mcp@0.0.81 --isolated`, and Playwright MCP serves
  core tools only unless capabilities are named - so an analysis could read an
  accessibility tree but could not assert anything, could not reach a logged-in
  surface without attaching to the user's real Chrome, and could not set the
  offline state. It is now `--caps=testing,storage,network`: `testing` turns a UX
  claim into a re-runnable `browser_verify_*` assertion, `storage` saves and
  restores a state file instead of touching the real profile, `network` sets
  offline and mocks a failing endpoint. `devtools` stays off - the opt-in
  chrome-devtools sidecar owns tracing and deep network. `analyze-app` gained the
  capability table, the mobile gap (Mobile MCP has no assertion, mocking or
  geometry tool, so a mobile UX claim is a judgement unless re-walked and contrast
  or tap-target size is not claimed without a screenshot), and `product-analysis`
  gained the evidence map from claim to exact call. Verified:
  `TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py` reports playwright
  exposing 52 tools and mobile-mcp 32, and `tests/e2e_analyze_wiring.py` now
  requires the four cap tools, so a silently dropped `--caps` fails CI. The cost
  is real: more tools mean a larger schema band.

### Removed

- **`HANDBOOK.md`, and the `--bundle` mode that generated it.** The ten pages of
  `docs/` were also shipped as one file in the repository root, regenerated by
  `bin/tezgah-docs --bundle` and held current by a test that compared the committed
  copy against the generator's output byte for byte. It was a second copy of the
  layer with its own drift: an edit to a page that did not regenerate it failed the
  suite, and it carried the same citations the pages carry, so every citation rebase
  meant editing it as well. Removed whole - the mode and its three helpers
  (`bundle`, `demoted`, `relinked`), the test, the root file, and the mentions in
  `docs/README.md` and `AGENTS.md`. The layer is `docs/*.md` plus `docs/index.json`,
  reached by `bin/tezgah-docs`.

### Fixed

- **the dsh inception route could not serve a model, and the TypeSafe row counted
  a file omp never reads.** A review of the provider commit found both. pi-ai's
  installed catalog ships `openrouter` and `deepseek`; a route it does not carry
  and that declares no `api` resolves with `api: undefined`, keeps the adapter's
  `PiAiCatalogError` as its `catalogError` and throws `INVALID_CONFIG` for every
  request that selects it - so `inception:` with only `apiKeyEnv` was inert while
  two `tezgah-setup --report` rows read `ok` over it (the routes row only greps
  the patch text). The route now declares `api: openai-completions`,
  `baseURL: https://api.inceptionlabs.ai/v1`, `compat.maxTokensField:
  max_completion_tokens` and its two models, the shape the adapter README
  documents for a route outside the catalog; the schema accepts it (`profile` in
  `@deepseek-ai/dsh-llm-pi-ai`, `supportedProtocols()` -> `openai-completions,
  openai-responses, anthropic-messages`) and the composed tree carries it.
  `have_typesafe_key()` had counted `~/.config/typesafe/key`, which is tezgah's
  key-file convention and not a path omp opens (0 occurrences in the binary): a
  file with no export and no login record would print `ok` while omp silently
  read the fallback chat model. It now counts the env var omp reads or a
  `typesafe` record in omp's login store, and a test pins that the key file alone
  is not enough. Three copies of the same fact were left behind and are corrected
  with them: the consult no-key appendix in `skills/tezgah-contract/SKILL.md`
  (the hand-kept twin of the policy text) and the two labels that still
  enumerated two providers (`bin/tezgah-setup`'s report row,
  `hooks/tezgah_context.py`'s health line).

- **The Stop rule's claim vocabulary missed a completion stated as a completed
  state.** `DONE` carried the first person and a handful of English forms
  (`yaptım`, `düzelttim`, `done`, `fixed`, `all tests pass`), so a reply that said
  the work *was* done - `güncellendi`, `kuruldu`, `eklendi`, `düzeltildi`,
  `uygulandı`, `yayına girdi`, `kapatıldı`, `landed`, `merged`, `wired into`,
  `is green`, `all checks pass` - was not a claim at all and never reached the
  `false_completion / claims` denominator the layer reads its own effect from.
  Measured over this machine's own 161 final replies in
  `~/.omp/agent/sessions/-Projects-tezgah` plus a hand-drawn set of 15 completions
  in that shape: the old list caught 2 of the 15 and read 34 of the 161 replies as
  claims; the widened list catches 13 and reads 39, with 0 of 5 control replies (a
  question, a plan, an explicit `doğrulanmadı`) claimed. The verdict does not
  move: a turn that recorded work is refused on its evidence whatever its wording,
  so the list is read for the claim row's detail and nothing else. `docs/gate.md`
  records the seat this leaves empty beside the gate's own, with the same reason
  and one of its own.

- **A passing check licensed a claim about a tree it never saw.** The Stop rule's
  refusal branch was turn-scoped while its pass branch was not, and neither
  compared a check's position against a write's, so `edit -> verify_ok -> edit`
  could end "done": the green run was real, and about the previous revision. An
  earlier turn's check licensed a later turn's edit-only claim the same way. The
  after-state that refutes both was already on the ledger and read by nothing -
  `_post_write` records `changed`, and `changed_files` had no caller outside its
  test - so the fix is a comparison, not a new record: the newest passing check
  must be newer than the newest write the gate saw change the tree
  (`_last_pass`/`_last_change`/`stale_paths`, `hooks/tezgah_integrity.py`), and
  the refusal names the files written after the check
  (`blocked: stale evidence`). A write that changed nothing does not count, a new
  file does, and the reply's own "doğrulanmadı" still clears it. Measured before
  the change on the real function, cells A and B:
  `.tezgah/research/infra-candidates/experiments/E0-current-stop-rule/`.
- **The legacy `verify_ok` tolerance is gone from `passing_check`.** Rows written
  before the ledger carried an `exit` were read as support; the branch's own
  comment set its removal condition at "no live session's first row predates
  plan 012", and the corpus now meets it - 464 such rows, in 150 ledgers, none of
  them written in the last 24 hours, and no current writer can produce one
  (`failed=False` always writes `exit: 0`).
- **The gate's effect table missed five remote-destructive actions, and three
  rules had no shell twin.** `gh repo delete`, `gh repo archive`, `aws s3 rb`,
  `aws s3 rm --recursive` and `flyway clean` derived no class, so the consent rule
  never asked about them; they do now (the `--recursive` flag is read from the raw
  text, because `mask()` blanks the tail of an `s3://` argument - named as the
  ceiling it is). Separately, `SKIP_TEST`, the attribution line and the secret scan
  were attached to `WRITE_TOOLS`, which is disjoint from `BASH_TOOLS`, so a
  heredoc writing a test skip, a `Co-Authored-By:` line or a credential into a
  file was refused by nothing - the route the E7c block measured as the one an
  agent takes once the write tools are refused. All three now read a shell write's
  body through the same shape test the task rule uses, so a quoted `>` is still
  not a redirect. The local-only actions (`git reset --hard`, `git tag -d`,
  `docker compose down -v`, `chmod -R 000`, a plain `git push origin main`) were
  deliberately left asking nothing, because a consent ask costs a round-trip and
  those are routine; they are listed for the maintainer's call.
- **The `out_bytes` guard was inert; a result size now reaches it from three more
  hosts.** `passing_check` refuses a check whose result was empty, and measured on
  2026-09-19 **0 of 1224 `verify_ok` rows across 1162 ledgers carried the field** -
  the guard had never rejected one. The codex, cursor and omp adapters now measure
  the result their own payload carries (a size, never the body, in O(1) and never
  a re-serialization) and write it. **This is a behaviour change, not only a
  repair**: a check whose host-reported result is empty - `grep -q`, `test -f` -
  no longer counts as support for a "done" claim on those hosts; run a check that
  prints something, or mark the claim "doğrulanmadı".
- **The `idx` mark reported a fresh graph when it could not compare one.** Both a
  missing stamp file and a failed `git rev-parse HEAD` fell through to the armed
  glyph, and `index_notice` stayed silent because the notice only existed for the
  stale state - so a graph built before the code moved was delivered with the
  index's authority, and on a host where the worker never writes a stamp the mark
  was permanently wrong. A fourth state (`idx?`, "cannot compare") says exactly
  that, the turn gets a line saying the graph's age is unknown, and the legend
  and the status-line page carry it (`hooks/tezgah_context.py`).
- **The reminder's standing merge authority was swallowed by its own exception
  list.** It said to merge a clean-reviewed PR without asking, then listed
  "anything touching a live production account or external service" among the
  cases to stop and report instead - and a PR merge is an external-service write.
  The carve-out that resolves this ("beyond the merge") lived only in the
  on-demand contract; it is now in the always-on paragraph too, at a cost of 17
  characters, plus the same clause in the per-turn reminder.
- **The subagent brief omitted two always-on blocks while asserting the rule set
  was complete.** It carried neither the on-demand-rules pointer nor any kill
  switch, so a delegated agent could not learn that spec-first, consult, research
  routing or graph-first exist, and could not answer "how do I switch this off".
  Both are in the brief now (2082 -> 3001 characters, inside the subagent budget).
- **The per-turn lessons digest moved for text the model was never shown.** The
  digest was taken over the untruncated lesson lines while the injected block
  truncates each at 200 characters, so a tail-only edit of a long line announced a
  change the model could not see. One reader now produces both the shown text and
  the digest, which is what the docstring already claimed.
- **`rsync` was classified by the wrong end of the command.** `rsync host:/src
  ./dst` - a read - was refused as a `send`, while `rsync ./dst host:/dst` - the
  data egress - derived no class at all, and a flag in front of the source
  defeated the pattern in both directions. The destination decides now
  (`hooks/tezgah_gate.py`), the opencode mirror agrees on the same nine forms,
  and the residual (`scp` is still matched by shape) is named on the gate page.
- **`powershell` could not be gated on any Python host, and `pwsh` was gated
  nowhere.** The name sat in `BASH_TOOLS`, but no `PreToolUse` matcher carried it,
  so those hosts recorded PowerShell rows and never refused one, and dsh's own
  spellings (`PowerShell`, `pwsh`) reached the hook only after the matcher was
  wired. `pwsh` itself was missing from `BASH_TOOLS` and from the JS mirror, so
  even a wired matcher let a `--no-verify` command through; both tuples carry it
  now.
- **The consent lease answered for command text rather than for an action.** The
  action digest has no workspace in it, so a grant obtained for one command in one
  repository answered for the same text in another; the lease is now bound to the
  workspace the ask recorded. And on Cursor - which reports no exit code for a
  successful shell call - the spender never fired, so a single approval became a
  standing permit there, against the documented lease model; an outcome row of any
  step kind now spends it on every host.

- **opencode's half of the gate had no `send` class, so an outbound send ran
  unasked there.** The JS mirror derives five effect classes and `send` was not
  one of them: `mail`, `sendmail`, `curl -X POST`, a payment API - each refused by
  the Python gate and allowed by opencode. The class is now named in the JS table
  (so a `tezgah:effect=send` declaration is ranked instead of silently dropped)
  and a command that looks like a send is put to the core through
  `bin/tezgah-gate`, which owns the pattern - the idiom the write path already
  uses. The pre-filter is the whole bound on a spawn per bash call, and
  `tests/test_opencode_plugin.py` pins both halves: a candidate reaches the core,
  while a read and a class the table already derives never do.
- **The contract's source list could go stale without saying so.** The set the
  installer hashes omitted `hooks/tezgah_context.py` - the renderer that selects
  and orders the policy's paragraphs - so editing the renderer left the hash
  unchanged and opencode's always-on text rendering the previous selection. That
  hash is the only thing that re-renders opencode's text: opencode has no
  session-start hook. The list names it now, a missing source still reads as
  stale rather than current (`contract_sha` returns `""` for an unreadable one),
  and `tests/test_setup.py` asserts the installer's list against the three
  sources `docs/operations.md` names.
- **`hooks.json wired` passed on any single event.** The row asked whether one
  marker appeared under *some* event, so a manifest wired for 6 of 7 events - or
  12 of 13 on Cursor - read as armed, and a host with no Stop hook at all read as
  armed. `_hooks_has(path, marker, events)` now returns True only when every
  named event carries the marker (`None` keeps the old any-event meaning that
  `predecessors()` relies on), and the two event lists are module constants the
  installers write from and the rows check against, so a row cannot drift from
  what the installer wired.
- **The plugin-copy freshness check could not see a file the copy held and the
  checkout no longer shipped.** The hash covered only files that still exist, and
  an unreadable source reads as `None`. `plugin_copy_current` compares both
  directions now, walking the copy with the same `managed()` predicate the source
  list is filtered through, and `--install` still empties the copy first, so the
  ghost goes.
- **The failed-index note named a log the worker never writes.** The note and the
  worker's stdout are one value now (`log_path`), so the path a reader is sent to
  is the file that exists - the hook opens it and hands the descriptor to the
  worker, which writes no log of its own. Line-count neutral, so no citation into
  that file moves.
- **`tezgah-research init` accepted any slug, and one of them wrote into
  `.tezgah` itself.** `check`, `status` and `claim` list `[a-z0-9][a-z0-9-]*`
  only, so a slug with a separator or a leading dot made a line no other command
  could see; `..` resolved to `.tezgah`, where `state.json` and `claims.jsonl`
  were written. `init` refuses anything outside that set with exit 2 (misuse) and
  `append_claim` returns a problem instead of writing, so no line can exist that
  the readers cannot find.
- **A referee's answer was printed as a judgement without being read.** The
  reply was checked for being non-empty and nothing else, so a model answering in
  prose under `## referee (<model>)` read as a cross-examination:
  `consult --models m1` exited 0, printed `referee: m1`, and printed the
  paragraph. The five field names the referee is asked for are checked now, and a
  reply missing any of them is disclosed exactly as a dead referee is -
  `referee: FAILED (unstructured)`, the panel standing unjudged, a retry hint -
  and the verdict text is not printed at all, because an unheadlined paragraph
  under that heading reads as a verdict whatever the footer says. Presence only:
  the content of an answer that does carry the headings is not judged.
- **codegen vouched for a draft by its suffix.** The parse guard keyed on `.py`,
  so a draft with no suffix - the repository's own `bin/*` scripts, which are
  exactly what the router hands it - was never parsed and still exited 0. A
  Python shebang counts now, and a language nothing here parses (`.tsx`, `.js`)
  is named on stderr instead of passing silently: `codegen: NOTE <path> was not
  parsed (no checker for this type)`. The ceiling is stated in code and in the
  contract: a broken `.tsx` draft still exits 0, and the point is that the router
  is told which file nothing read.
- **A consult or codegen answer was not an untrusted channel.** `curl` to a
  provider's URL was a network read; the tools that call one on the session's
  behalf were not, so the two highest-trust paths into the context carried no
  provenance label and no taint. A shell line that runs `consult` or `codegen` at
  a program position is a `tier` read now, named `an external model answer`, and
  every caller of `untrusted_source()` gets it - the label on the result, the row
  `source`, the taint notice and the gate's sink rule. The invocation shape is
  the rule rather than a list of local forms: `-h`/`--help` and a bare invocation
  reach no provider and are not reads, while `consult --version` was measured
  reaching one (3 calls, the panel asked the question `--version`). Two ceilings
  are stated in code: `python3 bin/consult q` is missed (the shell reader keeps
  basenames and does not treat `python3` as a wrapper), and a question that
  spells `--help` inside itself still counts - each closure would mean teaching
  the reader or duplicating a tool's argument parser, and the direction is the
  module's own: a missed read costs a label, a false one costs the turn.
- **The freshness rule could not see a shell write.** Its fold read `edit` rows
  only, while the gate's own experience is that a refused write tool sends an
  agent to the shell - the route E7c measured, and the structural limit
  ActPlane names. A `run` row whose captured target changed counts as a change
  now beside an `edit` row (`_change_row`, `hooks/tezgah_integrity.py`), and the
  gate hands a shell write's redirect target - or `tee`'s argument - to the same
  `capture` a write tool goes through (`write_paths`, `shell_target`,
  `SHELL_AS_WRITE` in `hooks/tezgah_gate.py`), mirrored in the JS half. No new
  mechanism and no new ledger field: `capture` already took a write tool's path
  field and `_post_write` already hashed the after-state. Four things still do
  not count, each pinned: a `verify*` row (the row that carries a pass cannot
  also be the row read as the change, or a check redirecting its own log would
  stale itself), a no-op write, a command that writes no file, and a quoted `>`
  or `> /dev/null` - the shape test runs on masked text. Ceiling named in code:
  `_stale_paths` still names edit rows only, so a refusal for a shell-only change
  falls back to "a file this session wrote".
- **`ssh` derived no effect class, and neither did two `gh` deletes.** `scp` was
  the send class and `ssh` was not, though `ssh host cmd` reaches a machine this
  ledger holds no pre-state for and can run a command there - the same egress,
  and further. It is classed now beside `nc`/`ncat`/`scp` (a bare `ssh` still
  derives nothing), and `gh run delete` / `gh cache delete` joined the
  `destructive` clause beside `gh repo delete|archive` and `aws s3 rb`: a CI
  run's record, and the caches other runs read, stop existing. `gh run view` and
  `gh cache list` stay unclassified, and a `# ponytail:` note records the
  ceiling - the next run rebuilds a cache, so the ask may not be earned.
- **`PowerShell` reached no hook on two of the five hosts that route it.** codex's
  and cursor's PreToolUse matchers named neither `PowerShell` nor `pwsh`, and a
  host runs the hook only for the tool names its matcher carries - so a call
  under either spelling never reached the gate at all, while the shared rules had
  known both spellings since the earlier round. Both matchers name both now (the
  installer's constants and the two committed manifests), and omp's `GATED` list
  gains `pwsh`. Nothing changes on a host that never emits the name; on one that
  does, a whole tool name's worth of refusals the gate could not make. The
  installed manifests pick this up on the next `--install`. Two claims next to it
  went with the fix: `docs/hosts.md` said `pwsh` "is not a `BASH_TOOLS` name" (it
  is, and the sentence now says so), and `dsh_patch_block`'s docstring said
  `hosts/dsh/hooks.json` carries "those seven" events where the file declares six
  - it says six now, and why nothing here handles a subagent's end.
- **A chained shell write was invisible to the freshness rule.** The target
  reader sliced `\S+` out of the masked command, so `printf a > x.txt; printf b >
  y.txt` yielded `x.txt;` - a path nothing is ever written to. No pre-state was
  captured, no after-state hashed, so the half of the rule the previous round
  closed for a single redirect stayed open for a chain, which is the shape an
  agent uses when it does two things in one call. The slice is trimmed of `; | &
  )` unless it is quoted, and `tests/test_gate.py` drives the real gate for the
  shape (fails before the trim, passes after). Measured while closing it, and left
  open with its ceiling in `shell_target`'s docstring: a target that is a *quoted*
  name reads as no target at all, because the slice is taken by offset from the
  text where masking blanks a quoted string.
- **A notebook write was captured nowhere.** `NotebookEdit` is classified as an
  edit and so runs the write-tool branches, but its target arrives in
  `notebook_path`, a key the path reader did not carry: no pre-state to roll back
  to, no after-state, so a notebook write could not be undone and could not stale
  a check. The reader carries the key now, and a test asserts both halves - the
  reader finds the path, and the gate hands the call to capture.
- **A generated agent was told to run a tool its own brief could not load.**
  `GRAPH_TOOLS` - the list the ToolSearch select line is built from, and the list
  the Codex/opencode briefs print - omitted `detect_changes`, while the reviewer
  body says "Load detect_changes and the graph tools" and then instructs the agent
  to run it for the blast radius. On Claude, where ToolSearch is what makes a tool
  callable, the generated role therefore named a tool it could not select; the
  hand-written plugin agent (`agents/tezgah-reviewer.md`) listed it, so the shipped
  role worked and every generated one did not. The tool is in the list now, the
  same string in the three `cbm-*` workflows and the harness skill, and
  `tests/test_agents.py` fails if the reviewer's select line stops naming every
  graph tool its body names.
- **`tezgah-doctor` could not see 2.1 GB of dead databases.**
  codebase-memory-mcp renames a database it cannot open to `*.db.corrupt`, and
  nothing reads a renamed database - dead bytes by construction - but `cbm_db_count`
  counts `.db` alone, so a cache holding 2.1 GB of them in 12 files reported 33
  live databases and silence about the rest. The doctor counts and reports them on
  their own line (`dead_dbs`), `--clean` deletes every one of them with no age
  threshold (a re-index rebuilds what they held), and the reclaim hint fires on
  their size as well as on the log and session counts. It also reports the hosts'
  own state - `~/.codex`, `~/.omp`, `~/.claude`, which on this machine are 10.9 GB,
  1.4 GB and 499 MB - and never touches it: the number is there so a reader can
  decide, and the reported bytes are apparent file sizes, not disk blocks, so a
  `du -sh` beside it will read smaller.
- **opencode carried no untrusted-content control at all.** The channel
  classifier, the `source` row, the label on the result and the sink rule reach
  five hosts through the shared Python core; a plugin cannot import that core in
  process, and nothing here mirrored the control, so a session on that host that
  read a fetched page, an MCP answer or a `curl` result went unlabelled and an
  effect leaving the workspace after it was not refused. The plugin carries all
  three halves in JavaScript now: a classifier whose answers are pinned against
  the Python half over a **shared corpus** (33 calls, plus a throwaway 53-shape
  probe of the shell reader - the probe found one real divergence before the
  change was finished, on four malformed-quote shapes, and it is closed), the
  label and the taint notice in front of the result the hook is handed (the
  runtime passes that object to the model and returns it, read out of the
  installed 138 MB binary), and the sink rule in `tool.execute.before` beside the
  consent rule: an effect that leaves the workspace is refused while the turn has
  a live read, an inside-root one passes with the notice, and the user's own grant
  from after the read lifts it. Every path fails open, as that plugin's convention
  requires - an unreadable ledger, a missing session id, or a result that is not a
  string leaves the call to the host. Six mutation checks were run against the new
  tests (five killed a test, the sixth is an equivalent mutant: one row is not
  two). Two ceilings are the Python module's own, verified as identical misses on
  both halves rather than assumed: a tier read reached through an interpreter
  (`python3 bin/consult q`) and a network read behind `sudo`. Two docs sentences
  that the change made false are corrected: `docs/evidence.md` said "opencode's
  plugin makes no call to the provenance test ... so that host supplies neither
  half", and the capability row in `docs/hosts.md` said the plugin does neither.
- **A write outside the workspace staled a check it could not have invalidated.**
  The fold behind `blocked: stale evidence` asks whether the newest passing check
  is newer than the newest write to *the tree this reply is about*, and it read
  every recorded write as one to that tree. A scratch file outside it is not a
  revision of the tree - a commit message written to `/tmp`, a harness log, a
  report written somewhere else - so a check that passed before it is still
  evidence about the tree. `_post_write` records no after-state for a target
  beyond the call's own root now, and such a row stops being readable as a change.
  Measured on this session's own turn: writing `/tmp/commitD.txt` after a green
  suite blocked the reply that reported the suite, which is the ceiling an earlier
  note had reasoned about and never observed. The three neighbours in
  `tests/test_integrity.py` are the control on the other side - a write inside the
  workspace, and a new file in it, both still stale the check - and the new test
  was watched failing with the guard reverted in place and passing after the file
  was restored byte-identical.
- **Three pages' citations into `hooks/tezgah_integrity.py` were repointed by
  anchor, and two of them had been wrong since before this session.** A bare
  `:NNN` citation inherits its path from the sentence, which neither the citation
  audit nor its tooling reads, so the numbers the automatic passes cannot see are
  the ones that drift: `_snapshot_hash` was cited 49 lines from where it lives and
  the `verify_ok` branch 71. Each was verified against the code it names rather
  than against a shift, which is what the rest of that page's citations into the
  module needed too (`note_tool` `:1115`, `stop_reason` `:1347`, the `external`
  and `unknown` rows `:1161`/`:1172`, the `source` field `:1177`, the `worked`
  set `:1433`). A bare-citation pass is still missing from the audit; the
  remainder is `.tezgah/plans/open/002-docs-citation-drift.md`'s.
- **A check named in a commit message was recorded as a check that passed.** The
  Stop rule reads the newest `verify_ok` row as support for a "done" claim, and
  `verify_command` searched the raw command text: a `git commit -F - <<'MSG'`
  whose message mentioned tests - and a `git commit -m "run pytest before this"` -
  were both recorded as `verify_ok` with no check having run. This session's own
  ledger had a `git commit` as its newest passing check at the moment the rule
  refused a reply. Both halves scan the masked text now, which is the convention
  this module already states for the twin rule ("a commit message that names
  `--no-verify` (quoted, or a heredoc body) is not a bypass"). The miss it opens
  is the piped check's own: a check run inside a quoted body (`bash -c 'pytest'`)
  records as one that ran, never as one that passed - the direction to prefer,
  because a lost pass costs a re-run while an invented pass costs the rule its
  meaning. `tests/test_integrity.py` and `tests/test_opencode_plugin.py` each
  drive their own half through the real hook, and both were watched failing with
  the fix reverted in place and passing after both files were restored
  byte-identical.

### Changed

- **the citations that name no symbol beside them were adjudicated page by page,
  and 224 of them were rebound.** `bin/tezgah-docs --citations` judges only the
  citations a symbol sits next to (243 of them); the other 575 were unjudged, and
  six read-only passes over them - one page each, with the sentence as the
  specification and the cited file as the evidence - found 175 pointing at a range
  that no longer showed what the sentence names. Six writers, one page each,
  applied them: 224 citation tokens across the ten pages, re-verified by reading
  the target line, in a diff that touches numbers only (184 insertions against 184
  deletions). The twenty most severe were spot-checked independently afterwards,
  and all twenty showed the quoted line where the writer said it would be. The
  three that named no symbol at all, plus the residue the writers' own rule could
  not settle, are what the audit still counts as unjudged - the number to watch
  after the next change to a cited module.

- **`bin/tezgah-docs --citations` could not see most of the CLI citations.** Its
  pattern for a path required a file extension, so every citation to
  `bin/tezgah-setup`, `bin/tezgah-status` and the other extension-less commands was
  invisible to it: not judged, not counted, not shifted by any mechanical pass -
  which is why a page citing the installer drifted furthest. The pattern now takes
  a path with a slash or a dotted name, and the judged population went from 243 to
  260.

- **the bare citations the 002 audit left open were rebased, and 81 numbers were
  wrong.** A citation that names a symbol beside it (`note_tool` `:1115`) is
  checkable: the range has to lie inside that symbol's body, and that is the half
  no tool covered - `tests/test_docs.py` checks that the cited file exists and the
  line is inside it, which a citation pointing at the wrong line passes, and a
  bare `:N` inherits its path from the sentence, so the rebase that repaired
  `path:line` never saw it. The audit now judges every such citation (242) and
  reports none outside its symbol; reaching zero corrected 81 numbers across six
  pages, the evidence page worst at 49, in the shape a moved line leaves behind
  (`_post_write` `:1008-1035` -> `:1066-1112`, `stop_reason` `:1254-1279` ->
  `:1356-1382`, `TIER_PROGRAMS` `:933` -> `:942`). Two numbers the same pass
  caught as stale are corrected with them: `docs/evidence.md` said no `verify_ok`
  row carried `out_bytes` (6 of 1423 do, across 1454 ledgers) and that
  `false_completion / claims` was 0.271 over 1166 ledgers (0.224 over 1454).

- **the docs layer's `path:line` citations were audited against HEAD, and 414 of
  them corrected.** The code moved under the pages and most citations pointed at
  the wrong line - the gate page worst, at 130. Ten page-by-page audits are
  recorded under `.tezgah/research/jev-classifier/` (local, gitignored);
  `tests/test_docs.py` now checks the half a script can (the cited file exists and
  the line is inside it); and the 61 citations the mechanical pass could not
  verify are tracked in `.tezgah/plans/open/002-docs-citation-drift.md`.
- **that audit left the page it corrected most mangled, and no check could see
  it.** Twelve citations in `docs/operations.md` carried a path stitched onto
  itself with a range running backwards
  (`bin/tezgah-setupbin/tezgah-setupbin/tezgah-setup:2259-2256`, up to five
  repetitions of the path), and the same twelve were mirrored in the generated
  `HANDBOOK.md`. The mangling was two-part - the path repeated *and* the numbers
  moved - and the ten argument-parser rows pointed at no revision's flag line, so
  those numbers were re-derived from the code (`ap.add_argument("--wizard"` and
  its nine siblings) rather than un-shifted. `tests/test_docs.py` checked a
  range's bound but never the path, so a mangled token passed a green suite;
  `test_no_citation_repeats_its_own_file_name_or_runs_backwards` now rejects a
  token that names its own file twice or ends before it starts. Neither rule
  needs an allowlist, and the pattern had to be widened to every backticked
  `path:line`: the extension-shaped pattern the file's other check uses never
  reaches `bin/tezgah-setup`, which has no suffix - the first version of the new
  test passed on the mangled tree for exactly that reason, and was re-proved
  failing in a clean clone (12 failures) before it was re-proved passing.

### Added

- **TypeSafe (Jev) is reported as an armed capability, because omp spends its
  key.** `TYPESAFE_API_KEY` is what omp reads for `judge()`, auto thinking,
  unexpected-stop and AI staging, and a session without it silently gets the
  fallback chat model where a System One judgment was meant - so
  `have_typesafe_key()` (the env var omp reads, or a record in omp's own login
  store; the `~/.config/typesafe/key` file is tezgah's convention and only
  reaches omp through the export) and a `host_checks_omp` row
  (`tezgah-setup --report`) say which one a session will get. The key itself is
  not a provider tezgah can route: `POST https://api.typesafe.ai/v1/systemone`
  takes state plus typed questions and answers with judgments, so `consult`,
  `codegen` and the host chat routes cannot name it - omp's own integration is
  the seat, and the row is what tells a session whether it is there.
  Checks: `unittest discover -s tests` (test_paths 23, test_setup 69),
  `ruff check .`, `compileall`, `tezgah-setup --report` showing the row `ok`
  with the key file present.

- **Inception Labs (Mercury) is a provider in `consult`, `codegen`, dsh and
  opencode.** Both CLIs take `--provider inception`: the key comes from
  `INCEPTION_API_KEY` and then `~/.config/inception/key`, the models are
  `mercury-2.5` and `mercury-2` (consult's panel) or `mercury-2.5` (codegen's
  default), and codegen names the token cap `max_completion_tokens` there - the
  OpenAI default is the wrong field, so the name follows the provider. The dsh
  home patch declares the third `llm-pi-ai` route beside OpenRouter and DeepSeek,
  and `tezgah-setup --report` says whether each host can resolve its key: dsh
  reads the launch env, a key file or its credential store; opencode reads the
  env or its own auth store, because its registry owns the provider and
  `opencode.json` carries no route block to add. `have_consult_key()`, the
  no-key appendix and the status-line page follow.
  Checks: `unittest discover -s tests` (test_providers, test_codegen,
  test_paths, test_setup), `ruff check .`, `compileall`, and the composed dsh
  profile read back with `dsh --profile headless --dump-config`.

- **`bin/tezgah-docs --citations`: the half of the citation audit a script can
  judge.** A page writes its citation either as `path:line` or as a bare `:line`
  inherited from the sentence, and only the first form was machine-checkable, so
  the second drifted unread - which is what the 002 plan recorded as still
  missing. A citation that names a symbol right beside it is decidable: the range
  must lie inside that symbol's body, which is the property the last audit
  established by hand across ten page-by-page passes. The mode resolves the
  symbol in the code (a name that exactly one file defines; a path-quoted
  citation is judged against the symbol in *that* file), prints every range that
  falls outside, and counts what it could not judge rather than guessing - 242
  judged and 575 unjudged on this tree, with the recursion found in the resolver
  and two cut-short spans fixed before its own output was trusted. It is a
  report, not a gate: exit 1 with findings, 0 with none, and the pages say so.

- **`order`: the first rule that asserts an ordering between two actions.** Every
  other rule in `decision` reads one call plus a ledger tail; none of them says
  that one action must not follow another. The field's own measurements put
  sequence-dependent constraints at 90% of real instruction files, so the gate now
  has a rule kind for them, with exactly one obligation in it: a `git commit` or
  `git commit --amend` is refused while the newest check in the session failed.
  It cannot fire when no check ran or when the newest check passed - a docs-only
  commit is untouched - and it rides the existing `verify-off` switch, so no new
  switch and no new always-on text. The measurement is pre-registered in
  `.tezgah/research/infra-candidates/experiments/E3-commit-on-red/protocol.md`.
- **`tezgah-status --unclassified`: the gate's own blind spot, read from real
  traffic.** Nothing extracted "allowed + effectful + derived no class" from the
  ledger, so the pattern table could only grow by hand. On this machine's 1195
  ledgers it reports 10,294 such shell calls (9,268 distinct) and, in its first
  run, named two effects that no pattern covers and no one had listed: `gh run
  delete` / `gh cache delete` (a delete at a service) and `ssh host cmd` (data
  egress, which `SEND` covers for `scp` but not for `ssh`). `--unclassified
  <PROGRAM>` narrows it; `--json` prints the dict.
- **`tezgah-status --counters --all`: the layer's own headline number over every
  ledger.** `counters` reads one session and writes nothing, so
  `false_completion / claims` - the ratio the code itself calls the only measure
  of the layer's effect - could not be read across a day's work. The arithmetic
  moved into one `_counts(rows)` reader, `counters_all()` folds every ledger
  through it (1166 ledgers, 17520 events, 0.19 s on this machine: no window and
  no cap, because a cap would make the total contradict the per-session numbers
  it claims to be), and the CLI takes `--all` (`--json` prints the dict).
- **`HANDBOOK.md`: the docs layer as one file.** The ten pages under `docs/`,
  joined in the router's order by `bin/tezgah-docs --bundle`, with their
  cross-references turned into anchors inside the one document and each page's
  headings demoted under a single title - the file to hand to someone outside the
  checkout, or to paste where a relative link cannot reach. It is generated and
  cannot drift quietly: `docs/README.md` names the command that rewrites it, and
  `tests/test_docs.py` fails while the committed copy is stale.

- **`docs/`: the engineering layer, with a router an agent can reach.** Ten pages
  - architecture, hosts, contract, gate, evidence, status-line, skills, testing,
  operations, glossary - each opening with what it is and who reads it, ending
  with the files it documents, and citing `path:line` for every non-obvious
  claim. `docs/README.md` is the router, `docs/index.json` the machine-readable
  index, and `bin/tezgah-docs` answers a query with the page(s) that own it, so a
  session reaches the internals in one hop instead of reading 55 files. The
  glossary is the only place a term is defined. `tests/test_docs.py` pins the
  layer: every page has an index entry, every entry resolves, every relative
  anchor a page links to exists, and every page carries a citation.

- **The act-on-it output shape is a rule of its own (`tezgah-adhd off`,
  `.no-adhd`).**
  `skills/i-have-adhd` (MIT, vendored and adapted) is armed beside ponytail:
  the answer or the next action on the first line, numbered steps for
  multi-step work, the position restated in one line while it runs, tangents
  waiting their turn, errors as location/cause/fix, a list capped at five ranked
  items with the rest kept in reserve, and an estimate marked as an estimate.
  Two upstream rules are rewritten rather than imported verbatim, because they
  collided with rules already in force: the state restatement points at the todo
  list instead of duplicating it, and a time estimate can no longer be read as a
  measurement (the integrity rule). Armed everywhere ponytail is - the always-on
  text, the on-demand contract, the subagent brief, every host's skill router -
  with its own switch (`tezgah-adhd off|on`, or a repo's `.no-adhd`) and its own
  `adhd` status mark.

- **The ponytail intensity level is a stored switch (`tezgah-pony lite|full|ultra`,
  `/tezgah:ponytail` on Claude).** The skill advertised a level switch and
  nothing stored one, so `lite` and `ultra` were phrases in a document. The level
  lives in `~/.config/tezgah/ponytail.level` and rides the per-turn reminder when
  it is not `full`, which is why an armed level is no longer something the model
  has to remember. The default removes the file and adds no characters.

### Fixed

- **The `research` mark could never light up on Claude, and a bare mention could
  light `consult`.** The transcript half resolved a Bash call with a substring
  test for one tool name; it now calls the same `shell_kind` tokenizer every
  other host uses, so an `orx` run marks `research` and a command that merely
  quotes the word marks nothing.
- **The opencode gate let a repeat of an unapproved irreversible command
  through.** Its JavaScript half still carried the pre-lease model: the first
  refusal counted as the approval, a `repeat-allowed` row was written, and a
  `grant` was never spent - so one approval authorised unlimited repeats. It now
  matches the Python gate (commit 3a45a1f, "a lease instead of a repeat"): a
  repeat is refused again with the ask-stands clause, and a grant is spent by the
  outcome row that follows it. Its refusal also names the action's digest and
  `bin/tezgah-consent`, which the JavaScript text had left out.
- **dsh's status line had no used marks at all.** The shared PostToolUse hook
  never recorded a used kind, and dsh (unlike Claude) has no transcript to derive
  one from, so its `consult`/`research`/`cbm` marks could not light. The hook now
  records the kind it can see, and SubagentStart records `orch`.
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
  passes. `task-off` removes all of them.

- **A read-only phase refuses a shell write, and the per-turn task line no
  longer prints a command the gate refuses.** Rule 10 was re-measured against
  the same task, model and k=25 with the printed unlock gone (E7b): obedience
  moved from 0 of 25 armed runs to **21 of 25**, and every route left was the
  shell. The 3 bypassing rows wrote the target with a heredoc redirect
  (`cat > app/api.py <<'EOF'`, `cat >>`, one absolute) after taking 12 phase
  refusals and 5 record-CLI refusals, and the one row that passed the task did
  it by editing the record with `sed -i` (rows under
  `benchmarks/arm-bench/results/e7b/` on the `benchmarks/lab` branch, designed in
  `PREREGISTRATION-E7b.md` there). A read-only phase now refuses a shell command
  that writes a file - redirects, `tee` at the end of a pipe, `sed -i`/`perl -pi`,
  `dd of=`, `truncate`, `cp`/`mv`, `patch`, `git apply|restore|checkout --` -
  over the masked text, so a quoted `>` is not a redirect and `> /dev/null` is
  not a write, and without consulting the allowlist (a shell line's targets are
  not read). The per-turn line that names the active task used to end with
  "Advance it with `tezgah-task phase P`"; one E7b row ran that command five
  times in a row against a gate that refuses it every time, so the line states
  whose the phase is now instead of naming an act the gate refuses. The route
  left is a **code-execution tool** (`eval`), which the gate classifies as
  neither a write nor a shell command: the same block measured one row in 25
  writing the target through it after both were refused. That residual is named
  in the rule's comment, not closed. `task-off`
  removes all four refusals.

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

- **`pony` reports the read, not just the arming.** The mark meant "the rule is
  on", which is a different claim from "the session has the full skill text" -
  the always-on text is a fifth of it. It flips from armed to in-force when the
  session actually opens `skills/ponytail/SKILL.md`, on the three hosts that can
  observe a read without paying a process for it (Claude parses its transcript,
  opencode classifies in-process, omp's embedded runner filters the path before
  it asks python). A host that cannot see the read does not get to say "not used
  yet" either: it passes the measures it does have
  (`tezgah-status --observable=`, the new flag every status surface threads
  through) and those marks render dim with no glyph, so the line neither claims
  the skill was opened nor that it was not. Codex and Cursor pass the tool-use
  four; so does dsh's Web route - which along the way gained the used marks it
  never had, because the shared PostToolUse hook now records the kind it can see
  (consult, research, cbm) instead of leaving that store empty for the one host
  with no transcript of its own.

- **The always-on ponytail rule now points at the full skill.** The summary
  paragraph carried the ladder, the root-cause rule and the `ponytail:` comment
  but never told the session to open `skills/ponytail/SKILL.md` - that pointer
  lived only inside the on-demand `tezgah-contract` skill, so the intensity
  levels (`lite|full|ultra`), the single runnable-check rule and the
  `[code] -> skipped:` output pattern arrived only if the model happened to read
  it. One sentence sends it there on the first non-trivial coding task, in the
  always-on core and in the `output-styles/tezgah.md` mirror (+150 chars, ~38
  tokens per session).

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

- **The two switch-only marks are documented, and the six research lines'
  reader-facing artifacts exist.** `docs/status-line.md` now names `cbm` and
  `orch` as the marks that carry no availability probe, and says where a missing
  capability is reported instead: `idx`'s `-` for the graph, beside the note that
  names the absent MCP. That is the asymmetry four of the eight marks raised and
  the page never answered, and it is a documentation gap rather than a defect -
  the graph-first rule ships whether or not codebase-memory-mcp is installed, so
  `cbm` reports the rule, not the toolchain. The four concluded lines that owed a
  `to_human/review.json`, and the two that owed a `to_human/report.md`, now carry
  them: six dimensions scored 1-5, findings that quote their target verbatim, and
  `grade: revise` on all four, because none of them was worth accepting - one
  line's protocol turned out to be a re-creation written after its run, another's
  own measurement refutes a claim it still carries. `migrate` derived 64 claim
  `kind`s and results-row `source`s from the fields the artifacts already held
  rather than inventing them, and the E7 acceptance rows were filed under the
  receipt they match row for row (`raw-results.json`). Over the six lines
  `bin/tezgah-research check` drops from about 125 warnings to 21, all of them
  named and deliberate: seven experiments whose results stay untracked because
  committing them would assert an order their own protocols deny, six protocols
  that are delegated-map briefs, and one source that exists on no second index.

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
  `:875`) - so two sessions recording at the same moment could lose a claim
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

[0.16.1]: https://github.com/r1z4x/tezgah/releases/tag/v0.16.1
[0.16.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.16.0
[0.15.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.15.0
[0.14.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.14.0
[0.13.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.13.0
[0.12.1]: https://github.com/r1z4x/tezgah/releases/tag/v0.12.1
[0.12.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.12.0
[0.11.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.11.0
[0.10.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.10.0
[0.9.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.9.0
