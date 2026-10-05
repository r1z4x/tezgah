"""The reply after a Stop block: recorded, never judged a second time.

A host re-runs its Stop hook with `stop_hook_active` set when the model answers
a block. That reply used to be dropped unread, so the ledger could not say what a
block led to - a fix, an admission or the same claim again (REPORT.md §4.2,
evidence-03). Claude, Codex and omp now judge it in record-only mode: one
`after_block` row per reply, no decision printed, and a core that raises still
leaves the host its empty answer. Cursor is not wired: its payload is unverified.
"""
import os
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
        self.stop("claude", text="Done, ama testler doğrulanmadı.")
        self.assertEqual([r["detail"] for r in self.rows("after_block")], ["ok"])

    def test_a_reply_with_no_claim_still_leaves_its_row(self):
        # a session with no work: nothing to refuse and no claim made, which
        # the first stop would not record at all
        self.session = "s-clean"
        self.stop("claude", text="Parser yazıldı, sırada testler var.")
        self.assertEqual([r["detail"] for r in self.rows("after_block")],
                         ["no claim"])

    def test_off_root_and_verify_off_record_nothing(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        for host in ("claude", "codex", "omp"):
            with self.subTest(host=host):
                self.assertNotIn("decision", self.stop(host))
        self.assertEqual(self.rows("after_block"), [])

    def test_the_kind_is_not_a_tool_hook_row_and_not_a_claim(self):
        self.assertIn(b"after_block", tezgah_context.NOT_TOOL_HOOK)
        self.stop("claude")
        counts = self.counters()
        self.assertEqual((counts["claims"], counts["false_completion"]), (0, 0))

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
