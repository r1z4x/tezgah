# Orca: what it owns, what tezgah owns, where they meet

Orca is an IDE that runs agent sessions in its own terminals and worktrees.
This page is for a maintainer or an agent working inside Orca. Read it when a
session asks how tezgah and Orca share a machine. It describes Orca 1.4.221 and
1.4.222 as observed on 2026-10-07. Each Orca claim names the command or file
behind it, so a reader can check it again after a later release.

## How a process knows it runs in Orca

Every terminal Orca starts exports its own markers. The table lists the ones
tezgah reads, as `env` printed them inside an Orca terminal.

| Variable | Value shape | Read by |
|---|---|---|
| `ORCA_WORKTREE_ID` | `<repoId>::<absolute path>` of the Orca worktree | `hooks/tezgah_orca.py::session` |
| `ORCA_TERMINAL_HANDLE` | `term_<uuid>`, the handle `orca terminal` commands take | `hooks/tezgah_orca.py::session` |
| `ORCA_PANE_KEY` | `<tab>:<pane>` | `hooks/tezgah_orca.py::session` |
| `TERM_PROGRAM` | `Orca` | `hooks/tezgah_orca.py::session` |
| `ORCA_APP_VERSION` | `1.4.221` | `hooks/tezgah_orca.py::session` |
| `ORCA_CLI_COMMAND` | the wrapper Orca exports for WSL sessions (orca-cli skill) | `hooks/tezgah_orca.py::cli` |
| `ORCA_CLI_BIN_DIR` | `/Applications/Orca.app/Contents/Resources/bin` | `hooks/tezgah_orca.py::cli` |
| `CODEX_HOME`, `ORCA_CODEX_HOME` | `~/Library/Application Support/orca/codex-accounts/<id>/home` | `hooks/tezgah_paths.py::HOST_DIRS` (CODEX_HOME only) |

Orca also exports `ORCA_AGENT_HOOK_*` for its hook endpoint, port and token.
It exports `ORCA_OMP_*` for its omp status extension. tezgah reads none of
them and writes no `ORCA_*` variable. The marker set in `MARKERS` is the whole
contract.

A shell started from an Orca terminal inherits the variables. A subagent whose
working directory is a raw worktree still reports the parent's
`ORCA_WORKTREE_ID`. So the marker says "inside Orca", not "inside this
checkout".

## What Orca owns

| Surface | What Orca keeps | Evidence |
|---|---|---|
| Worktrees | a git worktree plus a card (status, comment, lineage, links), by default under `~/orca/workspaces/<repo>/<name>` | `orca worktree create --help`; `orca repo show` lists paths under `~/orca/workspaces/tezgah/` |
| Terminals | live PTYs with handles, read/send/wait | `orca terminal list --json` |
| Agent sessions | agent type and state per pane, shown in `orca worktree ps` | `agents[].agentType`, `agents[].state` in `orca worktree ps --json` |
| Orchestration | runs, tasks, dispatch, supervised workers, decision gates | `orca --help`, section Orchestration |
| Embedded browser | tabs per worktree, snapshot and element refs | `orca --help`, section Browser Automation |
| Artifacts | public HTML or Markdown links, off until a human enables them in Settings | `orca skills get orca-cli`, section Artifacts |
| Codex accounts | one codex home per account, marked by `.orca-managed-home` | the account home's directory listing |
| Its hooks | `~/.orca/agent-hooks/`, plus entries tagged `orca-agent-hook-form=1` in each managed codex `hooks.json` | the account home's `hooks.json` |
| omp extensions | `orca-agent-status.ts`, `orca-prefill.ts` and `orca-titlebar-spinner.ts` in `~/.omp/agent/extensions/` | that directory's listing |

The `orca-cli` skill is a stub. The full guide comes from the binary itself:
`orca skills get orca-cli`. Run it before any Orca command a session has not
run before.

## What tezgah owns

tezgah owns the contract text, the gate, the evidence ledger and the status
line. It also owns its own hook entries in each host config
([architecture](architecture.md), [hosts](hosts.md)). It does not create
worktrees or terminals in code. A parallel slice is an instruction to the
session: the `Tier 1` paragraph of `hooks/tezgah_policy.py::ORCHESTRATE`,
mirrored in `skills/tezgah-contract/SKILL.md`, and the orchestrator agent body
`hooks/tezgah_agents.py::_orch_body`.

## Where they meet

