# Tezgah

The working contract for the repositories you point it at, packaged as a Claude
Code plugin. Installing it arms the whole thing; disabling it removes the whole
thing. It is inert everywhere outside its configured roots.

## What it arms

| Component | Effect |
|---|---|
| `hooks/projects-auto-init.py` | SessionStart, UserPromptSubmit, SubagentStart and PostCompact. Injects the code-graph rule, the workflow menu, the orchestration contract, the ponytail code style, the Turkish reporting contract, the consult rule, and the open-plan list. Inert outside the configured roots. |
| `hooks/projects-pretooluse.py` | PreToolUse on `Agent\|Task\|Grep\|Bash`. Denies the Explore subagent in this tree and nudges the first identifier-shaped search of a session — `Grep` or a `grep`/`rg` inside a Bash command — toward the code graph. |
| `hooks/tezgah_paths.py` | Shared resolver: which roots are armed, where `codebase-memory-mcp` is, whether a consult key exists. |
| `bin/tezgah-setup` | Reports and wires the parts a plugin install cannot do by itself. |
| `skills/` | `harness`, `ponytail`, `plan-add`, `plan-status`, `plan-sync`, `no-ai-slop` |
| `bin/consult` | Second opinion from independent models through OpenRouter |
| `bin/codegen` | Bounded code drafts from a cheap model; prints a diff, writes nothing |
| `workflows/` | `cbm-map`, `cbm-review`, `cbm-impact` graph harnesses |
| `statusline.py` | The `pony✓ exec✓ · consult○ cbm○ orch○ · plans N` segment |

## Install

```bash
git clone <this repo> ~/Projects/tezgah        # anywhere; the path is not baked in
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
~/Projects/tezgah/bin/tezgah-setup --install   # or --roots ~/work:~/oss --install
```

`tezgah-setup` writes the root list, links the status line and the three
workflow scripts, and then prints what is still missing. With no arguments it
only reports, so it is also the "why is nothing happening here" check:

```
wiring:
    ok   config /Users/you/.config/tezgah/config.json
    ok   statusline symlink
   MISS  statusLine in settings.json
    ok   workflows in ~/.claude/workflows
    ok   consult/codegen on ~/.claude/bin
    ok   codebase-memory-mcp on PATH
   MISS  OpenRouter key (consult/codegen)
```

The one thing it deliberately will not touch is your `~/.claude/settings.json`;
it prints the line to paste:

```json
"statusLine": { "type": "command", "command": "python3 \"$HOME/.claude/statusline.py\"" }
```

## Where it is armed

Resolution order, in `hooks/tezgah_paths.py`:

1. `TEZGAH_ROOTS` — `os.pathsep`-separated, for CI and one-offs
2. `~/.config/tezgah/config.json` → `{"roots": ["~/work", "~/oss"], "cbm_bin": "..."}`
3. `~/Projects`, so an existing setup keeps working untouched

Hooks are spawned by the app and not by an interactive shell, so an env var set
in `.zshrc` may never reach them; the config file is the reliable channel.

Everything degrades instead of breaking. No `codebase-memory-mcp` on PATH: the
session is told there is no graph and to say so rather than pretend the index
answered. No OpenRouter key: the consult block is replaced by one that forbids
claiming an external check happened. Neither case is a crash and neither is
silent.

## Editing it

Installing COPIES the plugin into `~/.claude/plugins/cache/rizacan-local/tezgah/<version>/`,
and `claude plugin update` compares versions rather than content. Editing the
source alone changes nothing:

```bash
# bump "version" in BOTH .claude-plugin/plugin.json and .claude-plugin/marketplace.json
claude plugin marketplace update rizacan-local
claude plugin update tezgah
# then start a new session
```

While iterating, `bin/tezgah-setup --sync` copies the checkout straight over the
installed copy without a version bump. It is a development shortcut: it does not
update what `claude plugin list` reports, and a new session is still required.

`claude plugin validate .claude-plugin/plugin.json` checks the manifest;
`claude plugin details tezgah` prints the component inventory and the
token cost the plugin adds to every session.

## Kill switches

Per machine, in `~/.claude/`: `ponytail-auto.off`, `exec-mode.off`, `consult-off`,
`orchestrate-off`, `reminder-off`, `pretooluse-off`.
Per repository, at its root: `.no-ponytail`, `.no-cbm`.

## Not part of this

The MCP server `codebase-memory-mcp` stays declared in `~/.claude.json`. A plugin
can declare MCP servers, but the tools would be renamed `mcp__plugin_tezgah_...`,
and every rule and skill here names the current tools. Installing the server
itself is also on you; `tezgah-setup` only reports whether it found it.

Orca's hooks, its four symlinked skills and its status line script are not ours
and are untouched.

## Third-party material

`skills/ponytail` and `skills/no-ai-slop` are vendored MIT skills and keep their
own terms; see `NOTICE`. The root `LICENSE` covers tezgah's own files.
