# Operations: install, upgrade, repair

This is the operator's page: how to arm tezgah, prove each
[host](glossary.md#host) is wired, and what to check first when one is not.
`bin/tezgah-setup` is the one entry point; what a host receives is
[hosts.md](hosts.md), what a session is told is [contract.md](contract.md).

## Installer flags

The parser's own arguments (`bin/tezgah-setup:2247-2270`); a bare run with no
argument prints the wizard on a terminal and the report on a pipe (`:2303-2307`).
Lines below are of `bin/tezgah-setup`; the early branches (`:2275-2295`) return
before an install is considered.

| Flag | What it does |
|---|---|
| `--install` | Arm the `--hosts` (default: every detected host): writes `~/.config/tezgah/config.json`, the contract hash, the `~/.config/tezgah/bin` symlinks and every host file, then prints the report. Installs the missing optional tools first unless `--no-deps` (`:2248`, `:2333`, `:2215-2243`). |
| `--wizard` | Ask the install questions and write only after the final yes; the other flags supply the defaults, so `--wizard --hosts omp` asks only the rest (`:2249-2250`, `:2172-2202`). |
| `--report` | Print what is armed, per host, and stop (`:2251-2252`, `:1716-1748`). |
| `--refresh` | Re-render the generated opencode contract and skill router when the policy or `skills/tezgah-contract/SKILL.md` changed; prints the path it refreshed, else `contract is current` — also on a machine that was never installed, because the branch returns before it compares anything (`:2253-2254`, `:564-579`). |
| `--uninstall` | Remove only tezgah's own wiring, per host (`:2255`, `:1489-1495`). |
| `--adopt` | Move pre-tezgah wiring aside instead of deleting it; alone it stops there, with `--install` it runs first (`:2256`, `:1507-1573`). |
| `--sync` | Copy this checkout over every installed Claude plugin [copy](glossary.md#plugin-copy) (`:2257`, `:2001-2052`). |
| `--status [PATH]` | Print the armed/used checklist for PATH (default cwd) and stop — the same line as `bin/tezgah-status` (`:2258`, `:2281-2283`). |
| `--agents [PATH]` | Regenerate PATH's per-repo subagent set (default cwd); outside a [root](glossary.md#root) it prints `no agents generated` (`:2259-2260`, `:2291-2294`). |
| `--deps` | Install the missing optional tools and stop; with `--install` the install already does it (`:2261`, `:2284-2286`). |
| `--mcp-schemas` | Measure the MCP tool-schema band by asking each registered server (`initialize` + `tools/list`) and stop (`:2262-2263`, `:1672-1704`). |
| `--no-deps` | Skip the optional-tool install; `TEZGAH_NO_DEPS` is the same switch for CI (`:2264`, `:2321`). |
| `--devtools` | Also wire the optional Chrome DevTools MCP (`:2265-2266`). |
| `--dry-run` | Print what the optional-tool install would run, and run none of it (`:2267`). |
| `--version` | Print the plugin version and exit (`:2268`, `:131-147`). |
| `--roots R` | Set the roots for this install, `os.pathsep`-separated. Without `--install` it exits 1: `--roots only means something with --install` (`:2269`, `:2337`). |
| `--hosts H` | Comma-separated subset of `claude,codex,opencode,cursor,dsh,omp`; an unknown name exits 1 before anything is written, and naming hosts switches off the re-detection that follows a tool install (`:2270`, `:2296-2301`, `:2215-2231`). |
| `-h`, `--help` | Usage and the list above (`:2247`). |

## A first install

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah && bin/tezgah-setup --install
```

`--install` arms every host it detects; the optional integrations belong to the
[README's Install section](../README.md#install). On a terminal the bare
`bin/tezgah-setup` is the wizard: it asks which hosts, the roots, whether to
install the missing optional tools and whether to wire the DevTools MCP, prints
the plan, and writes only after a yes (`:2172-2202`). A pre-tezgah setup is
named under `predecessor wiring still present` and retired by `--adopt`
(`:1574-1589`); narrow it with `--hosts omp`, `--roots ~/work:~/oss`, `--dry-run`.

A successful run prints, in order: `dependencies:`, a line per missing optional
tool with the vendor command it runs — over the network, no sudo
(`:1105-1147`) — or `all optional tools present` (the run is appended to
`~/.config/tezgah/install.log`, `:1149-1191`); `installing for: <hosts>`
(`:2227`); the common block — config and roots, the contract sha, one `ok` line
per `~/.config/tezgah/bin` symlink, the app artifacts dir (`:346-386`);
`openresearch (orx):`, a line per host orx has a harness for (`:1073-1095`); one
`ok` line per link or write inside each host's block (`:387-1067` — a write that
met a real file in the way says so instead, `:187-207`); then the report and the
context budget table (`:1705-1748`). Its tail:

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
block per host, then the budget (`:1716-1748`). Each block is
`host_checks_<host>` (`:1939-1942`), and those rows are the source of truth for
"is this host armed" (`AGENTS.md:58-59`) — not the presence of a directory, and
not the status line. A row can read ` MISS ` too: claude's `plugin copy current`
row fails on a machine with no copy at all, because an absent copy is not a
current one (`:1761-1766`).

`--status [PATH]` answers a different question — which rules are in force in that
repo — as one line of marks rendered by the same code every status line uses
(`hooks/tezgah_context.py:1116-1181`, `:1212-1226`). Mark meanings are in
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
  `:564-579`).
- `--refresh` does that for opencode alone, without a reinstall: opencode has no
  session-start hook, so its plugin calls it once per session when the stored
  hash no longer matches the source
  (`hosts/opencode/plugins/tezgah.js:1420-1423`).
- `--sync` copies the checkout over the Claude plugin copy, because Claude Code
  runs `~/.claude/plugins/cache/<owner>/tezgah/<version>/` and never this
  checkout (`:1978-1999`); `--install` refreshes a stale copy itself
  (`:2055-2062`). Then restart Claude — hooks are read once per session
  (`:2051`).

From the user's side a stale copy looks like this: Claude keeps applying the old
rules while `--report` shows ` MISS plugin copy current (hooks/tezgah_policy.py
matches)`. That row compares a sha256 of one file rather than the version number
both trees report, which is what lets it catch a copy that lags HEAD
(`:1967-1999`).

## Uninstall and adopt

`--uninstall` removes only tezgah-managed things: the `~/.config/tezgah/bin`
links and the generated repo agent files (`:1281-1287`), and per host the skill
symlinks, hook entries, managed blocks, MCP rows and status-line keys that host's
own installer wrote (`:1381-1483`). A symlink counts as tezgah's only when it
resolves inside this checkout, so a file you put in the same place is kept
(`:1194-1213`), and `~/.claude/settings.json` loses only the keys tezgah added
(`:1289-1305`). Kept: every non-tezgah file, every `<file>.tezgah-bak`
(`:227-233`, `:1494`), and the Claude plugin copy — no uninstaller touches
`~/.claude/plugins/cache`, so delete that by hand if Claude must stop loading
tezgah (see Safety). The orx skill shims come from orx's own installer, so they
are never listed for removal (`:1073-1085`).

`--adopt` moves, never deletes: `~/.codex/projects-harness`, the old codex bin
shims that exec'd it, `~/.claude/hooks/cbm-*`, and the hook entries in
`~/.codex/hooks.json` and `~/.claude/settings.json` that called them, all go to
`~/.config/tezgah/adopted/<timestamp>/` (`:1507-1573`). `predecessors()` is what
the report prints and what adopt retires (`:1574-1589`). Under the wizard adopt
waits for the yes: a declined plan leaves the predecessor wiring exactly where it
was (`:2311-2317`).

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
| A host shows no status line | `bin/tezgah-setup --report --hosts claude`, then `readlink ~/.claude/statusline.py` | that host's own rows read ` MISS `: the `statusline.py` symlink or the `statusLine` key (`bin/tezgah-setup:1754-1755`). For omp the row `status line answers` runs `hosts/omp/hook.py`, so it fails whenever the Python half cannot start (`:1879-1897`). codex has no status-line row at all — its surface is hooks, skills and MCP (`:1780-1800`) |
| A skill is missing in one host | `ls ~/.codex/skills/*/SKILL.md` (the host's skills dir is in [hosts.md](hosts.md)) | the link was never made: that host was not in the last `--hosts`. `bin/tezgah-setup --install --hosts codex` relinks it. Claude has no skills directory — it reads the plugin copy, so the row to read there is `plugin copy current` (`bin/tezgah-setup:1761-1766`) |
| A skill link dangles | `ls -lL ~/.omp/agent/skills/*/SKILL.md` | the link resolves to nothing: its source was renamed or removed, or the checkout moved. `skills_linked` asks for a readable `SKILL.md` precisely so this cannot read as linked (`bin/tezgah-setup:76-82`); `--install` relinks from what exists now |
| A rule still fires after its kill switch | `ls ~/.config/tezgah/*.off`, then `bin/tezgah-context user_prompt . < /dev/null` | the switch was flipped mid-session: the rule leaves the text injected from the next turn on, but text already in the context is not retracted (`hooks/tezgah_context.py:479-536`). On opencode it reaches the per-turn reminder and not the static `opencode-contract.md`, which is rendered by `always_on_core()` with no switch or mark filtering (`:539-547`, `bin/tezgah-setup:536-539`). A per-repo `.no-*` mark does the same job as a switch file (`hooks/tezgah_paths.py:45`, `:218-220`) |
| The status line is thinner outside the roots | `bin/tezgah-setup --status "$PWD"`, then `bin/tezgah-context session_start .` | by design, mostly: the line is global and only the per-repo `idx` and `plans` marks appear inside a root (`hooks/tezgah_context.py:1130-1132`), while the injected contract text is exactly what goes silent off-root (`bin/tezgah-context:21-22`). A line that is empty everywhere is wiring: see the first row |
| An agent cannot see the graph tools | `bin/tezgah-setup --report` — the common row `codebase-memory-mcp on PATH` and the host's own MCP row; then `which codebase-memory-mcp` | the binary is missing (it is the user's to install; `TEZGAH_CBM_BIN` or `config.json`'s `cbm_bin` can point at it, `hooks/tezgah_paths.py:195-198`), or the host's MCP row was overwritten and `--install --hosts <host>` rewrites it. `.no-cbm` in a repo turns the code-graph rule off there (`hooks/tezgah_context.py:1157`) |
| Claude keeps applying old rules | `bin/tezgah-setup --report --hosts claude` — the `plugin copy current` row; then `bin/tezgah-setup --sync` | the copy lags HEAD: Claude runs the copy, not the checkout. `--install` refreshes it too; restart Claude after either (`bin/tezgah-setup:2055-2062`, `:2051`) |

## Safety

Reversible and safe to repeat: every link and settings key it writes is
idempotent and re-created by `--install`; a file it overwrote is kept once as
`<file>.tezgah-bak` (`:227-233`); `--adopt` moves and prints the destination
(`:1507-1513`); `--uninstall` removes only symlinks resolving into this checkout
and tezgah's own entries (`:1194-1213`, `:1489-1495`); a bad write is undone with
`bin/tezgah-rollback <snapshot-id> [--force]`, reaching the pre-write bytes
through the id on the ledger's snapshot row (`bin/tezgah-rollback:1-13`,
[evidence.md](evidence.md)).

Not reversible, so do them deliberately: `--sync` deletes the plugin copy's
contents (bar `.git`) and copies the checkout over it (`:2026-2049`) — it refuses
a copy that holds this very checkout (`:2022-2025`) — and `--prune-sessions` and
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
