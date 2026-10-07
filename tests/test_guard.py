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
import hashlib
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
        rows = support.all_ledger_rows(os.path.join(self.home, ".cache", "tezgah"))
        crashes = [r for r in rows if r.get("kind") == "crash"]
        self.assertTrue(crashes, "no crash row was written: %r" % rows)
        self.assertIn("decision", crashes[0].get("detail", ""))


# Run one entry point with an import forced to fail before it loads. `MOD:NAME`
# loads the module and removes the name, so the entry's own `from MOD import
# NAME` raises ImportError while the ledger still imports; a bare `MOD` makes
# every import of that module raise, the shape of a module that cannot load.
IMPORT_PROBE = (
    "import importlib.abc, os, runpy, sys\n"
    "hook, broken = sys.argv[1], sys.argv[2]\n"
    "sys.path.insert(0, %r)\n"
    "if ':' in broken:\n"
    "    mod, name = broken.split(':')\n"
    "    delattr(__import__(mod), name)\n"
    "else:\n"
    "    class Refuse(importlib.abc.MetaPathFinder):\n"
    "        def find_spec(self, fullname, path=None, target=None):\n"
    "            if fullname == broken:\n"
    "                raise ImportError('forced: ' + fullname)\n"
    "    sys.meta_path.insert(0, Refuse())\n"
    "sys.argv = [hook] + sys.argv[3:]\n"
    "runpy.run_path(hook, run_name='__main__')\n" % support.HOOKS)


