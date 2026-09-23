---
name: analyze-app
description: >
  Analyze a running web or mobile app from its structured accessibility / DOM /
  native view tree, and from screenshots of the rendered screen. Use when a task
  must drive,
  inspect, or verify a running application - walk a flow, read the UI, check the
  console, network or device logs, or confirm behavior end to end - rather than
  only read its source. Covers a real browser (Playwright MCP), an iOS Simulator
  or Android emulator (Mobile MCP), and optional web diagnostics (Chrome
  DevTools MCP).
---

# analyze-app

Drive the running app through its accessibility tree. The tree answers structure;
the rendered image answers hierarchy, rhythm, colour and feel - so a screenshot is
taken whenever a claim needs those, and for what the tree cannot represent at all
(canvas, game, animation, pixel-level visual regression). It is read, not merely
saved, and it is still not a per-step default: capture what the tree could not
answer, and say what that was.

## Pick the target

| Target | Server | Tool prefix |
|---|---|---|
| Web page / webview | Playwright MCP | `browser_*` |
| iOS Simulator / Android emulator | Mobile MCP | `mobile_*` |
| Web perf / deep network / source-mapped console | Chrome DevTools MCP (opt-in) | `*` |

If the `browser_*` / `mobile_*` tools are not in this session, the server is not
wired for this host, or it failed to start: say so and fall back to the CLI on
the shell, with the same pins tezgah wires (`hooks/tezgah_apps.py`) -
`npx -y @playwright/mcp@0.0.81 --isolated --caps=testing,storage,network` or
`npx -y @mobilenext/mobile-mcp@1.0.4`. Never `@latest`: a floating tag fetches
whatever the registry serves at session start and runs it with the agent's
privileges.

## What each capability buys an audit

Playwright MCP serves core tools only unless the capabilities are named, and the
three tezgah wires are the difference between "the tree looked fine" and a claim
someone can re-run:

| Capability | Tools | What an analysis does with it |
|---|---|---|
| core (always on) | `browser_snapshot`, `browser_find`, interaction, `browser_evaluate`, `browser_console_messages`, `browser_network_requests`, `browser_resize` | read the flow and its element names, roles and states; run a measurement in the page; collect the errors a step produced |
| `testing` | `browser_verify_text_visible`, `browser_verify_element_visible`, `browser_verify_list_visible`, `browser_verify_value`, `browser_generate_locator` | turn a UX claim into an assertion that fails or passes on a re-run - the difference between a `failure` and a `judgement` in a product analysis |
| `storage` | `browser_storage_state`, `browser_set_storage_state`, cookies, localStorage | audit a logged-in surface from a saved state file instead of attaching to the user's real Chrome profile |
| `network` | `browser_route`, `browser_route_list`, `browser_network_state_set` | set the offline state and mock a failing endpoint - the two states a mobile-first product is judged on |
| `devtools` (off) | tracing, video, highlight | owned by the opt-in chrome-devtools sidecar; enabling it here would duplicate that and widen the tool list |

`browser_resize` matters more than it looks: a product audit must name the
viewport it judged, and a layout finding that holds at one width and not another
is not a finding until both are checked.

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

## Triage: read the lines that matter, not the screen

A snapshot is the whole screen as text - one 40-row admin table came back as
13,045 characters in 356 lines - and the loop pays for all of it to find the dozen
lines that carry the controls. So after the snapshot, and before reading it:

1. **Flatten and keep it**: save the `browser_snapshot` result (or the flattened
   text of one) to a file.
2. **Triage**: `tezgah-triage --select FILE --task "what this pass is looking
   for"` sends the tree's repeating units - a row, a table cell, a control on its
   own - and the task in one batched judgement, and prints the line ids under the
   selected units with their original `ref=` values, the unselected count and the
   characters that may now be skipped.
3. **Read the selected refs** in the tree, and act on them. Read the whole snapshot
   when the task is "is anything wrong on this screen at all" - a selection cannot
   answer a question it was not asked.

