# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Real bash now checks the shell readers.** `tests/fuzz_shell.py`
  draws seeded lines from the hand vectors' grammar. It runs each in `bash`
  with a stub per program word and prints each class where `shell_programs` or
  `mask` disagrees. `tests/test_fuzz_shell.py` runs a small sample per suite
  run and fails if `mask` blanks a program bash ran.
- **Concluding or closing a research line seals it.** `conclude` and `close`
  write `state.json` `order_seal`. It holds, per experiment, the sha256 of
  `protocol.md` and `results.jsonl`, and no order verdict. Every `check`
  verifies the hashes, with or without git, so the session note reports an
  edit after the seal. While the hashes hold, `check` re-derives the order, so
  results committed after the close still count. `tezgah-research seal <slug>
  --history-lost --ack "<decision>"` gives the owner's `history-lost` verdict
  to a line concluded before seals (ADR 009). It covers only an order the lost
  history left undecidable. A real violation stays an error.
- **`tezgah-research import <checkout> [<slug>]` moves a line with its
  history.** It fetches the other checkout's `.tezgah` repository from disk.
  It merges that history as a second parent and takes only the imported lines.
  It refuses a plain copy, because a copy loses the order proof. It needs no
  remote. An open line arrives beside open ones only with `--allow-open`.
- **The MCP tool `tezgah_research_check` takes a `slug`.** The server checks it
  as a line name. It passes the slug after `--`, so `tezgah-research` never
  reads it as a flag.
- **The neuter matrix mutates the Stop rule.** `tests/neuter_matrix.py`
  generates one mutant per Stop-class return site. The sites sit in
  `_stop_block`, `_shape_block` and `_evidence_block`: 13 over 11 classes. Hand-written rows add the
  guards around them: the pass predicate, the empty-run read, the pipe
  guard and the "doğrulanmadı" clear. The lost call, the bookkeeping and
  idle-turn fallbacks, the refusal row and the `other repo` cause are rows
  too. The run adds the omp and after-block Stop test modules.
- **Every session attests tezgah's own hook entries.** The installer now
  records each host's tezgah-owned hook entries in `contract.sha256`, one line
  per entry. On a release install it also records the scripts they run. Each
  session start compares the entries on disk with that record. opencode does
  it at its first message. The session gets one `attest` row: `ok`,
  `drifted: <entries>` or `unverified: <why>`. A drifted row names the entry.
  It also names a hook file any user can write and a stale omp bridge. The row
  lists the kill switches present. A drifted session shows a `drift` status
  mark, and its claim rows carry the drift in `harness`. Drift never blocks a
  reply. `--report` prints the same comparison per host.
- **`tezgah update` shows the hook change.** It prints each tezgah hook entry
  the new release adds, removes or changes. That comes before the re-arm. On
  a terminal it waits for a yes. A piped update goes on (decision 12).
  `--upgrade` does the same. The new tree answers through
  `tezgah-setup --hook-entries`.
- **`upgrade.sh` checks build provenance when `gh` is there.** It runs
  `gh attestation verify` on the tarball against the release workflow's
  attestation. Without `gh` it prints `provenance not checked`, and a `gh`
  that cannot answer is a warning. The checksum stays the gate.
- **`docs/hosts.md` states each host's enforcement capability.** One table
  covers the gate, the Stop rule and subagents per host, in gate, observe,
  partial and unavailable. A cell no driver can probe says unverified.
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
- **`--install` arms Claude Code through its own CLI.** Claude's gate, Stop and
  ledger hooks ship in the plugin. The installer never registered that plugin,
  so only the maintainer's machine had them. The install now
  writes `.claude-plugin/{plugin,marketplace}.json` from the release version
  into its own tree. The pair stays untracked. It then runs `claude plugin
  marketplace add <tree>` and `claude plugin install tezgah@tezgah-local`. An
  existing `tezgah@*` row is left alone, so no hook fires twice. Claude's
  `plugin copy current` row now fails `--install` where a `claude` CLI exists.
  `--uninstall` also drops the `enabledPlugins` key and the rendered pair.
