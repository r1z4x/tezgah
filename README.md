<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a>
</p>

# Tezgah

<p align="center">
  <img src="assets/logo/tezgah-logo.svg" alt="tezgah logo" width="180">
</p>

<h3 align="center">One working contract for every AI coding assistant you run.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">What it enforces</a> &bull;
  <a href="#supported-hosts">Supported hosts</a> &bull;
  <a href="#install">Install</a> &bull;
  <a href="#day-to-day">Day-to-day</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#cost">Cost</a> &bull;
  <a href="#development">Development</a> &bull;
  <a href="#contributing">Contributing</a> &bull;
  <a href="#security">Security</a> &bull;
  <a href="#license">License</a>
</p>

<p align="center"><sub>English is the source of truth; translations may lag behind it.</sub></p>

---

One working contract for every AI coding assistant you run — Claude Code,
opencode, Codex, Cursor, and DeepSeek's dsh harness — inside a set of
configured repository roots.

Left alone, each assistant has its own habits: one answers in Turkish, another
in English; one greps for everything, another queries a code graph; one says
"done" without running a test. Tezgah removes the drift. Open any host and you
get the same language, the same discipline, and the same standard of evidence.

The design is two layers. The rules live once in a shared core; each host gets
a thin adapter that translates that core into the shape the host understands.
Change a rule in one place and all five hosts see it — no five-way copy of the
same text.

<a id="what-it-enforces"></a>

## What it enforces

- **Outcome-first Turkish reporting.** Every reply is in Turkish and leads with
  the result or decision (BLUF), then points ordered by impact. Code, commits,
  docs, and subagent prompts stay English; names, CLI commands, and error
  strings are never translated.
- **Minimal code (ponytail).** The laziest change that actually works: YAGNI,
  then reuse an existing helper, then stdlib, then a native platform feature,
  then an installed dependency, then one line. No unrequested abstractions.
  Validation, error handling, and security are never simplified away.
- **Code-graph-first discovery.** "Where is X", "who calls Y", "what breaks if
  Z changes" go to the `codebase-memory-mcp` graph (`search_graph`,
  `trace_path`, `search_code`), not to grep. Grep stays right for literal text,
  configs, and non-code files.
- **Accessibility-first app analysis.** A running web or mobile app is read
  through its accessibility / DOM / native view tree, not a screenshot per step.
  `analyze-app` covers a browser (Playwright MCP), an iOS Simulator or Android
  emulator (Mobile MCP), and optional web diagnostics (Chrome DevTools MCP); a
  screenshot is an explicit, on-demand action for what the tree cannot answer.
- **External second opinion.** Before a non-trivial or hard-to-reverse call,
  `~/.config/tezgah/bin/consult` asks independent models through OpenRouter (or the DeepSeek API
  with `--provider deepseek`) in parallel, and the agent reports where they
  agreed or disagreed.
- **Research via OpenResearch.** When the router judges a task is research — a
  literature review, forming and testing hypotheses, running experiments, a
  research artifact — it drives the work through alphaXiv's OpenResearch (`orx`)
  and loads the `orx` manual first, instead of improvising the protocol. Plain
  code discovery stays on the code graph. When `orx` is absent, the router says
  so and falls back to a host subagent.
- **Honesty under verification.** Nothing is reported done, tested, or fixed
  unless the output was seen. A failing test is reported as failing with its
  exact error, and a skipped check is stated plainly.
- **No AI attribution, anywhere.** Nothing persisted or published — commit,
  merge, and tag messages, PR and issue text, code comments, file headers, docs
  — may credit the assistant, model, vendor, or "AI". Using a tool is fine;
  signing its name to your work is not.
- **Two-tier orchestration.** The main thread decides and verifies; a cheap
  model (`~/.config/tezgah/bin/codegen`, OpenRouter by default or `--provider deepseek`) drafts
  bounded, well-specified edits to a scratch directory. Nothing reaches the repo
  except through the router, and a failed draft falls back to the main model
  automatically.
- **Per-repo subagents.** At session start the enclosing repo gets a small set of
  capability-gated agents (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus a `tezgah-orchestrator`, rendered
  into each installed host's native surface (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` plus a live config injection, Codex
  `.codex/agents/`) and ignored with one managed `.gitignore` block. On Claude the
  orchestrator's `Agent(tezgah-*)` allowlist only takes effect when it runs as the
  main thread (`claude --agent tezgah-orchestrator`); as a subagent the list is
  ignored. dsh has no per-role surface, so the contract's router rule covers it.

<a id="supported-hosts"></a>

## Supported hosts

