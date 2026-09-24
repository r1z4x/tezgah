# Operations: install, upgrade, repair

This is the operator's page: how to arm tezgah, prove each
[host](glossary.md#host) is wired, and what to check first when one is not.
`bin/tezgah-setup` is the one entry point; what a host receives is
[hosts.md](hosts.md), what a session is told is [contract.md](contract.md).

## Installer flags

The parser's own arguments (`bin/tezgah-setup:4018-4085`); a bare run with no
argument prints the wizard on a terminal and the report on a pipe (`bin/tezgah-setup:3738-3739`).
Lines below are of `bin/tezgah-setup`; the early branches (`bin/tezgah-setup:3704-3723`) return
before an install is considered.

| Flag | What it does |
|---|---|
| `--install` | Arm the `--hosts` (default: every detected host): writes `~/.config/tezgah/config.json`, the contract hash, the `~/.config/tezgah/bin` symlinks and every host file, then prints the report. Installs the missing optional tools first unless `--no-deps` (`bin/tezgah-setup:4197-4199`, `bin/tezgah-setup:4182-4192`, `bin/tezgah-setup:1951-2009`). |
| `--wizard` | Ask the install questions and write only after the final yes; the other flags supply the defaults, so `--wizard --hosts omp` asks only the rest (`bin/tezgah-setup:3199-3200`, `bin/tezgah-setup:3124-3149`). |
| `--report` | Print what is armed, per host, and stop (`bin/tezgah-setup:4204-4205`, `bin/tezgah-setup:2993-3071`). |
| `--refresh` | Re-render the generated opencode contract and skill router when the policy, the renderer (`hooks/tezgah_context.py`) or `skills/tezgah-contract/SKILL.md` changed; prints the path it refreshed, else `contract is current` — also on a machine that was never installed, because the branch returns before it compares anything (`bin/tezgah-setup:4111-4113`, `bin/tezgah-setup:3227-3230`, `:1053-1054`). |
| `--uninstall` | Remove everything tezgah installed — per host the wiring it wrote, plus (a full run) the Claude plugin copy with its registry rows, the generated config state, the kill switches, the caches and the versioned install tree — then verify the removal; nonzero exit while anything tezgah wrote survives (`bin/tezgah-setup:4143-4145`, `bin/tezgah-setup:2646-2722`). |
| `--adopt` | Move pre-tezgah wiring aside instead of deleting it; alone it stops there, with `--install` it runs first (`bin/tezgah-setup:3206`, `bin/tezgah-setup:2724-2815`). |
| `--sync` | Copy this checkout over every installed Claude plugin [copy](glossary.md#plugin-copy) (`bin/tezgah-setup:3207`, `bin/tezgah-setup:3664-3722`). |
| `--status [PATH]` | Print the armed/used checklist for PATH (default cwd) and stop — the same line as `bin/tezgah-status` (`bin/tezgah-setup:3208`, `bin/tezgah-setup:4117-4119`). |
| `--agents [PATH]` | Regenerate PATH's per-repo subagent set (default cwd); outside a [root](glossary.md#root) it prints `no agents generated` (`bin/tezgah-setup:3209-3210`, `bin/tezgah-setup:4127-4131`). |
| `--write-manifest` | Regenerate the tracked `MANIFEST` from `git ls-files` and stop — the release step, its only writer, and it says so on a tree with no `.git` rather than writing an empty listing (`bin/tezgah-setup:4032-4035`, `bin/tezgah-setup:3190-3207`). |
| `--deps` | Install the missing optional tools and stop; with `--install` the install already does it (`bin/tezgah-setup:4120-4122`, `bin/tezgah-setup:4120-4122`). |
| `--mcp-schemas` | Measure the MCP tool-schema band by asking each registered server (`initialize` + `tools/list`) and stop (`bin/tezgah-setup:4123-4125`, `bin/tezgah-setup:4123-4125`). |
| `--no-deps` | Skip the optional-tool install; `TEZGAH_NO_DEPS` is the same switch for CI (`bin/tezgah-setup:4037-4039`, `bin/tezgah-setup:4180`). |
| `--devtools` | Also wire the optional Chrome DevTools MCP (`bin/tezgah-setup:4038-4040`). |
| `--dry-run` | Print what the optional-tool install would run, and run none of it (`bin/tezgah-setup:4051-4054`). |
| `--prefix DIR` | Set the install prefix for this run: where a released artifact unpacks, and the second root a farm link may resolve into along with the checkout. It wins over `TEZGAH_PREFIX`, which wins over `$XDG_DATA_HOME/tezgah`, which wins over `~/.local/share/tezgah` (`bin/tezgah-setup:4056-4058`, `bin/tezgah-setup:4089-4100`, `bin/tezgah-setup:59-65`). |
| `--upgrade [VERSION]` | Move the install tree to VERSION (default: the newest release): `packaging/upgrade.sh` fetches it, checksum-verifies it, unpacks `<prefix>/<VERSION>` and flips `current`, then the installer re-runs **from the new tree**; `--dry-run` prints every step and runs none (`bin/tezgah-setup:4062-4066`, `bin/tezgah-setup:3940-3941`, `bin/tezgah-setup:3918-3966`). |
| `--version` | Print the plugin version and exit (`bin/tezgah-setup:4067-4072`, `:163-178`). |
| `--roots R` | Set the roots for this install, `os.pathsep`-separated. Without `--install` it exits 1: `--roots only means something with --install` (`bin/tezgah-setup:4069-4070`, `bin/tezgah-setup:4201`). |
| `--hosts H` | Comma-separated subset of `claude,codex,opencode,cursor,dsh,omp`; an unknown name exits 1 before anything is written, and naming hosts switches off the re-detection that follows a tool install (`bin/tezgah-setup:4071`, `bin/tezgah-setup:3780-3790`, `bin/tezgah-setup:4198`). |
| `-h`, `--help` | Usage and the list above (`bin/tezgah-setup:3124`). |

## Install from the artifact

What a user receives is a release tarball, not this checkout:
`dist/tezgah-<version>.tar.gz` beside `dist/tezgah-<version>.tar.gz.sha256`,
built by `packaging/build.sh` from the tracked `MANIFEST` plus a generated
`VERSION`, both written into the payload (`packaging/build.sh:4`,
`packaging/build.sh:61`, `packaging/build.sh:137`). A version unpacks at
`<prefix>/<version>` and `<prefix>/current` is a symlink to the active one, so a
team can stay on one version and a rollback is one tree away: the older version is
never removed, and going back is
`ln -sfn <prefix>/<previous> <prefix>/current` (`packaging/upgrade.sh:9-11`,
`packaging/upgrade.sh:98-117`). The prefix is `~/.local/share/tezgah` unless
`TEZGAH_PREFIX` or `$XDG_DATA_HOME` says otherwise (`packaging/upgrade.sh:61`),
and `bin/tezgah-setup --prefix DIR` wins over both (`bin/tezgah-setup:59-65`).
A farm link counts as tezgah's when it resolves into the checkout **or** into the
install root, which is what keeps an upgrade from orphaning the wiring
(`is_tezgah_link()`, `bin/tezgah-setup:1998-2011`).

| Step | Command |
|---|---|
| first install, POSIX | `curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/v<version>/packaging/install.sh \| sh -s -- --version <version>` |
| from a tarball you hold | unpack it, then `sh packaging/install.sh --version <version>` — it finds `upgrade.sh` beside itself (`packaging/install.sh:29-30`) |
| first install, Windows | `$env:TEZGAH_VERSION = '<version>'; irm https://raw.githubusercontent.com/r1z4x/tezgah/v<version>/packaging/install.ps1 \| iex` |
| upgrade | `bin/tezgah-setup --upgrade [VERSION]` from the installed tree, or `sh packaging/upgrade.sh --version X.Y.Z` |

`packaging/install.sh` is a bootstrap, never a second implementation: it runs
`packaging/upgrade.sh` — the one place a version is fetched, checksum-verified,
unpacked and made current — and then starts `bin/tezgah-setup --install` from the
tree that just became current (`packaging/install.sh:42-49`). `upgrade.sh`
compares the digest it fetched against the artifact before unpacking anything and
stops, printing both, on a mismatch (`packaging/upgrade.sh:86-94`).
`TEZGAH_DIST` points `upgrade.sh` and `install.ps1` at a directory holding
`tezgah-<version>.tar.gz` + `.sha256` instead of the release URL — the seam that
installs a locally built artifact with no published release, which is what CI
uses (`packaging/upgrade.sh:16-18`, `packaging/upgrade.sh:72-76`).

Windows goes through `packaging/install.ps1`, which assumes no `sh`, no `python3`
and no symlink privilege: it unpacks with the `tar.exe` that Windows 10 1803+
ships, materialises `current` as a directory junction, copies the tree where a
junction is refused, and starts the installer with the first of `py -3`,
`python`, `python3` it finds (`packaging/install.ps1:10-23`,
`packaging/install.ps1:126-150`).

An unpacked tree lists itself without git. `plugin_files()` reads `git ls-files`
in a checkout and falls back to the tracked `MANIFEST` where there is no `.git`; a
missing or empty manifest answers `None`, which is what makes `--sync` refuse
instead of emptying a copy it cannot refill (`plugin_files()`,
`bin/tezgah-setup:3475-3499`). `MANIFEST` is written by `--write-manifest`, its
only writer, from the same filter the reader applies — `managed()` — so the
listing and its reader cannot disagree (`managed()`, `bin/tezgah-setup:3464-3473`,
`write_manifest()`, `bin/tezgah-setup:3501-3517`). The payload also carries
`VERSION`, which is what a tree with no `.claude-plugin/` answers from
(`version()`, `hooks/tezgah_context.py:1431-1455`).

## A first install from a checkout

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah && bin/tezgah-setup --install
```

`--install` arms every host it detects; the optional integrations belong to the
[README's Install section](../README.md#install). On a terminal the bare
`bin/tezgah-setup` is the wizard: it asks which hosts, the roots, whether to
install the missing optional tools and whether to wire the DevTools MCP, prints
the plan, and writes only after a yes (`bin/tezgah-setup:3124-3149`). A pre-tezgah setup is
named under `predecessor wiring still present` and retired by `--adopt`
(`bin/tezgah-setup:2724-2815`); narrow it with `--hosts omp`, `--roots ~/work:~/oss`, `--dry-run`.

A successful run prints, in order: `dependencies:`, a line per missing optional
tool with the vendor command it runs — over the network, no sudo
(`:1200-1240`) — or `all optional tools present` (the run is appended to
`~/.config/tezgah/install.log`, `bin/tezgah-setup:1413-1420`); `installing for: <hosts>`
(`bin/tezgah-setup:3178`); the common block — config and roots, the contract sha, one `ok` line
per `~/.config/tezgah/bin` symlink, the app artifacts dir (`:394-429`);
`openresearch (orx):`, a line per host orx has a harness for (`bin/tezgah-setup:1347-1370`); one
`ok` line per link or write inside each host's block (`bin/tezgah-setup:464-1226` — a write that
met a real file in the way says so instead, `:223-242`); then the report and the
context budget table (`bin/tezgah-setup:2024-2050`, `bin/tezgah-setup:2409-2419`). Its tail:

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
block per host, then the budget (`bin/tezgah-setup:2744-2779`). Each block is
`host_checks_<host>` (`bin/tezgah-setup:2744-3109`), and those rows are the source of truth for
"is this host armed" (`AGENTS.md:73-74`) — not the presence of a directory, and
not the status line. A row can read ` MISS ` too: claude's `plugin copy current`
row fails on a machine with no copy at all, because an absent copy is not a
current one (`bin/tezgah-setup:3645-3663`).

`--status [PATH]` answers a different question — which rules are in force in that
repo — as one line of marks rendered by the same code every status line uses
(`hooks/tezgah_context.py:1299-1367`, `hooks/tezgah_context.py:1387-1395`). Mark meanings are in
[status-line.md](status-line.md); `bin/tezgah-status` is that checklist with
`--json`, `--legend` and `--observable=`.

## Upgrading

The version lives in `.claude-plugin/plugin.json` when that untracked local
manifest is present, else in the newest `## [x.y.z]` heading of `CHANGELOG.md`
(`bin/tezgah-setup:207-209`); `.gitignore:18-19` is why it is not in the repository, and
`RELEASING.md:3-7` is how a release bumps it.

An installed version moves with one command, and nothing moves it on tezgah's own
initiative: a session may not install, upgrade or restart tezgah's own
installation (`hooks/tezgah_policy.py:811-817`). `bin/tezgah-setup --upgrade
[VERSION]` runs `packaging/upgrade.sh --version V --prefix P`, then re-runs the
installer **from the new tree** — this process started from the old one, so its
farm links would point back into it — with the hosts and roots already in
`config.json`, so the install questions are not asked twice; the previous version
stays installed, so a rollback is a `current` flip (`upgrade()`,
`bin/tezgah-setup:3918-3966`). It is the flag's only caller: no other flag
upgrades tezgah as a side effect of another. `--upgrade --dry-run` prints the
fetch, the flip and the re-arm and runs none of the three
(`bin/tezgah-setup:3940-3941`).

After a change to the contract text (`hooks/tezgah_policy.py`,
`hooks/tezgah_context.py`, `skills/tezgah-contract/SKILL.md`):

- `--install` re-renders every host file, the opencode contract and the skill
  router, and rewrites `~/.config/tezgah/contract.sha256`
  (`bin/tezgah-setup:240-269`, `bin/tezgah-setup:797-812`).
- `--refresh` does that for opencode alone, without a reinstall: opencode has no
  session-start hook, so its plugin calls it once per session when the stored
  hash no longer matches the source
  (`hosts/opencode/plugins/tezgah.js:2313-2319`).
- `--sync` copies the checkout over the Claude plugin copy, because Claude Code
  runs `~/.claude/plugins/cache/<owner>/tezgah/<version>/` and never this
  checkout (`bin/tezgah-setup:3664-3722`); `--install` refreshes a stale copy itself
  (`bin/tezgah-setup:3724-3730`). Then restart Claude — hooks are read once per session.

From the user's side a stale copy looks like this: Claude keeps applying the old
rules while `--report` shows ` MISS plugin copy current (every copied file
matches)`. That row compares a sha256 over every tracked file `sync` copies —
not the version number both trees report, and not a single file: a one-file hash
cannot see a change to another hook, which is how a gate change once left the
installed copy running the previous rules while `--install` printed `ok`
(`bin/tezgah-setup:3645-3663`, `bin/tezgah-setup:3649-3655`). Recognising a copy
at all is still the presence of one file (`bin/tezgah-setup:3533-3548`).

## Uninstall and adopt

`--uninstall` removes everything tezgah installed, then proves the removal. The
run is **full** when it covers every host `config.json` records as armed, and
**partial** otherwise (`uninstall()`, `bin/tezgah-setup:2646-2722`). Both runs
take the host wiring back - the skill symlinks, hook entries, managed blocks,
MCP rows and status-line keys each host's own installer wrote
(`bin/tezgah-setup:2496-2644`), plus the farm links and the generated repo agent
files (`bin/tezgah-setup:2110-2116`). A link — or an entry the installer
materialised where a platform refuses symlinks — counts as tezgah's only when it
resolves inside this checkout or the install root, so a file you put in the same
place is kept (`is_tezgah_entry()`, `bin/tezgah-setup:2013-2019`), and
`~/.claude/settings.json` loses only the keys tezgah added
(`bin/tezgah-setup:2404-2426`).

A **full** run also takes everything the wiring was serving from:

- the Claude plugin copy under `~/.claude/plugins/cache` and its rows in
  `installed_plugins.json` — the tree Claude actually runs and the registry row
  that makes it keep loading both outlived every other removal, which is how an
  uninstalled tezgah kept applying its rules (`remove_plugin_copies()`,
  `bin/tezgah-setup:2138-2185`). A marketplace row sourced from a tezgah tree
  goes with them once nothing else installs from it.
- the `~/.config/tezgah` generated state: config, contract hash, install log,
  materialised ledger, the generated opencode files, and every kill switch —
  the canonical ones with the dir, the legacy `~/.claude` ones by name
  (`remove_generated_state()`, `bin/tezgah-setup:2214-2253`;
  `sweep_legacy_switches()`, `bin/tezgah-setup:2187-2212`).
- both state caches (`~/.cache/tezgah` and the sandbox fallback).
- the versioned install tree: every `<prefix>/<version>` carrying
  `bin/tezgah-setup` plus the `current` flip (`remove_install_tree()`,
  `bin/tezgah-setup:2255-2304`).

Kept in every run: the user's own files, every `<file>.tezgah-bak` backup
outside the config dir, `~/.config/tezgah/adopted/` (the only copy of the
predecessor wiring adopt moved aside), and every repository's `.tezgah/`
research state. A **partial** run also keeps config.json and the install tree,
because the hosts still armed read both at runtime, and says so. The orx skill
shims come from orx's own installer, so they are never listed for removal
(`bin/tezgah-setup:1687-1714`).

Every run ends in a verify pass that re-derives the removal from the filesystem
alone — one line per claim, and the exit code is 1 while anything tezgah wrote
survives (`verify_uninstall()`, `bin/tezgah-setup:2306-2494`), so a leftover can
never read as a clean uninstall. It ends by naming what needs a restart and, if
the checkout's own `.mcp.json` registers the tezgah MCP server, saying that
that file is the source tree's dev config, not an install artifact.
`tests/e2e_docker_cycle.py` makes the same claim in a clean container with an
independent path scan that imports nothing of tezgah's.

`--adopt` moves, never deletes: `~/.codex/projects-harness`, the old codex bin
shims that exec'd it, the older harness's `~/.claude/hooks/cbm-*` files (a
name that predates tezgah's own graph engine; the probe stays because
those files are the thing adopt has to retire), the hook entries in
`~/.codex/hooks.json` and `~/.claude/settings.json` that called them, and the
projects-harness marker block in a root's `AGENTS.md` — a block that points
every session at a POLICY.md inside the moved harness, so leaving it is leaving
a dead pointer — all go to `~/.config/tezgah/adopted/<timestamp>/`
(`bin/tezgah-setup:2724-2815`). `predecessors()` is what
the report prints and what adopt retires (`bin/tezgah-setup:2836-2857`). Under the wizard adopt
waits for the yes: a declined plan leaves the predecessor wiring exactly where it
was (`bin/tezgah-setup:3896-3902`).

## Health pass: `tezgah-doctor`

`bin/tezgah-doctor` reports the stores that grow without bound — opencode's SQLite
session/event database and each indexed repository's `.codegraph` database — and
the hosts' own state, which it never touches (`bin/tezgah-doctor:2-31`), read-only
by default, with `--json` for a script and `--coverage` for the files the graph
does not hold.

| Invocation | What it does |
|---|---|
| `tezgah-doctor` | nothing: sizes, session and event counts, whether opencode is running, the two context-hygiene settings, the `.codegraph` bytes and index presence per repository, and the three host state dirs (`bin/tezgah-doctor:138-158`, `:277-280`) |
| `tezgah-doctor --clean` | vacuums opencode's database, and only when opencode is not running (`:211-221`, `:315-339`) |
| `tezgah-doctor --coverage` | every tracked file the codegraph index does not hold, in two classes — a supported extension the index is missing, and a shebang-only script with no `.py` twin — with the file counts it read, so an empty result cannot read as "everything is covered" |
| `tezgah-doctor --prune-sessions DAYS` | deletes sessions idle longer than DAYS through `opencode session delete`, then vacuums; skipped when opencode is running or its CLI is missing (`:241-260`, `:304-316`) |

`VACUUM` alone cannot shrink that database — its pages are all live — so
`--prune-sessions` is the action that actually reclaims space
(`bin/tezgah-doctor:19-21`).

The coverage report exists because codegraph ships none: its `status` counts what
it parsed, never what it skipped, and the two ways a file goes missing are an
extension the engine has no parser for and an extensionless script it cannot key
on at all. The extensionless case is why `bin/*` carries `.py` twins, and the
report counts a tracked `bin/x` as covered when the index holds `bin/x.py`.

## Troubleshooting

| Symptom | First check | Likely cause |
|---|---|---|
| A host shows no status line | `bin/tezgah-setup --report --hosts claude`, then `readlink ~/.claude/statusline.py` | that host's own rows read ` MISS `: the `statusline.py` symlink or the `statusLine` key (`bin/tezgah-setup:2103-2104`). For omp the row `status line answers` runs `hosts/omp/hook.py`, so it fails whenever the Python half cannot start (`bin/tezgah-setup:2529-2548`). codex has no status-line row at all — its surface is hooks, skills and MCP (`bin/tezgah-setup:2419-2440`) |
| A skill is missing in one host | `ls ~/.codex/skills/*/SKILL.md` (the host's skills dir is in [hosts.md](hosts.md)) | the link was never made: that host was not in the last `--hosts`. `bin/tezgah-setup --install --hosts codex` relinks it. Claude has no skills directory — it reads the plugin copy, so the row to read there is `plugin copy current` (`bin/tezgah-setup:3645-3663`) |
| A skill link dangles | `ls -lL ~/.omp/agent/skills/*/SKILL.md` | the link resolves to nothing: its source was renamed or removed, or the checkout moved. `skills_linked` asks for a readable `SKILL.md` precisely so this cannot read as linked (`bin/tezgah-setup:81-86`); `--install` relinks from what exists now |
| A rule still fires after its kill switch | `ls ~/.config/tezgah/*.off`, then `bin/tezgah-context user_prompt . < /dev/null` | the switch was flipped mid-session: the rule leaves the text injected from the next turn on, but text already in the context is not retracted (`hooks/tezgah_context.py:554-618`). On opencode it reaches the per-turn reminder and not the static `opencode-contract.md`, which is rendered by `always_on_core()` with no switch or mark filtering (`hooks/tezgah_context.py:620-628`, `bin/tezgah-setup:759-796`). A per-repo `.no-*` mark does the same job as a switch file (`hooks/tezgah_paths.py:43`, `hooks/tezgah_context.py:1107-1123`) |
| The status line is thinner outside the roots | `bin/tezgah-setup --status "$PWD"`, then `bin/tezgah-context session_start .` | by design, mostly: the line is global and only the per-repo `idx` and `plans` marks appear inside a root (`hooks/tezgah_context.py:1356-1364`), while the injected contract text is exactly what goes silent off-root (`bin/tezgah-context:21-22`). A line that is empty everywhere is wiring: see the first row |
| An agent cannot see the graph tools | `bin/tezgah-setup --report` — the common row `codegraph on PATH` and the host's own MCP row; then `which codegraph` | the binary is missing (it is the user's to install; `TEZGAH_CODEGRAPH_BIN` or `config.json`'s `codegraph_bin` can point at it, `hooks/tezgah_paths.py:209-216`), or the host's MCP row was overwritten and `--install --hosts <host>` rewrites it. `.no-graph` in a repo turns the code-graph rule off there (`hooks/tezgah_context.py:1303`) |
| Claude keeps applying old rules | `bin/tezgah-setup --report --hosts claude` — the `plugin copy current` row; then `bin/tezgah-setup --sync` | the copy lags HEAD: Claude runs the copy, not the checkout. `--install` refreshes it too; restart Claude after either (`bin/tezgah-setup:3724-3730`, `bin/tezgah-setup:3720`) |

## Safety

Reversible and safe to repeat: every link and settings key it writes is
idempotent and re-created by `--install`; a file it overwrote is kept once as
`<file>.tezgah-bak` (`:278-285`); `--adopt` moves and prints the destination
(`bin/tezgah-setup:2724-2815`); `--uninstall` removes only tezgah's own entries — a
symlink resolving into this checkout or the install tree, or an entry the
installer materialised (`bin/tezgah-setup:2013-2019`, `bin/tezgah-setup:2021-2034`) — and prints
a verify pass whose nonzero exit says when anything survived; a bad write is
undone with
`bin/tezgah-rollback <snapshot-id> [--force]`, reaching the pre-write bytes
through the id on the ledger's snapshot row (`bin/tezgah-rollback:1-13`,
[evidence.md](evidence.md)).

Not reversible, so do them deliberately: `--sync` deletes the plugin copy's
contents (bar `.git`) and copies the checkout over it (`bin/tezgah-setup:3684-3719`) — it refuses
a copy that holds this very checkout (`bin/tezgah-setup:3676-3683`) — and `--prune-sessions` and
`--clean` delete session rows and index logs. Two things this tool never does. It
never force-pushes, rewrites pushed history, deletes a repo or branch, applies a
migration to a live database, deploys, or touches a live account: those need the
user's explicit ask, and `bin/tezgah-consent --last` is how the user grants one
the [gate](glossary.md#gate) refused (`hooks/tezgah_policy.py:802-809`,
`bin/tezgah-consent:1-15`). And it never upgrades itself, or its optional tools
and config, on its own initiative (`hooks/tezgah_policy.py:811-817`).

## Triage: `tezgah-triage` and the `judge-off` switch

One judgement seam serves three callers, each of them asking TypeSafe a batched
question instead of paying an agent to read a page: the analyze-app loop's snapshot
triage (`bin/tezgah-triage`), `bin/tezgah-docs` for a query its keyword index
cannot place, and the prompt-path skill hint (`hooks/tezgah_skill_pick.py`), the
one caller no shell row sees. All three go through the same stdlib-only seam,
which returns `None` rather than raising because a hook may import it
(`available()`, `hooks/tezgah_judge.py:88-92`); the request is
one batched call, and the credential resolves per call (`ask()`,
`hooks/tezgah_judge.py:93-126`; `key()`, `hooks/tezgah_judge.py:72-87`).

A transient failure is retried once, and only once: a timeout, a connection error
or a 5xx gets a second identical request, while a 4xx (a refused credential, a
rejected body) and a reply that parsed malformed are never retried, so a call that
worked is never billed twice. The rate was measured rather than assumed - 184 live
calls this round (60 at a small payload, 124 at the `--states` shape, 64 of those
eight-way concurrent) returned `None` zero times for $0.0105, against 2 of 50 seen
in one earlier `--states` run whose cells answered the same on retry; 0 of 184
bounds the steady rate at 1.6% (95%) and puts that earlier pair down to a transient
epoch rather than something this path meets every run, so the retry is there for
the epoch and costs the normal call nothing.

| Invocation | What it does |
|---|---|
| `tezgah-triage --select FILE --task "TEXT"` | flattens a `browser_snapshot` result (or the flattened text of one), takes the repeating units the tree marks - a row, a cell, a control on its own, and any line the tree does not mark standing alone (`units()`, `bin/tezgah-triage:204-229`) - asks one Noul per unit in one request, and prints the line ids under the selected units with their original `ref=` values, the unselected count and the characters that may now be skipped (`select()`, `bin/tezgah-triage:249-284`) |
| `tezgah-triage --states FILE [--component T]` | one judgement per state over a component's subtree - the 13 states the analyze-app contract names (`STATES`, `bin/tezgah-triage:64-68`), each question carrying what counts as shown, with the interactive pair (`focus`, `active`) asked as one three-way Choice (`neither` / `focus` / `pressed`) whose answer decides both rows, because an aria snapshot marks the focused element `[active]` and carries no separate mark for a press - so a state the tree does not show is a finding, and the five an aria snapshot cannot carry at all (default, hover, active, skeleton, long-text) are printed on their own `unmarked:` line instead of being counted as missing (`states()`, `bin/tezgah-triage:308-431`) |

The judgement is an aid, not the finding: it ranks units, the agent reads the
selected refs and still owns the claim. Its recall was measured this round rather
than assumed, on two reproduced screens: the unit selection kept 100% of the
control lines at a 94% read on a 356-line 40-row table and 100% at a 74% read on a
31-line 20-button screen, against 73.5% at a 26% read for one question per line.
The threshold those numbers were taken at is `SELECTED_AT` (`bin/tezgah-triage:63-65`),
and the tool prints the measurement with every run. Exit 1 means no judgement was
made - no credential, the switch below, or a failed call - and the loop reads the
tree directly instead.

The state leaves the machine. A judgement sends the state and the questions to
`api.typesafe.ai` (`ask()`, `hooks/tezgah_judge.py:93-126`) - for the triage that is
the snapshot's own text, so a screen carrying personal data is read by a third
party, and for the docs fallback it is the reader's query. Nothing else goes: no
session id, no workspace path, no credential beyond the bearer header, and the
state is not redacted because sending it is the point; the module docstring says
the same, and `tests/test_judge.py` pins the wire (`Egress`) so the prose and the
request cannot drift. That is why the two shell callers are on-demand - an agent
asks for a judgement, no gate does - while the skill hint asks only with its own
marker armed, and why the switch below is the off button for the whole path.

The credential resolves from `TYPESAFE_API_KEY`, else from
`~/.config/typesafe/key` (`credential()`, `hooks/tezgah_judge.py:150`), and when
neither resolves the same questions go to the OpenRouter fallback, whose key rides
`OPENROUTER_API_KEY` and then `~/.config/openrouter/key`
(`openrouter_key()`, `hooks/tezgah_judge.py:124`). The file is the channel that
matters on a machine exporting the variable from `~/.zshenv`: a hook or a bin tool
runs in a non-interactive shell, where that export never ran, so the file is what a
judgement actually resolves. Cost is input tokens alone - $0.042 per
1M, output billed at $0 - and every run prints the arithmetic it paid; the model
that answered is printed beside it, because the fallback answers with a chat model
rather than Jev (`result["model"]`, `bin/tezgah-triage:134`).

`judge-off` in `~/.config/tezgah` disarms all of it without touching the callers:
the snapshot is read the way the loop always read it, and a docs query matching no
page exits 1 with the message it always printed (`available()`,
`hooks/tezgah_judge.py:62-65`). A host whose files predate this tool is relinked by
`--install`, which links every `~/.config/tezgah/bin` entry including
`tezgah-triage` (`bin/tezgah-setup:449-471`).

## Source of truth

- `bin/tezgah-setup` — the parser, the install path, the per-host check rows,
  `--refresh`, `--sync`, `--adopt`, the uninstallers, the wizard, `--upgrade`.
- `packaging/build.sh`, `packaging/install.sh`, `packaging/upgrade.sh`,
  `packaging/install.ps1` — the artifact itself: the build from `MANIFEST` plus
  `VERSION`, the two installers, and the one fetch/verify/unpack/flip step.
  `tests/e2e_packaged_install.py` and `.github/workflows/ci.yml` install from the
  built tarball rather than the checkout, so the released shape is what CI proves.
- `bin/tezgah-doctor`, `bin/tezgah-rollback`, `bin/tezgah-status`,
  `bin/tezgah-context` — the health pass, the rollback, the checklist CLI, the
  injected text.
- `bin/tezgah-triage`, `hooks/tezgah_judge.py`, `bin/tezgah-docs` — the snapshot
  triage, the judgement seam all three callers share (the third is
  `hooks/tezgah_skill_pick.py`), and the docs fallback that uses it;
  `tests/test_judge.py`, `tests/test_triage.py` pin them against a loopback
  endpoint.
- `hooks/tezgah_paths.py`, `hooks/tezgah_context.py` — the paths and `off()`; the
  marks and the kill-switch filtering.
- `RELEASING.md`, `README.md`, `AGENTS.md`, `.gitignore`, `tests/test_setup.py` —
  the version rule, the install and configuration sections, the layer map, what
  stays untracked, and the behaviour these checks pin.