| Point | Behaviour | Code |
|---|---|---|
| Session start inside Orca | one `Orca:` line names the worktree and tells the session to use `orca worktree create`, `orca terminal create` and `orca worktree ps`. It reads env only and starts no process. | `hooks/tezgah_orca.py::context_line`, called from `hooks/tezgah_context.py::context_for` |
| Slice checkouts | inside Orca, `orca worktree create --name <slug> --parent-worktree active --json`, else `git worktree add` | `hooks/tezgah_policy.py::ORCHESTRATE`, `hooks/tezgah_agents.py::_orch_body` |
| Tracking | `tezgah-status --orca` lists each checkout Orca tracks (card, state, live terminals, agent states) and each git worktree Orca does not list | `bin/tezgah-status::print_orca`, `hooks/tezgah_orca.py::checkouts` |
| Install report | `tezgah-setup --status` prints one `orca:` line where Orca is present. The line names the runtime, the terminal and an Orca-managed CODEX_HOME. | `hooks/tezgah_orca.py::summary`, `bin/tezgah-setup::main` |
| Codex hooks | tezgah drops only entries holding `tezgah` and appends its own groups, so Orca's entries stay | `bin/tezgah-setup::install_codex` |
| Cursor hooks | the same merge | `bin/tezgah-setup::install_cursor` |
| Claude status line | tezgah's wrapper runs Orca's `~/.orca/agent-hooks/claude-statusline.sh` first and appends its own segment | `statusline.py::ORCA`, `bin/tezgah-setup::wire_claude_statusline` |
| Codex rules file | Orca links the account home's `AGENTS.md` to `~/.codex/AGENTS.md`. tezgah writes the managed block through that link with a plain `open`, so the link stays. | `bin/tezgah-setup::set_managed_md` |

### The collision this fixes

On 2026-10-07 the tezgah repository had eleven git checkouts and Orca listed
one. `git worktree list` printed the main checkout and ten under
`~/Projects/tezgah-wt/`, and `orca worktree list --repo path:<main> --json`
returned `totalCount: 1`. The ten came from raw `git worktree add`, so Orca
showed no card, terminal or agent state for them. `tezgah-status --orca` now
prints that gap.

A smoke run on the live runtime closed the loop. It ran `orca worktree create
--name tezgah-orca-smoke --parent-worktree active --setup skip --json` from the
main checkout. `tezgah-status --orca --json` then listed the new checkout as
tracked, with one terminal. `orca worktree rm --force` removed it, its branch
included.

### CODEX_HOME inside Orca

Inside Orca, CODEX_HOME names an Orca-managed account home. A `tezgah-setup
--install` run from an Orca terminal arms that home, and a run from another
terminal arms `~/.codex` (`hooks/tezgah_paths.py::HOST_DIRS`). On this machine
both homes carry tezgah's seven hook events. The Orca home keeps
Orca's own entries beside them. Orca also keeps
`.orca-hook-trust-provenance.json` there, keyed by event and entry index.
tezgah appends after Orca's entries, so Orca's index does not move. Whether
Orca re-trusts a changed tezgah entry on its own is not verified.

## What the Orca CLI does not offer

- No command adopts an existing raw git worktree as an Orca worktree. The
  `Worktrees` section of `orca --help` lists `list`, `show`, `current`,
  `create`, `set`, `rm` and `ps` only. `orca repo set --repo <sel>
  --external-worktree-visibility show` makes non-Orca worktrees visible in the
  sidebar. It does not give them cards.
- An agent cannot turn on artifact publishing. A human enables it in Settings
  (the `Artifacts` section of `orca skills get orca-cli`).

## Tests

`tests/test_orca.py` runs with no real Orca. A fake `orca` on disk answers
`worktree ps` and `status`, and every marker is a fixture. `tests/support.py`
strips the developer's own `ORCA_*` markers and `TERM_PROGRAM=Orca`, and pins
`TEZGAH_ORCA_BIN` to a missing path. Without that, a suite run inside Orca
would reach the live runtime.

## Source of truth

- `hooks/tezgah_orca.py`: detection, CLI resolution, the listing and both report lines
- `hooks/tezgah_context.py`: where the session line joins the session-start block
- `hooks/tezgah_policy.py`, `skills/tezgah-contract/SKILL.md`, `hooks/tezgah_agents.py`: the slice rule
- `bin/tezgah-status`, `bin/tezgah-setup`: the two report surfaces
- `tests/test_orca.py`, `tests/support.py`