| Host | Wired by | Status line |
|---|---|---|
| **Claude Code** | local plugin marketplace: hooks, commands, two read-only agents, output style | native `statusLine` |
| **opencode** | plugin + instructions + MCP + generated skill router (native skill list denied), repo auto-index on the first message | TUI plugin (no command statusLine) |
| **Codex** | `hooks.json` + skills + MCP, including a `PreToolUse` gate | hook `systemMessage` (footer item list is closed) |
| **Cursor** | `hooks.json` + skills + MCP | `statusLine` in `cli-config.json` |
| **dsh** | Claude Code hook bridge + managed patch block (hooks, MCP, LLM routes, an out-of-tree Web status line) | Web UI plugin: `tezgah-dsh-statusline` in the session header |

The Codex gate runs Bash, `exec_command`, `apply_patch`, Edit/Write, MCP tools,
and subagent calls through the same check as the other hosts. On Claude, the
attribution ban is enforced mechanically too: the `attribution` setting is
emptied (`commit`, `pr`, `sessionUrl`) so commit and PR credits are off at the
source.

### Status line

Every host renders the same one-line checklist from `tezgah-status`, so they
cannot drift. The state is the point: a mark is **green** when the rule is armed
and in force this session, **yellow** when it is armed but on demand (not used
yet), and **red** when a kill switch turned it off. `idx` reports graph readiness
separately (`✓` indexed, `↻` stale, `✗` not indexed, `–` not applicable) and
`plans N (M blk)` the open plans. `tezgah-status --legend` prints the key,
`--json` gives the same segments for a UI, and `--no-color` (or `NO_COLOR`)
forces plain text. Claude Code and Cursor color the native status line; the
opencode TUI colors its own component and refreshes on the host event bus; the
dsh Web UI colors its header component and refreshes only while its tab is
visible; Codex shows the plain string in `systemMessage`.

dsh runs the same Claude hook files through its `dsh-hooks-claude-code` bridge,
so the session-start contract, the attribution gate, and the first-grep nudge
all apply there. dsh exposes a single `subagent` tool, so the grep-only-explorer
denial is inert — there is no explorer subagent for it to refuse. dsh's default
`workspace-write` sandbox confines hook subprocesses to the workspace and the
platform temp dir, so tezgah writes its hook state (nudge marks, index stamp) to
a writable fallback there rather than failing on a denied write. The graph index
worker cannot write the `codebase-memory-mcp` cache from inside that sandbox, so
the `dsh` launcher warms the index in the user's unconfined shell before booting
dsh — a new repo is indexed exactly as on the other hosts, HEAD-stamped. A
session booted without the launcher still gets a clear report that the
unsandboxed MCP server serves the graph and needs `index_repository` for a repo
it has not indexed, instead of a raw `EPERM`. The managed
patch block also declares two OpenAI-compatible LLM routes on the pi-ai adapter
the base composition mounts: `openrouter` (`OPENROUTER_API_KEY`) and `deepseek`
(`DEEPSEEK_API_KEY`), selectable alongside the native `deepseek-official`
default. Keys resolve from the launch environment or the harness credential
store; neither key enters the config file. tezgah-setup also puts a `dsh`
launcher on PATH (`~/.local/bin/dsh`) that finds the installed CLI under
`$DSH_HOME`, so `dsh --profile web` works from any directory.

dsh has no command status line, so tezgah ships one as a Web UI plugin:
`tezgah-dsh-statusline`. Its host half serves the `tezgah-status` string for the
session's workspace over an authenticated `/api/tezgah.status` route (with
`?format=json` for the colored view); its browser half renders it in the session
header, colored by state with a hover/click legend, and refreshes only while the
tab is visible. `tezgah-setup`
links the plugin into the web profile and enables it with a managed row in
`profiles/web/cordis.patch.yml` (web-only, because the host half injects the
web-only `connection` service); a profile that has never booted `web` is skipped
with a hint instead of half-written. In `headless` mode, the hooks bridge injects
the SessionStart contract as its own trailing turn (its `agent/session-start`
calls `agent.inject()` detached, after the one-shot task is already the first
message), so `dsh --profile headless "<task>"` spends one extra turn and, for a
literal-answer prompt, prints the model's reaction to the contract rather than
the task's answer; interactive web sessions are unaffected.

`bin/tezgah-setup --install` also triggers `orx install-skills` for Claude,
Codex, opencode and Cursor when `orx` is on PATH, so the research rule has a
manual to load. The shim files belong to orx, so tezgah only runs that installer
and never lists them for uninstall. dsh has no orx harness; the research rule
there falls back to `orx skill` on the shell.

The Claude plugin also ships two read-only agents. `agents/tezgah-explorer.md`
does code discovery from the graph and returns `file:line` evidence;
`agents/tezgah-reviewer.md` turns a diff into its impact set with
`detect_changes` and then looks for real defects. Both have write and command
tools disabled; their output is advisory.

