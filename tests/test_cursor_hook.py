"""hosts/cursor/hook.py: event translation and the shared gate."""
import json
import os
import re
import unittest

import support
from support import TempHome, run_json


class CursorHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def call(self, payload):
        out, proc = run_json([support.CURSOR_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_session_start_returns_additional_context(self):
        out = self.call({"hook_event_name": "sessionStart", "cwd": self.repo,
                         "conversation_id": "s"})
        self.assertTrue(out["additional_context"].strip())

    def test_session_start_outside_roots_is_empty(self):
        out = self.call({"hook_event_name": "sessionStart", "cwd": self.home,
                         "conversation_id": "s"})
        self.assertEqual(out, {})

    def test_pre_tool_use_denies_attribution(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Shell",
                         "tool_input": {"command":
                                        'git commit -m "x Co-Authored-By: Claude"'},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out["permission"], "deny")
        self.assertTrue(out["agent_message"])

    def test_pre_tool_use_denies_explore(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Task",
                         "tool_input": {"subagent_type": "Explore"},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out["permission"], "deny")

    def test_pre_tool_use_allows_plain_commit(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Shell",
                         "tool_input": {"command": 'git commit -m "plain"'},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out, {"permission": "allow"})

    # ---- the write tools: the matcher has to reach the gate, and the payload
    # Cursor sends has to fit the gate's vocabulary ---------------------------
    def test_pre_tool_use_matcher_covers_the_write_tools(self):
        # Cursor runs a hook only for a tool type its matcher matches, and
        # Cursor's edit path is the `Write` tool. Without the write names in the
        # matcher the platform never calls this hook for an edit, so no hook code
        # can reach the gate's write branches.
        path = os.path.join(os.path.dirname(support.CURSOR_HOOK), "hooks.json")
        with open(path) as fh:
            groups = json.load(fh)["hooks"]["preToolUse"]
        pattern = re.compile("|".join(g["matcher"] for g in groups
                                      if isinstance(g.get("matcher"), str)))
        for tool in ("Shell", "Grep", "Task", "Write", "Edit"):
            self.assertTrue(pattern.search(tool), tool)

    def test_pre_tool_use_denies_a_credit_landed_by_the_write_tool(self):
        # Cursor's Write payload describes the change the way afterFileEdit does
        # (`edits: [{old_string, new_string}]`); this is the field the shared gate
        # reads, so a credit inside file content is denied here too.
        credit = "Co-Authored-By" + ": Someone <x@y>"
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Write",
                         "cwd": self.repo, "conversation_id": "s",
                         "tool_input": {"file_path": "src/a.py", "edits": [
                             {"old_string": "x = 1",
                              "new_string": "x = 1\n" + credit}]}})
        self.assertEqual(out["permission"], "deny")
        self.assertIn("Attribution", out["agent_message"])

    def test_pre_tool_use_denies_a_skip_added_by_the_write_tool(self):
        marker = "@pytest.mark." + "skip"
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Write",
                         "cwd": self.repo, "conversation_id": "s",
                         "tool_input": {"file_path": "tests/test_x.py",
                                        "content": marker + "\ndef test_x():\n    pass\n"}})
        self.assertEqual(out["permission"], "deny")
        self.assertIn(marker, out["agent_message"])

    def test_pre_tool_use_allows_a_plain_file_write(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Write",
                         "cwd": self.repo, "conversation_id": "s",
                         "tool_input": {"file_path": "src/a.py",
                                        "content": "x = 2\n"}})
        self.assertEqual(out, {"permission": "allow"})

    def test_the_gate_counts_the_failures_the_ledger_row_recorded(self):
        # One call, one id: the gate maps Cursor's `Shell` onto `Bash` and
        # `call_id` hashes the name it is handed, so a ledger row written under
        # the raw name gave the same call a second id - the loop guard read a
        # history that never matched and never denied. `postToolUseFailure` is
        # the event that carries the failure signal.
        for _ in range(2):
            self.call({"hook_event_name": "postToolUseFailure",
                       "cwd": self.repo, "conversation_id": "s",
                       "tool_name": "Shell",
                       "tool_input": {"command": "pytest -q"}})
        out = self.call({"hook_event_name": "preToolUse", "cwd": self.repo,
                         "conversation_id": "s", "tool_name": "Shell",
                         "tool_input": {"command": "pytest -q"}})
        self.assertEqual(out["permission"], "deny")
        self.assertTrue(out["agent_message"])

    # ---- used marks (what the status line turns green on) -------------------
    def kinds(self, session="s"):
        path = os.path.join(self.home, ".cache", "tezgah", "sessions",
                            support.slug(session) + ".jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line)["kind"] for line in fh if line.strip()]

    def test_a_mention_of_consult_is_not_a_use_of_it(self):
        # The mark means the tool ran. A grep whose argument names it, or a path
        # that carries the name, is not a call.
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": 'grep -rn "consult" docs/'}})
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "orx-notes.txt işle"}})
        self.assertEqual(self.kinds(), [])

    def test_a_real_consult_call_records_the_use(self):
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "bin/consult --online 'x mi y mi?'"}})
        self.assertIn("consult", self.kinds())

    def test_a_real_research_call_records_the_use(self):
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "orx experiment list"}})
        self.assertIn("research", self.kinds())

    def test_after_shell_execution_reads_the_command_on_the_event(self):
        self.call({"hook_event_name": "afterShellExecution", "cwd": self.repo,
                   "conversation_id": "s", "command": "bin/consult --online q"})
        self.assertIn("consult", self.kinds())

    # ---- the brief a delegated subagent gets --------------------------------
    def builder(self, event):
        """What the shared builder renders for an event inside this test's HOME."""
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": event,
                              "cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_subagent_start_briefs_the_delegate(self):
        # A Cursor subagent is a fresh context: it gets the same short contract
        # brief the other hosts hand a delegate, built once by the shared builder.
        out = self.call({"hook_event_name": "subagentStart", "cwd": self.repo,
                         "parent_conversation_id": "s",
                         "subagent_type": "generalPurpose",
                         "task": "index the docs"})
        self.assertEqual(out["permission"], "allow")
        self.assertEqual(out["additional_context"], self.builder("subagent_start"))

    def test_subagent_start_still_denies_a_grep_only_explorer(self):
        out = self.call({"hook_event_name": "subagentStart", "cwd": self.repo,
                         "parent_conversation_id": "s",
                         "subagent_type": "explore", "task": "find it"})
        self.assertEqual(out["permission"], "deny")
        self.assertNotIn("additional_context", out)

    def test_subagent_start_is_inert_outside_the_roots(self):
        out = self.call({"hook_event_name": "subagentStart", "cwd": self.home,
                         "parent_conversation_id": "s",
                         "subagent_type": "generalPurpose", "task": "t"})
        self.assertEqual(out, {"permission": "allow"})

    def test_before_submit_prompt_injects_the_reminder(self):
        out = self.call({"hook_event_name": "beforeSubmitPrompt", "cwd": self.repo})
        self.assertTrue(out["continue"])
        self.assertIn("harness-reminder", out["additional_context"])

    def test_before_submit_prompt_respects_reminder_off(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        out = self.call({"hook_event_name": "beforeSubmitPrompt", "cwd": self.repo})
        self.assertEqual(out, {"continue": True})

    # ---- the Stop rule (reply from afterAgentResponse, decision at stop) ---
    def response(self, text):
        return self.call({"hook_event_name": "afterAgentResponse", "cwd": self.repo,
                          "conversation_id": "s", "text": text})

    def stop(self, **extra):
        payload = {"hook_event_name": "stop", "cwd": self.repo,
                   "conversation_id": "s", "status": "completed"}
        payload.update(extra)
        return self.call(payload)

    def answer_file(self):
        """The file `remember_answer` writes for this test's conversation."""
        return os.path.join(self.home, ".cache", "tezgah", "answer",
                            support.slug("s"))

    def test_stop_blocks_a_done_claim_no_check_backs(self):
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "ls"}})
        self.response("Done. All tests pass.")
        out = self.stop()
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out["reason"])

    def test_stop_refuses_a_done_claim_whose_check_reported_no_outcome(self):
        # Cursor hands this hook no exit code on a successful call - only
        # `postToolUseFailure` carries a failure - so a shell check is recorded
        # as one that RAN. The Stop rule is the one every host runs: a "done"
        # the session cannot evidence does not end the turn, and the honest
        # spelling passes on the same evidence.
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "pytest -q"}})
        self.response("Done. All tests pass.")
        out = self.stop()
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out["reason"])
        self.response("Doğrulanmadı.")
        self.assertEqual(self.stop(), {})

    def test_stop_passes_a_claim_free_answer(self):
        self.response("Toplam 5 dosya incelendi.")
        self.assertEqual(self.stop(), {})

    def test_stop_ignores_an_aborted_turn(self):
        self.response("Done. All tests pass.")
        self.assertEqual(self.stop(status="aborted"), {})

    def test_stop_is_inert_outside_the_roots(self):
        self.call({"hook_event_name": "afterAgentResponse", "cwd": self.home,
                   "conversation_id": "s2", "text": "Done. All tests pass."})
        self.assertEqual(self.stop(cwd=self.home, conversation_id="s2"), {})

    # ---- the reply the stop decision reads back ------------------------------
    def test_a_long_reply_keeps_both_ends_the_stop_rule_reads(self):
        # The stored reply is what `stop` judges, and the rule reads both its
        # ends: the opener (SYCOPHANT anchors at the very start) and the closing
        # line. A tail-only slice stored the wrong half of every reply longer
        # than the budget, so the opener rule never fired on Cursor.
        long_reply = ("Haklısın, hemen düzeltiyorum.\n"
                      + "Ara satır. " * 450
                      + "\nİşte kapanış satırı. Doğrulanmadı.")
        self.assertGreater(len(long_reply), 4000)
        self.response(long_reply)
        with open(self.answer_file()) as fh:
            stored = fh.read()
        self.assertTrue(stored.startswith("Haklısın,"))
        self.assertTrue(stored.rstrip().endswith("Doğrulanmadı."))
        self.assertIn("characters dropped", stored)
        out = self.stop()
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("placation", out["reason"])

    def test_a_short_reply_is_stored_unchanged(self):
        # The cut is for the over-budget reply only: applying it to a short one
        # would hand the rule a marker it never wrote and lose the reply's text.
        self.response("Toplam 5 dosya incelendi.")
        with open(self.answer_file()) as fh:
            self.assertEqual(fh.read(), "Toplam 5 dosya incelendi.")


