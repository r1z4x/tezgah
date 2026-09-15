---
id: 001
title: Generate per-repo subagent definitions from detected infrastructure
status: open
branch: plan/001-per-repo-subagents
pr: 1
created: 2026-09-15
updated: 2026-09-15
---
## Goal
When tezgah is armed in a target repo (not its own checkout), detect that repo's
infrastructure and generate subagent definitions appropriate to it, kept
updatable. Infrastructure = both the target repo's stack/toolchain and the
machine's installed tooling (codebase-memory-mcp graph, orx, model key). Update =
regenerated when either the tezgah manifest or the repo's detected infra changes,
plus an explicit `--agents` trigger. The main thread stays the orchestrator/router
and delegates to the generated agents.

## Acceptance
- [x] Capability-gated generation into every host with a real custom-agent
      surface: Claude + Cursor `.claude/agents/*.md`, opencode `.opencode/agents/
      *.md` plus a live `config.agent` injection, Codex `.codex/agents/*.toml`.
      Proof: `tests/test_agents.py` (18 cases) in a throwaway HOME.
- [x] Idempotent: a second sync reports `current` and writes nothing (asserted).
- [x] Non-destructive: generated files carry a managed marker; `--uninstall`
      removes only those and leaves user-authored agent files untouched.
- [x] Auto-refresh: the managed file header carries a manifest hash and the repo
      stack is re-detected each session, so a source or repo change regenerates.
- [x] opencode same-session: the plugin `config` hook calls `tezgah-agents --json`
      and merges `config.agent` (a user agent of the same name wins), so a
      brand-new `.opencode/agents/` dir is no longer limited to the next session.
- [x] dsh: no role-level surface exists. Verified from `dsh-agent-presets`: the
      only authoring surface is whole-session presets (copy-only `agent.cordis.yml`
      compositions), not per-role subagents; the `subagent` tool takes a prompt.
      Covered by the existing router directive in the injected contract.
- [x] `python3 -m unittest discover -s tests` (118) and `ruff check .` pass. The
      opencode plugin `config` hook is exercised in node by a test.

## State
Implemented on branch `plan/001-per-repo-subagents` (commits `4f8a944`,
`70ca07a`, `e029221`, `df28788`, `72c9907`); PR #1 open, not merged.
- New `hooks/tezgah_agents.py`: one source-of-truth role manifest
  (explorer/reviewer gated on the graph, researcher on orx, verifier on the
  consult key) rendered per host format, plus a `tezgah-orchestrator`.
- `hooks/tezgah_context.py` calls `sync_agents(root)` at SessionStart only, so
  every hook host generates. opencode has no such hook, so its plugin injects the
  agents at `config` load (same session) and also spawns the file writer on the
  first message (fallback/versionable). `bin/tezgah-agents [--json] [PATH]` is the
  single CLI; `bin/tezgah-setup --agents [PATH]` triggers it; `--uninstall` removes
  generated files via `~/.config/tezgah/agents.state.json`.
- Corrected host capabilities (verified against docs): Codex custom agents are
  `.codex/agents/*.toml` (name/description/developer_instructions, plus
  `sandbox_mode`); Cursor subagents are `.cursor/agents/*.md` and it also reads
  `.claude/agents/` and `.codex/agents/`, so the `.claude/agents/` output serves
  Cursor too (`readonly: true` emitted for read-only roles). Claude's
  `Agent(agent_type)` allowlist in `tools` is valid and only takes effect when the
  agent runs as the main thread via `--agent`, which is exactly what the
  orchestrator is for.

### End-to-end verification (real CLIs, non-tezgah scratch repo)
- **opencode**: verified with the real binary, three ways — from
  `.opencode/agents/` files, from the `.claude/agents/` compatibility dir (opencode
  reads it), and with both dirs removed, where the plugin `config` hook still
  injected all five agents in-session. `opencode agent list` / `debug agent`
  report `tezgah-explorer (subagent)` and `tezgah-orchestrator (primary)` with the
  `tezgah-*` task allowlist.
- **Codex**: verified with the real binary — `codex exec` (gpt-5.5) listed the four
  custom agents `tezgah-{explorer,reviewer,researcher,verifier}` from
  `.codex/agents/`.
- **Claude**: `claude plugin validate .claude/agents` reports `Validation passed`
  (offline; login not required). A live session was not run — the installed Claude
  is logged out (`claude auth status` -> loggedIn false).
- **Cursor**: reads `.claude/agents/` per the official docs; a live check was not
  run because `cursor-agent status` reports not logged in. Not runtime-verified.
- **dsh**: no per-role surface; nothing to generate.

### Bug found and fixed by this verification
The first e2e run made opencode reject the whole config: the Claude-format
orchestrator (`tools: Agent(...)`) was being written into `.opencode/agents/`, and
opencode validates `tools` as an object. opencode markdown now renders native
frontmatter (`mode` + `permission`, no `tools` string); commit `72c9907`, guarded by
a test. An earlier commit also restored a lost `AGENTS_BIN` const in the plugin
(`df28788`).

## Next
Merged when PR #1 is green. Remaining: a live Cursor (and for completeness a live
Claude) session check, both blocked on login only; and decide whether to keep the
now-redundant `.opencode/agents/` files or drop them in favour of the plugin hook.
