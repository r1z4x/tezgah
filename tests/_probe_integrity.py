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
    ti.note(p.get("session"), p.get("kind"), p.get("detail", ""),
            id=p.get("id"), exit=p.get("exit"), out_bytes=p.get("out_bytes"),
            fail_class=p.get("fail_class"), workspace=p.get("workspace"))
    out = None
elif fn == "note_tool":
    # the argument is omitted when the test omits it, so the signature's default
    # is what a host that passes no outcome actually gets
    failed = {} if "failed" not in p else {"failed": p["failed"]}
    ti.note_tool(p.get("session"), p.get("tool"), p.get("input") or {},
                 **failed, out_bytes=p.get("out_bytes"),
                 error=p.get("error"), cwd=p.get("cwd"))
    out = None
elif fn == "note_turn":
    ti.note_turn(p.get("session"), p.get("prompt"),
                 workspace=p.get("workspace"))
    out = None
elif fn == "kinds":
    out = sorted(ti.kinds(p.get("session")))
elif fn == "events":
    out = ti.events(p.get("session"), tail=p.get("tail"))
elif fn == "prior_calls":
    out = list(ti.prior_calls(p.get("session"), p.get("id"), p.get("tail", 200)))
elif fn == "counters":
    out = ti.counters(p.get("session"))
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
