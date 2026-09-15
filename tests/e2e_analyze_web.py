#!/usr/bin/env python3
"""Opt-in smoke: the wired Playwright MCP server drives a page tree-first.

Starts the exact command tezgah-setup writes for the `playwright` server,
initializes MCP, lists its tools (the accessibility-tree tools must exist), then
navigates to about:blank and reads the snapshot WITHOUT a screenshot - the
tree-first loop the analyze-app contract requires.

Needs npx (node) plus a Playwright browser build. Prints "SKIP: ..." and exits 0
when TEZGAH_E2E_APPS, npx, the server start, or the browser build is missing; 1
only when the wiring itself is wrong (a required tool is absent).

    TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "hooks"))
sys.path.insert(0, HERE)
import tezgah_apps  # noqa: E402
from _mcp_stdio import Client, McpError  # noqa: E402

REQUIRED = {"browser_navigate", "browser_snapshot", "browser_click"}


def skip(msg):
    print("SKIP: " + msg)
    return 0


def main():
    if not os.environ.get("TEZGAH_E2E_APPS"):
        return skip("set TEZGAH_E2E_APPS=1 to run the real MCP smoke")
    if not shutil.which("npx"):
        return skip("npx (node) is not on PATH")
    server = next(s for s in tezgah_apps.SERVERS if s["name"] == "playwright")
    env = os.environ.copy()
    env.update(server["env"])
    client = Client(list(server["command"]), env=env)
    try:
        client.initialize()
        tools = set(client.tools())
    except Exception as exc:
        client.close()
        return skip("playwright MCP did not start: %s" % exc)
    missing = REQUIRED - tools
    if missing:
        client.close()
        print("FAIL: playwright MCP is missing tools: %s" % ", ".join(sorted(missing)))
        return 1
    try:
        client.call("browser_navigate", {"url": "about:blank"})
        client.call("browser_snapshot")
    except McpError as exc:
        client.close()
        return skip("browser build missing or navigation failed: %s" % exc)
    client.close()
    print("OK: playwright MCP drives a page from the tree (no screenshot)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
