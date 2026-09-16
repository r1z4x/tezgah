# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-09-16

First tagged release: one shared working contract for Claude Code, Codex,
Cursor, opencode, dsh and omp.

### Added

- Task-class arming: the advisory rules (spec-first, second-opinion consult,
  OpenResearch routing, code-graph-first) are expanded per prompt from the
  per-turn hook, wired for Claude, Codex, Cursor and dsh. Their invariants and
  the irreversible-actions safety rule stay always-on, every advisory rule keeps
  an actionable one-line pointer, and the per-prompt decision is audited to
  `~/.cache/tezgah/classify.log` (armed set and prompt length, no text).
- `omp` (oh-my-pi) host: `~/.omp/agent` gets a managed `RULES.md` always-on
  block, skills, generated subagents, an `mcp.json` and a `hooks/pre` gate.
- Always-on context-budget report from `tezgah-setup`.
- tezgah-vs-oh-my-pi harness benchmark under `benchmarks/`.
- README translations and a logo, plus the community-health files.

### Changed

- opencode's generated skill router keeps only the coding buckets always-on and
  points at `opencode-skills.full.md` for the rest: about 20.5 KB → 7 KB of
  instructions per session.

[0.9.0]: https://github.com/r1z4x/tezgah/releases/tag/v0.9.0
