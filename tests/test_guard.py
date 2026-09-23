"""hooks/tezgah_guard.py, and the entry points it wraps.

One rule, pinned host by host: a core call that raises costs one feature, never
the session. It is measured the way a host actually calls a hook - one process,
the payload on stdin - with the core function replaced by a raiser *before* the
hook is loaded (`tests/_probe_poisoned.py`), so what is under test is the hook's
guard and not the core. An unguarded hook lets the traceback out and exits
non-zero, which is the failure this file exists to catch: on omp the bridge turns
that same crash into a session-wide disable of the gate, the ledger and the
status line.

The crash is also asserted to be *recorded*: a swallowed fault that leaves no row
is indistinguishable from a rule that never fired, which is the reason the gate
records every refusal it makes (hooks/tezgah_gate._deny).
"""
import glob
import json
import os
import sys

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_guard as tg  # noqa: E402
import tezgah_integrity  # noqa: E402


def boom(*_args, **_kwargs):
    raise RuntimeError("poisoned core")


class Unit(TempHome):
    """`safe` itself: the value, the None, and the row that must not raise."""

    def test_it_returns_the_value_and_passes_arguments_through(self):
        self.assertEqual(tg.safe(None, lambda a, b=0: a + b, 2, b=3), 5)

    def test_it_returns_none_when_the_call_raises(self):
        self.assertIsNone(tg.safe(None, boom))

    def test_it_never_raises_even_when_the_row_cannot_be_written(self):
        # the guard is best effort by construction: a guard that raised while
        # reporting a raise would be the failure it exists to stop
        real = tezgah_integrity.note
        tezgah_integrity.note = boom
        try:
            self.assertIsNone(tg.safe("s", boom))
        finally:
            tezgah_integrity.note = real


class EntryPoints(TempHome):
    """One row per host entry point and the core call it makes first."""

    def rows(self, root):
        return [
            ("claude pretooluse", support.PRETOOLUSE, "tezgah_gate", "decision",
             {"cwd": root, "tool_name": "Bash", "tool_input": {"command": "ls -la"},
              "session_id": "g1"}),
            ("claude auto-init", support.AUTO_INIT, "tezgah_context", "context_for",
             {"hook_event_name": "SessionStart", "cwd": root, "session_id": "g1"}),
            ("claude posttooluse", support.POSTTOOLUSE, "tezgah_integrity",
             "note_tool",
             {"hook_event_name": "PostToolUse", "cwd": root, "tool_name": "Bash",
              "tool_input": {"command": "ls"}, "tool_response": {"ok": True},
              "session_id": "g1"}),
            ("claude stop", support.STOP_HOOK, "tezgah_integrity", "stop_reason",
             {"cwd": root, "session_id": "g1",
              "last_assistant_message": "done, tests pass"}),
            ("codex", support.CODEX_HOOK, "tezgah_gate", "decision",
             {"hook_event_name": "PreToolUse", "cwd": root, "tool_name": "Bash",
              "tool_input": {"command": "ls"}, "session_id": "g1"}),
            ("cursor", support.CURSOR_HOOK, "tezgah_gate", "decision",
             {"hook_event_name": "preToolUse", "cwd": root, "tool_name": "Shell",
              "tool_input": {"command": "ls"}, "conversation_id": "g1"}),
            ("omp", support.OMP_HOOK, "tezgah_gate", "decision",
             {"event": "pre_tool_use", "cwd": root, "tool": "bash",
              "input": {"command": "ls"}, "session_id": "g1"}),
        ]

    def probe(self, hook, module, function, payload, root):
        return support.run([support.PROBE_POISONED, hook, module, function],
                           payload=payload, env=self.env([self.roots]), cwd=root)

    def test_a_crashing_core_leaves_the_host_with_its_own_answer(self):
        root = self.make_repo()
        for name, hook, module, function, payload in self.rows(root):
            with self.subTest(host=name):
                proc = self.probe(hook, module, function, payload, root)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                # fail open: a core that crashed refused nothing, so the host is
                # told nothing - not that the call was denied
                self.assertNotIn("deny", proc.stdout)
                self.assertNotIn("\"block\"", proc.stdout)

    def test_the_crash_is_recorded_rather_than_swallowed(self):
        root = self.make_repo()
        name, hook, module, function, payload = self.rows(root)[0]
        self.probe(hook, module, function, payload, root)
        rows = []
        for path in glob.glob(os.path.join(self.home, ".cache", "tezgah",
                                           "evidence", "*.jsonl")):
            with open(path) as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
        crashes = [r for r in rows if r.get("kind") == "crash"]
        self.assertTrue(crashes, "no crash row was written: %r" % rows)
        self.assertIn("decision", crashes[0].get("detail", ""))
