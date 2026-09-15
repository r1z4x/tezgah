#!/usr/bin/env python3
"""Test probe: call one tezgah_agents entry point, print JSON.

Reads {"fn": "sync_root"|"cleanup"|"detect", ...} as JSON on stdin.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import tezgah_agents as ta  # noqa: E402

p = json.load(sys.stdin)
fn = p.get("fn")
if fn == "sync_root":
    out = ta.sync_root(p["root"])
elif fn == "cleanup":
    out = ta.cleanup()
elif fn == "detect":
    out = ta.detect_infra(p["root"])
else:
    raise SystemExit("unknown fn: %s" % fn)
print(json.dumps(out))
