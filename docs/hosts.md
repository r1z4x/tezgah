# Hosts

tezgah is one Python core with six host adapters around it: `claude`, `codex`,
`cursor`, `opencode`, `dsh`, `omp`. This page is for the maintainer wiring a new
host, adding a mark, or debugging a status line that claims something a host
cannot see. Read it when a question starts with "does this host get X?" or "can
this host observe Y?" - the answer is not uniform, and guessing it produces a
line that lies. What a rule *does* is [gate.md](gate.md) and
[evidence.md](evidence.md); how the text is composed is
[contract.md](contract.md); the marks are [status-line.md](status-line.md).

## Capability matrix

One row per host. "Measures" is the set of [marks](glossary.md#mark) the host's
surface can honestly report this session; the two skill-read marks (`pony`,
`adhd`) are the ones most hosts cannot.

| Host | Hook events it fires | Always-on contract | Per-turn reminder | Status surface, how drawn | Measures |
|---|---|---|---|---|---|
| claude | SessionStart, SubagentStart, PostCompact, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, Stop, SubagentStop (record-only, `subagent_end`) - `hooks/hooks.json:2-30` | the managed block in `~/.claude/CLAUDE.md` (`CLAUDE_RULES`), Claude's global memory file; the SessionStart/PostCompact hook rows declare `TEZGAH_CORE_IN_FILE` (`hooks/hooks.json:4`) and the hook drops the core when the block is there, so the contract is paid for once (`hooks/projects-auto-init.py:1-6`; the static `output-styles/tezgah.md` mirror (`output-styles/tezgah.md:1`) is the hookless build's copy) | UserPromptSubmit -> `additionalContext` (`hooks/hooks.json:12-14`, `hooks/projects-auto-init.py::main`) | `statusLine` command in `~/.claude/settings.json` (`bin/tezgah-setup:529-581`), ANSI, forwards Orca first (`statusline.py:30-48`) | all seven: the transcript parse covers the two skill reads, `graph`, `orch` and the three shell kinds - `consult`, `research` and the judgement callers (`statusline.py::claude_used`, `observable=None` at `statusline.py::observable`) |
| codex | SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart, PostCompact, Stop (`bin/tezgah-setup:131-133`; named in `hosts/codex/hook.py:6-7`) | hook: the normalized events inject `context_for` (`hosts/codex/hook.py::main`) | UserPromptSubmit -> `additionalContext` (`hosts/codex/hook.py::main`) | no custom footer item (`tui.status_line` is a closed enum) - the line rides `systemMessage`, plain, at SessionStart and Stop (`hosts/codex/hook.py:10-12,186-189,200-203`) | five tool-use (`TOOL_USE_MEASURES` at `hosts/codex/hook.py:195,201`) |
| cursor | 13 events: sessionStart, preToolUse, postToolUse, postToolUseFailure, subagentStart, subagentStop, beforeSubmitPrompt, stop, beforeMCPExecution, afterShellExecution, afterMCPExecution, afterFileEdit, afterAgentResponse (`bin/tezgah-setup:134-185`) | hook: sessionStart -> `additional_context` (`hosts/cursor/hook.py::dispatch`) | beforeSubmitPrompt -> `additional_context` plus `{"continue": true}` (`hosts/cursor/hook.py::dispatch`) | `statusLine` in `~/.cursor/cli-config.json` -> `tezgah-statusline --cursor` (`bin/tezgah-setup::install_cursor`), ANSI (`statusline.py:116-117`) | five tool-use (`statusline.py::observable`) |
| opencode | no lifecycle events; plugin hooks: config, permission.ask, tool.execute.before, shell.env, experimental.session.compacting, chat.message, tool.execute.after (`hosts/opencode/plugins/tezgah.js:2051-2381`) - `tool.execute.before` carries the whole gate, `tool.execute.after` the channel on the row, the provenance label on the result and the taint notice on the next effect (`untrustedSource` `hosts/opencode/plugins/tezgah.js:1658`, `labelResult` `:1710`) | static only: generated `instructions` files, because there is no session-start injection point (`hosts/opencode/plugins/tezgah.js:3-6`, `bin/tezgah-setup:975-1008`) | chat.message pushes a synthetic part (`hosts/opencode/plugins/tezgah.js:2315-2360`) | TUI plugin `tezgah-tui.tsx` declared in `tui.json`, runs `tezgah-status` on the event bus (`hosts/opencode/tui/tezgah-tui.tsx:1-11`; wiring `bin/tezgah-setup::install_opencode`) | all seven: skill reads and kinds are classified in process (`hosts/opencode/plugins/tezgah.js:1900-1945`) |
| dsh | SessionStart, SubagentStart, UserPromptSubmit, PreToolUse, PostToolUse (`hosts/dsh/hooks.json:2-19`); no Stop rule, because the bridge drops every call's outcome and no check there can show a pass | hook: the same Claude-family scripts, named by `configPath` (`bin/tezgah-setup::dsh_patch_block`) | UserPromptSubmit, through the bridge (`hosts/dsh/hooks.json:9-11`) | web-profile plugin: authenticated `GET /api/tezgah.status` -> `tezgah-status` (`hosts/dsh/statusline/lib/index.js:14,39-60`) | five tool-use: the route passes `--observable=consult,research,graph,orch,judge` (`hosts/dsh/statusline/lib/index.js:18,47-48`) |
| omp | session_start, session_compact, session_switch, turn_end, before_agent_start, tool_call, tool_result, session_stop (`hosts/omp/tezgah-hook.ts.in:177,198-199,201,221,235,267`) | both: static `RULES.md` (`bin/tezgah-setup:1370-1373`) and a session payload carrying only what a static file cannot know (`hosts/omp/hook.py::handle`) | before_agent_start returns a hidden message (`hosts/omp/tezgah-hook.ts.in:236-253`) | extension draws `ctx.ui.setWidget` below the editor, `setStatus` as fallback (`hosts/omp/tezgah-hook.ts.in:20-27`); ANSI line from `hosts/omp/hook.py::status_line` | all seven: the embedded runner filters skill reads before asking python (`hosts/omp/tezgah-hook.ts.in:40-53`) and no `observable` is passed (`hosts/omp/hook.py::status_line`) |

