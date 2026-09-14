#!/usr/bin/env python3
"""Test probe: run the shared gate for one call, print the deny reason or null.

Reads {"tool", "input", "cwd", "session_id"} as JSON on stdin.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
from tezgah_gate import decision  # noqa: E402

p = json.load(sys.stdin)
print(json.dumps(decision(
    p.get("tool", ""), p.get("input") or {}, p["cwd"], p.get("session_id"))))
