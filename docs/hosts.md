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
| claude | SessionStart, SubagentStart, PostCompact, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, Stop - `hooks/hooks.json:2-26` | both: SessionStart hook context (`hooks/projects-auto-init.py:1-6`) and the static `output-styles/tezgah.md` mirror (`README.md:507-508`) | UserPromptSubmit -> `additionalContext` (`hooks/hooks.json:12-14`, `hooks/projects-auto-init.py:38-41`) | `statusLine` command in `~/.claude/settings.json` (`bin/tezgah-setup:527-548`), ANSI, forwards Orca first (`statusline.py:30-48`) | all seven: the transcript parse covers the two skill reads, `graph`, `orch` and the three shell kinds - `consult`, `research` and the judgement callers (`statusline.py:58-107`, `observable=None` at `:112`) |
| codex | SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart, PostCompact, Stop (`bin/tezgah-setup:129-131`; named in `hosts/codex/hook.py:6-7`) | hook: the normalized events inject `context_for` (`hosts/codex/hook.py:188-194`) | UserPromptSubmit -> `additionalContext` (`hosts/codex/hook.py:188-194`) | no custom footer item (`tui.status_line` is a closed enum) - the line rides `systemMessage`, plain, at SessionStart and Stop (`hosts/codex/hook.py:10-12,182-184,195-198`) | five tool-use (`TOOL_USE_MEASURES` at `hosts/codex/hook.py:182,196`) |
| cursor | 13 events: sessionStart, preToolUse, postToolUse, postToolUseFailure, subagentStart, subagentStop, beforeSubmitPrompt, stop, beforeMCPExecution, afterShellExecution, afterMCPExecution, afterFileEdit, afterAgentResponse (`bin/tezgah-setup:132-182`) | hook: sessionStart -> `additional_context` (`hosts/cursor/hook.py:244-246`) | beforeSubmitPrompt -> `additional_context` plus `{"continue": true}` (`hosts/cursor/hook.py:358-364`) | `statusLine` in `~/.cursor/cli-config.json` -> `tezgah-statusline --cursor` (`bin/tezgah-setup:1092-1100`), ANSI (`statusline.py:116-117`) | five tool-use (`statusline.py:112`) |
| opencode | no lifecycle events; plugin hooks: config, permission.ask, tool.execute.before, shell.env, experimental.session.compacting, chat.message, tool.execute.after (`hosts/opencode/plugins/tezgah.js:1559-1826`) - `tool.execute.before` carries the whole gate, `tool.execute.after` the channel on the row, the provenance label on the result and the taint notice on the next effect (`untrustedSource` `hosts/opencode/plugins/tezgah.js:1228`, `labelResult` `:1303`) | static only: generated `instructions` files, because there is no session-start injection point (`hosts/opencode/plugins/tezgah.js:3-6`, `bin/tezgah-setup:896-929`) | chat.message pushes a synthetic part (`hosts/opencode/plugins/tezgah.js:1756-1801`) | TUI plugin `tezgah-tui.tsx` declared in `tui.json`, runs `tezgah-status` on the event bus (`hosts/opencode/tui/tezgah-tui.tsx:1-11`; wiring `bin/tezgah-setup:960-971`) | all seven: skill reads and kinds are classified in process (`hosts/opencode/plugins/tezgah.js:1455-1473`) |
| dsh | SessionStart, SubagentStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop (`hosts/dsh/hooks.json:2-19`) | hook: the same Claude-family scripts, named by `configPath` (`bin/tezgah-setup:1420-1421`) | UserPromptSubmit, through the bridge (`hosts/dsh/hooks.json:9-11`) | web-profile plugin: authenticated `GET /api/tezgah.status` -> `tezgah-status` (`hosts/dsh/statusline/lib/index.js:14,39-60`) | five tool-use: the route passes `--observable=consult,research,graph,orch,judge` (`hosts/dsh/statusline/lib/index.js:18,47-48`) |
| omp | session_start, session_switch, turn_end, before_agent_start, tool_call, tool_result, session_stop (`hosts/omp/tezgah-hook.ts.in:164,198-199,201,221,235,267`) | both: static `RULES.md` (`bin/tezgah-setup:1290-1293`) and a session payload carrying only what a static file cannot know (`hosts/omp/hook.py:123-131`) | before_agent_start returns a hidden message (`hosts/omp/tezgah-hook.ts.in:201-218`) | extension draws `ctx.ui.setWidget` below the editor, `setStatus` as fallback (`hosts/omp/tezgah-hook.ts.in:20-27`); ANSI line from `hosts/omp/hook.py:85-107` | all seven: the embedded runner filters skill reads before asking python (`hosts/omp/tezgah-hook.ts.in:40-53`) and no `observable` is passed (`hosts/omp/hook.py:94-96`) |