### App analysis

`analyze-app` drives a running application from its accessibility tree. The
default loop is open, read the tree, act, observe console/network/logs, and
re-read the tree — a screenshot is an explicit action for what the tree cannot
answer (canvas, game, animation, pixel-level visual regression). The skill is
one path for all hosts; the servers under it are one shared spec in
`hooks/tezgah_apps.py`:

| Server | Target | Wired by |
|---|---|---|
| `playwright` (`@playwright/mcp`) | web pages, `browser_*` tools | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS Simulator / Android emulator, `mobile_*` tools | same |
| `chrome-devtools` (opt-in, `--devtools`) | web perf traces, deep network, source-mapped console | same |

The browser runs an **isolated** profile by default, so a run never touches your
real Chrome state; analyzing a logged-in flow is a deliberate attach
(`--cdp-endpoint` or the Playwright extension), not a default. Screenshots,
traces and tree dumps land in `~/.cache/tezgah/apps` (override with
`TEZGAH_ARTIFACTS`) and the agent gets a path back, never inline image bytes.
The servers run through `npx`, so they need node but no install of their own;
`tezgah-setup --install --devtools` adds the optional web diagnostics server.
dsh wires the same two servers through its `dsh-mcp-client` bridge
(`serverName` / `command` / `args` / `env`, confirmed against the published
config schema), and Claude gets them from the plugin's `.mcp.json`
(`claude plugin details tezgah` lists MCP servers 2 and both connect).
`mobile-mcp` is the higher-friction half: macOS may prompt for Accessibility /
Screen-Recording permission and the view tree can drop under load, so the skill
retries the tree before falling back to a screenshot.

CI runs a deterministic handshake for both servers (no browser, no device):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Two opt-in local
smokes go further: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` starts
Playwright MCP, navigates and reads the snapshot with no screenshot;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` starts Mobile MCP, checks
the view-tree tools and lists a device. They print `SKIP: ...` when node, a
browser build or a device is missing.

<a id="install"></a>

## Install

Requires Python 3.8+. node + npm are needed for the dsh host and, with `pnpm`,
for its web status line. The optional integrations degrade gracefully:
`codebase-memory-mcp` on PATH powers the graph; a model key powers `consult`
and `codegen` — OpenRouter by default (`OPENROUTER_API_KEY` or
`~/.config/openrouter/key`), or the DeepSeek API with `--provider deepseek`
(`DEEPSEEK_API_KEY` or `~/.config/deepseek/key`); and OpenResearch's `orx` on
PATH gives the research rule something to drive. When the chosen provider's key
is missing, tezgah says so instead of pretending.

Clone, then arm every detected host in one pass:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` also installs the optional tools that are missing by running each
vendor's own installer **over the network**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(its home profile through `npx`), and `pnpm` when dsh needs it (via `npm`) —
`curl ... | sh` included. None needs sudo; the run is recorded in
`~/.config/tezgah/install.log`. Preview with `--dry-run`, skip it with
`--no-deps` (useful in CI), or install the tools alone with `--deps`. Tools land
in `~/.local/bin` or `~/.cargo/bin`, so a fresh shell may be needed before they
are on PATH; tezgah's own checks look in those dirs regardless, so a non-interactive
shell still reports them as present.

If a predecessor setup is already present, import it first — it is moved aside,
not deleted:

```bash
bin/tezgah-setup --adopt
```

Claude Code installs through its own plugin channel:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Limit the install explicitly when needed:

```bash
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Day-to-day

Nothing to run: the rules load when a host starts. A few commands are worth
knowing:

