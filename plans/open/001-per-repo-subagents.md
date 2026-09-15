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
- [x] Capability-gated file generation for the two hosts with a real file
      surface: Claude `.claude/agents/*.md` and opencode `.opencode/agents/*.md`,
      only when that host is detected and the capability it needs is present.
      Proof: `tests/test_agents.py` (13 cases) in a throwaway HOME.
- [x] Idempotent: a second sync reports `current` and writes nothing (asserted).
- [x] Non-destructive: generated files carry a managed marker; `--uninstall`
      removes only those and leaves user-authored agent files untouched.
- [x] Auto-refresh: the managed file header carries a manifest hash and the repo
      stack is re-detected each session, so a source or repo change regenerates.
      Hosts run it from SessionStart; opencode from its plugin's first message
      (detached). Known limit: opencode may not pick up a brand-new `agents/` dir
      until the next session.
- [x] Prompt-only hosts (Codex, Cursor, dsh): deliberately NOT given a generated
      block. They have no file-based custom-agent surface, so a generated set
      would be dead weight; the existing router directive in the injected
      contract covers them (this mirrors the consult objection below).
- [x] `python3 -m unittest discover -s tests` (114) and `ruff check .` pass.

## State
Implemented on branch `plan/001-per-repo-subagents` (commits `4f8a944`,
`70ca07a`); not merged.
- New `hooks/tezgah_agents.py`: a single-source role manifest
  (explorer/reviewer gated on the graph, researcher on orx, verifier on the
  consult key) rendered per host, plus a `tezgah-orchestrator` agent. opencode's
  orchestrator is a primary agent with `permission.task {"*": deny, "tezgah-*":
  allow}`; Claude's uses `tools: Agent(tezgah-*)`.
- `hooks/tezgah_context.py` calls `sync_agents(root)` at SessionStart only, so
  every hook host generates; `bin/tezgah-agents` lets opencode's plugin do the
  same from its first-message path. `bin/tezgah-setup --agents [PATH]` triggers it
  on demand and `--uninstall` removes generated files via
  `~/.config/tezgah/agents.state.json`.
- Verified files written: `.claude/agents/tezgah-{explorer,reviewer,researcher,
  verifier,orchestrator}.md` and the same under `.opencode/agents/`. Re-running
  reports `current`; dropping orx removes the two researcher files; uninstall
  keeps a hand-written `my-own.md`.
- Resolution of the recorded risk: the leaky-abstraction objection (Gemini and
  Grok) is answered by emitting files only for the two file-surface hosts and
  keeping the shared action in one Python module with per-host frontmatter, not a
  host `if/else` in the setup oracle.

Research findings (verified earlier): Claude `.claude/agents/*.md` project
scope; opencode `.opencode/agents/*.md` + JSON `agent` key with `mode` and
`permission.task`; Codex and dsh have no observed file-based custom-agent surface.

## Next
Open a PR from `plan/001-per-repo-subagents`, then verify end to end in a real
Claude/opencode session in a non-tezgah repo before merging. Consider syncing the
generated set into the plugin `agents/` bundle so Claude needs no per-repo files
at all (that would drop the Claude half of the repo surface).