- **`--report --live` proves the gate runs.** Each host now also gets one
  PreToolUse for `git commit --no-verify -m x` through its own wiring. The row
  is ok only when the host answers with its own deny and the ledger gains a
  deny row. `pretooluse-off` and `verify-off` make it UNVERIFIED, named. The omp
  bridge must match a fresh render byte for byte. opencode's plugin now writes
  a deny row for its own refusals. The Python gate already did.
- **`reply_lang` picks the reply language.** `tezgah-setup --install
  --reply-lang tr|en|any` stores it in `config.json`, and `install.sh` forwards
  the flag. `tr` is the default and what an install without the key reads. `en`
  asks for English and `any` for the user's language. The Stop rule checks
  the language only under `tr`. The contract's first rule and
  the per-turn reminder name the configured language.
- **README: what tezgah changes on your machine**, in all five languages.
- **The gate guards tezgah's own control plane (`control`).** It refuses a
  change to a kill switch. It covers `~/.config/tezgah`, the evidence ledger
  and the hook wiring too. It also refuses a change to a repository's `.no-*`
  mark or `.git/hooks`. It
  refuses a delete or move of `.husky` or of an open plan. It refuses a
  forced `git add` of a `.tezgah/` path, and the CLIs that change that state.
  Claude's `disableAllHooks` and Codex's hook trust entries count as wiring.
  The rule follows a `cd`, `if`/`for`/`!`, `eval` and `bash -lc`. It refuses a
  write through a link and a delete of a directory that holds this state.
  Only `pretooluse-off` removes the rule, and the refusal names no command.
  All 12 tamper probes of the deep analysis passed the gate before. Now the
  gate refuses all 12. ADR 010 freezes new gate rules, and ADR 004 makes this
  one the exception: it ships this half of R05 (R05a) now. An interpreter
  (`python3 -c`) still gets through. `SECURITY.md` names it as a residual.
- **A damaged ledger line blocks a done-claim.** A bad ledger line used to
  make the reader raise. The Stop rule then failed open for the turn. The new
  Stop class is "evidence tampered". Now the reader
  skips the line and writes one `ledger_damage` row for it. The Stop rule
  refuses a done or tested claim in that turn. That covers a corrupted
  `verify_fail` row too.
- **A switch armed mid-session leaves a record.** The prompt hook writes one
  `disarm` row for a switch that appears after the session's first prompt.
  The status line shows its `gate✗` mark while that switch stays armed.
- **Subagents stop sharing taint on Claude.** Claude's hook payload names the
  subagent (`agent_id`), and its rows now carry it. One sibling's web read no
  longer marks another sibling's effects. The repeat ceilings count each
  agent's own attempts.
- **`SECURITY.md` states the threat model.** It names a cooperative but
  fallible agent, the state the gate guards and how, and the residual routes.
- **The control rule also guards the attestation state.** It refuses a
  change to the `harness-drift/` and `import-crash/` status marks and a
  `tezgah-context attest` run. The `hook:<host>:...` rows of `contract.sha256`
  were already covered as tezgah's configuration, and a test now pins them.

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
- **`tezgah-setup --write-plugin-agents`.** The plugin's `agents/tezgah-reviewer.md`
  is now rendered from the same role body the per-repo reviewer gets. A test
  fails until the flag has run after a body change.

### Changed

- **A session pays each armed rule once.** The first matching prompt gets the
  full paragraph of spec, consult, research, product or graph. A later match in
  the same session gets one line that names the rule. The research line keeps
  its open-lines fact. A compaction brings the full paragraph back. So does a
  match 20 turns after the last full showing, for Cursor and dsh. The per-turn
  reminder no longer restates spec, graph or research. Those rules reach a turn
  through their own paragraph. It keeps the short consult clause, because a
  terse irreversible ask arms nothing. The `user_prompt` budget now drops the
  skill hint before the task phase, the delta and the pointer. A replay of
  1,452 uncut real prompts from 85 local sessions ran through `context_for` in
  a fixture repo. Injected bytes per session fell from 37,387 B to 28,928 B
  (-22.6%). Per turn they fell from 1,599 B to 1,104 B. The Stop-shape and
  claim-rate comparison needs a 2-week window and has no result yet.
