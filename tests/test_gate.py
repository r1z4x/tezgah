"""hooks/tezgah_gate.py: attribution gate, explore gate, first-grep nudge."""
import os
import unittest

import support
from support import TempHome, run_json


class Gate(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.probe = support.PROBE_GATE

    def decide(self, tool, inp, cwd=None, session_id="s1"):
        payload = {"tool": tool, "input": inp, "cwd": cwd or self.repo,
                   "session_id": session_id}
        out, proc = run_json([self.probe], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def make_index(self):
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        with open(os.path.join(db_dir, support.slug(self.repo) + ".db"), "w"):
            pass

    # ---- attribution -------------------------------------------------------
    def test_attribute_less_commit_passes(self):
        self.assertIsNone(self.decide("Bash", {"command": 'git commit -m "fix: typo"'}))

    def test_attribution_forms_deny_a_commit(self):
        for credit in ("Co-Authored-By: Claude <noreply@anthropic.com>",
                       "Generated with Claude Code",
                       "\U0001F916"):
            command = 'git commit -m "change\n\n%s"' % credit
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, credit)
            self.assertIn("Attribution", reason)

    def test_attribution_denies_gh_pr_create(self):
        reason = self.decide("Bash", {
            "command": 'gh pr create --title "x" --body "Generated with Cursor"'})
        self.assertIsNotNone(reason)
        self.assertIn("Attribution", reason)

    def test_attribution_denies_a_credit_landed_by_a_write_tool(self):
        # The rule covers file contents, so the gate has to read the payload,
        # not only a bash command.
        for tool, inp in (
                ("Write", {"file_path": "src/a.py", "content":
                           "def f():\n    return 1\n\n# Generated with Claude Code\n"}),
                ("Edit", {"file_path": "src/a.py", "old_string": "x = 1",
                          "new_string": "x = 1\nCo-Authored-By: Claude <noreply@anthropic.com>"}),
                ("write_file", {"file_path": "a.py", "content": "\U0001F916"}),
                ("apply_patch", {"patch": "*** Begin Patch\n+// Made with Cursor\n*** End Patch"})):
            reason = self.decide(tool, inp)
            self.assertIsNotNone(reason, tool)
            self.assertIn("Attribution", reason)

    def test_prose_that_names_the_ban_is_not_a_credit(self):
        # The anchor is what keeps the rule from denying the documentation that
        # describes it: a credit owns its line, prose does not.
        for body in (
                "Banned forms include `Co-Authored-By` / `Co-authored-by`, any\n"
                'Never add a Co-Authored-By trailer or a "Generated with" line.\n',
                "- `Generated with X` is a banned signature\n",
                "| form | `authored by` |\n",
                "The gate denies a commit whose message carries a Co-Authored-By "
                "trailer.\n"):
            self.assertIsNone(
                self.decide("Write", {"file_path": "docs/policy.md", "content": body}),
                body)

    def test_attribution_denies_writes_behind_git_global_options(self):
        # a global option between `git` and the subcommand must not hide a write
        for command in (
                'git -c user.name=x commit -m "Co-Authored-By: Claude"',
                'git -C /tmp/repo commit -m "Generated with Cursor"',
                'git --no-pager commit -m "Built by GPT"'):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Attribution", reason)

    def test_attribution_denies_gh_merge_and_api_writes(self):
        for command in (
                'gh pr merge 7 --body "Co-Authored-By: Claude"',
                'gh api repos/o/r/issues/1/comments -f body="Generated with x"'):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Attribution", reason)

    def test_attribution_without_a_write_passes(self):
        self.assertIsNone(self.decide("Bash", {"command": 'echo "Generated with x"'}))

    def test_global_option_without_a_write_subcommand_passes(self):
        self.assertIsNone(self.decide(
            "Bash", {"command": 'git -c core.pager=cat log --grep="Generated with"'}))

    def test_naming_claude_code_to_use_it_passes(self):
        # Naming a tool to use or describe it is allowed; only crediting it as
        # author is blocked, so a bare "Claude Code" must not deny a commit.
        self.assertIsNone(self.decide(
            "Bash", {"command": 'git commit -m "integrate with Claude Code hooks"'}))

    def test_git_grep_identifier_uses_the_same_nudge(self):
        self.make_index()
        first = self.decide("Bash", {"command": "git grep some_identifier"},
                            session_id="gg")
        self.assertIsNotNone(first)
        self.assertIn("search_graph", first)
        self.assertIsNone(self.decide("Bash", {"command": "git grep some_identifier"},
                                      session_id="gg"))

    def test_attribution_outside_roots_passes(self):
        self.assertIsNone(self.decide(
            "Bash", {"command": 'git commit -m "Co-Authored-By: x"'},
            cwd=self.home))

    # ---- explore subagent --------------------------------------------------
    def test_explore_subagent_denies(self):
        for tool, sub in (("Agent", "Explore"), ("Task", "explorer")):
            reason = self.decide(tool, {"subagent_type": sub})
            self.assertIsNotNone(reason, sub)
            self.assertIn("grep-only explorer", reason)

    def test_general_purpose_subagent_passes(self):
        self.assertIsNone(self.decide("Agent", {"subagent_type": "general-purpose"}))

    # ---- anti-shortcut: verification that cannot fail ---------------------
    def test_no_verify_commit_denied(self):
        reason = self.decide("Bash", {"command": "git commit -m x --no-verify"})
        self.assertIsNotNone(reason)
        self.assertIn("Verification bypass", reason)

    def test_skip_env_denied(self):
        reason = self.decide("Bash", {"command": "SKIP=ruff git commit -m x"})
        self.assertIsNotNone(reason)
        self.assertIn("bypass", reason.lower())

    def test_neutered_check_denied(self):
        reason = self.decide("Bash", {"command": "pytest -q || true"})
        self.assertIsNotNone(reason)
        self.assertIn("neutered", reason.lower())

    def test_plain_check_passes(self):
        self.assertIsNone(self.decide("Bash", {"command": "pytest -q"}))
        self.assertIsNone(self.decide("Bash", {"command": "git commit -m fix"}))

    def test_adding_a_test_skip_denied(self):
        reason = self.decide("Edit", {
            "file_path": "tests/test_t.py",
            "old_string": "def test_x():\n    assert 1",
            "new_string": "@pytest.mark.skip\ndef test_x():\n    assert 1"})
        self.assertIsNotNone(reason)
        self.assertIn("Test disable", reason)

    def test_a_skip_marker_outside_a_test_file_passes(self):
        # the rule is a disabled *test*; a probe script or a note that carries
        # the marker disables nothing (the gate denied these before the gate)
        self.assertIsNone(self.decide("Write", {
            "file_path": "probe.py",
            "content": "CASES = ['@pytest.mark.skip']\ndef run(): pass"}))
        self.assertIsNone(self.decide("Write", {
            "file_path": "NOTES.md", "content": "we added @unittest.skip to x"}))

    def test_a_commit_message_that_names_no_verify_passes(self):
        # describing the rule is not a bypass; the flag has to be in command
        # position (the gate denied the description before the masking)
        self.assertIsNone(self.decide("Bash", {
            "command": 'git commit -m "gate: deny --no-verify bypasses"'}))
        self.assertIsNone(self.decide("Bash", {
            "command": "git commit -F - <<'MSG'\ngate denies --no-verify\nMSG"}))
        self.assertIsNotNone(self.decide("Bash", {
            "command": "git commit --no-verify -m x"}))

    def test_plain_edit_passes(self):
        self.assertIsNone(self.decide("Edit", {
            "file_path": "t.py", "old_string": "a = 1", "new_string": "a = 2"}))

    def test_shortcut_denials_respect_pretooluse_off(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "pretooluse-off"))
        self.assertIsNone(
            self.decide("Bash", {"command": "git commit -m x --no-verify"}))

    def test_verify_off_drops_the_shortcut_denials_only(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertIsNone(
            self.decide("Bash", {"command": "git commit -m x --no-verify"}))
        self.assertIsNone(self.decide("Bash", {"command": "pytest -q || true"}))
        self.assertIsNone(self.decide("Edit", {
            "file_path": "tests/test_t.py",
            "new_string": "@pytest.mark." + "skip\ndef t(): pass"}))
        # attribution and the explorer refusal are different rules: still armed
        self.assertIsNotNone(self.decide("Bash", {
            "command": 'git commit -m "x Co-Authored-By: Claude"'}))
        self.assertIsNotNone(self.decide("Agent", {"subagent_type": "Explore"}))

    def test_skip_env_mention_in_a_read_passes(self):
        self.assertIsNone(self.decide("Bash", {"command": 'grep -rn "SKIP=" .'}))

    # ---- kill switch -------------------------------------------------------
    def test_pretooluse_off_kills_denials(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "pretooluse-off"))
        self.assertIsNone(self.decide("Agent", {"subagent_type": "Explore"}))

    # ---- first identifier grep nudge --------------------------------------
    def test_identifier_grep_nudged_once_then_passes(self):
        self.assertIsNone(self.decide("Grep", {"pattern": "some_identifier"}))
        self.make_index()
        first = self.decide("Grep", {"pattern": "some_identifier"})
        self.assertIsNotNone(first)
        self.assertIn("search_graph", first)
        self.assertIsNone(self.decide("Grep", {"pattern": "some_identifier"}))

    def test_bash_grep_identifier_uses_the_same_nudge(self):
        self.assertIsNone(
            self.decide("Bash", {"command": "grep some_identifier src/x.py"}))
        self.make_index()
        first = self.decide("Bash", {"command": "grep some_identifier src/x.py"},
                            session_id="b1")
        self.assertIsNotNone(first)
        self.assertIsNone(self.decide("Bash", {"command": "grep some_identifier src/x.py"},
                                      session_id="b1"))

    def test_non_identifier_search_never_nudged(self):
        self.make_index()
        self.assertIsNone(self.decide("Grep", {"pattern": "two words"}))
        self.assertIsNone(self.decide("Grep", {"pattern": "x"}))

    def test_index_for_a_different_repo_does_not_nudge(self):
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        with open(os.path.join(db_dir, support.slug(self.home) + ".db"), "w"):
            pass
        self.assertIsNone(self.decide("Grep", {"pattern": "some_identifier"}))

    def test_nudge_survives_an_unwritable_global_cache(self):
        # a sandboxed host (dsh) cannot write ~/.cache/tezgah; the once-per-
        # session nudge must still fire from the fallback instead of failing open
        self.make_index()
        cache = os.path.join(self.home, ".cache", "tezgah")
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        open(cache, "w").close()  # a file blocks the dir, like a denied write
        self.envv = self.env(extra={
            "TEZGAH_FALLBACK_CACHE": os.path.join(self.home, "fallback")})
        first = self.decide("Grep", {"pattern": "some_identifier"}, session_id="sb")
        self.assertIsNotNone(first)
        self.assertIn("search_graph", first)
        self.assertIsNone(
            self.decide("Grep", {"pattern": "some_identifier"}, session_id="sb"))


if __name__ == "__main__":
    unittest.main()
