---
name: analyze-app
description: >
  Analyze a running web or mobile app from its structured accessibility / DOM /
  native view tree instead of taking screenshots. Use when a task must drive,
  inspect, or verify a running application - walk a flow, read the UI, check the
  console, network or device logs, or confirm behavior end to end - rather than
  only read its source. Covers a real browser (Playwright MCP), an iOS Simulator
  or Android emulator (Mobile MCP), and optional web diagnostics (Chrome
  DevTools MCP).
---

# analyze-app

Drive the running app through its accessibility tree. A screenshot is an
on-demand action for what the tree cannot answer (canvas, game, animation,
pixel-level visual regression) - never a per-step default.

## Pick the target

| Target | Server | Tool prefix |
|---|---|---|
| Web page / webview | Playwright MCP | `browser_*` |
| iOS Simulator / Android emulator | Mobile MCP | `mobile_*` |
| Web perf / deep network / source-mapped console | Chrome DevTools MCP (opt-in) | `*` |

If the `browser_*` / `mobile_*` tools are not in this session, the server is not
wired for this host, or it failed to start: say so and fall back to the CLI on
the shell, with the same pins tezgah wires (`hooks/tezgah_apps.py`) -
`npx -y @playwright/mcp@0.0.81 --isolated` or
`npx -y @mobilenext/mobile-mcp@1.0.4`. Never `@latest`: a floating tag fetches
whatever the registry serves at session start and runs it with the agent's
privileges.

## The loop (tree first)

1. **Open** the target: `browser_navigate` / `mobile_launch_app`. On mobile,
   boot the simulator/emulator first and confirm with
   `mobile_list_available_devices`.
2. **Read the tree, do not screenshot**: `browser_snapshot` (web) or
   `mobile_list_elements_on_screen` (mobile). Act on the returned element
   references, not on coordinates.
3. **Act**: `browser_click`, `browser_fill_form`, `browser_press_key`,
   `browser_evaluate`; `mobile_click_on_screen_at_coordinates`,
   `mobile_type_keys`, `mobile_swipe_on_screen`, `mobile_press_button`.
4. **Observe after every change**: `browser_console_messages`,
   `browser_network_requests`, `mobile_get_device_logs`, `mobile_list_crashes`.
   Re-read the tree instead of taking a screenshot.
5. **Screenshot only when the tree is insufficient**, and name the reason:
   `browser_take_screenshot` or `mobile_save_screenshot`. Reference the saved
   path; never paste image bytes into the conversation.

## Browser profile

Isolated by default, so a run never touches the user's real Chrome state. To
analyze a logged-in flow, attach deliberately - `--cdp-endpoint` or the
Playwright extension instead of the isolated default - and say so before doing
it, because it exposes the real session to the analysis.

## Artifacts

Screenshots, traces and tree dumps go to the app artifact directory
(`PLAYWRIGHT_MCP_OUTPUT_DIR`, default `~/.cache/tezgah/apps`). Return the file
path; keep image tokens out of the context.

## Mobile caveats

macOS may prompt for Accessibility / Screen-Recording permission on first use,
and a real iOS device needs Developer Mode. The view tree can drop under load:
retry the tree once, then fall back to a screenshot. iOS/Android tooling version
skew is the usual failure - report the exact error instead of guessing.
