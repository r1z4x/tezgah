"""hosts/amp/tezgah-plugin.ts.in: the wiring from Amp's plugin events to the hook.

The rendered plugin is imported by node (which strips its type annotations)
against a stub PluginAPI, as tests/test_omp_extension.py does for omp, so which
Amp event reaches the hook - and what Amp is told to do with the answer - is
checked without Amp. The hook's own behaviour is tests/test_amp_hook.py's.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

import support
from support import TempHome
from test_omp_extension import node_loads_ts

DENIED = "git commit --no-verify -m x"
MARK = "[tezgah:stop]"


class AmpPlugin(TempHome):
    def setUp(self):
        super().setUp()
        self.node = shutil.which("node")
        if not self.node:
            self.skipTest("node is not installed")
        if not node_loads_ts(self.node):
            self.skipTest("node on PATH cannot load a .ts file (needs 22.18+)")
        self.repo = self.make_repo("proj")
        self.plugin = self.render(support.AMP_HOOK)

    def render(self, hook, name="tezgah.ts"):
        """The installed form: the template with the hook's absolute path in it."""
        with open(support.AMP_PLUGIN) as fh:
            text = fh.read().replace("@HOOK@", hook)
        self.assertNotIn("@HOOK@", text)
        path = os.path.join(self.home, name)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def fake_hook(self, answer, code=0):
        """A stand-in python half: records every payload and answers `answer`."""
        log = os.path.join(self.home, "asked.jsonl")
        path = os.path.join(self.home, "fake-hook.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("import json, sys\n"
                     "payload = json.load(sys.stdin)\n"
                     "open(%r, 'a').write(json.dumps(payload) + '\\n')\n"
                     "print(json.dumps(%r))\n"
                     "sys.exit(%d)\n" % (log, answer, code))
        self.plugin = self.render(path, name="fake.ts")
        return log

    def asked(self, log):
        with open(log) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def drive(self, calls, **spec):
        spec = dict({"plugin": self.plugin, "dir": self.repo, "thread": "T-1",
                     "parent": None, "active": False, "calls": calls}, **spec)
        proc = subprocess.run([self.node, support.AMP_HARNESS], input=json.dumps(spec),
                              capture_output=True, text=True, env=self.env(), timeout=120,
                              cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertNotIn("fatal", out, out.get("fatal"))
        errors = [r.get("error") for r in out["results"]]
        self.assertEqual(errors, [None] * len(errors), out["results"])
        return out

    def outs(self, out):
        return [r["out"] for r in out["results"]]

    def test_registers_the_five_amp_events(self):
        self.assertEqual(sorted(self.drive([])["handlers"]),
                         ["agent.end", "agent.start", "session.start", "tool.call",
                          "tool.result"])

    def test_a_bash_cmd_the_gate_refuses_is_rejected_and_the_turn_goes_on(self):
        for helpers in (True, False):
            out = self.drive([{"event": "tool.call", "arg": {
                "tool": "Bash", "toolUseID": "t1", "input": {"cmd": DENIED}}}],
                noHelpers=not helpers)
            res, = self.outs(out)
            self.assertEqual(res["action"], "reject-and-continue", helpers)
            self.assertIn("--no-verify", res["message"])

    def test_an_ungated_or_allowed_call_is_an_explicit_allow(self):
        log = self.fake_hook({})
        out = self.drive([{"event": "tool.call", "arg": {"tool": "Read", "input": {}}},
                          {"event": "tool.call", "arg": {"tool": "Bash",
                                                         "input": {"cmd": "ls"}}}])
        self.assertEqual(self.outs(out), [{"action": "allow"}] * 2)
        # Read never spawned the hook; the Bash call did, with `command` filled in
        asked = self.asked(log)
        self.assertEqual([a["tool"] for a in asked], ["Bash"])
        self.assertEqual(asked[0]["input"]["command"], "ls")
        self.assertEqual(asked[0]["session_id"], "T-1")

    def test_a_dead_hook_allows_and_is_told_once_per_thread(self):
        self.plugin = self.render(os.path.join(self.home, "missing", "hook.py"), "dead.ts")
        call = {"event": "tool.call", "arg": {"tool": "Bash", "input": {"cmd": DENIED}}}
        out = self.drive([call, call, {"event": "agent.start", "arg": {"message": "hi"}},
                          {"event": "agent.end", "arg": {"status": "done", "message": "hi",
                                                         "messages": []}}],
                         active=True)
        allow, again, start, end = self.outs(out)
        self.assertEqual((allow, again), ({"action": "allow"},) * 2)
        self.assertEqual(len(out["notified"]), 1, out["notified"])
        self.assertIn("tezgah: its Amp hook failed", start["message"]["content"])
        self.assertIs(start["message"]["display"], False)
        self.assertIsNone(end)
        self.assertIn("hook\u2717 tezgah hook failed", out["status"])

    def test_a_done_turn_the_rule_blocks_continues_with_the_marker(self):
        log = self.fake_hook({"decision": "block", "reason": "no check ran"})
        reply = [{"role": "user", "content": [{"type": "text", "text": "go"}]},
                 {"role": "assistant", "content": [{"type": "thinking", "thinking": "x"},
                                                   {"type": "text", "text": "Done."}]}]
        out = self.drive([
            {"event": "agent.end", "arg": {"status": "done", "message": "go",
                                           "messages": reply}},
            {"event": "agent.end", "arg": {"status": "done", "message": MARK + " no check",
                                           "messages": reply}},
            {"event": "agent.end", "arg": {"status": "cancelled", "message": "go",
                                           "messages": reply}}])
        first, second, cancelled = self.outs(out)
        self.assertEqual(first, {"action": "continue",
                                 "userMessage": MARK + " no check ran"})
        self.assertNotIn("maxContinuations", first)
        self.assertEqual(second["action"], "continue")
        self.assertIsNone(cancelled)
        stops = [a for a in self.asked(log) if a["event"] == "stop"]
        self.assertEqual([(s["last_assistant_message"], s["stop_hook_active"])
                          for s in stops], [("Done.", False), ("Done.", True)])

    def test_the_marker_prompt_is_never_sent_as_the_user_prompt(self):
        log = self.fake_hook({"context": "CTX"})
        out = self.drive([{"event": "session.start", "arg": {}},
                          {"event": "agent.start", "arg": {"message": "fix it"}},
                          {"event": "agent.start", "arg": {"message": MARK + " again"}}])
        _, first, marked = self.outs(out)
        self.assertEqual(first, {"message": {"content": "CTX\n\nCTX", "display": False}})
        self.assertEqual(marked, {})
        events = [a["event"] for a in self.asked(log)]
        self.assertEqual(events, ["session_start", "user_prompt"])
        prompt = [a for a in self.asked(log) if a["event"] == "user_prompt"][0]
        self.assertEqual((prompt["prompt"], prompt["subagent"]), ("fix it", False))

    def test_a_tool_result_sends_an_exit_code_only_from_an_integer_on_an_object(self):
        log = self.fake_hook({})
        results = [("done", "ok"), ("done", {"output": "ok", "exitCode": 0}),
                   ("done", {"output": "ok", "exitCode": "0"}), ("error", "boom")]
        self.drive([{"event": "tool.result", "arg": {
            "tool": "Bash", "toolUseID": "t", "input": {"cmd": "pytest"},
            "status": status, "output": output}} for status, output in results])
        asked = self.asked(log)
        self.assertEqual([a.get("exit_code") for a in asked], [None, 0, None, None])
        self.assertEqual([a["status"] for a in asked], ["done", "done", "done", "error"])
        self.assertEqual([a["result_len"] for a in asked], [2, 2, 2, 4])
        self.assertTrue(all("output" not in a for a in asked))

    def test_a_labelled_result_keeps_its_status_and_gets_the_label_first(self):
        self.fake_hook({"label": "LABEL"})
        out = self.drive([
            {"event": "tool.result", "arg": {"tool": "read_web_page", "input": {},
                                             "status": "done", "output": "page"}},
            {"event": "tool.result", "arg": {"tool": "mcp__x__get", "input": {},
                                             "status": "done",
                                             "output": [{"type": "text", "text": "t"}]}},
            {"event": "tool.result", "arg": {"tool": "web_search", "input": {},
                                             "status": "done", "output": {"rows": 1}}},
            {"event": "tool.result", "arg": {"tool": "Read", "input": {"path": "/x"},
                                             "status": "done", "output": "x"}}])
        page, mcp, odd, read = self.outs(out)
        self.assertEqual(page, {"status": "done", "output": "LABEL\npage"})
        self.assertEqual(mcp["output"][0], {"type": "text", "text": "LABEL"})
        self.assertIsNone(odd)
        self.assertIsNone(read)

    def test_a_subagent_thread_is_briefed_as_one_and_only_recorded_at_its_end(self):
        log = self.fake_hook({"decision": "block", "reason": "r"})
        out = self.drive([{"event": "agent.start", "arg": {"message": "task brief"}},
                          {"event": "agent.end", "arg": {"status": "done",
                                                         "message": "task brief",
                                                         "messages": []}}],
                         parent="T-parent")
        self.assertIsNone(self.outs(out)[1])
        asked = self.asked(log)
        self.assertEqual([a["event"] for a in asked],
                         ["session_start", "user_prompt", "subagent_stop"])
        self.assertEqual((asked[0]["subagent"], asked[0]["parent"]), (True, "T-parent"))
        self.assertEqual(asked[2]["parent"], "T-parent")

    def test_the_status_item_shows_only_the_active_thread(self):
        self.fake_hook({"status": "pony\u2713 line", "idx": "\u2713"})
        session = [{"event": "session.start", "arg": {}}]
        self.assertEqual(self.drive(session, active=True)["status"], ["pony\u2713 line"])
        self.assertEqual(self.drive(session, active=False)["status"], [])

    def test_the_empty_run_literal_is_the_cores(self):
        sys.path.insert(0, support.HOOKS)
        import tezgah_integrity as ti
        with open(support.AMP_PLUGIN) as fh:
            text = fh.read()
        m = re.search(r"^const EMPTY_RUN = /(.*)/(\w*);$", text, re.M)
        self.assertEqual(m.group(1), ti.EMPTY_RUN.pattern)
        self.assertEqual(set(m.group(2)), {"i", "m"})
        self.assertIn("const EMPTY_RUN_TAIL = %d;" % ti.EMPTY_RUN_TAIL, text)


if __name__ == "__main__":
    unittest.main()
