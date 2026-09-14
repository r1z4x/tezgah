# Tezgah

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
- **External second opinion.** Before a non-trivial or hard-to-reverse call,
  `bin/consult` asks independent models through OpenRouter (or the DeepSeek API
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
  model (`bin/codegen`, OpenRouter by default or `--provider deepseek`) drafts
  bounded, well-specified edits to a scratch directory. Nothing reaches the repo
  except through the router, and a failed draft falls back to the main model
  automatically.

## Supported hosts

| Host | Wired by | Status line |
|---|---|---|
| **Claude Code** | local plugin marketplace: hooks, commands, two read-only agents, output style | native `statusLine` |
| **opencode** | plugin + instructions + MCP + generated skill router (native skill list denied), repo auto-index on the first message | TUI plugin (no command statusLine) |
| **Codex** | `hooks.json` + skills + MCP, including a `PreToolUse` gate | hook `systemMessage` (footer item list is closed) |
| **Cursor** | `hooks.json` + skills + MCP | `statusLine` in `cli-config.json` |
| **dsh** | Claude Code hook bridge + managed patch block (hooks, MCP, and OpenRouter/DeepSeek LLM routes) | not yet — a UI plugin is needed and is unpackaged |

The Codex gate runs Bash, `exec_command`, `apply_patch`, Edit/Write, MCP tools,
and subagent calls through the same check as the other hosts. On Claude, the
attribution ban is enforced mechanically too: the `attribution` setting is
emptied (`commit`, `pr`, `sessionUrl`) so commit and PR credits are off at the
source.

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

## Install

Requires Python 3.8+. The optional integrations degrade gracefully:
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

## Day-to-day

Nothing to run: the rules load when a host starts. A few commands are worth
knowing:

| Command | Purpose |
|---|---|
| `bin/tezgah-setup` | Report what is armed, per host |
| `bin/tezgah-status [PATH]` | Show whether the rules are active in that repo |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Report harness disk use; `--clean` deletes old index logs and vacuums the opencode DB; `--prune-sessions` deletes idle sessions (the only action that actually shrinks the DB) |
| `/plan-add` | Turn a piece of work into a tracked plan |
| `/plan-status` | Summarize open plans and pick the next one |
| `/plan-sync` | Close out finished plans |
| `bin/tezgah-setup --version` | Print the plugin version |
| `bin/tezgah-setup --uninstall` | Remove only tezgah's symlinks, host hook entries, and the dsh managed block |

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
| `consult-off` | the external-second-opinion rule |
| `research-off` | routing research tasks to OpenResearch |
| `orchestrate-off` | subagent delegation (adds a do-not-delegate line) |
| `reminder-off` | the per-turn reminder text |
| `pretooluse-off` | the PreToolUse gate itself (attribution, explorer, grep nudge) |

Per repo, `.no-ponytail` and `.no-cbm` turn off the minimal-code rule and the
code-graph rule (and its auto-index) respectively.

## Cost

Measured on this machine (macOS, Python 3.10), not estimated:

- **Context.** A session start injects ~3.52 KB (~900 tokens) of contract text.
  On Codex a 480-byte reminder rides each turn; Claude and the other hosts have
  no per-turn hook, so their per-turn cost is zero. The full `tezgah-contract`
  skill (~18.2k characters) is paid only when a task loads it. On opencode the
  contract ships as a ~4.1 KB instructions file. opencode would otherwise
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

## Development

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
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

## License

The root `LICENSE` (MIT) covers tezgah's own files. `skills/ponytail` and
`skills/no-ai-slop` are vendored under their own MIT terms, recorded in
`NOTICE`.
