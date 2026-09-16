"""The browser and mobile app-analysis MCP servers tezgah wires into each host.

One source of truth: tezgah-setup renders these into opencode.json, Codex
config.toml and Cursor mcp.json, so the per-host configs cannot drift. The
Claude plugin reads the committed `.mcp.json` at the plugin root instead.

Both servers drive the app from its accessibility / DOM / native view tree, so
an analysis run does not need a screenshot per step; a screenshot is an
explicit, on-demand action. The browser profile is isolated by default - the
user's real Chrome is only reached by a deliberate attach, never automatically.

Nothing here is installed by tezgah: the commands run through `npx`, which is
present wherever node is (the dsh host and its status line already need it).
"""
import os

HOME = os.path.expanduser("~")

# Where screenshots, traces and tree dumps land. The agent gets a path back;
# image bytes are never inlined into the prompt.
ARTIFACTS = os.environ.get("TEZGAH_ARTIFACTS") or os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.join(HOME, ".cache"),
    "tezgah", "apps")

# Pinned on purpose. A floating tag (`@latest`) makes every session start fetch
# whatever is current on the registry and run it with the agent's privileges -
# a supply-chain defect a 2,660-harness study found in 9.8% of committed agent
# configurations ("Scanning the Harness", arXiv 2609.07360). Bump these
# deliberately, not implicitly.
_PLAYWRIGHT = ["npx", "-y", "@playwright/mcp@0.0.81", "--isolated"]
_CHROME_DEVTOOLS = ["npx", "-y", "chrome-devtools-mcp@1.9.0", "--isolated",
                    "--no-usage-statistics"]
_MOBILE = ["npx", "-y", "@mobilenext/mobile-mcp@1.0.4"]

# Wired by default: the two surfaces an app analysis actually needs.
SERVERS = (
    {"name": "playwright",
     "why": "web app analysis from the accessibility tree",
     "command": _PLAYWRIGHT,
     "env": {"PLAYWRIGHT_MCP_OUTPUT_DIR": ARTIFACTS}},
    {"name": "mobile-mcp",
     "why": "iOS Simulator / Android emulator from the native tree",
     "command": _MOBILE,
     "env": {"MOBILEMCP_DISABLE_TELEMETRY": "1"}},
)

# Opt-in (`--devtools`): perf traces, deep network and source-mapped console.
# Playwright's tree snapshot is the analysis default; this is the diagnostic
# sidecar the second opinion recommended keeping separate.
OPTIONAL = (
    {"name": "chrome-devtools",
     "why": "web perf traces, deep network and source-mapped console",
     "command": _CHROME_DEVTOOLS,
     "env": {}},
)


def servers(devtools=False):
    return tuple(SERVERS) + (tuple(OPTIONAL) if devtools else ())


def names(devtools=True):
    """Every app server name tezgah may have written (for cleanup/checks)."""
    return [s["name"] for s in servers(devtools)]
