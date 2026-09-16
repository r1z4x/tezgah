#!/usr/bin/env python3
"""Test probe: exercise hooks/tezgah_integrity.py against a temp HOME.

Reads {"fn": ..., ...} as JSON on stdin and prints the result as JSON, so a test
can seed a session's evidence ledger and read it back in a clean environment.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import tezgah_integrity as ti  # noqa: E402

p = json.load(sys.stdin)
fn = p.get("fn")
if fn == "note":
    ti.note(p.get("session"), p.get("kind"), p.get("detail", ""))
    out = None
elif fn == "note_tool":
    ti.note_tool(p.get("session"), p.get("tool"), p.get("input") or {},
                 bool(p.get("failed")))
    out = None
elif fn == "kinds":
    out = sorted(ti.kinds(p.get("session")))
elif fn == "shortcut_command":
    out = ti.shortcut_command(p.get("command"))
elif fn == "shortcut_edit":
    out = ti.shortcut_edit(p.get("input") or {})
elif fn == "stop_reason":
    out = ti.stop_reason(p.get("text"), p.get("session"))
elif fn == "verify_command":
    out = ti.verify_command(p.get("command"))
else:
    raise SystemExit("unknown fn: %r" % fn)
print(json.dumps(out))
