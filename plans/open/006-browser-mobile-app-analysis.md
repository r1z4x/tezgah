---
id: 006
title: Browser and mobile app analysis, accessibility-first with screenshots on demand
status: open
branch: plan/006-browser-mobile-app-analysis
pr:
created: 2026-09-15
updated: 2026-09-15
---
## Goal
Let tezgah agents analyze a running web or mobile app with structured
accessibility / DOM / native view-tree interaction as the default, so a
screenshot is needed only when the tree is genuinely insufficient (canvas, game,
animation, visual regression). Adopt mature MCP servers instead of forking them,
and add a thin tezgah layer: per-host wiring, one `analyze-app` skill that
enforces the tree-first discipline, and an artifact policy.

## Acceptance
- [x] `bin/tezgah-setup` wires the browser + mobile MCP servers and reports them
      per host. The servers run through `npx` (no separate install), so the
      report gained an `npx` row and each host check gained an app-server row.
      Prove: `tests/test_setup.py::Install::test_apps_mcp_wired_optional_devtools_and_removable`.
- [x] `skills/analyze-app/SKILL.md` exists and appears in the generated opencode
      skill router. Prove: same test asserts `analyze-app` in the router body.
- [x] Web smoke: through the a11y tree, start Playwright MCP, navigate and read
      the snapshot with **zero** screenshots. `TEZGAH_E2E_APPS=1
      python3 tests/e2e_analyze_web.py` -> `OK` (run on this machine).
- [x] Mobile smoke: start Mobile MCP, assert the view-tree tools, list a device.
      `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` -> `OK`.
- [x] Screenshot only by explicit call: the web smoke left only a `.yml` a11y
      snapshot in the artifact dir, no image file.
- [x] Artifacts land in a configured dir (`~/.cache/tezgah/apps`, override
      `TEZGAH_ARTIFACTS`) and the tool returns a path, not inline bytes.
- [x] `python3 -m compileall -q hooks hosts bin statusline.py`,
      `python3 -m unittest discover -s tests` (145), `ruff check .` all pass.

## State
Decisions fixed with the user and a second opinion (`bin/consult`,
gemini-2.5-pro + grok-4.3, no failures):
- v1 targets web + iOS Simulator + Android emulator, web first.
- Adopt existing servers plus a thin tezgah layer; Playwright MCP is the primary
  web server, Chrome DevTools MCP the opt-in diagnostic secondary, Mobile MCP the
  mobile server.
- Isolated browser profile by default, optional CDP attach to the real Chrome.
- A11y-first is enforced in the skill, not by prompt alone; screenshot is a
  non-default, explicitly named action.

Observed facts (external, read this session): Playwright MCP drives pages from
the accessibility tree, "bypassing the need for screenshots"; Mobile MCP is
accessibility-first ("no image tokens, falling back to screenshots only when
needed") across iOS Simulator / Android emulator / real devices.

Implemented on `main` this session (not yet branched/committed at acceptance
time). What changed:
- `hooks/tezgah_apps.py` (new): one shared spec for the app MCP servers
  (`playwright`, `mobile-mcp`, optional `chrome-devtools`) plus the artifact dir.
- `bin/tezgah-setup`: renders that spec into opencode.json, Codex config.toml
  and Cursor mcp.json; `--devtools` adds the optional server; uninstall strips
  only tezgah's app tables (the code graph stays); host checks and the report
  gained app rows; `analyze-app` added to `SKILLS`; artifact dir created.
- `.mcp.json` at the plugin root (Claude plugin-provided MCP).
- `skills/analyze-app/SKILL.md`: the tree-first loop, isolated-profile default,
  on-demand screenshot, artifact + mobile caveats.
- `tests/_mcp_stdio.py`, `tests/e2e_analyze_web.py`,
  `tests/e2e_analyze_mobile.py`: opt-in real-server smokes (both ran `OK` here).
- `tests/test_setup.py`: wiring/idempotency/`--devtools`/uninstall + router test.
- README: accessibility-first bullet and an "App analysis" section.

Unverified / deferred:
- The Claude plugin `.mcp.json` is the idiomatic plugin path but was not loaded
  in a live Claude session here, so Claude MCP wiring is unverified.
- dsh app MCP wiring is intentionally absent (its MCP client config format for
  `npx` + args is unverified); the skill falls back to the server CLI there.
- No CI e2e: the smokes are opt-in and local only, matching the dsh one.

## Next
Commit this work on `plan/006-browser-mobile-app-analysis` (plan already on
`main`), then verify the Claude `.mcp.json` loads in a live Claude session and
decide whether to add dsh app-MCP wiring once its config format is confirmed.