- **The subagent brief keeps each rule's operative sentence.** The brief kept
  only each rule's first sentence. A delegate lost "inter-agent reports stay
  English" and the lessons instruction. A per-rule sentence count now keeps two
  sentences of three rules, cut from CORE's own text. The brief grows from
  4,120 B to 4,263 B. The `subagent_start` budget moves from 5,000 B to 5,500 B.
- **User constraints survive compaction.** A prompt clause like "don't touch
  hooks.json" or "README'ye dokunma" now rides the turn stamp, to its
  sentence's end. The stamp holds that clause, never the prompt. A clause that
  starts inside quotes or code does not count. The recogniser skips a prompt
  over 12,000 characters: pasted material is not the user's constraint.
  A quoted object after a plain "don't touch" still counts. The post-compact and
  session-start blocks restate the clause. The compaction row counts its object
  phrase in `constraint_found`. On the 1,452 uncut real prompts the recogniser
  pinned 7 clauses in 6 prompts, all real constraints. Before these bounds it
  pinned 17 in 11 prompts, 6 of them from one pasted 387,905-char agent log.
  `tests/constraint-fixtures.md` lists the rows, the misses and the known false
  positives.
- **Generic arming stems carry a qualifier now.** Ten code-sense asks no
  longer arm product, spec or research. Examples: "add a feature flag",
  "segment fault", "tabloya sütun ekle (sql)", "bu fonksiyonu sadeleştir". Every
  frozen corpus row keeps its verdict.
- **The policy keeps no joined `CONTRACT` constant.** The cost report measures
  the shipped `tezgah-contract` skill file instead. `ContractParity` walks the
  policy blocks against that file. The executive-mode "these win" sentence now
  covers output and report style only. A nested AGENTS.md or CLAUDE.md still
  binds its subtree.
- **opencode compaction passes the session id.** The builder then forgets the
  lessons and armed paragraphs that session saw. The plugin used to send `{}`.
- **Research predictions and the per-component report stay frozen.** They keep
  working as documented and take no new rule, field or command (ADR 009).
- **`check` reports a superseded claim once.** Only the row that supersedes it
  warns, naming both ids. The superseded row no longer warns a second time.
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
- **tezgah teaches `codegraph affected` as what it is.** codegraph 1.6.0 says
  it "finds test files affected by changed source files". Every copy taught it
  as the blast radius of a ref. Now the contract, the reminder and the skills
  say it. The role bodies and the graph workflows say it too. The blast radius
  is `git diff` plus `codegraph impact <symbol>` per changed symbol.
  `git diff --name-only <ref> | codegraph affected --stdin` picks the tests.
  A reviewer with no shell (Claude, opencode) gets the changed files from its
  caller and runs the MCP `codegraph_impact` tool per symbol.
- **ToolSearch loads both codegraph MCP names.** A plugin install names the
  tools `mcp__plugin_tezgah_codegraph__*`, a checkout's own server
  `mcp__codegraph__*`. The select lines name both.
- **tezgah retires three unused roles.** It no longer generates
  `tezgah-explorer`, `tezgah-verifier` or `tezgah-researcher`. A session start
  sweeps their managed files from the repo agent dirs. `--install` sweeps them
  from omp's agent dir. The plugin's hand-kept `agents/tezgah-explorer.md` is
  gone. Steering names none of them.
- **`agents-off` removes the generated agents.** It used to stop generation and
  leave the old files for every host to keep loading. The next session start
  sweeps the repo agent dirs. The next `--install` sweeps omp's user-level
  agents, and it removes only names tezgah ever generated.
- **A repo's `.no-graph` hides the reviewer from steering**, also on omp, where
  the agent file is user-level.
- **Claude reads the graph workflows from the plugin only.** `--install` no
  longer links `~/.claude/workflows/*.js`, so each workflow loads once. It
  removes tezgah's old links there and any dangling `cbm-*.js` link. The
  report row now checks that no such link is left.
- **The `ai-research` feature row is gone.** It switched nothing. A
  `config.json` that still names it loads and installs as before.

### Fixed

