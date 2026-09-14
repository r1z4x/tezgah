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
  `bin/consult` asks independent models through OpenRouter in parallel and the
  agent reports where they agreed or disagreed.
- **Honesty under verification.** Nothing is reported done, tested, or fixed
  unless the output was seen. A failing test is reported as failing with its
  exact error, and a skipped check is stated plainly.
- **No AI attribution, anywhere.** Nothing persisted or published — commit,
  merge, and tag messages, PR and issue text, code comments, file headers, docs
  — may credit the assistant, model, vendor, or "AI". Using a tool is fine;
  signing its name to your work is not.
- **Two-tier orchestration.** The main thread decides and verifies; a cheap
  OpenRouter model (`bin/codegen`) drafts bounded, well-specified edits to a
  scratch directory. Nothing reaches the repo except through the router, and a
  failed draft falls back to the main model automatically.

## Supported hosts

| Host | Wired by | Status line |
|---|---|---|
| **Claude Code** | local plugin marketplace: hooks, commands, two read-only agents, output style | native `statusLine` |
| **opencode** | plugin + instructions + MCP + skills | TUI plugin (no command statusLine) |
| **Codex** | `hooks.json` + skills + MCP, including a `PreToolUse` gate | hook `systemMessage` (footer item list is closed) |
| **Cursor** | `hooks.json` + skills + MCP | `statusLine` in `cli-config.json` |
| **dsh** | Claude Code hook bridge + managed patch block | not yet — a UI plugin is needed and is unpackaged |

The Codex gate runs Bash, `exec_command`, `apply_patch`, Edit/Write, MCP tools,
and subagent calls through the same check as the other hosts. On Claude, the
attribution ban is enforced mechanically too: the `attribution` setting is
emptied (`commit`, `pr`, `sessionUrl`) so commit and PR credits are off at the
source.

The Claude plugin also ships two read-only agents. `agents/tezgah-explorer.md`
does code discovery from the graph and returns `file:line` evidence;
`agents/tezgah-reviewer.md` turns a diff into its impact set with
`detect_changes` and then looks for real defects. Both have write and command
tools disabled; their output is advisory.

## Install

Requires Python 3.8+. Both optional integrations degrade gracefully:
`codebase-memory-mcp` on PATH powers the graph, and an OpenRouter key
(`OPENROUTER_API_KEY` or `~/.config/openrouter/key`) powers `consult` and
`codegen`. When either is missing, tezgah says so instead of pretending.

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

Kill switches live in `~/.config/tezgah/`:
`exec-mode.off`, `orchestrate-off`, `consult-off`, `ponytail-auto.off`, and
`reminder-off`. Per repo, `.no-ponytail` and `.no-cbm` opt out of the minimal-code
rule and the graph rule respectively.

## Cost

This is not free, and the numbers are measured, not estimated:

- **Context.** Roughly 12.5 KB (≈3,100 tokens) of contract text is added at
  session start. On Claude, a further ~1.3 KB reminder rides each turn.
- **Latency.** Session start adds ~12 ms on top of Python's ~19 ms baseline;
  the per-tool-call gate costs ~0.1 ms. Installation takes ~47 ms and is
  idempotent.
- **Disk.** Every file tezgah rewrites is first kept as `<file>.tezgah-bak`.

The payoff shows up on caller questions. In one real repo, a default `grep`
ignored the relevant folder and found nothing; with ignore disabled it took
3.95 s and still mixed definitions with call sites. The code graph answered the
same question in 16 ms, listing only the 8 true call sites.

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
part of this project and are left untouched.

## License

The root `LICENSE` (MIT) covers tezgah's own files. `skills/ponytail` and
`skills/no-ai-slop` are vendored under their own MIT terms, recorded in
`NOTICE`.