| Command | Purpose |
|---|---|
| `bin/tezgah-setup` | Report what is armed, per host |
| `bin/tezgah-status [PATH]` | Show whether the rules are active in that repo |
| `bin/tezgah-setup --status [PATH]` | Print the armed/used checklist |
| `bin/tezgah-setup --deps [--dry-run]` | Install missing optional tools (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Report harness disk use; `--clean` deletes old index logs and vacuums the opencode DB; `--prune-sessions` deletes idle sessions (the only action that actually shrinks the DB) |
| `/plan-add` | Turn a piece of work into a tracked plan |
| `/plan-status` | Summarize open plans and pick the next one |
| `/plan-sync` | Close out finished plans |
| `bin/tezgah-setup --version` | Print the plugin version |
| `bin/tezgah-setup --uninstall` | Remove only tezgah's symlinks, host hook entries, and the dsh managed block |

<a id="configuration"></a>

## Configuration

Tezgah is armed only under its configured roots; anywhere else it is silent.

- Default root: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (path-separator list) overrides the file for one-offs and CI.

Kill switches live in `~/.config/tezgah/`. Each one removes its rule from the
text injected into the session, so the rule actually stops:

| Switch | Turns off |
|---|---|
| `exec-mode.off` | Turkish, outcome-first reporting |
| `ponytail-auto.off` | the minimal-code rule |
| `spec-off` | the spec-before-building rule |
| `consult-off` | the external-second-opinion rule |
| `research-off` | routing research tasks to OpenResearch |
| `orchestrate-off` | subagent delegation (adds a do-not-delegate line) |
| `reminder-off` | the per-turn reminder text |
| `pretooluse-off` | the PreToolUse gate itself (attribution, explorer, grep nudge) |

Per repo, `.no-ponytail`, `.no-cbm` and `.no-lessons` turn off the minimal-code
rule, the code-graph rule (and its auto-index), and the lessons ledger
respectively.

When the user flags a mistake, the agent appends a one-line lesson to the repo's
`.tezgah/lessons.md`; the most recent lines are injected at session start so the
same mistake cannot silently repeat.

## Cost

Measured on this machine (macOS, Python 3.10), not estimated:

- **Context.** A session start injects ~4.8 KB (~1.2k tokens) of contract text.
  On Codex a 480-byte reminder rides each turn; Claude and the other hosts have
  no per-turn hook, so their per-turn cost is zero. The full `tezgah-contract`
  skill (~19.9k characters) is paid only when a task loads it. On opencode the
  contract ships as a ~5.5 KB instructions file. opencode would otherwise
  inject ~53 KB of skill name/description/location text into every session's
  system prompt; tezgah denies that list (`permission.skill = deny`) and ships
  a generated ~16 KB skill router instead, so a skill is found by reading its
  `SKILL.md` path from the router.
- **Latency.** Hooks are separate Python processes, so the ~19 ms interpreter
  start dominates. On top of it, session start adds ~25 ms, a gated tool call
  (Bash/Grep/Task) adds ~9 ms, and Codex's Stop segment adds ~15 ms per turn.
- **Disk.** Installation takes ~58 ms and every file tezgah rewrites is kept
  once as `<file>.tezgah-bak`.

The payoff shows up on caller questions. In one real repo, a default `grep`
ignored the relevant folder and found nothing; with ignore disabled it took
3.95 s and still mixed definitions with call sites. The code graph answered the
same question in 16 ms, listing only the 8 true call sites.

opencode is also armed for long-session context hygiene: `tezgah-setup --install`
sets `compaction.prune` so old tool results are cleared from the prompt instead
of being re-sent every step, and a `watcher.ignore` list keeps the file watcher
out of `.git`, `node_modules` and build dirs. Both merge — an explicit user value
wins. This matters because opencode only auto-compacts near the model's context
limit (for a 1M-token model, about 980k), so without pruning the working set
grows to hundreds of thousands of tokens. `bin/tezgah-doctor` reports the
resulting disk footprint; `--prune-sessions DAYS` deletes idle sessions through
the opencode CLI, which is the only action that actually shrinks the database —
VACUUM alone cannot, since its pages are all live.

<a id="development"></a>

## Development

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI runs both on Python 3.10 and 3.12. To refresh an installed Claude copy from
this checkout, use `bin/tezgah-setup --sync`, and validate the manifest with
`claude plugin validate .claude-plugin/plugin.json`. When bumping the version,
update `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
together — they must agree.

`codebase-memory-mcp` is installed by the user. Orca's hooks and files are not
part of this project and are left untouched. Claude receives the always-on core
from the SessionStart hook; `output-styles/tezgah.md` is a duplicate for builds
that load plugin output styles, so the hook is the authoritative path.

<a id="contributing"></a>

## Contributing

Small, single-purpose changes are the easiest to accept. A rule belongs in the
shared core (`hooks/`) unless it is genuinely host-specific; a host difference
belongs in its adapter under `hosts/<name>/`. Keep the diff as short as it can
be while still correct — the project's own minimal-code rule applies to the
project.

Before opening a pull request, run the same three checks CI runs:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` comes from `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
which is the only development dependency.

<a id="security"></a>

## Security

Report vulnerabilities privately through GitHub's security advisories
(**Security** tab → **Report a vulnerability**) rather than a public issue.

tezgah runs shell hooks, writes host configuration, and injects text into every
session, so anything that makes a hook execute attacker-controlled code, leaks a
key into a config file, widens a sandbox, or lets repository content escalate
into instruction text is in scope. Include the host, the tezgah version
(`bin/tezgah-setup --version`), and a minimal reproduction.

<a id="license"></a>

## License

The root `LICENSE` (MIT) covers tezgah's own files. `skills/ponytail` and
`skills/no-ai-slop` are vendored under their own MIT terms, recorded in
`NOTICE`.
