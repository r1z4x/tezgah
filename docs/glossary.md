# Glossary

The one place a tezgah term is defined. Read it when a word in the injected
contract or in another `docs/` page is ambiguous, or before you use one of these
words in a new rule, a page or a review comment. Every other page uses these terms
and links here; no page restates a definition. Entries are alphabetical; each
gives the sense this repository uses, the `path:line` where the concept lives, and
- where a term is confused with a neighbour - one line on what it is not. These
are definitions, not rules: the rule text belongs to [contract](contract.md),
[gate](gate.md) and [evidence](evidence.md).

### always-on
The part of the contract every session pays for - the invariants plus the one-line [pointer](#pointer) - built by `always_on_core()` (`hooks/tezgah_context.py:1053-1063`) out of [CORE](#core) with the [conditional rules](#conditional-rule) removed; it is not the whole contract, whose long tail is the `tezgah-contract` [skill](#skill) ([contract](contract.md)).

### budget
The byte ceiling one injected event may spend: `CONTEXT_BUDGET` per event with `DEFAULT_BUDGET` behind it (`hooks/tezgah_context.py:1079-1081`), enforced by `budgeted()` (`hooks/tezgah_context.py:1195-1231`), which gives up whole blocks lowest value first along `DROP_ORDER` (`hooks/tezgah_context.py:1156-1161`); bytes, never tokens, because the module has no tokenizer (`hooks/tezgah_context.py:1077-1078`). Not the [metadata band](#metadata-band), which is the installer's measurement of the same text rather than a runtime bound.

### capture
The pre-write copy the gate takes of every file a write is about to change, `capture()` (`hooks/tezgah_snapshot.py:192`), called on the gate's allow path (`hooks/tezgah_gate.py:1343-1362`) and capped at `CAP` snapshots and `MAX_BYTES` per file (`hooks/tezgah_snapshot.py:51-52`); a file too large or unreadable is left uncaptured and writes no row, so nothing claims a copy that is not there. Not a transaction: the copy is bytes on disk, not a rollback that runs itself.

### claim
A ledger [row](#row) recording the [Stop rule](#stop-rule)'s verdict on one reply, `detail` being `ok` or `blocked: <reason class>`, written by `stop_reason()` (`hooks/tezgah_integrity.py:2827-2875`, row at `:2466`). Not a deny: nothing ran, the turn simply may not end.

### conditional rule
A rule armed for one prompt only, when its task class matches - `spec`, `consult`, `research`, `product`, `graph` (`hooks/tezgah_policy.py:842`) - selected by `classify_prompt()` against the prompt hints (`hooks/tezgah_context.py:890-895`, `hooks/tezgah_context.py:82-294`) and injected only on the turn that matched (`hooks/tezgah_context.py:1278-1282`). Not an [always-on](#always-on) rule, though it sits in [CORE](#core) even while unarmed.

### contract
The whole working document, `CONTRACT` as the join of every block (`hooks/tezgah_policy.py:874-898`), shipped on demand as `skills/tezgah-contract/SKILL.md`, with the always-on [CORE](#core) as its summary and the [pointer](#pointer) line as the way in (`hooks/tezgah_policy.py:847-852`). Its clauses are [contract](contract.md)'s subject.

### CORE
The single string holding the whole always-on contract, one bold-labelled paragraph per [rule](#rule) (`hooks/tezgah_policy.py:622-838`), filtered against [per-repo marks](#per-repo-mark) and [kill switches](#kill-switch) by `core_split()` (`hooks/tezgah_context.py:987-1043`). Not [contract](#contract), the on-demand join of every block.

### deny
A refusal the gate returns and records: `_deny()` writes a `deny` row carrying the rule name and the first 80 characters of the reason (`hooks/tezgah_gate.py:1228-1243`). Not the reason text itself - the adapter renders the reason into its own envelope ([hosts](hosts.md)).

### digest
The identity of one tool call, `call_id()` = `sha1(tool.lower() + " " + canonical(args))[:12]` (`hooks/tezgah_integrity.py:474-498`); both the gate and the post-tool hook compute it here, so a [row](#row) and the call it belongs to agree. Not a session id.

<a id="ledger"></a>
### evidence ledger
One JSONL file per session recording what ran, `<cache>/evidence/<slug>.jsonl` (`hooks/tezgah_integrity.py:515`), appended by `note()` (`hooks/tezgah_integrity.py:724-736`) and read by `events()` (`hooks/tezgah_integrity.py:829-842`), with its contract in the module docstring (`hooks/tezgah_integrity.py:2-24`) and every reader failing open. Not the [session store](#session-store), which holds only used-tool marks.

### false completion
The count of [claim](#claim) rows a stop refused, `false_completion` in `counters()`, read against `claims` so the rate is meaningful (`hooks/tezgah_integrity.py:1068-1093`, `:1122-1127`). Not the count of [denies](#deny): a deny is the gate refusing a call, a false completion is the Stop rule refusing the end of a turn.

### gate
The pre-tool refusal layer, `decision()` (`hooks/tezgah_gate.py:1413-1607`), which runs only inside a [root](#root) (`:1126-1128`) and returns a reason or nothing ([gate](gate.md)). Not the [Stop rule](#stop-rule), which runs after the reply.

### group
The partition a status [mark](#mark) carries so a renderer separates the marks the same way: `_GROUP` maps each key to an index and `render_line()` joins groups with `  ·  ` (`hooks/tezgah_context.py:1730-1731`, `hooks/tezgah_context.py:1931-1941`). Not a [state](#state).

### harness
This project's own frame for the work, tezgah being the wrapper it puts around a coding agent - the injected contract, the [gate](#gate) and the [ledger](#evidence-ledger) - whose per-turn text still travels in the `<harness-reminder>` envelope (`hooks/tezgah_policy.py:853-873`). Two neighbours share the word: the agent runtime itself, which the current literature calls a complete agent harness (arXiv 2606.10106; `README.md:27-28` calls dsh one) and the multi-agent selection of the `harness` [skill](#skill), including the graph workflows the policy lists under "Graph harnesses" (`hooks/tezgah_policy.py:609-621`); [layers](layers.md) draws the three apart. Not the [host](#host): the host is the agent, the harness is what tezgah puts around it.

### harness skill
The [skill](#skill) that picks and runs a multi-agent harness for a task too wide for one context window - a code-graph workflow such as `graph-map` or a briefed subagent set (`skills/harness/SKILL.md:2-8`). Not tezgah's own wrapper around a [host](#host) ([harness](#harness), [layers](layers.md)).

### host
One coding agent tezgah is installed into - claude, codex, cursor, opencode, dsh, omp - with its config location in `HOST_DIRS` (`hooks/tezgah_paths.py:52`), its presence test in `host_installed()` (`hooks/tezgah_paths.py:69-79`) and its adapter under `hosts/<name>/` ([hosts](hosts.md)); also written "agent host", and the agent runtime the current literature calls the agent harness ([harness](#harness), [layers](layers.md)). Not a [root](#root): a host is a program, a root is a directory tezgah is armed over.

### kind
The label on an evidence [row](#row) saying what happened: `classify()` gives `edit` or `run`/`verify` (`hooks/tezgah_integrity.py:1392-1399`), `note_tool()` refines a check into `verify_ok`/`verify_fail` (`:1896-1898`), writes `interrupted` when the host said the call was stopped (`:1905`) and adds `external` (`:1925`) or `unknown` (`:1938`), and the machinery adds `deny`, `nudge`, `turn`, `claim`, `drift`, `snapshot`, `rollback`; `kinds()` returns the distinct set (`:725-727`).

### kill switch
A file whose presence removes exactly its own rule from the injected text and from the gate, not merely from the status line: `off()` checks the canonical config dir and the legacy `~/.claude` (`hooks/tezgah_paths.py:493-495`, `:46`), and the list is in [CORE](#core) (`hooks/tezgah_policy.py:825-832`). Not a [per-repo mark](#per-repo-mark): a switch is per machine, a mark per repo.

### legend
The prose explaining the status [marks](#mark) and their glyphs, `LEGEND` (`hooks/tezgah_context.py:1919-1944`), printed by `tezgah-status --legend` (`bin/tezgah-status:73-75`). Not the marks themselves.

### mark
One item of the armed/used checklist as a host shows it, a segment carrying `key`, `state`, `glyph`, `text` and `group` from `health_segments()` (`hooks/tezgah_context.py:1948-2016`, `hooks/tezgah_context.py:1817-1820`), for example `pony✓` or `consult○`. Not a [kind](#kind), which is a ledger row, and not the [state](#state), which is the value one mark carries.

### metadata band
One measured row of always-on context the installer reports in bytes: the core contract, the per-turn reminder, skill metadata, subagent metadata and the conditional rules (`context_budget()`, `bin/tezgah-setup:3133-3159`, rows at `bin/tezgah-setup:3150-3156`), with the MCP tool schemas as the one band it cannot count and measures by handshake instead (`mcp_schema_report()`, `bin/tezgah-setup:3196-3232`). Not the [budget](#budget): a band is a measurement, a budget a bound.

### mirror
`output-styles/tezgah.md`, a by-hand duplicate of `always_on_core()` kept for the host path that is hookless, which a test holds to the generator (`tests/test_context.py:1989-1999`). Not generated: an edit to [CORE](#core) must be carried into it by hand - a lesson the local `.tezgah/lessons.md` ledger holds; that file is untracked by design, so it carries no `path:line` here.

### nudge
The one-time hint that sends a first identifier-shaped search to the code graph, `first_nudge()` consuming a per-session mark before the grep is denied (`hooks/tezgah_gate.py:405-421`) with the text naming the graph tools (`nudge_reason()`, `hooks/tezgah_gate.py:427-447`). Not a deny: it is spent by being delivered, and the identical call passes on the retry.

### observable measure
A used-mark a surface is able to see at all, so it can say "armed, not used yet" without inventing it: `health_segments(observable=...)` (`hooks/tezgah_context.py:1817-1818`) with the five tool-use measures in `TOOL_USE_MEASURES` (`hooks/tezgah_context.py:1945-1947`), a measure outside the set rendering as `info` rather than `ready`. Which host can see a skill read is [hosts](hosts.md)'s.

### once-only
A mark consumed by its own first use, so the thing it protects happens once: the grep [nudge](#nudge) is written before the deny so later greps pass (`hooks/tezgah_gate.py:1316-1317`). Not a licence for the session: the identical call passes on the retry.

### per-repo mark
An opt-out file in the repo tree - `.no-ponytail`, `.no-adhd`, `.no-graph`, `.no-lessons` - collected by `repo_marks()` walking up to the enclosing root (`hooks/tezgah_context.py:1605-1621`). Not a [kill switch](#kill-switch): a mark travels with the repo, a switch with the machine.

### plan
A piece of work spanning sessions, one markdown file with frontmatter under `<repo root>/.tezgah/plans/open/`, moved to `.tezgah/plans/done/` when closed, up to three of them injected by `open_plans()` (`hooks/tezgah_context.py:594-612`) and its work happening on a `plan/NNN-slug` branch. Not a TODO in code.

### plan table
The status table in `.tezgah/plans/README.md` (`.tezgah/plans/README.md:3`), owned by the `plan-status` skill (`skills/plan-status/SKILL.md:1`) and among the first blocks the [budget](#budget) gives up because it lives on disk (`hooks/tezgah_context.py:1082-1085`). Not the injected list of open plans.

### plugin copy
Claude's own copy of this checkout under `~/.claude/plugins/cache`, from which its hooks and skills actually run, found by `plugin_copies()` (`bin/tezgah-setup:3815-3829`) and refreshed by `sync()` against the fingerprint file (`bin/tezgah-setup:3957-4016`, `bin/tezgah-setup:3709`). Not the checkout: a stale copy lags HEAD until `tezgah-setup --sync`.

### pointer
The one-line always-on stand-in for the [conditional rules](#conditional-rule), naming each so a host without a per-turn hook still knows the rule exists, `POINTERS` (`hooks/tezgah_policy.py:847-852`). Not a rule.

### probe
A small side effect tezgah makes when an answer cannot be read directly: a write probe to decide whether a directory is usable (`hooks/tezgah_paths.py:88`, `:100-104`), and the cached git fork that decides whether the graph stamp is behind HEAD (`hooks/tezgah_context.py:1618-1635`). Not a check of the work.

### reminder
The compact per-turn text every user turn pays for, `PROMPT_REMINDER` (`hooks/tezgah_policy.py:853-873`), injected as the `reminder` block (`hooks/tezgah_context.py:1275`) and carrying the standing constraints rather than the long rationale. Not [CORE](#core), which is paid once per session.

### rollback
Putting a [snapshot](#snapshot)'s bytes back, `restore()` (`hooks/tezgah_snapshot.py:218`), reached only through `tezgah-rollback` (`bin/tezgah-rollback:2-13`), which writes a `rollback` row (`hooks/tezgah_snapshot.py:263-265`). Tezgah never rolls back on its own.

### root
A directory tezgah is armed over, from `TEZGAH_ROOTS`, the config file or `~/Projects` (`hooks/tezgah_paths.py:8-14`), resolved by `roots()` longest first (`:167-182`) and looked up per path by `root_for()` (`hooks/tezgah_paths.py:183-204`); a linked `git worktree` outside every root is inside when its main checkout is, and answers its own top level (`worktree_top`, `hooks/tezgah_paths.py:233-248`). Not a repository: one root may contain many repositories.

### root boundary
The edge of a root: outside every root the gate returns nothing (`hooks/tezgah_gate.py:1245-1246`), the context builder returns nothing (`hooks/tezgah_context.py:1244-1245`) and the per-repo extras are omitted from the status line (`hooks/tezgah_context.py:1828-1829`). Not a repository boundary.

### row
One line of an [evidence ledger](#evidence-ledger): `{"kind","ts","detail"}` plus whatever the writer knew of `LEDGER_FIELDS` (`id`, `exit`, `out_bytes`, `fail_class`, `workspace`, `source`, `hash`, `changed`, `tool`), written by `note_path()` (`hooks/tezgah_integrity.py:699-723`, `:537`) with `detail` redacted and cut to `DETAIL_MAX` (`hooks/tezgah_integrity.py:587-593`). A missing key means the writer did not know it, never null. `tool` is the call's own name where the host reports one, which is what makes a firing histogram possible: `classify` folds the name into `run`/`edit`, so a row that predates the field carries none.

### rule
One bold-labelled paragraph of the contract, the unit a [kill switch](#kill-switch) drops and a test pins: `CORE_RULES` pairs each key with the label it must start with (`hooks/tezgah_context.py:304-323`) and `core_split()` drops exactly the paragraph whose label matches (`:927-983`). Not a [skill](#skill), which the model chooses to read.

### session
One host conversation, identified by the id `session_of()` reads from a payload under whichever name the host uses (`hooks/tezgah_context.py:1056-1058`), keying the [ledger](#evidence-ledger) filename (`hooks/tezgah_integrity.py:514-524`), the [session store](#session-store) and the per-turn markers (`note_turn()`, `hooks/tezgah_integrity.py:1027-1050`). Not a [turn](#turn), of which one session has many.

### session store
The used-tool marks one session wrote, `<cache>/sessions/<slug>.jsonl`, appended by `record()` (`hooks/tezgah_context.py:1564-1587`) and read by `used()` (`hooks/tezgah_context.py:1646-1666`) to feed the "used" half of the status marks, with a missing kind recorded nowhere at all. Not the [evidence ledger](#evidence-ledger).

### skill
`skills/<name>/SKILL.md` - frontmatter with `name` and `description`, then instructions the model reads by choice; [skills](skills.md) owns the layer. Not a [rule](#rule), which is injected, and not a [slash command](#slash-command).

### skill read
A read of a tezgah skill's own `SKILL.md` earning a used mark, `skill_read_kind()` matching on the path (`hooks/tezgah_context.py:359-382`), which is the only signal that the full rule text reached the session, and only `ponytail` and `i-have-adhd` carry a mark (`SKILL_MARKS`, `hooks/tezgah_context.py:362-366`). Not a general read.

### skill router
The generated list that stands in for a skill index where a host has none, `~/.config/tezgah/opencode-skills.md` always-on and `.full.md` on demand (`bin/tezgah-setup:106-109`), built by `skill_router_texts()` from `skill_groups()` (`bin/tezgah-setup:1264-1313`, `bin/tezgah-setup:1150-1172`). Not a directory listing: each line is name, trigger and path ([skills](skills.md)).

### slash command
A file under `commands/` wired only through the Claude plugin channel and named with the plugin's prefix (`/tezgah:plan-sync`), installed by no other host ([skills](skills.md)). Not a [skill](#skill), though one feature may be both.

### snapshot
The stored pre-write bytes of one file plus its manifest, created by [capture](#capture) and read only by [rollback](#rollback) (`hooks/tezgah_snapshot.py:2-17`), the capture also writing a `snapshot` row whose `detail` is the file's realpath and whose `hash` is its pre-write sha256 (`:184`). Not a checkpoint of the session, only of the files a write was about to change.

### source
The ledger field naming the untrusted channel a result came through - `web`, `mcp`, `network` or `tier` - set only when there was one (`hooks/tezgah_integrity.py:1447-1449`, `untrusted_source` `hooks/tezgah_integrity.py:1957-1980`), a missing `source` meaning the user or this workspace, which is what every reader assumes. Not a record of what the content said.

### state
The value of one status [mark](#mark): `on`, `ready`, `off` or `info` (`hooks/tezgah_context.py:1818`), drawn as `✓ ○ ✗` or nothing by `GLYPHS` (`hooks/tezgah_context.py:1867-1869`) and mapped to a colour by `COLORS` (`hooks/tezgah_context.py:1870-1870`), with `off` winning over the observable test because a kill switch is visible everywhere ([status-line](status-line.md)). Not a glyph, which is only how the state is drawn.

### step kind
One of the row kinds that count as a step of work - `run`, `edit`, `verify`, `verify_ok`, `verify_fail`, `interrupted` (`STEP_KINDS`, `hooks/tezgah_integrity.py:1097-1102`), summed into `steps` and into the drift threshold, while `deny`, `nudge`, `claim` and `turn` are the machinery around the work (`:1014-1015`). `interrupted` is the one that is not a failure: the host said the call was stopped, so the row carries no `exit` and no `fail_class`, no reader folds it as a failed check and no attempt is spent on it (`:882-886`). Not any row.

### Stop rule
The end-of-turn refusal, `stop_reason()` (`hooks/tezgah_integrity.py:2827-2875`), run by the Stop hooks of Claude, Codex, Cursor and omp (`hooks/projects-stop.py:33`, `hosts/codex/hook.py:186`, `hosts/cursor/hook.py:352`, `hosts/omp/hook.py:190`): it blocks on a placating opener or a banned sign-off on the last prose line, on a completion claim the newest check does not support, on a check that passed before the newest write the gate saw change the tree, or on a turn that recorded work with no passing check (`_stop_block()`, `hooks/tezgah_integrity.py:2889-3110`), and an explicit "doğrulanmadı" clears it. Not the [gate](#gate), which runs before a call ([evidence](evidence.md)).

### surface
A place a host can show tezgah's output - a status line, a TUI widget, a `systemMessage` - and therefore the reason the same [marks](#mark) render differently per host (`hooks/tezgah_context.py:1822-1831`, `hooks/tezgah_context.py:1931-1941`); each host's surfaces are [hosts](hosts.md)'s. Not the host itself.

### taint
The state of a turn that has read content tezgah cannot vouch for and not yet marked an effect, `turn_channel()` (`hooks/tezgah_untrusted.py:47`) plus the line the model reads on the next effect, `taint_notice()` (`:69`). A state, not a verdict: whether the content caused the write is not observable.

### turn
One user prompt and everything before the next one, delimited on the ledger by a `turn` marker row written by `note_turn()` (`hooks/tezgah_integrity.py:1027-1050`) and found by `_turn_start()` (`hooks/tezgah_integrity.py:904-916`), with the loop guard's count, the drift threshold and the [taint](#taint) all turn-scoped. Not a request/response pair.

### untrusted content
A result that arrived from outside the user and this workspace - a fetched page, an MCP server's answer, a shell read that left the machine, or the tier's own answer (`bin/consult`, `bin/codegen`: a model over the network, however deliberately the session asked for it) - named by `untrusted_source()` and labelled by `untrusted_label()` (`hooks/tezgah_integrity.py:1981-1995`, `hooks/tezgah_integrity.py:1957-1980`), the label and the [taint](#taint) notice being `hooks/tezgah_untrusted.py:2-22`. Not a deny: the model may use the text, but instructions inside it are data, never a request.

### used kind
The tool kind a session was observed to use, one word per call, recorded by `record()` (`hooks/tezgah_context.py:1564-1587`) and read by `used()` (`hooks/tezgah_context.py:1646-1666`) to turn an armed mark into a used one, with `shell_kind()` and `skill_read_kind()` as the classifiers. Not a [step kind](#step-kind): this is the status line's vocabulary, not the ledger's.

### vendored
Copied into this repository from an upstream project and kept, with its licence, rather than depended on: `skills/ai-research` is the large case (`ai_research_dir()`, `hooks/tezgah_paths.py:159-166`), and a vendored file carries a `<!-- vendored from ... -->` header checked against a manifest (`tests/test_ai_research_library.py:72`, `:145`). Not a git submodule.

### verify
The [kind](#kind) family for a check: `verify` when it ran but no outcome was seen, `verify_ok` when the host reported exit 0 with output on an unmasked command, `verify_fail` when it failed (`note_tool()`, `hooks/tezgah_integrity.py:2151-2264`, `:1804-1809`, with `passing_check()` as the acceptance test, `:1879-1893`). Only `verify_ok` supports a "done" claim; it is not the check's own result, since the ledger records what the host reported. An `interrupted` row sits outside the family: the host said the call was stopped rather than answering it, so there is no outcome to be one of the three (`:1824-1828`).

### version prefix
The product's own name and version at the head of the [status line](status-line.md), `tezgah v0.12.1`: one segment from `version_segment()` (`hooks/tezgah_context.py:2160-2175`) carrying no glyph and the [state](#state) `info` - nothing is armed or used by it - and a group of its own, so the marks separate from it the way the groups separate from one another. Its number comes from `version()` (`hooks/tezgah_context.py:2130-2159`), the one reader `bin/tezgah-setup --version` also calls: the local plugin manifest, else the newest release heading in `CHANGELOG.md`, read bounded and never raising, and an unreadable version leaves the bare name rather than a placeholder. Not a [mark](#mark): a mark reports a switch or a capability, this reports which build is talking.

### workspace
The ledger field naming which [root](#root) a row happened under, `root_for(cwd)` (`hooks/tezgah_integrity.py:1733`), recorded so a refusal can say where it was stopped. Not the cwd the call ran in, and not the repository.

## Source of truth
- `hooks/tezgah_context.py` - the injected text, the status segments, used marks, budget, per-repo marks
- `bin/tezgah-status`, `bin/tezgah-rollback` - the CLI side of the status marks and rollback
- `hooks/tezgah_gate.py` - `decision()` and every refusal rule
- `hooks/tezgah_integrity.py` - the ledger contract, kinds, claims, the Stop rule
- `hooks/tezgah_paths.py` - roots, kill switches, hosts, the cache dir, probes
- `hooks/tezgah_snapshot.py` - capture, snapshots, rollback
- `hooks/tezgah_untrusted.py` - the untrusted label and the taint notice
- `bin/tezgah-setup` - the bands, the plugin copy, the skill router
