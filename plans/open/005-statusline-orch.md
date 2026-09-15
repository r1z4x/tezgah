---
id: 005
title: Colored, self-explaining status line and event-driven refresh
status: open
branch: plan/005-statusline-orch
pr:
created: 2026-09-15
updated: 2026-09-15
---
## Goal
Make the status line show state, not just a glyph: color `✓/○/✗` and `idx`, add
a legend so `○` is not misread as "off", drive it from host events instead of a
5s poll where the host exposes an event bus, and fix the orchestration gaps found
in the same review.

## Findings this acts on
- `○` means "armed, unused this session", not off (`✗` is off); the report read
  `research○/cbm○/orch○` as broken. The glyphs need color + a legend.
- Generated agent bodies carry bare `bin/consult` / `orx`
  (`hooks/tezgah_agents.py`), the same bug plan 004 fixed in the contract.
- The five hosts never record `research`; dsh records no used-marks at all.
- Per-repo `.claude/agents`, `.codex/agents`, `.opencode/agents` are written but
  not ignored, so every repo shows them as untracked.

## Workstreams
1. **Core**: `health_segments(cwd, session_id, used_override)` -> structured
   `[(key, state, meas)]`, `state in {on, ready, off}`; `health_lines()` renders
   plain text on top of it (tests keep passing). One state->color table.
2. **CLI**: `bin/tezgah-status --color|--no-color|--json|--legend`.
3. **Bug**: agent bodies inject `tool("consult")` / `orx_bin() or "orx"`.
4. **Claude/Cursor**: `statusline.py` emits ANSI color (`NO_COLOR` honoured).
5. **opencode TUI**: use `api.event` (event bus) instead of the 5s poll, theme
   colors for state, a keybind that opens a legend/detail dialog.
6. **dsh web**: `?format=json` on the status route; colored spans + hover legend;
   visibility-gated refresh instead of an unconditional 5s poll.
7. **Codex**: try ANSI in `systemMessage`; fall back to plain state words.
8. **Consistency**: record `research` when a bash command runs `orx`; document
   that dsh has no used-mark recorder.
9. **Hygiene**: add a tezgah-managed `.gitignore` block for the generated agent
   dirs; `--uninstall` removes it.
10. **Docs/tests**: README legend + color table; new unit tests; `ruff`.

## Acceptance
- [ ] Generated `.claude/.opencode/.codex` agent bodies contain no bare
      `bin/consult` or `orx`.
- [ ] `tezgah-status --json` returns the segments; `--legend` explains the
      glyphs; `--no-color`/`NO_COLOR` strips ANSI.
- [ ] opencode TUI no longer polls: it refreshes on events and opens a legend
      dialog from a keybind.
- [ ] dsh web refresh stops while the tab is hidden.
- [ ] `.gitignore` gets one idempotent managed block and `--uninstall` removes it.
- [ ] `python3 -m unittest discover -s tests` and `ruff check .` pass.

## State
Not started.

## Next
Write the plan doc and create `plan/005-statusline-orch`, then start with the
core `health_segments()` change.
