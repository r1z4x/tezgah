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
updatable. Infrastructure = both the target repo's stack/toolchain (language,
test/lint/build commands) and the machine's installed tooling
(codebase-memory-mcp graph, orx, model key). Update = regenerated on `--install`
AND auto-refreshed when the target repo's detected infra changes. The main thread
stays the orchestrator/router and delegates to the generated agents.

## Acceptance
- [ ] Capability-gated file generation for the two hosts with a real file
      surface: Claude `.claude/agents/*.md` and opencode `.opencode/agents/*.md`,
      only when that host is detected and the capability it needs is present
      (graph / orx / model key). Proof: a test installs into a throwaway HOME and
      asserts the files exist with the expected frontmatter.
- [ ] Idempotent: a second `--install` changes nothing (test asserts byte-equal
      files and single occurrence of each managed marker).
- [ ] Non-destructive: generated files are tezgah-prefixed/marked; `--uninstall`
      removes only those and leaves user-authored agent files untouched.
- [ ] Prompt-only hosts (Codex, Cursor, dsh) receive an orchestrator prompt
      block, never files; generation degrades gracefully when a host has no file
      surface (observed: Codex `multi_agent=true` but no file-based custom-agent
      config; dsh has a single `subagent` tool).
- [ ] Auto-refresh path exists for repo-infra change, or is explicitly deferred
      to v2 with the reason recorded in State.
- [ ] `python3 -m unittest discover -s tests` and `ruff check .` both pass.

## State
Not started. Research findings, verified:
- Today tezgah injects the same static contract into every repo
  (`hooks/tezgah_policy.py:304` CORE) and ships only two static, read-only Claude
  agents via the plugin (`agents/tezgah-explorer.md`, `agents/tezgah-reviewer.md`).
- `bin/tezgah-setup:224` `detected()` only checks host presence, not repo/machine
  infra; `bin/tezgah-setup:367` and `:434` already generate per-host text
  (`opencode-contract.md`, `opencode-skills.md`) from a single source, which is
  the pattern to extend.
- Host file surfaces (verified against docs): Claude `.claude/agents/*.md`
  project scope, watched live, but a brand-new `agents/` dir needs a restart;
  opencode `.opencode/agents/*.md` + JSON `agent` key, with `mode:
  subagent|primary`, `permission.task` allowlist, and a primary `orchestrator`
  example. Codex and dsh have no observed file-based custom-agent surface.
- Constraint: tezgah currently writes nothing into target repos (only
  `~/.config`, `~/.cache`, host configs); this plan introduces that new surface
  and must stay uninstall-clean.
- Consult (Gemini 2.5 Pro + Grok 4.3) agreed on the strongest risk: the five
  hosts do not share a "subagent" concept, so one generator leaks per-host
  branching; Codex/dsh files would be dead weight, and runtime dynamic agent
  creation would be non-deterministic and would not load mid-session.

## Next
Design the capability-detection + manifest format: one source manifest in tezgah
mapping capability -> agent template, plus a `detect_infra(repo)` helper, before
writing any generator.
