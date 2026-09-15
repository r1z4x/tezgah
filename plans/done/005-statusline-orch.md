---
id: 005
title: Colored, self-explaining status line and event-driven refresh
status: done
branch: plan/005-statusline-orch
pr: 5
created: 2026-09-15
updated: 2026-09-15
---
## Goal
Make the status line show state, not just a glyph: color `✓/○/✗` and `idx`, add
a legend so `○` is not misread as "off", drive it from host events instead of a
5s poll where the host exposes an event bus, and fix the orchestration gaps found
in the same review.

## Acceptance
- [x] Generated `.claude/.opencode/.codex` agent bodies contain no bare
      `bin/consult` / `orx`; the verifier carries the absolute `consult` path and
      the researcher the resolved orx. `tests/test_agents.py`.
- [x] `tezgah-status --json` returns the segments; `--legend` explains the
      glyphs; `--color` forces ANSI and `--no-color`/`NO_COLOR` strips it.
      `tests/test_context.py`, `tests/test_statusline.py`.
- [x] Core is one structured source: `health_segments()`, with `health_lines()`
      kept as the plain renderer so every host and the old tests are unchanged.
- [x] opencode TUI refreshes on the host event bus (message parts, session
      state, permissions) with a slow safety timer, colors segments from the
      theme, and opens a legend dialog from a command.
- [x] dsh Web UI serves `?format=json`, renders colored spans with a hover/click
      legend, and stops refreshing while the tab is hidden.
- [x] `.gitignore` gets one idempotent managed block for the generated agent
      dirs; `--uninstall` strips the block and keeps user content.
- [x] `research` is recorded when a Bash command runs `orx` (Codex, Cursor,
      opencode classifiers).
- [x] `python3 -m unittest discover -s tests` (139) and `ruff check .` pass.

## State
Implemented on branch `plan/005-statusline-orch` (commit `8a98fee`); not merged.

What changed and where:
- `hooks/tezgah_context.py`: `health_segments()` (state in on/ready/off/info),
  `render_line()`, `COLORS`/`GLYPHS`, `LEGEND`; `health_lines()` now renders the
  segmented source, so its plain string is byte-identical to before.
- `bin/tezgah-status`: `--color|--no-color|--json|--legend`.
- `statusline.py` (Claude/Cursor): colored output with `NO_COLOR` /
  `TEZGAH_STATUS_COLOR=0` opt-out and an optional `TEZGAH_STATUS_LEGEND=1` second
  line.
- `hosts/opencode/tui/tezgah-tui.tsx`: event-driven (no 5s poll), theme colors,
  legend dialog behind a command.
- `hosts/dsh/statusline/lib/{index,client}.js`: `?format=json`, colored spans,
  popover legend, visibility-gated refresh.
- `hosts/{codex,cursor}/hook.py`, `hosts/opencode/plugins/tezgah.js`: record
  `research` for `orx`.
- `hooks/tezgah_agents.py`: absolute CLI paths in the bodies; managed
  `.gitignore` block, stripped on cleanup.
- README: status-line section (marks, colors, per-host surface) and a per-repo
  subagents bullet with the Claude `Agent(...)` main-thread caveat.

Known limits (documented, not fixed):
- Codex `systemMessage` ANSI rendering is unverified, so it stays plain text.
- The opencode TUI and dsh Web renderers are not run in CI; their Python/JS
  syntax is checked, the runtime needs a live session.
- dsh has no used-mark recorder, so its `cbm/consult/orch` stay on-demand (`○`).

## Next
Merged in PR #5 (`ba9cd34`). Verify in a live opencode session that the TUI colors
and the legend command work, and confirm Cursor picks up `.claude/agents/`.
