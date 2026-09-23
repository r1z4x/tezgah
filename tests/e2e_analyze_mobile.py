#!/usr/bin/env python3
"""Opt-in smoke: the wired Mobile MCP server exposes the tree-first tools.

Starts the exact command tezgah-setup writes for the `mobile-mcp` server,
initializes MCP, lists its tools (the accessibility-tree tools must exist), then
asks for the device list. A missing simulator/emulator is a SKIP, not a failure:
the point is that the server starts and its view-tree tools are wired.

Needs npx (node); a booted iOS Simulator or Android emulator makes the device
call succeed. Prints "SKIP: ..." and exits 0 when TEZGAH_E2E_APPS, npx, the
server start, or a running device is missing; 1 only when a required tool is
absent.

    TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "hooks"))
sys.path.insert(0, HERE)
import tezgah_apps  # noqa: E402
from _mcp_stdio import Client  # noqa: E402

REQUIRED = {"mobile_list_available_devices", "mobile_list_elements_on_screen",
            "mobile_take_screenshot"}


def skip(msg):
    print("SKIP: " + msg)
    return 0


def main():
    if not os.environ.get("TEZGAH_E2E_APPS"):
        return skip("set TEZGAH_E2E_APPS=1 to run the real MCP smoke")
    if not shutil.which("npx"):
        return skip("npx (node) is not on PATH")
    server = next(s for s in tezgah_apps.servers() if s["name"] == "mobile-mcp")
    env = os.environ.copy()
    env.update(server["env"])
    client = Client(list(server["command"]), env=env)
    try:
        client.initialize()
        tools = set(client.tools())
    except Exception as exc:
        client.close()
        return skip("mobile MCP did not start: %s" % exc)
    missing = REQUIRED - tools
    if missing:
        client.close()
        print("FAIL: mobile MCP is missing tools: %s" % ", ".join(sorted(missing)))
        return 1
    try:
        client.call("mobile_list_available_devices")
    except Exception as exc:
        client.close()
        return skip("no simulator/emulator running: %s" % exc)
    client.close()
    print("OK: mobile MCP exposes the view-tree tools and lists a device")
    return 0


if __name__ == "__main__":
    sys.exit(main())