class ImportGuard(TempHome):
    """Every entry point whose core imports sat outside `safe()`: a module that
    cannot import costs the call, never a traceback, and leaves a trace."""

    def entries(self, root):
        """(name, script, extra argv, payload, the name the entry imports first)."""
        bin_ = os.path.join(support.REPO, "bin")
        sid = {"session_id": "imp", "cwd": root}
        return [
            ("projects-stop", support.STOP_HOOK, [], sid, "tezgah_integrity:stop_reason"),
            ("projects-pretooluse", support.PRETOOLUSE, [], sid, "tezgah_gate:decision"),
            ("projects-posttooluse", support.POSTTOOLUSE, [], sid,
             "tezgah_context:GRAPH_TOOL_MARK"),
            ("projects-auto-init", support.AUTO_INIT, [], sid,
             "tezgah_context:context_for"),
            ("codex", support.CODEX_HOOK, [], sid, "tezgah_context:TOOL_USE_MEASURES"),
            ("cursor", support.CURSOR_HOOK, [], sid, "tezgah_context:command_text"),
            ("omp", support.OMP_HOOK, [], sid, "tezgah_context:color_default"),
            ("statusline", support.STATUSLINE, [], sid, "tezgah_context:GRAPH_TOOL_MARK"),
            ("tezgah-gate", os.path.join(bin_, "tezgah-gate"), ["check"], sid,
             "tezgah_gate:decision"),
            ("tezgah-context", os.path.join(bin_, "tezgah-context"),
             ["session_start", root], sid, "tezgah_context:context_for"),
            ("tezgah-capture", os.path.join(bin_, "tezgah-capture"),
             [json.dumps(dict(sid, tool="Edit", input={"file_path": "a.py"}))], None,
             "tezgah_snapshot:capture"),
        ]

    def probe(self, script, broken, argv, payload, root):
        import subprocess
        return subprocess.run(
            [sys.executable, "-c", IMPORT_PROBE, script, broken] + argv,
            input="" if payload is None else json.dumps(payload),
            capture_output=True, text=True, env=self.env([self.roots]), cwd=root,
            timeout=60)

    def rows(self):
        return support.all_ledger_rows(os.path.join(self.home, ".cache", "tezgah"))

    def expected_code(self, name):
        # `tezgah-gate check` is asked for a verdict: an empty answer with exit
        # 0 read as a pass from a gate that is not there. Every hook fails open.
        return 3 if name == "tezgah-gate" else 0

    def test_a_failed_import_fails_open_and_leaves_a_crash_row_and_a_line(self):
        root = self.make_repo()
        entries = self.entries(root)
        self.assertEqual(len(entries), 11)
        for name, script, argv, payload, broken in entries:
            with self.subTest(entry=name):
                proc = self.probe(script, broken, argv, payload, root)
                self.assertEqual(proc.returncode, self.expected_code(name), proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertNotIn("deny", proc.stdout)
                # the stderr line is written whether or not the row is
                self.assertIn("could not import its core", proc.stderr)
                crashes = [r for r in self.rows() if r.get("kind") == "crash"
                           and broken.split(":")[1] in r.get("detail", "")]
                self.assertTrue(crashes, "%s left no crash row" % name)
                self.assertTrue(crashes[-1]["detail"].startswith("import: ImportError"))
                # and the status line's mark for the session
                mark = os.path.join(self.home, ".cache", "tezgah", "import-crash",
                                    hashlib.sha256(b"imp").hexdigest()[:16])
                self.assertTrue(os.path.exists(mark), name)

    def test_an_unimportable_ledger_leaves_one_stderr_line_and_no_row(self):
        root = self.make_repo()
        for module in ("tezgah_integrity", "tezgah_paths"):
            for name, script, argv, payload, _broken in self.entries(root):
                with self.subTest(entry=name, module=module):
                    proc = self.probe(script, module, argv, payload, root)
                    self.assertEqual(proc.returncode, self.expected_code(name),
                                     proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)
                    self.assertIn("could not import its core", proc.stderr)
                    self.assertIn("forced: %s" % module, proc.stderr)
        self.assertEqual(self.rows(), [])

    def test_gate_decide_fails_open_while_check_says_it_cannot_answer(self):
        root = self.make_repo()
        gate = os.path.join(support.REPO, "bin", "tezgah-gate")
        call = {"tool": "Bash", "input": {"command": "git commit --no-verify -m x"},
                "cwd": root, "session_id": "imp"}
        check = self.probe(gate, "tezgah_gate", ["check"], call, root)
        decide = self.probe(gate, "tezgah_gate", ["decide"], call, root)
        self.assertEqual(check.returncode, 3, check.stderr)
        self.assertEqual(decide.returncode, 0, decide.stderr)
        self.assertIn("could not import its core", check.stderr)

    def test_the_status_line_says_the_core_is_down(self):
        root = self.make_repo()
        proc = self.probe(support.STATUSLINE, "tezgah_context", [], {"cwd": root}, root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("core import failed", proc.stdout)

    def test_a_dead_gate_shows_as_a_crash_mark_on_the_status_line(self):
        # A copy of the tree whose tezgah_gate.py does not parse: the gate hook
        # fails open and marks the session, and the status line - which reaches
        # tezgah_gate through the index mark - must still draw, with `crash`.
        import shutil
        import subprocess
        tree = os.path.join(self.home, "tree")
        shutil.copytree(support.HOOKS, os.path.join(tree, "hooks"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(support.STATUSLINE, os.path.join(tree, "statusline.py"))
        with open(os.path.join(tree, "hooks", "tezgah_gate.py"), "a") as fh:
            fh.write("\ndef broken(:\n")
        root = self.make_repo()
        os.makedirs(os.path.join(root, ".git"))
        # a graph binary, so the status line really asks the index mark
        env = dict(self.env([self.roots]), TEZGAH_CODEGRAPH_BIN=sys.executable)
        env.pop("PYTHONPATH", None)

        def run(script, payload):
            return subprocess.run([sys.executable, script], input=json.dumps(payload),
                                  capture_output=True, text=True, env=env, cwd=root,
                                  timeout=60)
        hook = run(os.path.join(tree, "hooks", "projects-pretooluse.py"),
                   {"cwd": root, "tool_name": "Bash", "session_id": "dead",
                    "tool_input": {"command": "git commit --no-verify -m x"}})
        self.assertEqual(hook.returncode, 0, hook.stderr)
        self.assertIn("could not import its core", hook.stderr)
        line = run(os.path.join(tree, "statusline.py"),
                   {"cwd": root, "session_id": "dead"})
        self.assertEqual(line.returncode, 0, line.stderr)
        self.assertNotIn("Traceback", line.stderr)
        self.assertIn("crash", line.stdout)

    def test_a_broken_attestation_module_never_costs_the_gate(self):
        # tezgah_attest is imported only inside the attest call (under safe):
        # a module that cannot load must leave every PreToolUse deny standing
        root = self.make_repo()
        deny = "git commit --no-verify -m x"
        rows = [
            (support.PRETOOLUSE, {"cwd": root, "tool_name": "Bash", "session_id": "a1",
                                  "tool_input": {"command": deny}}),
            (support.CODEX_HOOK, {"hook_event_name": "PreToolUse", "cwd": root,
                                  "tool_name": "Bash", "session_id": "a1",
                                  "tool_input": {"command": deny}}),
            (support.CURSOR_HOOK, {"hook_event_name": "preToolUse", "cwd": root,
                                   "tool_name": "Shell", "conversation_id": "a1",
                                   "tool_input": {"command": deny}}),
            (support.OMP_HOOK, {"event": "pre_tool_use", "cwd": root, "tool": "bash",
                                "input": {"command": deny}, "session_id": "a1"}),
        ]
        for script, payload in rows:
            with self.subTest(hook=script):
                proc = self.probe(script, "tezgah_attest", [], payload, root)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("deny", proc.stdout)
        for script, payload in (
                (support.AUTO_INIT, {"hook_event_name": "SessionStart", "cwd": root,
                                     "session_id": "a1"}),
                (support.CODEX_HOOK, {"hook_event_name": "SessionStart", "cwd": root,
                                      "session_id": "a1"})):
            with self.subTest(start=script):
                proc = self.probe(script, "tezgah_attest", [], payload, root)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)


class DebugLog(TempHome):
    """TEZGAH_DEBUG (audit L-11, GAP-10): one line per hook process naming the
    host, the script, each guarded core call with its outcome and the elapsed
    time, in an owner-only file - and nothing at all when the variable is unset."""

    def log_path(self):
        return os.path.join(self.home, ".cache", "tezgah", "debug.log")

    def deny_call(self, env):
        root = self.make_repo()
        proc = support.run([support.CODEX_HOOK],
                           {"hook_event_name": "PreToolUse", "cwd": root,
                            "tool_name": "Bash", "session_id": "d1",
                            "tool_input": {"command": "git commit --no-verify -m x"}},
                           env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("deny", proc.stdout)
        return root

    def test_off_by_default_writes_nothing(self):
        self.deny_call(self.env())
        self.assertFalse(os.path.exists(self.log_path()))

    def test_on_it_writes_one_owner_only_line_per_invocation(self):
        env = self.env(extra={"TEZGAH_DEBUG": "1"})
        root = self.deny_call(env)
        support.run([support.OMP_HOOK], {"event": "pre_tool_use", "cwd": root,
                                         "tool": "bash", "input": {"command": "ls"},
                                         "session_id": "d1"}, env=env)
        with open(self.log_path()) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertRegex(lines[0], r"^\d+ host=codex script=hook\.py "
                                   r"calls=gate_reason:answer ms=\d+$")
        self.assertRegex(lines[1], r" host=omp script=hook\.py calls=handle:answer ")
        self.assertEqual(os.stat(self.log_path()).st_mode & 0o777, 0o600)

    def test_a_crash_is_logged_by_its_exception_class(self):
        env = self.env([self.roots], extra={"TEZGAH_DEBUG": "1"})
        root = self.make_repo()
        support.run([support.PROBE_POISONED, support.PRETOOLUSE, "tezgah_gate",
                     "decision"],
                    payload={"cwd": root, "tool_name": "Bash",
                             "tool_input": {"command": "ls"}, "session_id": "d2"},
                    env=env, cwd=root)
        with open(self.log_path()) as fh:
            # the probe replaces the core function with its own raiser, so the
            # class - not the name - is what this line is about
            self.assertRegex(fh.read(), r"calls=\w+:RuntimeError ms=\d+")