The middle five marks (`consult`, `research`, `graph`, `orch`, `judge`) are tool-use marks:
any adapter that sees its host's tool calls can light them by calling
`record()` (`hooks/tezgah_context.py:1094`). CLI-side, `tezgah-status` reads
the same core and takes the session id as an argument or `TEZGAH_SESSION`
(`bin/tezgah-status:123`).

## What each host gets, and where it is written

Every host gets the skill symlinks from `SKILLS` (`bin/tezgah-setup:76-78`)
except claude, whose skills arrive with the plugin. `install_common` writes the
shared config, contract hash and the CLI symlinks every host shell can call
(`bin/tezgah-setup:438-487`).

- **claude** - `install_claude` (`bin/tezgah-setup:493-503`): `~/.claude/statusline.py`,
  `~/.claude/workflows/{graph-map,graph-review,graph-impact}.js`, the
  `~/.claude/bin/{consult,codegen,tezgah-render-table}` links, and two keys in
  `~/.claude/settings.json` - `statusLine` (`bin/tezgah-setup:527-548`) and the attribution
  off-switch (`bin/tezgah-setup:506-526`). Its hook manifest is the plugin's own
  `hooks/hooks.json`; no `hooks.json` is written into `~/.claude`. Claude runs a
  **copy** of the checkout under `~/.claude/plugins/cache`, refreshed by
  `--sync` (`bin/tezgah-setup:3663-3721`).
- **codex** - `install_codex` (`bin/tezgah-setup:551-636`): `$CODEX_HOME/hooks.json`
  (one group per event, PreToolUse carrying `CODEX_PRETOOL_MATCHER` at `:129-131`),
  `skills/*` symlinks, `~/.codex/bin/consult`, and `mcp_servers.*` tables in
  `config.toml` (`ensure_toml_mcp`, `bin/tezgah-setup:641-673`).
- **cursor** - `install_cursor` (`bin/tezgah-setup:1057-1102`): `~/.cursor/hooks.json`
  (tezgah entries replaced, a user's Orca entries merged), `skills/*` symlinks,
  `mcp.json` servers, and `cli-config.json` `statusLine`.
- **opencode** - `install_opencode` (`bin/tezgah-setup:973-1056`): the plugin under
  both `plugins/` and `plugin/` (version drift), `skills/*` symlinks, the
  generated `~/.config/tezgah/opencode-contract.md` (`bin/tezgah-setup:759-795`) and
  `opencode-skills.md` + `.full.md` (`bin/tezgah-setup:1162-1229`), then `opencode.json`
  (`instructions`, `mcp`, `permission.skill=deny`, `compaction.prune`,
  `watcher.ignore`, the two `external_directory` grants) and `tui.json` +
  `tui-plugins/tezgah-tui.tsx`.
- **dsh** - `install_dsh` (`bin/tezgah-setup:1228-1239`): `~/.dsh/skills/*` symlinks,
  a managed block in `~/.dsh/cordis.patch.yml` (`dsh_patch_block`, `bin/tezgah-setup:1130-1188`) that
  mounts the Claude-code hook bridge on `hosts/dsh/hooks.json`, the MCP client
  rows and the three `llm-pi-ai` routes, plus `~/.local/bin/dsh` ->
  `bin/tezgah-dsh`. `install_dsh_statusline` (`bin/tezgah-setup:1201-1227`) links the statusline
  package into the **web profile** and adds its row to
  `~/.dsh/profiles/web/cordis.patch.yml`.
- **omp** - `install_omp` (`bin/tezgah-setup:1286-1340`): `~/.omp/agent/RULES.md`
  (managed block), `skills/*` symlinks, `agents/tezgah-*.md`, `mcp.json`
  (`$schema`, `mcpServers`), and `hooks/pre/tezgah-hook.ts` rendered from
  `hosts/omp/tezgah-hook.ts.in` with the python path substituted for `@HOOK@`.

An adapter is responsible for its host's **envelope** and its **surface**: it
translates the host's event and tool names into the shared vocabulary (one call
has to hash to one id - `hosts/codex/hook.py:70-79`, `hosts/cursor/hook.py:65-72`),
draws the line, and returns the host's own output shape. The contract text, the
gate decision, the evidence ledger, the untrusted-content marks and the segment
builder stay in the shared core under `hooks/` (`hosts/omp/hook.py:1-11`,
`hosts/cursor/hook.py:1-40`).

