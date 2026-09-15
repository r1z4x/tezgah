#!/usr/bin/env python3
"""CI smoke: the tezgah-wired app MCP servers start and expose their tools.

Starts the exact command tezgah-setup writes for `playwright` and `mobile-mcp`,
completes the MCP handshake and checks the accessibility-tree tools exist. It
launches no browser and needs no device: `tools/list` is served before any
automation starts, so this is deterministic on CI. The heavier, real-interaction
smokes (`e2e_analyze_web.py`, `e2e_analyze_mobile.py`) stay local and opt-in.

Exits 0 when every server answers. A server that cannot start (no npm registry)
is a SKIP by default, but a FAIL when TEZGAH_E2E_STRICT=1 - which is how CI runs
it, so a broken wire cannot hide behind a skip.

    TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "hooks"))
sys.path.insert(0, HERE)
import tezgah_apps  # noqa: E402
from _mcp_stdio import Client  # noqa: E402

REQUIRED = {
    "playwright": {"browser_navigate", "browser_snapshot", "browser_click"},
    "mobile-mcp": {"mobile_list_available_devices",
                   "mobile_list_elements_on_screen", "mobile_take_screenshot"},
}
STRICT = os.environ.get("TEZGAH_E2E_STRICT") == "1"


def main():
    if not shutil.which("npx"):
        print("SKIP: npx (node) is not on PATH")
        return 0
    bad = False
    for srv in tezgah_apps.SERVERS:
        env = os.environ.copy()
        env.update(srv["env"])
        client = Client(list(srv["command"]), env=env)
        try:
            client.initialize()
            tools = set(client.tools())
        except Exception as exc:
            client.close()
            print("%s: %s did not start: %s"
                  % ("FAIL" if STRICT else "SKIP", srv["name"], exc))
            bad = bad or STRICT
            continue
        missing = REQUIRED[srv["name"]] - tools
        client.close()
        if missing:
            print("FAIL: %s is missing tools: %s"
                  % (srv["name"], ", ".join(sorted(missing))))
            bad = True
        else:
            print("OK: %s exposes %d tools incl. its tree tools"
                  % (srv["name"], len(tools)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
