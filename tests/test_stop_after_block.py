"""The reply after a Stop block, the refusal row and the subagent's end.

A host re-runs its Stop hook with `stop_hook_active` set when the model answers
a block. That reply used to be dropped unread, so the ledger could not say what a
block led to - a fix, an admission or the same claim again (REPORT.md §4.2,
evidence-03). Claude, Codex and omp now judge it in record-only mode: one
`after_block` row per reply, no decision printed, and a core that raises still
leaves the host its empty answer. Cursor's `stop` is not wired: no real payload
was captured.

A refused reply that claimed nothing is a `refusal` row, not a `claim` (part h),
and a subagent's end on Claude and Cursor leaves a record-only `subagent_end`
row (part k, ADR 011).
"""
import os
import re
import sys
import unittest

import support
from support import TempHome, run, run_json

sys.path.insert(0, support.HOOKS)
import tezgah_context  # noqa: E402

CLAIM = "Done. Implemented the parser and all tests pass."


class AfterBlock(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-after"
        self.work()

    def work(self):
        """Work with no passing check: the first stop on a claim is refused."""
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "ls"}, "failed": False}, env=self.envv)

    def payload(self, host, text=CLAIM, active=True):
        if host == "omp":
            return [support.OMP_HOOK], {
                "event": "stop", "cwd": self.repo, "session_id": self.session,
                "last_assistant_message": text, "stop_hook_active": active}
        hook = support.STOP_HOOK if host == "claude" else support.CODEX_HOOK
        return [hook], {
            "hook_event_name": "Stop", "cwd": self.repo,
            "session_id": self.session, "last_assistant_message": text,
            "stop_hook_active": active}

    def stop(self, host, **kw):
        args, payload = self.payload(host, **kw)
        out, proc = run_json(args, payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def rows(self, kind):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session},
                          env=self.envv)
        return [r for r in out if r.get("kind") == kind]

    def counters(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "counters", "session": self.session},
                          env=self.envv)
        return out

    def test_the_reply_after_a_block_writes_one_row_and_no_decision(self):
        for host in ("claude", "codex", "omp"):
            with self.subTest(host=host):
                self.session = "s-after-" + host
                self.work()
                self.assertEqual(self.stop(host, active=False).get("decision"),
                                 "block")
                out = self.stop(host)
                self.assertNotIn("decision", out)
                # the same reply handed over twice is still one reply
                self.stop(host)
                rows = self.rows("after_block")
                self.assertEqual([r["detail"] for r in rows],
                                 ["would block: no verify_ok"])
                self.assertTrue(rows[0].get("id"))
                # the refusal is the one claim row; the reply after it is not
                self.assertEqual([r["detail"] for r in self.rows("claim")],
                                 ["blocked: no verify_ok"])

    def test_an_honest_reply_after_a_block_records_its_verdict(self):
        self.stop("claude", active=False)
        self.stop("claude", text="Done, ama testler doğrulanmadı.")
        self.assertEqual([r["detail"] for r in self.rows("after_block")], ["ok"])

    def test_a_reply_with_no_claim_still_leaves_its_row(self):
        # a session with no work, refused for its opener only
        self.session = "s-clean"
        self.assertEqual(self.stop("claude", text="Haklısın, düzelttim.",
                                   active=False).get("decision"), "block")
        self.stop("claude", text="Parser yazıldı, sırada testler var.")
        self.assertEqual([r["detail"] for r in self.rows("after_block")],
                         ["no claim"])

    def test_another_hooks_block_leaves_no_row(self):
        # `stop_hook_active` says only that SOME Stop hook blocked: with no
        # tezgah refusal in the turn the reply is not an answer to this rule
        for host in ("claude", "codex", "omp"):
            with self.subTest(host=host):
                self.assertNotIn("decision", self.stop(host))
        self.assertEqual(self.rows("after_block"), [])
        self.assertEqual(self.rows("shape"), [])

    def test_an_allowed_claim_is_not_a_block_to_answer(self):
        self.session = "s-clean"
        self.assertNotIn("decision", self.stop("claude", text="Done.",
                                               active=False))
        self.assertEqual([r["detail"] for r in self.rows("claim")], ["ok"])
        self.stop("claude", text="Done, ve testler geçti.")
        self.assertEqual(self.rows("after_block"), [])

    def turn(self, prompt):
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_turn", "session": self.session, "prompt": prompt},
                 env=self.envv)

    def test_only_a_block_in_this_turn_is_answered(self):
        # the lookup is turn-scoped: a refusal in an earlier turn is not the
        # block this reply answers
        self.session = "s-turns"
        self.turn("first")
        self.work()
        self.assertEqual(self.stop("claude", active=False).get("decision"),
                         "block")
        self.turn("second")
        self.stop("claude", text="Done. Testler doğrulanmadı.")
        self.assertEqual(self.rows("after_block"), [])
        # the control: the same shape inside one turn leaves exactly one row
        self.session = "s-one-turn"
        self.turn("first")
        self.work()
        self.assertEqual(self.stop("claude", active=False).get("decision"),
                         "block")
        self.stop("claude", text="Done. Testler doğrulanmadı.")
        self.assertEqual([r["detail"] for r in self.rows("after_block")], ["ok"])

    def test_verify_off_records_nothing(self):
        self.stop("claude", active=False)
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        for host in ("claude", "codex", "omp"):
            with self.subTest(host=host):
                self.assertNotIn("decision", self.stop(host))
        self.assertEqual(self.rows("after_block"), [])

    def test_the_kind_is_not_a_tool_hook_row_and_not_a_claim(self):
        self.assertIn(b"after_block", tezgah_context.NOT_TOOL_HOOK)
        self.stop("claude", active=False)
        self.stop("claude", text="Parser yazıldı; testler doğrulanmadı.")
        self.assertEqual(len(self.rows("after_block")), 1)
        counts = self.counters()
        # the refusal is the one claim, and the one reply the shape rate sees
        self.assertEqual((counts["claims"], counts["false_completion"],
                          counts["replies"]), (1, 1, 1))

    def test_a_work_only_refusal_is_a_refusal_not_a_claim(self):
        # ROW_VERSION 3: the reply claimed nothing, so false_completion/claims
        # does not count it; the class stays, with the cause beside it
        self.assertEqual(self.stop("claude", text="Parser yazıldı.",
                                   active=False).get("decision"), "block")
        rows = self.rows("refusal")
        self.assertEqual([(r["detail"], r.get("cause"), r.get("v")) for r in rows],
                         [("blocked: no verify_ok", "no check", 3)])
        self.assertEqual(self.rows("claim"), [])
        counts = self.counters()
        self.assertEqual((counts["claims"], counts["false_completion"],
                          counts["refusals"]), (0, 0, 1))
        # a refusal is a block this rule made, so the reply after it is answered
        self.stop("claude", text="Parser yazıldı; testler doğrulanmadı.")
        self.assertEqual([r["detail"] for r in self.rows("after_block")],
                         ["no claim"])

    def test_a_check_with_no_outcome_is_cause_outcome_unread(self):
        self.session = "s-unread"
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "pytest -q"}}, env=self.envv)
        self.assertEqual(self.stop("claude", active=False).get("decision"), "block")
        self.assertEqual([(r["detail"], r.get("cause")) for r in self.rows("claim")],
                         [("blocked: no verify_ok", "outcome unread")])

    def subagent_stop(self, host, text=CLAIM):
        if host == "cursor":
            args, payload = [support.CURSOR_HOOK], {
                "hook_event_name": "subagentStop", "conversation_id": self.session,
                "workspace_roots": [self.repo], "status": "completed",
                "summary": text}
        else:
            args, payload = [support.STOP_HOOK], {
                "hook_event_name": "SubagentStop", "cwd": self.repo,
                "session_id": self.session, "last_assistant_message": text,
                "stop_hook_active": False}
        out, proc = run_json(args, payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def test_a_subagent_end_is_recorded_never_blocked(self):
        for host in ("claude", "cursor"):
            with self.subTest(host=host):
                self.session = "s-sub-" + host
                self.work()
                self.assertEqual(self.subagent_stop(host), {})
                self.assertEqual([r["detail"] for r in self.rows("subagent_end")],
                                 ["would block: no verify_ok"])
                # not a claim, not a reply in the shape rate, not an after-block
                for kind in ("claim", "refusal", "shape", "after_block"):
                    self.assertEqual(self.rows(kind), [], kind)

    def test_a_subagent_report_is_not_judged_for_its_shape(self):
        # a delegate reports to its parent in English; the record reads the
        # evidence half only
        self.session = "s-sub-shape"
        english = ("The parser change is in place and the report below lists "
                   "every file that was touched together with the reason for "
                   "each edit so the parent can review it before merging it.")
        self.subagent_stop("claude", text=english)
        self.assertEqual([r["detail"] for r in self.rows("subagent_end")],
                         ["no claim"])

    def test_a_raising_core_at_a_subagent_end_answers_empty(self):
        proc = run([support.PROBE_POISONED, support.STOP_HOOK,
                    "tezgah_integrity", "stop_reason"],
                   {"hook_event_name": "SubagentStop", "cwd": self.repo,
                    "session_id": self.session,
                    "last_assistant_message": CLAIM},
                   env=self.envv, cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_a_subagent_end_row_names_its_agent(self):
        # plan 055 separates subagent rows from the parent's by this field
        self.session = "s-sub-agent"
        self.work()
        out, proc = run_json([support.STOP_HOOK], {
            "hook_event_name": "SubagentStop", "cwd": self.repo,
            "session_id": self.session, "agent_id": "a-123",
            "last_assistant_message": CLAIM}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([r.get("agent") for r in self.rows("subagent_end")],
                         ["a-123"])

    def test_new_kinds_are_not_tool_hook_rows(self):
        for kind in (b"after_block", b"refusal", b"subagent_end"):
            self.assertIn(kind, tezgah_context.NOT_TOOL_HOOK)

    def test_every_stop_adapter_re_asks_once(self):
        # ADR 011: one re-ask per host, a per-host constant, value 1 everywhere
        for path in (support.STOP_HOOK, support.CODEX_HOOK, support.OMP_HOOK,
                     support.CURSOR_HOOK):
            with open(path, encoding="utf-8") as fh:
                self.assertRegex(fh.read(), re.compile(r"^STOP_REASKS = 1$", re.M),
                                 path)

    def test_a_raising_core_still_yields_an_empty_answer(self):
        for host in ("claude", "codex", "omp"):
            with self.subTest(host=host):
                args, payload = self.payload(host)
                proc = run([support.PROBE_POISONED, args[0],
                            "tezgah_integrity", "stop_reason"],
                           payload, env=self.envv, cwd=self.repo)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertNotIn("decision", proc.stdout)
                if host != "codex":
                    self.assertEqual(proc.stdout.strip(), "")
        self.assertEqual(self.rows("after_block"), [])


if __name__ == "__main__":
    unittest.main()
