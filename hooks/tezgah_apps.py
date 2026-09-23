"""The browser and mobile app-analysis MCP servers tezgah wires into each host.

One source of truth: one row per feature in `REGISTRY`. tezgah-setup renders the
rows a selection enables into opencode.json, Codex config.toml, Cursor mcp.json,
omp's mcp.json and the dsh patch, so the per-host configs cannot drift; Claude
reads the `.mcp.json` at the plugin root, which the installer renders from the
same rows. A row carries the vendor command and env of its server, the `default`
state a config without a `features` key means, and the `dep` it cannot start
without - so what is wired, what is installed and what is reported all answer
from one key.

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
# Playwright MCP exposes core tools only unless capabilities are named, and the
# caps are exactly what a product audit needs: `testing` turns a UX claim into a
# re-runnable assertion (browser_verify_*), `storage` reaches a logged-in surface
# by saving and restoring a state file instead of attaching to the user's real
# Chrome, and `network` sets the offline state and mocks a failure - the two
# states a mobile-first product is judged on. `devtools` (traces, video) stays
# off: the opt-in chrome-devtools sidecar owns perf and deep network, and a
# second copy of it would only widen the tool list.
_PLAYWRIGHT = ["npx", "-y", "@playwright/mcp@0.0.81", "--isolated",
               "--caps=testing,storage,network"]
_CHROME_DEVTOOLS = ["npx", "-y", "chrome-devtools-mcp@1.9.0", "--isolated",
                    "--no-usage-statistics"]
_MOBILE = ["npx", "-y", "@mobilenext/mobile-mcp@1.0.4"]

# The browser build the playwright row launches, installed by the same Playwright
# version that server ships: `@playwright/mcp@0.0.81` declares
# `playwright@1.64.0-alpha-2026-09-14` as its own dependency (read from its
# published package.json), and a browser cache written by another version can be
# the wrong revision for it. Bumping `_PLAYWRIGHT` means bumping this with it.
_PW_BROWSERS = ["npx", "-y", "playwright@1.64.0-alpha-2026-09-14",
                "install", "chromium"]


# ------------------------------------------------------------------- probes ---
# Each probe answers "can this feature start?", not "is it wired": the wiring is
# tezgah's own file and the report reads that separately. They are called only
# when a feature's state is asked for, so `shutil` and `tezgah_paths` are
# imported here rather than at module level - this module is a leaf the
# installer imports on every host.

def _which(name):
    import shutil
    return shutil.which(name)


def _tp(attr):
    import tezgah_paths
    return getattr(tezgah_paths, attr)


def _browser_caches():
    """Every directory Playwright itself would look in, in its own order.

    `PLAYWRIGHT_BROWSERS_PATH=0` means "beside the package", which for an
    npx-fetched server is inside the npx cache; the probe treats it as any other
    miss instead of guessing a path there."""
    local = os.environ.get("LOCALAPPDATA")
    return tuple(p for p in (
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
        os.path.join(HOME, "Library", "Caches", "ms-playwright"),
        os.path.join(HOME, ".cache", "ms-playwright"),
        os.path.join(local, "ms-playwright") if local else None,
    ) if p)


def _playwright_browsers():
    """A browser cache holding a build, or None.

    The server launches a browser on its first tool call, so one wired without a
    build fails there instead of at install time - which is what the probe is
    for. Any build counts: the row's own pin decides which one."""
    for d in _browser_caches():
        try:
            found = sorted(e for e in os.listdir(d)
                           if e.startswith(("chromium", "firefox", "webkit")))
        except OSError:
            continue
        if found:
            return os.path.join(d, found[0])
    return None


def _probe_playwright():
    """`npx` to start the server, and a browser build for it to launch."""
    if not _which("npx"):
        return None
    return _playwright_browsers()


def _probe_device_toolchain():
    """`adb` (Android platform tools) or `xcrun` (macOS, whose simulator
    services arrive with Xcode). Either one drives a device the native tree is
    read from; no server here can start a device itself."""
    return _which("adb") or _which("xcrun")


def _probe_npx():
    return _which("npx")


def _probe_orx():
    return _tp("orx_bin")()


def _probe_ai_research():
    """The payload a research task reads, by its entry point."""
    d = _tp("ai_research_dir")()
    return d if os.path.isfile(os.path.join(d, "SKILL.md")) else None


