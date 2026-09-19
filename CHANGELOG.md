# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

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
  module needed too (`note_tool` `:1068`, `stop_reason` `:1300`, the `external`
  and `unknown` rows `:1114`/`:1125`, the `source` field `:1130`, the `worked`
  set `:1386`). A bare-citation pass is still missing from the audit; the
  remainder is `plans/open/002-docs-citation-drift.md`'s.

### Changed

- **the docs layer's `path:line` citations were audited against HEAD, and 414 of
  them corrected.** The code moved under the pages and most citations pointed at
  the wrong line - the gate page worst, at 130. Ten page-by-page audits are
  recorded under `.tezgah/research/jev-classifier/` (local, gitignored);
  `tests/test_docs.py` now checks the half a script can (the cited file exists and
  the line is inside it); and the 61 citations the mechanical pass could not
  verify are tracked in `plans/open/002-docs-citation-drift.md`.
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