The middle five marks (`consult`, `research`, `graph`, `orch`, `judge`) are tool-use marks:
any adapter that sees its host's tool calls can light them by calling
`record()` (`hooks/tezgah_context.py::record`). CLI-side, `tezgah-status` reads
the same core and takes the session id as an argument or `TEZGAH_SESSION`
(`bin/tezgah-status::main`).

## Enforcement capability

What each host can enforce, in the
[enforcement capability](glossary.md#enforcement-capability) words. `gate`: the
hook can refuse. `observe`: it records and never refuses. `partial`: only part
of the surface fires. `unavailable`: the host has no event for it. A cell gets
`unverified` when no driver on this machine can probe it. Fixture payloads test
the code path there, but no run has shown the host obeying it.

| Host | Gate (PreToolUse) | Stop | Subagent |
|---|---|---|---|
| claude | gate, probed by `--report --live` (`bin/tezgah-setup::live_probe`) | gate, unverified (`hooks/projects-stop.py::main`) | observe, unverified: a brief at SubagentStart, a record-only `subagent_end` row at SubagentStop (ADR 011) |
| codex | gate, probed by `--report --live`; Codex runs only a trusted group | gate, unverified (`hosts/codex/hook.py::main`) | partial, unverified: a brief at SubagentStart, no subagent-end event |
| cursor | gate, probed by `--report --live` | gate, unverified (`hosts/cursor/hook.py::dispatch`) | observe, unverified: a brief at subagentStart, a record-only `subagent_end` row at subagentStop |
| opencode | gate, probed by `--report --live` through a node driver | unavailable: the plugin API has no end-of-turn event | unavailable |
| dsh | gate, probed by `--report --live` through the bridge | unavailable: ADR 003 removed the Stop entry, because the bridge carries no outcome | partial, unverified: a brief at SubagentStart, no SubagentStop entry |
| omp | gate, probed by `--report --live` (node 22.6+) | gate, unverified (`hosts/omp/hook.py::handle`) | partial, unverified: a brief at a task session's start; `session_stop` does not fire for task sessions |

Every host also attests its own hook entries once per session
(`hooks/tezgah_attest.py::run`). Claude, dsh, Codex, Cursor and omp do it at
session start. opencode does it at the first message, through `oncePerSession`.
The `attest` row and the `drift` mark are
[evidence](evidence.md#the-kinds-by-what-reads-them), never a block.
`--report` prints the same comparison per host
(`bin/tezgah-setup::attestation_rows`).

## What each host gets, and where it is written

Every host gets the skill symlinks from `SKILLS` (`bin/tezgah-setup::SKILLS`)
except claude, whose skills arrive with the plugin. `install_common` writes the
shared config, contract hash and the CLI symlinks every host shell can call
(`bin/tezgah-setup:440-489`).

- **claude** - `install_claude` (`bin/tezgah-setup::install_claude`): `~/.claude/statusline.py`,
  no `~/.claude/workflows` links (the plugin's own `workflows/` serves the graph
  workflows, and install removes tezgah's old links there and any dangling
  `cbm-*.js` one, `sweep_claude_workflows`), the
  `~/.claude/bin/{consult,codegen,tezgah-render-table}` links, two keys in
  `~/.claude/settings.json` - `statusLine` (`bin/tezgah-setup:529-581`) and the attribution
  off-switch (`bin/tezgah-setup:508-528`) - and the always-on block in
  `~/.claude/CLAUDE.md` (`CLAUDE_RULES`), Claude's own user-level memory file.
  Its hook manifest is the plugin's own
  `hooks/hooks.json`; no `hooks.json` is written into `~/.claude`. Claude runs a
  **copy** of the checkout under `~/.claude/plugins/cache`, refreshed by
  `--sync` (`bin/tezgah-setup::sync`). The install makes that copy through
  Claude's own CLI (`register_claude_plugin()`). It renders the untracked
  `.claude-plugin/{plugin,marketplace}.json` pair into the tree it runs from.
  It adds that tree as a directory marketplace and installs
  `tezgah@tezgah-local`. An existing `tezgah@*` row stops both calls. With no
  `claude` CLI, Claude stays unarmed and the run says so.
- **codex** - `install_codex` (`bin/tezgah-setup::install_codex`): `$CODEX_HOME/hooks.json`
  (one group per event, PreToolUse carrying `CODEX_PRETOOL_MATCHER` at `:131-133`),
  `skills/*` symlinks, `~/.codex/bin/consult`, and `mcp_servers.*` tables in
  `config.toml` (`ensure_toml_mcp`, `bin/tezgah-setup::ensure_toml_mcp`).
- **cursor** - `install_cursor` (`bin/tezgah-setup::install_cursor`): `~/.cursor/hooks.json`
  (tezgah entries replaced, a user's Orca entries merged), `skills/*` symlinks,
  `mcp.json` servers, and `cli-config.json` `statusLine`.
- **opencode** - `install_opencode` (`bin/tezgah-setup::install_opencode`): the plugin under
  both `plugins/` and `plugin/` (version drift), `skills/*` symlinks, the
  generated `~/.config/tezgah/opencode-contract.md` (`bin/tezgah-setup:817-853`) and
  `opencode-skills.md` + `.full.md` (`bin/tezgah-setup:1242-1309`), then `opencode.json`
  (`instructions`, `mcp`, `permission.skill=deny`, `compaction.prune`,
  `watcher.ignore`, the two `external_directory` grants) and `tui.json` +
  `tui-plugins/tezgah-tui.tsx`.
- **dsh** - `install_dsh` (`bin/tezgah-setup::install_dsh`): `~/.dsh/skills/*` symlinks,
  a managed block in `~/.dsh/cordis.patch.yml` (`dsh_patch_block`, `bin/tezgah-setup::dsh_patch_block`) that
  mounts the Claude-code hook bridge on `hosts/dsh/hooks.json`, the MCP client
  rows and the three `llm-pi-ai` routes, plus `~/.local/bin/dsh` ->
  `bin/tezgah-dsh`. `install_dsh_statusline` (`bin/tezgah-setup::install_dsh_statusline`) links the statusline
  package into the **web profile** and adds its row to
  `~/.dsh/profiles/web/cordis.patch.yml`.
- **omp** - `install_omp` (`bin/tezgah-setup::install_omp`): `~/.omp/agent/RULES.md`
  (managed block), `skills/*` symlinks, `agents/tezgah-*.md`, `mcp.json`
  (`$schema`, `mcpServers`), and `hooks/pre/tezgah-hook.ts` rendered from
  `hosts/omp/tezgah-hook.ts.in` with the python path substituted for `@HOOK@`.
  That path is then named in omp's `extensions:` setting through `omp config`
  (`register_omp_hook`, `bin/tezgah-setup::register_omp_hook`): omp 18.2.11 loaded
  nothing from `hooks/pre/` by discovery, the same file named there drew the
  status line, and omp dedupes a path that is both discovered and configured
  (`OMP_EXTENSIONS`, `bin/tezgah-setup::OMP_EXTENSIONS`). omp has no orx target of
  its own: orx's `codex` target writes the shim to `~/.agents/skills/orx`,
  omp's native `agents` skill root, so `install_openresearch` maps omp onto it
  (`ORX_AGENTS`, `bin/tezgah-setup::ORX_AGENTS`).

An adapter is responsible for its host's **envelope** and its **surface**: it
translates the host's event and tool names into the shared vocabulary (one call
has to hash to one id - `hosts/codex/hook.py:89-98`, `hosts/cursor/hook.py:72-79`),
draws the line, and returns the host's own output shape. The contract text, the
gate decision, the evidence ledger, the untrusted-content marks and the segment
builder stay in the shared core under `hooks/` (`hosts/omp/hook.py:1-12`,
`hosts/cursor/hook.py:1-41`).

## Where the always-on core reaches each host

One rule for every host: the core ships **globally**, never as an edit to a
tracked project file, and every host has exactly one delivery path so a session
pays for it once.

| host | how the core arrives |
|---|---|
| claude | the managed block in `~/.claude/CLAUDE.md` (`CLAUDE_RULES`), Claude's global memory file, which Claude reads into every session; its `SessionStart`/`PostCompact` hook rows declare `TEZGAH_CORE_IN_FILE` and the hook drops the core, so the contract is paid for once |
| codex | the managed block in the global instructions file (`codex_rules`, `CODEX_RULES` = `AGENTS.override.md` then `AGENTS.md`); its `SessionStart` hook runs with `with_core=False` because a hook context is one message where this file is the instructions Codex keeps |
| cursor | `~/.cursor/hooks.json` fires `sessionStart` -> `context_for` (`hosts/cursor/hook.py::dispatch`) |
| opencode | no stdout-inject hook: `install_opencode` writes the generated `~/.config/tezgah/opencode-contract.md` and references it from `opencode.json` `instructions` |
| omp | the managed block in `~/.omp/agent/RULES.md` |
| dsh | the session's own hook context: `hosts/dsh/hooks.json` runs the Claude-family scripts through the bridge, and no dsh file carries the core, so dsh's `SessionStart` row declares nothing and still gets it here (`~/.dsh/cordis.patch.yml` mounts that bridge) |

An installed host whose core line is missing is a health check's business
(`host_checks_<host>`), not a second copy: two delivery paths for one host is the
same rules paid twice per session.

## The model wire

The matrix above is about events. This is about the other side of a host: which
model API it speaks. tezgah's own half of that is already written down, because
the router has to name a model per host where that host can express it
(`hooks/tezgah_models.py:10-16`); the host's half never was, and it is the half a
reader needs to explain a score, since the same model moved 13 points across
three harness configurations while swapping the model inside one harness moved it
2.5-5. [layers](layers.md#three-senses-of-one-word) draws the three senses of
"harness" apart for the same reason.

| Host | tezgah names its model by | the model wire it speaks | checked against |
|---|---|---|---|
| claude | frontmatter `model:` + `effort:` (`hooks/tezgah_models.py:10`) | the Anthropic API; a managed gateway is reached through `ANTHROPIC_BASE_URL` and `allowedProviders` (Claude Code's gateway and settings docs) | vendor documentation |
| codex | `model` + `model_reasoning_effort` (`hooks/tezgah_models.py:11`) | OpenAI's Responses API by default and selectable per provider: a `model_providers` entry sets `wire_api = "responses"`, and `openai_base_url` moves the built-in provider's base URL (Codex's own configuration reference, checked 2026-10-01) | vendor documentation |
| cursor | frontmatter `model:` + `effort:` (`hooks/tezgah_models.py:10`) | `unverified`: the CLI's public documentation names no wire (checked 2026-10-01) | - |
| opencode | a selector read from `opencode models` (`hooks/tezgah_models.py:12`) | the AI SDK: `@ai-sdk/openai-compatible` for `/v1/chat/completions`, `@ai-sdk/openai` for `/v1/responses`, beside its own Anthropic and Bedrock providers (opencode's provider docs) | vendor documentation |
| omp | the session default's family, otherwise `task.agentModelOverrides` and `modelRoles.plan` (`hooks/tezgah_models.py:13-16`) | whichever provider the selected model names - Anthropic Messages, OpenAI Responses, OpenAI chat completions, Google, Bedrock - with text-based dialects where a native tool API is unavailable; the OpenRouter route dispatches to Responses unless `PI_OPENROUTER_RESPONSES=0` (omp's own `provider-compat-reference` documentation) | the tool's own documentation |
| dsh | the Claude-family scripts through the bridge (`hosts/dsh/hooks.json:2-18`); `README.md:27-28` calls it "DeepSeek's dsh harness" | `unverified`: its own `--help` describes it as "an ordered stack of plugin-bundle patch layers" and names no model API, and its profile directory names a provider (DeepSeek) rather than a wire (checked 2026-10-01) | - |

`unverified` is the point of the column rather than a gap in it. A wrong dialect
here is worse than a blank one: a reader would use it to explain a score, and the
explanation would be invented. Fill a row only from that host's own documentation,
and say which document it came from.

## The observability rule

A skill read is observable only where the host gives a channel that does not cost
a process per read: Claude parses its transcript (`statusline.py::claude_used`),
opencode classifies in process (`hosts/opencode/plugins/tezgah.js:1900-1945`),
omp filters in its embedded runner before it asks python
(`hosts/omp/tezgah-hook.ts.in:40-53`). On codex, cursor and dsh a read is not
observable at that price, so their surfaces pass the five tool-use measures as
`observable` and the two skill marks render dim (`info`, no glyph) instead of
claiming the skill was never opened (`hooks/tezgah_context.py::TOOL_USE_MEASURES`, and the
`observable` branch at `hooks/tezgah_context.py::health_segments`). Callers that pass `TOOL_USE_MEASURES`:
`statusline.py::observable`, `hosts/codex/hook.py::main,201`,
`hosts/dsh/statusline/lib/index.js:18`. A kill switch is observable everywhere
and still renders `off` (`hooks/tezgah_context.py::health_segments`).

## Adding a host

In order, each step verified by the one below it:

1. `HOST_DIRS` and, when the CLI can exist without a config dir, `HOST_BINS` in
   `hooks/tezgah_paths.py:71-87`. These are shared by the installer, the report
   and agent generation, so "is this host installed?" has one answer
   (`hooks/tezgah_paths.py:44-67`). Add the name to `ALL_HOSTS` in the report
   order (`bin/tezgah-setup:102`).
2. The hook adapter(s) under `hosts/<host>/` (an `install_*`-independent
   directory like `hosts/codex/hook.py`, `hosts/cursor/hook.py`) plus, for a
   TS/JS host, the bridge file with a substituted python path
   (`hosts/omp/tezgah-hook.ts.in` rendered at `hooks/tezgah_attest.py::omp_bridge`).
3. `install_<host>()` writing that host's files, registered in `INSTALLERS`
   (`bin/tezgah-setup::INSTALLERS`), and `uninstall_<host>()` removing only
   tezgah-managed links and blocks (`bin/tezgah-setup:2623-2774`).
4. `host_checks_<host>()` returning `(label, bool)` rows over what was actually
   written, registered in `HOST_CHECKS` (`bin/tezgah-setup::HOST_CHECKS`); the
   `--report` output is that list (`bin/tezgah-setup:3109-3187`). Give the row a home-qualified
   label if the host's dir can be relocated (`host_checks_codex`, `bin/tezgah-setup::host_checks_codex`).
5. Decide the surface: a `statusLine` command, a TUI/widget plugin, or the
   `systemMessage` fallback (`hosts/codex/hook.py:10-12`). Pass `observable` if
   the host cannot see a skill read, and `idx_override` on any redraw that must
   not fork git for a cosmetic glyph (`hooks/tezgah_context.py::health_segments`).
6. Tests, in two tiers: a per-host class in `tests/test_setup.py` pinning the
   report rows and the written files (e.g. `OmpHost:960-1030`,
   `CodexHome:657-702`, `CursorMatcher:705-722`, `DshStatusline:872-957`), and an
   opt-in script under `tests/e2e_*.py` for the thing only a real host can prove
   - not collected by `unittest discover`, it exits 0 with `SKIP` when the host
   is absent (`tests/e2e_omp_statusline.py:13-16`).

## Host-specific limits worth knowing

- **A disarmed gate is shown where the prompt hook can see it** (`gate_inactive`, audit
  Phase 1.3). Detection needs the host to hand its prompt hook a `transcript_path` and to
  run that hook while the tool hooks do not; it costs the last 256 KiB of the transcript and
  one byte scan of the session ledger per prompt.
  - **claude:** observed; the line rides the prompt context and `gate✗` shows on the status line.
  - **codex:** observed (rollout JSONL, `function_call` items); Codex has no status line, so
    `gate✗` appears only in the SessionStart/Stop status message.
  - **cursor, dsh:** observed only if their prompt payload carries `transcript_path`
    (unverified on a live host).
  - **omp, opencode:** not applicable: the prompt hook and the gate live in one extension or
    plugin process, so one cannot run without the other.
  - Everywhere: a disarmed PreToolUse beside a working PostToolUse writes rows and is not
    detected here. `tezgah-setup --report --live` sends each host one PreToolUse it must
    deny. A host whose gate does not answer reads MISS there.
- **Lessons and open plans are injected only when `.tezgah` came from tezgah.**
  `.tezgah/` is the user's private workspace, ignored by the project. When the
  project's own git index holds `.tezgah` or any path under it (as a file, a
  symlink or a submodule), when `.tezgah`, `lessons.md`, `plans` or
  `plans/open` is a symlink, or when the index cannot be read, the block is
  replaced by a one-line "repository-provided data" notice - the per-turn
  relevant-lessons block too, once per session
  (`workspace_from_repo`, audit L-16). Ceiling: a tree with no `.git` (an
  unpacked archive) carries no record of where `.tezgah` came from, so its
  lessons are injected; do not unpack untrusted archives under a configured root.
- **After a compaction, the live state comes back on four hosts, not six.**
  The block after a compaction is the same `post_compact` build everywhere:
  resume, plans, lessons and the graph line, without a core the static file
  already holds.
  - **claude, codex**: the host fires SessionStart again (`SessionStart:compact`,
    `source: "compact"`) and the block rides its `additionalContext`;
    PostCompact is observed, builds the block so the compaction row is written,
    and prints nothing, because both hosts reject an envelope on it
    (`hooks/projects-auto-init.py:25-36`, `hosts/codex/hook.py::main`).
  - **opencode**: `experimental.session.compacting` carries the builder's
    post-compact block, so the contract survives the summary
    (`hosts/opencode/plugins/tezgah.js:39-40`). It hands the builder the
    session id. The builder then forgets the lessons and armed paragraphs
    that session saw, and restates its pinned user constraints. The call
    used to send `{}`, which keyed nothing on the session.
  - **omp**: re-injected. The extension subscribes to omp's `session_compact`
    event (payload `{type, compactionEntry, fromExtension}`;
    `compactionEntry.summary` is the post-compaction summary) and asks
    `hosts/omp/hook.py` for `{"event": "post_compact"}`; the block is sent with
    `pi.sendMessage(..., {deliverAs: "nextTurn"})`, and the summary rides as
    `compact_summary` so `remember_compaction` writes the compaction row
    (`hosts/omp/tezgah-hook.ts.in:573-587`, `hosts/omp/hook.py::handle`).
    Subagent sessions are skipped, because the post-compact block starts the
    indexer.
  - **cursor**: not re-injected - a limitation. Cursor's only compaction hook,
    `preCompact`, is documented as observational: it fires before the summary,
    cannot modify it, and its output is `user_message` (shown to the user, not
    the model). No post-compaction event reaches the model, so the live-state
    block from sessionStart is not re-sent after a compaction
    (<https://cursor.com/docs/hooks>, read 2026-10-02).
  - **dsh**: not re-injected - a limitation. The Claude Code hook bridge
    (`@deepseek-ai/dsh-hooks-claude-code` 0.1.5-rc.2, README "Known
    Limitations") lists `PreCompact` and `PostCompact` among the unsupported
    events and ignores config for them, so `hosts/dsh/hooks.json` wires
    neither; the SessionStart context is not re-sent after a compaction.
- **Codex has no footer item to give.** `tui.status_line` is a closed enum, so
  the segment arrives as `systemMessage` twice per session and never carries
  color (`hosts/codex/hook.py:10-12`); PostToolUse there has no failure event, so
  the exit code is read from `tool_response` and an unread code stays `None`
  (`hosts/codex/hook.py:111-119`).
- **dsh runs the Claude-family scripts and knows seven events.** Its bridge
  accepts SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart,
  SubagentStop and Stop, and silently drops anything else - which is why
  `configPath` names `hosts/dsh/hooks.json` and not the Claude manifest
  (`bin/tezgah-setup::dsh_patch_block`). Its status route goes through `tezgah-status`
  with the five tool-use measures (`hosts/dsh/statusline/lib/index.js:18`), it
  declares `TEZGAH_CALL_OUTCOME=none` because the bridge drops the outcome field
  (`hosts/dsh/hooks.json:16`, `hooks/projects-posttooluse.py::main`), and its
  statusline row lives in the web profile because the plugin injects the
  web-only `connection` service (`bin/tezgah-setup::dsh_status_block`). It wires no
  Stop rule. With no outcome on any call, no check there can show a pass, so
  the rule could only refuse honest work. The entry stays out of
  `hosts/dsh/hooks.json` until the bridge carries outcomes.
- **opencode carries the untrusted-content control in the plugin**, not by
  importing `hooks/tezgah_untrusted.py`, which a plugin cannot do in process: the
  channel is decided in JS (`untrustedSource` `hosts/opencode/plugins/tezgah.js:1658`,
  the tier's argv reader at `:1619-1628`), the label and the taint notice ride the
  result the hook is handed (`labelResult` `:1710`). A shared corpus in
  `tests/test_opencode_plugin.py::OpenCodePlugin.test_the_classifier_agrees_with_the_python_half_on_a_shared_corpus` drives both halves over the same calls and
  fails if their answers differ, so neither can move without the other.
- **omp carries both untrusted-content marks through the shared core.** Its
  `post_tool_use` calls `marks` (`hooks/tezgah_untrusted.py::marks`), as
  `hooks/projects-posttooluse.py::main` does. The row's `source` carries the
  channel an effect inherits from its turn. The line goes back as `label`: the
  label on a result from outside, or the taint notice on the first effect after
  one. The bridge puts it in front of the result (`hosts/omp/hook.py::handle`,
  `labelled` in `hosts/omp/tezgah-hook.ts.in`). The bridge never sends a
  result's body. `marks` reads a missing result as a subagent call that read
  nothing. So the hook passes an empty stand-in, and a `task` report keeps its
  label. A failed call keeps its own channel and earns no notice. omp writes one
  ledger per subagent, so the hook passes no agent key.
- **No host gets the taint notice as PreToolUse context.** Checked 2026-10-06
  against each host's own reference, not in a live run:
  - Claude takes `additionalContext` but adds it "alongside the tool result"
    (code.claude.com/docs/en/hooks, PreToolUse decision control).
  - omp 18.6.1 takes a `tool_call` `additionalContext` and adds it after the
    tool ran (read from the installed binary).
  - Codex takes it (`pre-tool-use.command.output.schema.json` in openai/codex,
    and its hooks page). Its timing is not stated.
  - Cursor's `preToolUse` output has no context field, only `agent_message` on
    a deny (cursor.com/docs/hooks).
  - opencode's `tool.execute.before` can change only the arguments.
  - dsh: nobody has checked its bridge.

  On Claude and omp the line would land where the PostToolUse notice already
  does. Sending it there too would show it twice, with no timing gain.
- **opencode asks the core for the rules it cannot port, and counts the ask.** The
  task rule's phase and allowlist and the language rule's word list are answered by
  `bin/tezgah-gate decide` (the recording verb; `check` is the dry run) rather than copied into JavaScript (`IDENT_CMD`
  `hosts/opencode/plugins/tezgah.js:455`, the call site `:2168`) - one spawn per write
  and per identifier-creating command. The delegation fails open by design: a missing
  CLI, a non-zero exit, a broken pipe or a 10 s timeout refuses nothing (`collect`
  `hosts/opencode/plugins/tezgah.js:152-174`). One `delegation` row now records the class when the core could not
  answer (`noteDelegation` `:2002-2020`), so a silent fail-open is countable instead
  of invisible.
- **opencode has no session-start hook**, so its always-on file must carry the
  pointer every hook host appends, and the per-session index, agent and contract
  refreshes ride the first `chat.message` instead (`bin/tezgah-setup:854-869`,
  `hosts/opencode/plugins/tezgah.js:2347-2358`). It denies the native `skill`
  tool - the generated router replaces the injected skill list
  (`bin/tezgah-setup::install_opencode`) - and `permission.ask` may never be emitted by a
  given build, which is why `tool.execute.before` stays the enforcing half
  (`hosts/opencode/plugins/tezgah.js:11-14`).
- **Cursor only runs a PreToolUse hook for the tool types its matcher names**, so
  the matcher must list the write spellings or the gate's edit branches are
  unreachable there (`hosts/cursor/hook.py:35-41`,
  `bin/tezgah-setup:125-126`).
- **Claude, dsh, omp, codex and cursor run the gate only for the tool names
  their matcher carries**, so a name the PostToolUse side carries and the
  PreToolUse side does not is recorded in the ledger and never refused.
  `PowerShell` and `pwsh` are both `BASH_TOOLS` members
  (`hooks/tezgah_integrity.py::BASH_TOOLS`), so every PreToolUse matcher names both
  spellings: the Claude-family wire (`hooks/hooks.json:16`,
  `hosts/dsh/hooks.json:13`), codex and cursor
  (`bin/tezgah-setup:119-126`, mirrored in `hosts/codex/hooks.json:10` and
  `hosts/cursor/hooks.json:8` - neither named them until 2026-09-19, so a
  PowerShell call on those two reached no hook at all while the shared rules
  already knew the spelling), and omp's `GATED` list
  (`hosts/omp/tezgah-hook.ts.in:58-60`). A host this list does not cover is a
  host whose shell the gate cannot see.
- **Claude runs a copy of the checkout, never this tree** (`bin/tezgah-setup:3763-3781`),
  so a change is not live until `--sync` or a refresh
  (`refresh_plugin_copy`, `bin/tezgah-setup::refresh_plugin_copy`).
- **omp spawns the MCP `command` as one executable** and takes the rest in
  `args`; the whole argv in `command` fails with ENOENT (`bin/tezgah-setup::install_omp`),
  and `setStatus` strips ANSI, so only the widget path keeps the per-mark colors
  (`hosts/omp/tezgah-hook.ts.in:12-15`).
- **omp drops browser MCP servers while its native browser is on**: a server
  named `playwright`/`puppeteer`/... or running `@playwright/mcp`/... never
  connects there (omp 18.2.11 `/mcp` listed codegraph, mobile-mcp and tezgah
  only). `install_omp` therefore writes no Playwright row and sweeps one an older
  release wrote, and the report calls that absence green
  (`OMP_SUPERSEDED_MCP`, `bin/tezgah-setup::OMP_SUPERSEDED_MCP`); `skills/analyze-app`
  sends omp to the native `browser` instead.

## Source of truth

- `hooks/tezgah_paths.py` - `HOST_DIRS`, `HOST_BINS`, `host_installed`, `off`, `roots`
- `bin/tezgah-setup` - `install_<host>`, `host_checks_<host>`, `HOST_CHECKS`, `report`
- `hooks/hooks.json`, `hooks/projects-auto-init.py`, `hooks/projects-posttooluse.py`
- `hosts/codex/hook.py`, `hosts/codex/hooks.json`
- `hosts/cursor/hook.py`, `hosts/cursor/hooks.json`
- `hosts/dsh/hooks.json`, `hosts/dsh/statusline/lib/index.js`
- `hosts/omp/hook.py`, `hosts/omp/tezgah-hook.ts.in`
- `hosts/opencode/plugins/tezgah.js`, `hosts/opencode/tui/tezgah-tui.tsx`
- `statusline.py`, `bin/tezgah-status`, `hooks/tezgah_context.py`
- `hooks/tezgah_models.py` - the per-host model surface in `## The model wire`