# ----------------------------------------------------------------- registry ---
# One row per feature id. `command`/`env` are the server spec, so a row without
# a `command` is a feature with no host file to write (nothing iterates those
# into a host config - `servers()` is the accessor that filters them). `dep` is
# the runtime the feature cannot start without, in the shape the installer's own
# `DEPS` table uses: `probe` answers whether it is there, `needs` names the
# tools its `cmd` requires on PATH, `cmd` is the vendor's own installer, and a
# `cmd` of None is a dependency with no unattended installer to name - the
# probe still fails honestly instead of wiring a server whose runtime is absent.
REGISTRY = (
    {"id": "mcp-playwright",
     "name": "playwright",
     "why": "web app analysis from the accessibility tree",
     "command": _PLAYWRIGHT,
     "env": {"PLAYWRIGHT_MCP_OUTPUT_DIR": ARTIFACTS},
     "default": True,
     "dep": {"name": "playwright-browsers", "probe": _probe_playwright,
             "needs": ("npx",), "cmd": _PW_BROWSERS,
             "why": "the browser it launches on its first tool call"}},
    {"id": "mcp-mobile-mcp",
     "name": "mobile-mcp",
     "why": "iOS Simulator / Android emulator from the native tree",
     "command": _MOBILE,
     "env": {"MOBILEMCP_DISABLE_TELEMETRY": "1"},
     "default": True,
     "dep": {"name": "device-toolchain", "probe": _probe_device_toolchain,
             "needs": (),
             # Neither channel is an unattended vendor installer: Xcode comes
             # from the App Store, the Android SDK from its own manager.
             "cmd": None,
             "why": "adb or Xcode's simulator services, for the device it drives"}},
    # Opt-in (`--enable mcp-chrome-devtools`, or `--devtools`): perf traces, deep
    # network and source-mapped console. Playwright's tree snapshot is the
    # analysis default; this is the diagnostic sidecar the second opinion
    # recommended keeping separate.
    {"id": "mcp-chrome-devtools",
     "name": "chrome-devtools",
     "why": "web perf traces, deep network and source-mapped console",
     "command": _CHROME_DEVTOOLS,
     "env": {},
     "default": False,
     "dep": {"name": "npx", "probe": _probe_npx, "needs": (),
             # The package itself is fetched by npx on demand, and node has no
             # unattended vendor installer to name here.
             "cmd": None,
             "why": "node, which npx runs the server through"}},
    # Not a server: the vendored domain library a research task reaches. Its row
    # is here so the table, not a second private list, says whether it is on.
    {"id": "ai-research",
     "name": "ai-research",
     "why": "the vendored domain library a research task reads",
     "command": None,
     "env": None,
     "default": True,
     "dep": {"name": "ai-research", "probe": _probe_ai_research, "needs": (),
             # It ships inside the package; the only writer is the release-time
             # `bin/tezgah-import-ai-research`, which needs a source clone.
             "cmd": None,
             "why": "the payload, present in the plugin that is running"}},
    # Not a server either: the OpenResearch CLI the research routing shells out
    # to. Same dep record the installer's DEPS table carries for it.
    {"id": "orx",
     "name": "orx",
     "why": "research routing (OpenResearch)",
     "command": None,
     "env": None,
     "default": True,
     "dep": {"name": "orx", "probe": _probe_orx, "needs": ("curl", "sh"),
             "cmd": ["sh", "-c",
                     "curl -LsSf https://openresearch.sh/install.sh | sh"],
             "why": "research routing (OpenResearch)"}},
)

IDS = tuple(r["id"] for r in REGISTRY)
# Every id that carries a server, i.e. every name tezgah may have written into a
# host file. Uninstall reads this (`names(MCP_IDS)`), never a disable: a feature
# that is off today still has to be swept from a file an older release wrote.
MCP_IDS = tuple(r["id"] for r in REGISTRY if r["command"])


def defaults():
    """The ids a config with no `features` key means.

    Declared per row, never inferred from what is installed or from how the
    registry is ordered, so a config.json written before that key existed keeps
    exactly the wiring it had."""
    return tuple(r["id"] for r in REGISTRY if r["default"])


def selected_ids(selected=None):
    """`selected` normalised to registry order.

    `None` means the declared defaults - an absent key is not "none". An id this
    registry does not know is dropped rather than raising, so a selection an
    older release wrote cannot break a host writer; `--features` is where an
    unknown id is reported."""
    if selected is None:
        return defaults()
    if isinstance(selected, (bool, str)):
        # A bool is the `devtools` argument this signature replaced and a string
        # is iterable, so either one left at a call site would answer with the
        # wrong set - or, for the bool, with an unreadable "not iterable" from
        # `set()`. Name the argument the caller has to give instead.
        raise TypeError("selected is a list of feature ids, not %s"
                        % type(selected).__name__)
    wanted = set(selected)
    return tuple(r["id"] for r in REGISTRY if r["id"] in wanted)


def servers(selected=None):
    """The enabled rows that carry a server, in registry order."""
    on = set(selected_ids(selected))
    return tuple(r for r in REGISTRY if r["id"] in on and r["command"])


def names(selected=None):
    """The server names of `servers(selected)`."""
    return [r["name"] for r in servers(selected)]
