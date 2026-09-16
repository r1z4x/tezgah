#!/usr/bin/env python3
"""Test probe: call one tezgah_context entry point, print JSON.

Reads {"fn": "context_for"|"health_lines"|"record", ...} as JSON on stdin.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import tezgah_context as tc  # noqa: E402

p = json.load(sys.stdin)
fn = p.get("fn")
if fn == "context_for":
    out = tc.context_for(p.get("event", "session_start"), p["cwd"], p.get("payload"))
elif fn == "health_lines":
    out = tc.health_lines(p["cwd"], p.get("session_id"), color=p.get("color", False))
elif fn == "health_segments":
    out = tc.health_segments(p["cwd"], p.get("session_id"))
elif fn == "record":
    tc.record(p.get("session_id"), p.get("kind"))
    out = True
else:
    raise SystemExit("unknown fn: %s" % fn)
print(json.dumps(out))
