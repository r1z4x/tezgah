---
id: 001
title: Generate per-repo subagent definitions from detected infrastructure
status: open
branch: plan/001-per-repo-subagents
pr:
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
      Proof: `tests/test_agents.py` (16 cases) in a throwaway HOME.
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
- [x] `python3 -m unittest discover -s tests` (117) and `ruff check .` pass. The
      opencode plugin `config` hook is exercised in node by a test, so a lost
      const or a broken spawn fails the suite, not only the Python side.

## State
Implemented on branch `plan/001-per-repo-subagents` (commits `4f8a944`,
`70ca07a`, `e029221`, `df28788`); PR #1 open, not merged.
- New `hooks/tezgah_agents.py`: one source-of-truth role manifest
  (explorer/reviewer gated on the graph, researcher on orx, verifier on the
  consult key) rendered per host format, plus a `tezgah-orchestrator`.
- `hooks/tezgah_context.py` calls `sync_agents(root)` at SessionStart only, so
  every hook host generates. opencode has no such hook, so its plugin injects the
  agents at `config` load (same session) and also spawns the file writer on the
  first message (fallback/versionable). `bin/tezgah-agents [--json] [PATH]` is the
  single CLI; `bin/tezgah-setup --agents [PATH]` triggers it; `--uninstall` removes
  generated files via `~/.config/tezgah/agents.state.json`.
- Corrected host capabilities (verified against docs this round): Codex custom
  agents are `.codex/agents/*.toml` requiring name/description/
  developer_instructions; Cursor subagents are `.cursor/agents/*.md` and it also
  reads `.claude/agents/` and `.codex/agents/` (so the `.claude/agents/` output
  serves Cursor too, and `readonly: true` is emitted for the read-only roles).
- Verified in a throwaway HOME: four roles written to `.claude/agents/` (md),
  `.opencode/agents/` (md), `.codex/agents/` (toml, all four parse with a TOML
  parser, required fields present, read-only roles get `sandbox_mode =
  "read-only"`); `.opencode` JSON exposes the four subagents plus the orchestrator
  with `permission.task {"*": deny, "tezgah-*": allow}`; Cursor writes no separate
  dir; re-running reports `current`; dropping orx removes the researcher files;
  uninstall keeps a hand-written `my-own.md`.
- Resolution of the recorded risk: the leaky-abstraction objection (Gemini and
  Grok) is answered by rendering one shared role manifest into each host's native
  format in one module, not a host `if/else` in the setup oracle, and by NOT
  inventing a surface for dsh.

## Next
Open a PR from `plan/001-per-repo-subagents`, then verify end to end in a real
session per host (at least Claude, opencode, Codex) in a non-tezgah repo: confirm
the agents appear and the Cursor `.claude/agents/` compatibility actually loads.