## The observability rule

A skill read is observable only where the host gives a channel that does not cost
a process per read: Claude parses its transcript (`statusline.py:58-107`),
opencode classifies in process (`hosts/opencode/plugins/tezgah.js:1455-1473`),
omp filters in its embedded runner before it asks python
(`hosts/omp/tezgah-hook.ts.in:40-53`). On codex, cursor and dsh a read is not
observable at that price, so their surfaces pass the five tool-use measures as
`observable` and the two skill marks render dim (`info`, no glyph) instead of
claiming the skill was never opened (`hooks/tezgah_context.py:1271-1277`, and the
`observable` branch at `hooks/tezgah_context.py:1346-1347`). Callers that pass `TOOL_USE_MEASURES`:
`statusline.py:112`, `hosts/codex/hook.py:182,196`,
`hosts/dsh/statusline/lib/index.js:18`. A kill switch is observable everywhere
and still renders `off` (`hooks/tezgah_context.py:1323-1324`).

## Adding a host

In order, each step verified by the one below it:

1. `HOST_DIRS` and, when the CLI can exist without a config dir, `HOST_BINS` in
   `hooks/tezgah_paths.py:49-64`. These are shared by the installer, the report
   and agent generation, so "is this host installed?" has one answer
   (`hooks/tezgah_paths.py:44-48`). Add the name to `ALL_HOSTS` in the report
   order (`bin/tezgah-setup:100`).
2. The hook adapter(s) under `hosts/<host>/` (an `install_*`-independent
   directory like `hosts/codex/hook.py`, `hosts/cursor/hook.py`) plus, for a
   TS/JS host, the bridge file with a substituted python path
   (`hosts/omp/tezgah-hook.ts.in` rendered at `bin/tezgah-setup:1331-1332`).
3. `install_<host>()` writing that host's files, registered in `INSTALLERS`
   (`bin/tezgah-setup:1341-1345`), and `uninstall_<host>()` removing only
   tezgah-managed links and blocks (`bin/tezgah-setup:2495-2643`).
4. `host_checks_<host>()` returning `(label, bool)` rows over what was actually
   written, registered in `HOST_CHECKS` (`bin/tezgah-setup:3406-3412`); the
   `--report` output is that list (`bin/tezgah-setup:2992-3070`). Give the row a home-qualified
   label if the host's dir can be relocated (`host_checks_codex`, `:1914-1936`).
5. Decide the surface: a `statusLine` command, a TUI/widget plugin, or the
   `systemMessage` fallback (`hosts/codex/hook.py:10-12`). Pass `observable` if
   the host cannot see a skill read, and `idx_override` on any redraw that must
   not fork git for a cosmetic glyph (`hooks/tezgah_context.py:1326-1328`).
6. Tests, in two tiers: a per-host class in `tests/test_setup.py` pinning the
   report rows and the written files (e.g. `OmpHost:960-1030`,
   `CodexHome:657-702`, `CursorMatcher:705-722`, `DshStatusline:872-957`), and an
   opt-in script under `tests/e2e_*.py` for the thing only a real host can prove
   - not collected by `unittest discover`, it exits 0 with `SKIP` when the host
   is absent (`tests/e2e_omp_statusline.py:13-16`).

## Host-specific limits worth knowing

- **Codex has no footer item to give.** `tui.status_line` is a closed enum, so
  the segment arrives as `systemMessage` twice per session and never carries
  color (`hosts/codex/hook.py:10-12`); PostToolUse there has no failure event, so
  the exit code is read from `tool_response` and an unread code stays `None`
  (`hosts/codex/hook.py:92-100`).
