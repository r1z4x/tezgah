# Operations: install, upgrade, repair

This is the operator's page: how to arm tezgah, prove each
[host](glossary.md#host) is wired, and what to check first when one is not.
`bin/tezgah-setup` is the one entry point; what a host receives is
[hosts.md](hosts.md), what a session is told is [contract.md](contract.md).

## Installer flags

The parser's own arguments (`bin/tezgah-setup:2249-2272`); a bare run with no
argument prints the wizard on a terminal and the report on a pipe (`bin/tezgah-setup:2304-2307`).
Lines below are of `bin/tezgah-setup`; the early branches (`bin/tezgah-setup:2277-2297`) return
before an install is considered.

| Flag | What it does |
|---|---|
| `--install` | Arm the `--hosts` (default: every detected host): writes `~/.config/tezgah/config.json`, the contract hash, the `~/.config/tezgah/bin` symlinks and every host file, then prints the report. Installs the missing optional tools first unless `--no-deps` (`bin/tezgah-setup:2250`, `bin/tezgah-setup:2335-2336`, `bin/tezgah-setup:2217-2245`). |
| `--wizard` | Ask the install questions and write only after the final yes; the other flags supply the defaults, so `--wizard --hosts omp` asks only the rest (`bin/tezgah-setupbin/tezgah-setupbin/tezgah-setupbin/tezgah-setupbin/tezgah-setup:2259-2256`, `bin/tezgah-setup:2174-2203`). |
| `--report` | Print what is armed, per host, and stop (`bin/tezgah-setupbin/tezgah-setupbin/tezgah-setupbin/tezgah-setup:2259-2256`, `bin/tezgah-setup:1718-1751`). |
| `--refresh` | Re-render the generated opencode contract and skill router when the policy or `skills/tezgah-contract/SKILL.md` changed; prints the path it refreshed, else `contract is current` — also on a machine that was never installed, because the branch returns before it compares anything (`bin/tezgah-setupbin/tezgah-setupbin/tezgah-setup:2259-2256`, `bin/tezgah-setup:566-581`). |
| `--uninstall` | Remove only tezgah's own wiring, per host (`bin/tezgah-setupbin/tezgah-setup:2259`, `bin/tezgah-setup:1491-1497`). |
| `--adopt` | Move pre-tezgah wiring aside instead of deleting it; alone it stops there, with `--install` it runs first (`bin/tezgah-setupbin/tezgah-setup:2260`, `bin/tezgah-setup:1509-1571`). |
| `--sync` | Copy this checkout over every installed Claude plugin [copy](glossary.md#plugin-copy) (`bin/tezgah-setup:2259`, `:2001-2052`). |
| `--status [PATH]` | Print the armed/used checklist for PATH (default cwd) and stop — the same line as `bin/tezgah-status` (`bin/tezgah-setup:2260`, `bin/tezgah-setup:2283-2285`). |
| `--agents [PATH]` | Regenerate PATH's per-repo subagent set (default cwd); outside a [root](glossary.md#root) it prints `no agents generated` (`bin/tezgah-setupbin/tezgah-setup:2263-2262`, `bin/tezgah-setup:2293-2297`). |
| `--deps` | Install the missing optional tools and stop; with `--install` the install already does it (`bin/tezgah-setup:2263`, `bin/tezgah-setup:2286-2288`). |
| `--mcp-schemas` | Measure the MCP tool-schema band by asking each registered server (`initialize` + `tools/list`) and stop (`bin/tezgah-setupbin/tezgah-setup:2266-2265`, `bin/tezgah-setup:1674-1705`). |
| `--no-deps` | Skip the optional-tool install; `TEZGAH_NO_DEPS` is the same switch for CI (`bin/tezgah-setup:2266`, `bin/tezgah-setup:2323`). |
| `--devtools` | Also wire the optional Chrome DevTools MCP (`bin/tezgah-setupbin/tezgah-setupbin/tezgah-setup:2271-2268`). |
| `--dry-run` | Print what the optional-tool install would run, and run none of it (`bin/tezgah-setupbin/tezgah-setup:2271`). |
| `--version` | Print the plugin version and exit (`bin/tezgah-setupbin/tezgah-setup:2272`, `:131-147`). |
| `--roots R` | Set the roots for this install, `os.pathsep`-separated. Without `--install` it exits 1: `--roots only means something with --install` (`bin/tezgah-setup:2271`, `:2337`). |
| `--hosts H` | Comma-separated subset of `claude,codex,opencode,cursor,dsh,omp`; an unknown name exits 1 before anything is written, and naming hosts switches off the re-detection that follows a tool install (`bin/tezgah-setup:2272`, `:2296-2301`, `bin/tezgah-setup:2221-2228`). |
| `-h`, `--help` | Usage and the list above (`bin/tezgah-setup:2249`). |

## A first install

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah && bin/tezgah-setup --install
```

`--install` arms every host it detects; the optional integrations belong to the
[README's Install section](../README.md#install). On a terminal the bare
`bin/tezgah-setup` is the wizard: it asks which hosts, the roots, whether to
install the missing optional tools and whether to wire the DevTools MCP, prints
the plan, and writes only after a yes (`bin/tezgah-setup:2174-2203`). A pre-tezgah setup is
named under `predecessor wiring still present` and retired by `--adopt`
(`bin/tezgah-setup:1576-1588`); narrow it with `--hosts omp`, `--roots ~/work:~/oss`, `--dry-run`.

A successful run prints, in order: `dependencies:`, a line per missing optional
tool with the vendor command it runs — over the network, no sudo
(`:1105-1147`) — or `all optional tools present` (the run is appended to
`~/.config/tezgah/install.log`, `bin/tezgah-setup:1151-1191`); `installing for: <hosts>`
(`:2227`); the common block — config and roots, the contract sha, one `ok` line
per `~/.config/tezgah/bin` symlink, the app artifacts dir (`:346-386`);
`openresearch (orx):`, a line per host orx has a harness for (`bin/tezgah-setup:1075-1098`); one
`ok` line per link or write inside each host's block (`bin/tezgah-setup:389-1068` — a write that
met a real file in the way says so instead, `:187-207`); then the report and the
context budget table (`bin/tezgah-setup:1707-1751`). Its tail:

```text
omp:
    ok   status line answers
context budget (always-on text; ~tokens = chars/4):
     MCP tool schemas                   run --mcp-schemas to measure
```

## Verify: the report and `--status`

`--report` (or a piped bare run) answers one question per host: is it wired? It
prints the checkout, the roots and where they came from (`TEZGAH_ROOTS`, `config`
or `default`), a common block (config, the code-graph binary, a provider key,
`orx`, `npx`, the artifacts dir, `git`, the manifest, a stale-contract line), one
block per host, then the budget (`bin/tezgah-setup:1718-1751`). Each block is
`host_checks_<host>` (`bin/tezgah-setup:1941-1943`), and those rows are the source of truth for
"is this host armed" (`AGENTS.md:63-64`) — not the presence of a directory, and
not the status line. A row can read ` MISS ` too: claude's `plugin copy current`
row fails on a machine with no copy at all, because an absent copy is not a
current one (`:1761-1766`).

`--status [PATH]` answers a different question — which rules are in force in that
repo — as one line of marks rendered by the same code every status line uses
(`hooks/tezgah_context.py:1150-1215`, `hooks/tezgah_context.py:1246-1260`). Mark meanings are in
[status-line.md](status-line.md); `bin/tezgah-status` is that checklist with
`--json`, `--legend` and `--observable=`.

## Upgrading

The version lives in `.claude-plugin/plugin.json` when that untracked local
manifest is present, else in the newest `## [x.y.z]` heading of `CHANGELOG.md`
(`:131-147`); `.gitignore:18-19` is why it is not in the repository, and
`RELEASING.md:3-7` is how a release bumps it.

After a change to the contract text (`hooks/tezgah_policy.py`,
`hooks/tezgah_context.py`, `skills/tezgah-contract/SKILL.md`):

- `--install` re-renders every host file, the opencode contract and the skill
  router, and rewrites `~/.config/tezgah/contract.sha256` (`:152-187`,
  `bin/tezgah-setup:566-581`).
- `--refresh` does that for opencode alone, without a reinstall: opencode has no
  session-start hook, so its plugin calls it once per session when the stored
  hash no longer matches the source
  (`hosts/opencode/plugins/tezgah.js:1525-1528`).
- `--sync` copies the checkout over the Claude plugin copy, because Claude Code
  runs `~/.claude/plugins/cache/<owner>/tezgah/<version>/` and never this
  checkout (`bin/tezgah-setup:1980-2000`); `--install` refreshes a stale copy itself
  (`bin/tezgah-setup:2057-2063`). Then restart Claude — hooks are read once per session
  (`:2051`).

From the user's side a stale copy looks like this: Claude keeps applying the old
rules while `--report` shows ` MISS plugin copy current (hooks/tezgah_policy.py
matches)`. That row compares a sha256 of one file rather than the version number
both trees report, which is what lets it catch a copy that lags HEAD
(`bin/tezgah-setup:1969-2000`).

## Uninstall and adopt

`--uninstall` removes only tezgah-managed things: the `~/.config/tezgah/bin`
links and the generated repo agent files (`bin/tezgah-setup:1283-1289`), and per host the skill
symlinks, hook entries, managed blocks, MCP rows and status-line keys that host's
own installer wrote (`bin/tezgah-setup:1383-1484`). A symlink counts as tezgah's only when it
resolves inside this checkout, so a file you put in the same place is kept
(`bin/tezgah-setup:1196-1213`), and `~/.claude/settings.json` loses only the keys tezgah added
(`bin/tezgah-setup:1291-1306`). Kept: every non-tezgah file, every `<file>.tezgah-bak`
(`:227-233`, `:1494`), and the Claude plugin copy — no uninstaller touches
`~/.claude/plugins/cache`, so delete that by hand if Claude must stop loading
tezgah (see Safety). The orx skill shims come from orx's own installer, so they
are never listed for removal (`:1073-1085`).

`--adopt` moves, never deletes: `~/.codex/projects-harness`, the old codex bin
shims that exec'd it, `~/.claude/hooks/cbm-*`, and the hook entries in
`~/.codex/hooks.json` and `~/.claude/settings.json` that called them, all go to
`~/.config/tezgah/adopted/<timestamp>/` (`bin/tezgah-setup:1509-1571`). `predecessors()` is what
the report prints and what adopt retires (`bin/tezgah-setup:1576-1588`). Under the wizard adopt
waits for the yes: a declined plan leaves the predecessor wiring exactly where it
was (`bin/tezgah-setup:2313-2319`).

## Health pass: `tezgah-doctor`

`bin/tezgah-doctor` reports the two stores that grow without bound: opencode's
SQLite session/event database and codebase-memory-mcp's per-index logs
(`bin/tezgah-doctor:1-19`), read-only by default, with `--json` for a script.

| Invocation | What it does |
|---|---|
| `tezgah-doctor` | nothing: sizes, session and event counts, whether opencode is running, the two context-hygiene settings (`bin/tezgah-doctor:98-115`) |
| `tezgah-doctor --clean` | deletes index logs older than `--days` (default 7; `cbm-daemon.log` is never deleted, `:116-137`) and vacuums the database only when opencode is not running (`:139-149`, `:217-241`) |
| `tezgah-doctor --prune-sessions DAYS` | deletes sessions idle longer than DAYS through `opencode session delete`, then vacuums; skipped when opencode is running or its CLI is missing (`:151-189`, `:223-236`) |

`VACUUM` alone cannot shrink that database — its pages are all live — so
`--prune-sessions` is the action that actually reclaims space
(`bin/tezgah-doctor:9-11`).

## Troubleshooting

| Symptom | First check | Likely cause |
|---|---|---|
| A host shows no status line | `bin/tezgah-setup --report --hosts claude`, then `readlink ~/.claude/statusline.py` | that host's own rows read ` MISS `: the `statusline.py` symlink or the `statusLine` key (`bin/tezgah-setup:1754-1755`). For omp the row `status line answers` runs `hosts/omp/hook.py`, so it fails whenever the Python half cannot start (`bin/tezgah-setup:1881-1899`). codex has no status-line row at all — its surface is hooks, skills and MCP (`bin/tezgah-setup:1782-1801`) |
| A skill is missing in one host | `ls ~/.codex/skills/*/SKILL.md` (the host's skills dir is in [hosts.md](hosts.md)) | the link was never made: that host was not in the last `--hosts`. `bin/tezgah-setup --install --hosts codex` relinks it. Claude has no skills directory — it reads the plugin copy, so the row to read there is `plugin copy current` (`bin/tezgah-setup:1761-1766`) |
| A skill link dangles | `ls -lL ~/.omp/agent/skills/*/SKILL.md` | the link resolves to nothing: its source was renamed or removed, or the checkout moved. `skills_linked` asks for a readable `SKILL.md` precisely so this cannot read as linked (`bin/tezgah-setup:76-82`); `--install` relinks from what exists now |
| A rule still fires after its kill switch | `ls ~/.config/tezgah/*.off`, then `bin/tezgah-context user_prompt . < /dev/null` | the switch was flipped mid-session: the rule leaves the text injected from the next turn on, but text already in the context is not retracted (`hooks/tezgah_context.py:505-563`). On opencode it reaches the per-turn reminder and not the static `opencode-contract.md`, which is rendered by `always_on_core()` with no switch or mark filtering (`hooks/tezgah_context.py:565-573`, `bin/tezgah-setup:536-539`). A per-repo `.no-*` mark does the same job as a switch file (`hooks/tezgah_paths.py:45`, `:218-220`) |
| The status line is thinner outside the roots | `bin/tezgah-setup --status "$PWD"`, then `bin/tezgah-context session_start .` | by design, mostly: the line is global and only the per-repo `idx` and `plans` marks appear inside a root (`hooks/tezgah_context.py:1164-1166`), while the injected contract text is exactly what goes silent off-root (`bin/tezgah-context:21-22`). A line that is empty everywhere is wiring: see the first row |
| An agent cannot see the graph tools | `bin/tezgah-setup --report` — the common row `codebase-memory-mcp on PATH` and the host's own MCP row; then `which codebase-memory-mcp` | the binary is missing (it is the user's to install; `TEZGAH_CBM_BIN` or `config.json`'s `cbm_bin` can point at it, `hooks/tezgah_paths.py:195-198`), or the host's MCP row was overwritten and `--install --hosts <host>` rewrites it. `.no-cbm` in a repo turns the code-graph rule off there (`hooks/tezgah_context.py:1157`) |
| Claude keeps applying old rules | `bin/tezgah-setup --report --hosts claude` — the `plugin copy current` row; then `bin/tezgah-setup --sync` | the copy lags HEAD: Claude runs the copy, not the checkout. `--install` refreshes it too; restart Claude after either (`bin/tezgah-setupbin/tezgah-setup:2057-2063`, `:2051`) |

## Safety

Reversible and safe to repeat: every link and settings key it writes is
idempotent and re-created by `--install`; a file it overwrote is kept once as
`<file>.tezgah-bak` (`:227-233`); `--adopt` moves and prints the destination
(`:1507-1513`); `--uninstall` removes only symlinks resolving into this checkout
and tezgah's own entries (`bin/tezgah-setup:1196-1213`, `bin/tezgah-setup:1491-1497`); a bad write is undone with
`bin/tezgah-rollback <snapshot-id> [--force]`, reaching the pre-write bytes
through the id on the ledger's snapshot row (`bin/tezgah-rollback:1-13`,
[evidence.md](evidence.md)).

Not reversible, so do them deliberately: `--sync` deletes the plugin copy's
contents (bar `.git`) and copies the checkout over it (`bin/tezgah-setup:2028-2051`) — it refuses
a copy that holds this very checkout (`bin/tezgah-setup:2024-2027`) — and `--prune-sessions` and
`--clean` delete session rows and index logs. Two things this tool never does. It
never force-pushes, rewrites pushed history, deletes a repo or branch, applies a
migration to a live database, deploys, or touches a live account: those need the
user's explicit ask, and `bin/tezgah-consent --last` is how the user grants one
the [gate](glossary.md#gate) refused (`hooks/tezgah_policy.py:612-620`,
`bin/tezgah-consent:1-15`). And it never upgrades itself, or its optional tools
and config, on its own initiative (`hooks/tezgah_policy.py:621-629`).

## Source of truth

- `bin/tezgah-setup` — the parser, the install path, the per-host check rows,
  `--refresh`, `--sync`, `--adopt`, the uninstallers, the wizard.
- `bin/tezgah-doctor`, `bin/tezgah-rollback`, `bin/tezgah-status`,
  `bin/tezgah-context` — the health pass, the rollback, the checklist CLI, the
  injected text.
- `hooks/tezgah_paths.py`, `hooks/tezgah_context.py` — the paths and `off()`; the
  marks and the kill-switch filtering.
- `RELEASING.md`, `README.md`, `AGENTS.md`, `.gitignore`, `tests/test_setup.py` —
  the version rule, the install and configuration sections, the layer map, what
  stays untracked, and the behaviour these checks pin.
