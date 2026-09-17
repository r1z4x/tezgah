#!/usr/bin/env python3
"""Test probe: run the shared gate for one call, print the deny reason or null.

Reads {"tool", "input", "cwd", "session_id"} as JSON on stdin. With
{"capture_log": "<path>"} it also installs a stub `tezgah_snapshot` whose
`capture` appends its arguments there: the gate imports `capture` behind a
guard, and a module planted in sys.modules answers that import whether or not
hooks/tezgah_snapshot.py has landed - so one test pins the call site either way.
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

p = json.load(sys.stdin)

log = p.get("capture_log")
if log:
    def capture(tool, inp, cwd, session_id):
        with open(log, "a") as fh:
            fh.write(json.dumps({"tool": tool, "input": inp, "cwd": cwd,
                                 "session_id": session_id}) + "\n")
        return "0123456789ab"

    stub = types.ModuleType("tezgah_snapshot")
    stub.capture = capture
    sys.modules["tezgah_snapshot"] = stub

from tezgah_gate import decision  # noqa: E402

print(json.dumps(decision(
    p.get("tool", ""), p.get("input") or {}, p["cwd"], p.get("session_id"))))