- **dsh runs the Claude-family scripts and knows seven events.** Its bridge
  accepts SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart,
  SubagentStop and Stop, and silently drops anything else - which is why
  `configPath` names `hosts/dsh/hooks.json` and not the Claude manifest
  (`bin/tezgah-setup:1136-1149`). Its status route goes through `tezgah-status`
  with the five tool-use measures (`hosts/dsh/statusline/lib/index.js:18`), it
  declares `TEZGAH_CALL_OUTCOME=none` because the bridge drops the outcome field
  (`hosts/dsh/hooks.json:16`, `hooks/projects-posttooluse.py:103-112`), and its
  statusline row lives in the web profile because the plugin injects the
  web-only `connection` service (`bin/tezgah-setup:1120-1125`).
- **opencode carries the untrusted-content control in the plugin**, not by
  importing `hooks/tezgah_untrusted.py`, which a plugin cannot do in process: the
  channel is decided in JS (`untrustedSource` `hosts/opencode/plugins/tezgah.js:1228`,
  the tier's argv reader at `:1581-1590`), the label and the taint notice ride the
  result the hook is handed (`labelResult` `:1303`). A shared corpus in
  `tests/test_opencode_plugin.py:1246-1285` drives both halves over the same calls and
  fails if their answers differ, so neither can move without the other.
- **opencode asks the core for the rules it cannot port, and counts the ask.** The
  task rule's phase and allowlist and the language rule's word list are answered by
  `bin/tezgah-gate check` rather than copied into JavaScript (`IDENT_CMD`
  `hosts/opencode/plugins/tezgah.js:329`, the call site `:1670`) - one spawn per write
  and per identifier-creating command. The delegation fails open by design: a missing
  CLI, a non-zero exit, a broken pipe or a 10 s timeout refuses nothing (`collect`
  `hosts/opencode/plugins/tezgah.js:152-174`). One `delegation` row now records the class when the core could not
  answer (`noteDelegation` `:2013-2031`), so a silent fail-open is countable instead
  of invisible.
- **opencode has no session-start hook**, so its always-on file must carry the
  pointer every hook host appends, and the per-session index, agent and contract
  refreshes ride the first `chat.message` instead (`bin/tezgah-setup:796-811`,
  `hosts/opencode/plugins/tezgah.js:1788-1799`). It denies the native `skill`
  tool - the generated router replaces the injected skill list
  (`bin/tezgah-setup:945-947`) - and `permission.ask` may never be emitted by a
  given build, which is why `tool.execute.before` stays the enforcing half
  (`hosts/opencode/plugins/tezgah.js:11-14`).
- **Cursor only runs a PreToolUse hook for the tool types its matcher names**, so
  the matcher must list the write spellings or the gate's edit branches are
  unreachable there (`hosts/cursor/hook.py:34-40`,
  `bin/tezgah-setup:123-124`).
- **Claude, dsh, omp, codex and cursor run the gate only for the tool names
  their matcher carries**, so a name the PostToolUse side carries and the
  PreToolUse side does not is recorded in the ledger and never refused.
  `PowerShell` and `pwsh` are both `BASH_TOOLS` members
  (`hooks/tezgah_integrity.py:175-176`), so every PreToolUse matcher names both
  spellings: the Claude-family wire (`hooks/hooks.json:16`,
  `hosts/dsh/hooks.json:13`), codex and cursor
  (`bin/tezgah-setup:117-124`, mirrored in `hosts/codex/hooks.json:10` and
  `hosts/cursor/hooks.json:8` - neither named them until 2026-09-19, so a
  PowerShell call on those two reached no hook at all while the shared rules
  already knew the spelling), and omp's `GATED` list
  (`hosts/omp/tezgah-hook.ts.in:58-60`). A host this list does not cover is a
  host whose shell the gate cannot see.
- **Claude runs a copy of the checkout, never this tree** (`bin/tezgah-setup:3644-3662`),
  so a change is not live until `--sync` or a refresh
  (`refresh_plugin_copy`, `bin/tezgah-setup:3723-3754`).
- **omp spawns the MCP `command` as one executable** and takes the rest in
  `args`; the whole argv in `command` fails with ENOENT (`bin/tezgah-setup:1313-1315`),
  and `setStatus` strips ANSI, so only the widget path keeps the per-mark colors
  (`hosts/omp/tezgah-hook.ts.in:12-15`).

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
