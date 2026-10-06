"""The shared gate corpus (tests/gate_vectors.json) on every host's own entry point.

The rules under test are tezgah_gate's (`decision`) and the tezgah_integrity and
tezgah_taste readers it calls; tests/impacted.py maps a change to any of them
here by those names.

One vector is one call - a canonical tool and its input - and the verdict the
core rule gives it. Each host gets it through its own PreToolUse envelope and
entry point (the hook the host's manifest runs, or the opencode plugin through its
harness), under the tool name that host really uses, and only if the host's own
matcher routes that name to the gate at all: the matcher simulation reads each
host's manifest, so a manifest that drops a write tool shows up here as a
disagreeing cell instead of a silent pass. A cell that disagrees is a failure
unless the corpus names it a ceiling, and a ceiling that stops disagreeing is a
failure too, so the list cannot go stale.
"""
import json
import os
import re
import shutil
import subprocess
import unittest

import support
from support import TempHome, run_json

CORPUS = os.path.join(support.TESTS, "gate_vectors.json")
NODE = shutil.which("node")
# assembled at runtime: see the corpus's own `placeholders`
FILL = {"{GHP}": "ghp_" + "A1b2C3d4" * 5,
        "{SKLIVE}": "sk-live-" + "a1B2c3D4" * 3,
        "{SKIP}": "@pytest.mark." + "skip"}
# opencode's own spelling of the fields its tools carry
CAMEL = {"file_path": "filePath", "old_string": "oldString",
         "new_string": "newString"}


def load():
    with open(CORPUS, encoding="utf-8") as fh:
        return json.load(fh)


def fill(value):
    if isinstance(value, str):
        for key, text in FILL.items():
            value = value.replace(key, text)
        return value
    if isinstance(value, dict):
        return {k: fill(v) for k, v in value.items()}
    return value


def matcher(host, spec):
    """A predicate over a tool name: does this host route it to its gate?"""
    path = spec.get("matcher")
    if not path:
        return lambda name: True
    with open(os.path.join(support.REPO, path), encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".ts.in"):
        # omp: the exact GATED list, compared lowercase (tezgah-hook.ts.in)
        listed = re.search(r"const GATED = \[(.*?)\];", text, re.S).group(1)
        gated = set(re.findall(r'"([^"]+)"', listed))
        return lambda name: name.lower() in gated
    hooks = json.loads(text)["hooks"]
    groups = hooks.get("PreToolUse") or hooks.get("preToolUse") or []
    patterns = [g["matcher"] for g in groups if g.get("matcher")]
    # a matcher is a regex over the whole tool name, as each host applies it
    return lambda name: any(re.fullmatch(p, name) for p in patterns)


class GateVectors(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        # opencode asks the core through bin/tezgah-gate under its config dir,
        # linked the way tezgah-setup links it; without it the ask fails open
        support.linked(os.path.join(support.REPO, "bin", "tezgah-gate"), self.home)

    def hook(self, script, payload, extract):
        out, proc = run_json([script], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return extract(out or {}) or None

    def cell(self, host, name, inp, sid):
        """The refusal text one host gives one call, or None."""
        ids = {"cwd": self.repo, "session_id": sid, "conversation_id": sid}
        if host == "core":
            out, proc = run_json([support.PROBE_GATE],
                                 {"tool": name, "input": inp, "cwd": self.repo,
                                  "session_id": sid}, env=self.envv)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return out or None
        if host in ("claude", "dsh", "codex"):
            script = support.CODEX_HOOK if host == "codex" else support.PRETOOLUSE
            return self.hook(script, dict(ids, hook_event_name="PreToolUse",
                                          tool_name=name, tool_input=inp),
                             lambda out: out.get("hookSpecificOutput", {}).get(
                                 "permissionDecisionReason"))
        if host == "cursor":
            return self.hook(support.CURSOR_HOOK,
                             dict(ids, hook_event_name="preToolUse",
                                  tool_name=name, tool_input=inp),
                             lambda out: out.get("agent_message")
                             if out.get("permission") == "deny" else None)
        if host == "omp":
            return self.hook(support.OMP_HOOK,
                             dict(ids, event="pre_tool_use", tool=name, input=inp),
                             lambda out: out.get("deny"))
        raise AssertionError("no builder for host %s" % host)

    def opencode(self, calls):
        """Every opencode cell in one plugin instance: [(name, args, sid)]."""
        spec = {"plugin": support.OPENCODE_PLUGIN, "dir": self.repo,
                "calls": [{"hook": "tool.execute.before",
                           "input": {"tool": name, "args": args, "sessionID": sid}}
                          for name, args, sid in calls]}
        proc = subprocess.run([NODE, support.OPENCODE_HARNESS],
                              input=json.dumps(spec), capture_output=True,
                              text=True, env=self.envv, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertNotIn("fatal", out, out.get("fatal"))
        return [None if r["ok"] else r["error"] for r in out["results"]]

    def test_every_host_agrees_with_the_core_outside_its_ceilings(self):
        corpus = load()
        ceilings = {(c["host"], c["vector"]) for c in corpus["ceilings"]}
        ids = {v["id"] for v in corpus["vectors"]}
        self.assertEqual(len(ids), len(corpus["vectors"]), "duplicate vector id")
        self.assertLessEqual({v for _, v in ceilings}, ids, "ceiling names no vector")
        verdicts, pending = {}, []
        for host, spec in corpus["hosts"].items():
            if host == "opencode" and not NODE:
                continue
            routed = matcher(host, spec)
            for vector in corpus["vectors"]:
                name = spec["tools"].get(vector["tool"])
                if name is None:
                    continue    # the host has no tool of this dialect
                inp = fill(vector["input"])
                sid = "v-%s-%s" % (host, vector["id"])
                if not routed(name):
                    verdicts[(host, vector["id"])] = None
                elif host == "opencode":
                    pending.append(((host, vector["id"]), name,
                                    {CAMEL.get(k, k): v for k, v in inp.items()},
                                    sid))
                else:
                    verdicts[(host, vector["id"])] = self.cell(host, name, inp, sid)
        if pending:
            for (key, *_), got in zip(pending, self.opencode(
                    [(name, args, sid) for _, name, args, sid in pending])):
                verdicts[key] = got
        expect = {v["id"]: v["expect"] for v in corpus["vectors"]}
        disagree = {key for key, got in verdicts.items()
                    if not ((got is None) if expect[key[1]] is None
                            else (got is not None and expect[key[1]] in got))}
        detail = {"%s/%s" % k: verdicts[k] for k in sorted(disagree - ceilings)}
        self.assertEqual(disagree - ceilings, set(),
                         "cells that disagree with the core: %s"
                         % json.dumps(detail, indent=1))
        stale = {k for k in ceilings if k in verdicts and k not in disagree}
        self.assertEqual(stale, set(), "ceilings that now agree: drop them")
        # the corpus is evidence only while it reaches every host it names
        self.assertEqual({h for h, _ in verdicts},
                         set(corpus["hosts"]) - (set() if NODE else {"opencode"}))


if __name__ == "__main__":
    unittest.main()