- **The word reader follows bash on three shapes.** A `$'it\'s'` is one
  word, so the line after it no longer falls to the
  rough read. The words after a `$( )` or backtick close stay that command's
  arguments. `shell_programs` names the substitutions of an unquoted heredoc
  body and nothing of a quoted one. The fuzzer found all three.
- **A prefix bash reads as words no longer hides a shell rule.** Such a
  prefix is a URL's `//`, `a#b`, a glob pair or `'x\'`. The masker read it as
  a comment or an open string and hid the command after it: `HUSKY=0 git
  commit`, `pytest || true`, `tezgah-task phase` or a credential write. `mask()` now
  reads a shell line the way bash does. Source files keep the old reading
  (`mask_source`). `shell_programs` uses the gate's own reader, so `a#b`, a
  redirect target and an unreadable line no longer mislead it. The opencode
  plugin keeps its own masker.
- **A check whose status the line does not keep is no longer a pass.** These
  lines record as ran: `pytest; echo done`, `pytest; echo EXIT=$?`, `pytest &`,
  `pytest > log; tail log`. Each exits 0 whatever pytest found.
  `pytest && echo ok`, `cd x && pytest` and a `set -o pipefail;` pipe still
  pass (`status_hidden`). The NEUTER comment now names only what it denies.
  The piped and neutered remedies name the shape that keeps the status.
- **Two lines each delivering their own `to_human/report.md` are no longer
  serial twins.** `serial_twins` compares the resolved file, not the spelling.
- **A claim's `path:line` citation is not a number.** The containment rule
  lifts it off the statement, like a date.
- **The research skill's `init` example carries `--ask`.** Without it, `init`
  refused the command. The skill also says `source` does not check for a commit
  of the protocol. The order rule proves commit order, not run order.
- **A hook whose core cannot import fails open and says so.** Eleven entry
  points imported the core outside `safe()`. A rename or a broken module ended
  them with a traceback, and on omp that disabled the gate for the session.
  They now exit 0, print one stderr line and write a `crash` row. The status
  line shows a `crash` mark for that session. `tezgah-gate check` exits 3, so
  the MCP `gate_check` no longer reads a dead gate as a pass.
- **The disarmed-gate mark no longer counts PostToolUse rows.** A PostToolUse
  hook keeps writing while a broken PreToolUse lets every call through. Only a
  row from the gate now proves it ran, over write and shell calls.
- **`--sync` no longer leaves a half-empty plugin copy.** It used to delete
  the copy, then copy into it. It now builds each copy in a staging tree beside
  the plugin cache and swaps it in, keeping the copy's `.git`. A sync stopped
  mid-swap is put back by the next one, `.git` included. A failed copy makes
  `--sync` exit 1. Every copied file is 0644, or 0755 when executable.
- **The omp report row compares the bridge byte for byte.** It checked six
  handler names, so a stale or edited bridge passed. It now compares the
  bridge with a fresh render.
- **A malformed `~/.config/tezgah/config.json` is no longer rewritten.**
  `--install` read it as empty and wrote its defaults over the user's roots.
  It now refuses the file, names it, leaves its bytes alone and exits 1.
- **The graph workflows report a failed agent as unknown.** `graph-review` said
  "all four dimensions came back clean" when every dimension failed. It listed
  a finding as refuted when both refuters failed. `graph-impact` dropped a
  failed planner and turned a failed sweep into "no blind spots". Each script
  now names every failure in an `unknown` list. A finding no refuter answered
  stays unverified. A stub runtime (`tests/_workflow_harness.mjs`) tests both.
- **`graph-impact` parses again.** It had one closing parenthesis too many, so
  Claude's runtime could not load it at all.
- **The status line marks graph use on a plugin install.** It tested only
  `mcp__codegraph__`. It now shares the PostToolUse store's test.
- **tezgah records a Claude skill load.** The plugin's PostToolUse matcher
  carries `Skill`, and so does dsh's manifest, which mirrors it. The hook writes
  `skill:<name>` (or the pony/adhd mark). The skill-fitness report then counts
  Claude sessions. Nobody has checked that Claude fires PostToolUse for the
  Skill tool.
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