For one component, `tezgah-triage --states FILE --component "#12"` asks one
judgement per state over that component's subtree - the interactive pair `focus`
and `active` arrives as one three-way answer (`neither` / `focus` / `pressed`)
inside that same call, measured better than two separate questions - covering
default, hover, focus, active, disabled, loading, error; empty, skeleton, offline,
partial, long-text, permission-denied - and a state the judgement reports as not
shown is driven for
the interactive set (hover, focus, active, disabled) and routed for the data set
(offline, error, empty, loading) and then re-read, before it is called missing: a
static snapshot never shows hover, and it shows only the data state the route
happens to be in, so `--states` answers what the current tree shows, not what the
component implements.

**The triage is an aid, and its recall is measured, not assumed.** On two
reproduced screens this round the unit selection kept **100% of the control
lines** - at a 94% read on the 40-row table, 74% on the 20-button screen - while
one question per line kept only 73.5% at a 26% read, which is what "selective"
looked like when it was actually losing a quarter of the controls. 100% is a
measurement on those screens, not a guarantee: read what the selection names, then
judge from what the tree and the screen actually show, and say what you read. When
the printed selection is most of the screen, the task names a control every row
repeats and the triage bought coverage rather than skipping - the tool says so
itself, and reading the snapshot directly is then the cheaper move. With no
credential, or with the `judge-off` switch on, `tezgah-triage` prints why and
exits 1: read the snapshot directly, the way the loop reads it today, and say the
triage was unavailable.

## Browser profile

Isolated by default, so a run never touches the user's real Chrome state. To
analyze a logged-in flow, attach deliberately - `--cdp-endpoint` or the
Playwright extension instead of the isolated default - and say so before doing
it, because it exposes the real session to the analysis.

## Artifacts

Screenshots, traces and tree dumps go to the app artifact directory
(`PLAYWRIGHT_MCP_OUTPUT_DIR`, default `~/.cache/tezgah/apps`). Return the file
path; keep image tokens out of the context.

## Looking at the screen

The tree answers structure; the image answers hierarchy, rhythm, colour and feel.
Neither replaces the other, and a review that saves a screenshot without reading it
has produced a file, not evidence.

- Say what the tree could not answer before capturing. `browser_take_screenshot` /
  `mobile_save_screenshot` return a path; the bytes stay out of the context.
- Sweep the widths in scope with `browser_resize` - at least 320 / 768 / 1280 - then
  capture. Repeat in dark mode and at the largest text setting: hierarchy and
  contrast move with all three.
- Two checks that need the image and take seconds: the **blur test** (blur or squint
  - is the primary action still first?) and the **grayscale test** (does the
  hierarchy survive without colour?). Both are read from the same capture.
- Report what was seen: the screen, the region, what competes with what. That is a
  judgement, so run the pass twice and say whether both agreed.

## The automated sweeps

Two standards can be run in the page instead of argued about:

- **axe-core** - injected with `browser_evaluate` from a *pinned* build, never a
  `@latest` CDN script, which is the supply-chain defect the pins exist to avoid. It
  covers WCAG A/AA/AAA plus common best practices, and its own documentation puts it
  at "on average 57% of WCAG issues automatically", returning `incomplete` where it
  cannot be certain. The named gaps - focus appearance, target size, dragging,
  accessible authentication - are hand-checked, not assumed.
- **Core Web Vitals** via `PerformanceObserver` in the page: LCP <= 2500 ms,
  INP <= 200 ms and CLS <= 0.1 are "good" at the 75th percentile; > 4000 ms,
  > 500 ms and > 0.25 are "poor" (web.dev). A number outside them is a failure with
  its trace; the opt-in chrome-devtools sidecar is the path to that trace.

## Mobile caveats

Mobile MCP has no assertion, mocking or geometry tools: there is no
`mobile_verify_*`, no way to force an offline state, and the view tree carries no
colour or size maths. So on mobile -

- a UX claim is a **judgement** unless re-walking the flow reproduces it; say how
  many passes agreed,
- contrast, tap-target size and focus order are **not measurable** from the tree:
  take the screenshot (naming why), or do not make the claim,
- the two states mobile products are judged on - offline and a failing backend -
  come from the device or the app's own test hook, not from this server; if
  neither exists, that is the finding.

macOS may prompt for Accessibility / Screen-Recording permission on first use,
and a real iOS device needs Developer Mode. The view tree can drop under load:
retry the tree once, then fall back to a screenshot. iOS/Android tooling version
skew is the usual failure - report the exact error instead of guessing.