class CursorProvenance(TempHome):
    """The untrusted-content half on Cursor. Its postToolUse output carries
    `additional_context` ("extra context injected into the conversation after the
    tool result"), the field this hook already uses for the once-per-session
    code-graph reinforcement - so the two share the field instead of replacing
    each other. Cursor names an MCP tool by its server (`mcp_server_name`), which
    the adapter translates into the shared vocabulary's `mcp__<server>__<tool>`
    before the provenance test reads the name."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.conv = "c-untrusted"

    def call(self, tool, inp, conv=None, event="postToolUse", **extra):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "conversation_id": conv or self.conv, "tool_name": tool,
                   "tool_input": inp}
        payload.update(extra)
        out, proc = run_json([support.CURSOR_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def context(self, tool, inp, **kw):
        return self.call(tool, inp, **kw).get("additional_context", "")

    def rows(self, conv=None):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": conv or self.conv},
                          env=self.envv)
        return out

    def test_an_mcp_result_is_labelled_through_the_server_name(self):
        text = self.context("get_file", {"path": "x"}, mcp_server_name="github")
        self.assertIn("untrusted content", text)
        self.assertIn("an MCP server", text)

    def test_a_write_after_an_mcp_result_carries_the_channel(self):
        self.call("get_file", {"path": "x"}, mcp_server_name="github")
        out = self.call("Write", {"file_path": "/tmp/x"})
        self.assertIn("already read an MCP server", out["additional_context"])
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("external", "mcp"), ("edit", "mcp")])
        # one notice per read: the next write of the same turn is not marked
        self.assertEqual(self.call("Write", {"file_path": "/tmp/y"}), {})

    def test_the_notice_does_not_crowd_out_the_code_graph_reinforcement(self):
        # A graph call is an MCP call too, so the same result earns both lines;
        # one must not overwrite the other.
        text = self.context("callers", {"query": "x"},
                            mcp_server_name="codegraph")
        self.assertIn("untrusted content", text)
        self.assertIn("tezgah contract active", text)

    def test_an_ordinary_call_is_silent(self):
        self.assertEqual(self.call("Shell", {"command": "pytest -q"}), {})

    def test_outside_a_root_nothing_is_shown(self):
        self.assertEqual(
            self.context("get_file", {"path": "x"}, mcp_server_name="github",
                         cwd=self.home), "")


class CursorEvidence(TempHome):
    """The ledger the Stop rule reads on Cursor. Both events that carry the
    tool's own result - `postToolUse` with `tool_output`, `afterShellExecution`
    with the terminal `output` - hand this adapter a string, so the row keeps the
    result's size and never the result."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.conv = "c-evidence"

    def call(self, tool, inp, event="postToolUse", **extra):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "conversation_id": self.conv, "tool_name": tool,
                   "tool_input": inp}
        payload.update(extra)
        out, proc = run_json([support.CURSOR_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def rows(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.conv},
                          env=self.envv)
        return out

    def test_the_row_carries_the_result_size_and_never_the_result(self):
        # Cursor documents `tool_output` as the "JSON-stringified result payload
        # from the tool" and `output` as the full terminal output, so the size is
        # a length - O(1), no re-serialization - and the result itself is never
        # stored. Without this field the Stop rule's out_bytes guard read None on
        # every Cursor row and could never refuse the empty-result silent failure
        # it documents; a row for an empty result now records 0, the exact value
        # the guard refuses, rather than leaving the field out.
        result = '{"exitCode":0,"stdout":"All tests passed"}'
        self.call("Shell", {"command": "pytest -q"}, tool_output=result)
        self.call("Shell", {"command": "pytest -q"},
                  event="afterShellExecution", output="")
        ran, empty = self.rows()
        self.assertEqual((ran["kind"], ran["out_bytes"]),
                         ("verify", len(result)))
        self.assertEqual((empty["kind"], empty["out_bytes"]), ("verify", 0))
        self.assertNotIn("All tests passed", json.dumps(self.rows()))

    def test_a_result_the_event_does_not_carry_leaves_the_field_out(self):
        # Cursor's failure event reports an error, not a result, so the field
        # stays absent instead of being written as 0 - a row that claims an empty
        # result for a call that never returned one is the lie the ledger exists
        # to prevent.
        self.call("Shell", {"command": "pytest -q"},
                  event="postToolUseFailure", error_message="timed out")
        row = self.rows()[-1]
        self.assertEqual(row["kind"], "verify_fail")
        self.assertNotIn("out_bytes", row)

    def test_a_cancelled_or_denied_call_is_not_a_failed_check(self):
        # Cursor documents `is_interrupt` ("whether this failure was caused by a
        # user interrupt/cancellation") and `failure_type` on this event, and the
        # adapter hardcoded failed=True for both shapes: a `pytest` the user
        # cancelled, and one a policy denied before it ran, landed as verify_fail
        # with exit 1 - a failed check nobody saw fail, which armed the Stop
        # rule's partial-failure branch and the corpus error rate.
        self.call("Shell", {"command": "pytest -q"},
                  event="postToolUseFailure", is_interrupt=True)
        self.call("Shell", {"command": "pytest -q"},
                  event="postToolUseFailure", failure_type="permission_denied")
        rows = self.rows()
        self.assertEqual([r["kind"] for r in rows],
                         ["interrupted", "interrupted"])
        self.assertNotIn("exit", rows[0])


class CursorHookThroughTheInstalledLink(TempHome):
    """tezgah-setup wires cursor to ~/.config/tezgah/bin/tezgah-cursor-hook, a
    symlink; the hook must find the repo from the link path."""

    def test_events_run_through_the_symlink(self):
        repo = self.make_repo()
        env = self.env()
        env.pop("PYTHONPATH", None)  # the host's own environment carries none
        link = support.linked(support.CURSOR_HOOK, self.home)
        out, proc = run_json([link], {
            "hook_event_name": "preToolUse", "cwd": repo,
            "conversation_id": "s", "tool_name": "Shell",
            "tool_input": {"command": "pytest -q || true"}}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["permission"], "deny")


if __name__ == "__main__":
    unittest.main()
