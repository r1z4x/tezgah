# The app-analysis MCPs, read 2026-09-20

The two servers a product analysis reads a *running* app with, and what each can
and cannot evidence. Versions checked against the npm registry, not from memory.

## Versions

| package | tezgah pins | registry latest | note |
|---|---|---|---|
| `@playwright/mcp` | `0.0.81` | `0.0.82` | one behind by choice; the pin is deliberate |
| `@mobilenext/mobile-mcp` | `1.0.4` | `1.0.4` | current |
| `chrome-devtools-mcp` | `1.9.0` (opt-in) | `1.9.0` | current |

Verified with `npm view <pkg> version`. A version that does not resolve would mean
the server never starts, so this is checked rather than assumed.

## Capabilities are opt-in, and that was the defect

- **Source:** `https://playwright.dev/mcp/capabilities` (read 2026-09-20).
- Verbatim: "Capabilities control which tools the MCP server exposes to the LLM.
  **By default, only core tools are enabled.**"
- Core (always on): `browser_navigate`, `browser_navigate_back`, `browser_snapshot`,
  `browser_find`, `browser_click`, `browser_hover`, `browser_drag`, `browser_drop`,
  `browser_select_option`, `browser_type`, `browser_press_key`, `browser_fill_form`,
  `browser_take_screenshot`, `browser_run_code_unsafe`, `browser_evaluate`,
  `browser_wait_for`, `browser_handle_dialog`, `browser_file_upload`,
  `browser_console_messages`, `browser_network_requests`, `browser_network_request`,
  `browser_tabs`, `browser_close`, `browser_resize`.
- The groups that matter to an audit:
  - `testing` - `browser_verify_element_visible`, `browser_verify_text_visible`,
    `browser_verify_list_visible`, `browser_verify_value`,
    `browser_generate_locator`. This is what makes a UX claim **re-runnable**
    rather than a judgement.
  - `storage` - cookie / localStorage / sessionStorage plus
    `browser_storage_state` and `browser_set_storage_state`. This is how an
    analysis reaches a logged-in surface **without attaching to the user's real
    Chrome profile** - the safe route the `analyze-app` skill demands.
  - `network` - `browser_route`, `browser_route_list`, `browser_unroute`,
    `browser_network_state_set`. Sets offline and mocks a failing endpoint.
  - `devtools` - tracing, video, highlight, annotate. Left off: the opt-in
    chrome-devtools sidecar already owns perf traces and deep network.
  - `vision` (coordinate mouse tools, needs a vision model), `pdf`, `config` - not
    needed by an audit.
- The source's own tradeoff, which is why the cap list is short and named:
  "Capabilities limit the number of tools exposed to the LLM. Fewer tools means:
  Lower token cost ... Fewer hallucinated tool calls ... Faster responses."

## Mobile MCP's surface

- **Source:** `https://github.com/mobile-next/mobile-mcp` (README, read 2026-09-20;
  the docs site's tools-reference URL 404s today).
- Tools include: `mobile_list_available_devices`, `mobile_list_apps`,
  `mobile_launch_app`, `mobile_terminate_app`, `mobile_install_app`,
  `mobile_list_elements_on_screen`, `mobile_get_screen_size`,
  `mobile_get_orientation` / `mobile_set_orientation`,
  `mobile_click_on_screen_at_coordinates`, `mobile_double_tap_on_screen`,
  `mobile_long_press_on_screen_at_coordinates`, `mobile_swipe_on_screen`,
  `mobile_press_button`, `mobile_type_keys`, `mobile_take_screenshot`,
  `mobile_save_screenshot`, `mobile_get_device_logs`, `mobile_list_crashes`,
  `mobile_get_crash`, `mobile_clipboard`, `mobile_set_location`,
  `mobile_start_screen_recording`, `mobile_stop_screen_recording`,
  `mobile_get_foreground_app`, `mobile_batch_commands`, `mobile_open_url`,
  plus remote-device fleet tools.
- **What is missing for an audit:** there is no `mobile_verify_*` (no assertion),
  no way to force an offline state or mock a response, and no geometry or colour
  data in the view tree. So on mobile a UX claim is a judgement unless re-walking
  the flow reproduces it, and contrast, tap-target size and focus order cannot be
  claimed from the tree at all.

## Verified, not assumed

`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py` starts the exact commands
tezgah writes, completes the MCP handshake and lists tools:
`playwright` exposes **52** tools (core-only is ~24 - the caps are live) and
`mobile-mcp` exposes **32**. `tests/e2e_analyze_wiring.py` now requires four of the
cap tools, so a dropped `--caps` fails CI instead of silently shrinking the
analysis back to what it was.
