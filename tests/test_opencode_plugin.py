"""hosts/opencode/plugins/tezgah.js: the opencode half of the contract.

The Python gate is covered by test_gate/test_integrity; the plugin is a second,
independent implementation of the same rules in JavaScript. This drives its
hooks through a node harness with a throwaway HOME, so a drift between the two
implementations fails here instead of silently in a session. Skips when node is
missing, matching the other node-dependent checks.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import support
from support import TempHome

NODE = shutil.which("node")
# The marker the detector must catch, assembled at runtime: the gate denies a
# file that adds the literal marker, so the test source must not carry it whole.
SKIP_MARK = "@pytest.mark." + "skip"


class OpenCodePlugin(TempHome):
    def setUp(self):
        if not NODE:
            self.skipTest("node not installed")
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def drive(self, calls, directory=None):
        spec = {"plugin": support.OPENCODE_PLUGIN,
                "dir": directory or self.repo, "calls": calls}
        proc = subprocess.run(
            [NODE, support.OPENCODE_HARNESS], input=json.dumps(spec),
            capture_output=True, text=True, env=self.envv, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertNotIn("fatal", out, out.get("fatal"))
        return out["results"]

    def before(self, tool, args, session="s1", directory=None):
        return self.drive([{"hook": "tool.execute.before",
                            "input": {"tool": tool, "args": args,
                                      "sessionID": session}}], directory)[0]

    def denied(self, res):
        self.assertFalse(res["ok"], res)
        return res["error"]

    def allowed(self, res):
        self.assertTrue(res["ok"], res)
        return res

    def ledger(self, session="s1"):
        path = os.path.join(self.home, ".cache", "tezgah", "evidence",
                            support.slug(session) + ".jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def kinds(self, session="s1"):
        return [entry["kind"] for entry in self.ledger(session)]

    def used(self, session="s1"):
        """The used-tool kinds recorded for the status line (session ledger)."""
        path = os.path.join(self.home, ".cache", "tezgah", "sessions",
                            support.slug(session) + ".jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line)["kind"] for line in fh if line.strip()]

    # ---- shortcut gate -----------------------------------------------------
    def test_no_verify_commit_denied(self):
        for command in ("git commit -m x --no-verify", "git push --no-verify"):
            self.denied(self.before("bash", {"command": command}))

    def test_skip_env_denied(self):
        for command in ("SKIP=flake8 git commit -m x",
                        "HUSKY_SKIP_HOOKS=1 git commit -m x",
                        "HUSKY=0 git commit -m x"):
            self.denied(self.before("bash", {"command": command}))

    def test_neutered_check_denied(self):
        for command in ("pytest || true", "ruff check . ; true",
                        "cargo test || exit 0"):
            self.denied(self.before("bash", {"command": command}))

    def test_plain_commands_pass(self):
        for command in ("pytest -q", "git commit -m 'fix: typo'", "git status",
                        "make test", "ls || true"):
            self.allowed(self.before("bash", {"command": command}))

    def test_skip_env_mention_in_a_read_passes(self):
        # SKIP= only turns checks off inside a hook runner; a search that merely
        # mentions it must not be denied
        for command in ('grep -rn "SKIP=" .', "rg 'HUSKY_SKIP_HOOKS=' src/"):
            self.allowed(self.before("bash", {"command": command}))

    def test_verify_off_drops_the_shortcut_denials_only(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.allowed(self.before("bash",
                                 {"command": "git commit -m x --no-verify"}))
        self.allowed(self.before("edit", {
            "filePath": "tests/test_x.py",
            "old_string": "def test_x():\n    assert 1",
            "new_string": "%s\ndef test_x():\n    assert 1" % SKIP_MARK}))
        # attribution and the explorer refusal are different rules: still armed
        self.denied(self.before("bash", {
            "command": 'git commit -m "x Co-Authored-By: Claude"'}))
        self.denied(self.before("task", {"subagent_type": "explore"}))

    def test_pretooluse_off_kills_denials(self):
        self.touch(os.path.join(self.home, ".config", "tezgah",
                                "pretooluse-off"))
        self.allowed(self.before("bash",
                                 {"command": "git commit -m x --no-verify"}))

    def test_naming_no_verify_in_a_message_or_a_read_passes(self):
        # describing the rule is not a bypass; the flag has to be in command
        # position (the plugin denied the description before the masking)
        self.allowed(self.before("bash", {
            "command": 'git commit -m "gate: deny --no-verify bypasses"'}))
        self.allowed(self.before("bash", {
            "command": "git commit -F - <<'MSG'\ngate denies --no-verify\nMSG"}))
        self.denied(self.before("bash",
                                {"command": "git commit --no-verify -m x"}))

    # ---- newly added test disable -----------------------------------------
    def test_adding_a_disable_marker_denied(self):
        self.denied(self.before("edit", {
            "filePath": "tests/test_x.py",
            "old_string": "def test_x():\n    assert 1",
            "new_string": "%s\ndef test_x():\n    assert 1" % SKIP_MARK}))

    def test_a_marker_outside_a_test_file_passes(self):
        self.allowed(self.before("edit", {
            "filePath": "probe.py",
            "new_string": "%s\ndef test_x(): pass" % SKIP_MARK}))

    def test_a_marker_inside_a_string_is_not_a_disable(self):
        self.allowed(self.before("edit", {
            "filePath": "tests/test_x.py",
            "new_string": 'CASES = ["%s"]' % SKIP_MARK}))

    def test_rewriting_an_existing_marker_passes(self):
        old = "%s\ndef test_x(): pass" % SKIP_MARK
        self.allowed(self.before("edit",
                                 {"filePath": "tests/test_x.py",
                                  "old_string": old, "new_string": old}))

    def test_plain_edit_passes(self):
        self.allowed(self.before("edit",
                                 {"filePath": "tests/test_x.py",
                                  "old_string": "a = 1", "new_string": "a = 2"}))

    def test_optional_dependency_guard_allowed(self):
        guard = "@unittest." + "skipUnless(HAVE_NODE, 'node missing')"
        self.allowed(self.before("edit", {
            "filePath": "tests/test_x.py",
            "old_string": "def t():\n    pass",
            "new_string": guard + "\ndef t():\n    pass"}))

    def test_conditional_skip_denied_with_own_name(self):
        name = "@unittest." + "skipIf(x, 'y')"
        error = self.denied(self.before("edit", {
            "filePath": "tests/test_x.py",
            "old_string": "def t():\n    pass",
            "new_string": name + "\ndef t():\n    pass"}))
        self.assertIn(name.split("(")[0], error)

    # ---- attribution -------------------------------------------------------
    def test_attribution_denies_a_commit(self):
        for credit in ("Co-Authored-By: Claude <noreply@anthropic.com>",
                       "Generated with Cursor", "\U0001F916"):
            command = 'git commit -m "change\n\n%s"' % credit
            self.denied(self.before("bash", {"command": command}))

    def test_attribute_less_commit_passes(self):
        self.allowed(self.before("bash",
                                 {"command": 'git commit -m "fix: typo"'}))

    def test_attribution_denies_gh_pr_create(self):
        self.denied(self.before("bash", {
            "command": 'gh pr create --title x --body "Generated with Cursor"'}))

    def test_attribution_denies_a_credit_landed_by_a_write_tool(self):
        # The rule covers file contents, so the plugin has to read the payload,
        # not only a bash command - the same shape hooks/tezgah_gate.py denies.
        for tool, args in (
                ("write", {"filePath": "src/a.py",
                           "content": "x = 1\n# Generated with Claude Code\n"}),
                ("edit", {"filePath": "src/a.py", "old_string": "x = 1",
                          "new_string": "x = 1\nCo-Authored-By: Claude <noreply@anthropic.com>"}),
                ("apply_patch", {"patch": "*** Begin Patch\n+// Made with Cursor\n*** End Patch"})):
            error = self.denied(self.before(tool, args))
            self.assertIn("Attribution", error)

    def test_prose_that_names_the_ban_is_not_a_credit(self):
        for body in (
                "Banned forms include `Co-Authored-By` / `Co-authored-by`, any\n"
                'Never add a Co-Authored-By trailer or a "Generated with" line.\n',
                "- `Generated with X` is a banned signature\n",
                "The gate denies a commit whose message carries a Co-Authored-By "
                "trailer.\n"):
            self.allowed(self.before("write", {"filePath": "docs/policy.md",
                                               "content": body}))

    # ---- explore subagent --------------------------------------------------
    def test_explore_subagent_denied(self):
        self.denied(self.before("task", {"subagent_type": "explore"}))

    def test_general_subagent_passes(self):
        self.allowed(self.before("task", {"subagent_type": "general"}))

    # ---- evidence ledger ---------------------------------------------------
    def after(self, tool, args, exit=None, session="s1", directory=None):
        metadata = {} if exit is None else {"exit": exit}
        return self.drive([{"hook": "tool.execute.after",
                            "input": {"tool": tool, "args": args,
                                      "sessionID": session},
                            "output": {"metadata": metadata}}], directory)[0]

    def test_bash_check_records_verify_ok(self):
        self.after("bash", {"command": "pytest -q"}, exit=0)
        self.assertIn("verify_ok", self.kinds())

    def test_bash_failure_records_verify_fail(self):
        self.after("bash", {"command": "pytest -q"}, exit=1)
        self.assertIn("verify_fail", self.kinds())

    def test_check_without_exit_records_verify(self):
        self.after("bash", {"command": "pytest -q"})
        self.assertIn("verify", self.kinds())

    def test_non_check_command_records_run(self):
        self.after("bash", {"command": "ls -la"})
        self.assertIn("run", self.kinds())

    def test_edit_records_edit(self):
        self.after("edit", {"filePath": "/tmp/x.py"})
        self.assertIn("edit", self.kinds())

    def test_outside_root_records_nothing(self):
        self.after("bash", {"command": "ls"}, directory=self.home)
        self.assertEqual(self.kinds(), [])

    def test_a_mention_of_a_tool_is_not_a_use_of_it(self):
        # the plugin's cheap substring only decides whether to ask; the answer
        # comes from the shared tokenizer, so `grep -n consult hooks/` records
        # nothing while a real run still does
        self.context_bin()
        self.after("bash", {"command": "grep -n consult hooks/"})
        self.assertNotIn("consult", self.used())
        self.after("bash", {"command": "timeout 30 consult --online q"})
        self.assertIn("consult", self.used())

    # ---- first-grep nudge --------------------------------------------------
    def make_index(self):
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        open(os.path.join(db_dir, support.slug(self.repo) + ".db"), "w").close()

    def test_identifier_grep_nudged_once_then_passes(self):
        self.make_index()
        self.denied(self.before("grep", {"pattern": "FooBar"}))
        self.allowed(self.before("grep", {"pattern": "FooBar"}))

    def test_nudge_survives_an_unwritable_global_cache(self):
        # A sandboxed host denies the global cache. The Python half falls back
        # to temp (hooks/tezgah_paths.py cache_dir) and this half must too:
        # without the fallback the mark is never written, so the first grep
        # would pass unnudged instead of being denied once.
        self.make_index()
        cache = os.path.join(self.home, ".cache")
        os.chmod(cache, 0o500)
        self.addCleanup(os.chmod, cache, 0o700)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.envv = self.env(extra={"TMPDIR": tmp})

        self.denied(self.before("grep", {"pattern": "FooBar"}))
        self.allowed(self.before("grep", {"pattern": "FooBar"}))

    # ---- the shared builder (per-prompt arming + post-compact) -------------
    def builder(self, event, payload=None):
        """What bin/tezgah-context prints for an event in this test's HOME."""
        proc = subprocess.run(
            ["python3", os.path.join(support.REPO, "bin", "tezgah-context"),
             event, self.repo],
            input=json.dumps(payload or {}), capture_output=True, text=True,
            env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def context_bin(self):
        return support.linked(
            os.path.join(support.REPO, "bin", "tezgah-context"), self.home)

    def message(self, prompt, session="s1"):
        parts = [{"type": "text", "text": prompt, "id": "p1",
                  "sessionID": session, "messageID": "m1"}]
        output = {"message": {"id": "m1", "sessionID": session}, "parts": parts}
        res = self.drive([{"hook": "chat.message",
                           "input": {"sessionID": session, "messageID": "m1"},
                           "output": output}])[0]
        self.assertTrue(res["ok"], res)
        return res["output"]["parts"]

    def test_chat_message_pays_the_per_prompt_text(self):
        # opencode keeps no reminder of its own: the text comes from the shared
        # builder, and a prompt that arms a conditional rule gets that rule's
        # paragraph here too.
        self.context_bin()
        prompt = "Bu ekranı daha kullanıcı dostu yap"
        parts = self.message(prompt)
        injected = parts[-1]
        self.assertEqual(len(parts), 2, parts)
        self.assertTrue(injected.get("synthetic"), injected)
        self.assertEqual(injected["text"],
                         self.builder("user_prompt", {"prompt": prompt}))
        self.assertIn("**Spec before building.**", injected["text"])

    def test_chat_message_says_nothing_for_a_plain_prompt(self):
        self.context_bin()
        prompt = "add a docstring to parse_quantity"
        injected = self.message(prompt)[-1]["text"]
        self.assertEqual(injected, self.builder("user_prompt", {"prompt": prompt}))
        self.assertNotIn("**Spec before building.**", injected)

    def test_a_missing_builder_injects_nothing(self):
        # Every path fails open: a host without ~/.config/tezgah/bin still sends
        # the message, it just has no tezgah text in it.
        parts = self.message("selam")
        self.assertEqual(len(parts), 1, parts)

    def test_compacting_context_comes_from_the_builder(self):
        self.context_bin()
        res = self.drive([{"hook": "experimental.session.compacting",
                           "input": {"sessionID": "s1"},
                           "output": {"context": []}}])[0]
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["output"]["context"], [self.builder("post_compact")])

    def test_compacting_is_inert_outside_the_roots(self):
        self.context_bin()
        res = self.drive([{"hook": "experimental.session.compacting",
                           "input": {"sessionID": "s1"},
                           "output": {"context": []}}], directory=self.home)[0]
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["output"]["context"], [])


if __name__ == "__main__":
    unittest.main()
