"""hooks/tezgah_gate.py: the attribution, explore, shortcut, secret and
language refusals, the first-grep nudge, the concurrent-write refusal, the
long-turn re-statement and the task-phase refusal."""
import json
import os
import sys
import time
import unittest

import support
from support import TempHome, run_json

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402  (call_id only: the digest a grant carries)
import tezgah_gate as tg  # noqa: E402  (rm_outside's floor, read in process)

# The skip marker the shell-write half has to catch, assembled at runtime: the
# shortcut rule refuses a tests/ file that ADDS the literal marker, this file
# included, so the source must not carry it whole.
SKIP_MARK = "@pytest.mark." + "skip"


class Gate(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.probe = support.PROBE_GATE

    def decide(self, tool, inp, cwd=None, session_id="s1", capture_log=None):
        payload = {"tool": tool, "input": inp, "cwd": cwd or self.repo,
                   "session_id": session_id}
        if capture_log:
            payload["capture_log"] = capture_log
        out, proc = run_json([self.probe], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def make_index(self):
        """The repo's own codegraph index: what the nudge reads readiness from."""
        path = os.path.join(self.repo, ".codegraph", "codegraph.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

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

    def test_attribution_denies_a_credit_written_by_the_shell(self):
        # The shell's own write route: a credit inside a heredoc lands in a file
        # exactly as one in an edit's content does, and the write tools and the
        # shell are disjoint sets, so the text check never saw it.
        reason = self.decide("Bash", {"command":
            "cat >> CHANGELOG.md <<'EOF'\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\nEOF"})
        self.assertIsNotNone(reason)
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

    def test_prose_that_names_an_ordinary_actor_is_not_a_credit(self):
        # The "... by ..." verbs name what they credit: a build script, a
        # compiler or the gate is an actor, not a machine writing the artifact,
        # so none of these may be refused (the widen must not fire on prose).
        for body in ("the report was generated by the build script",
                     "generated by the compiler",
                     "the index is built by the gate",
                     "the file was written by hand",
                     "the plan was authored by the team"):
            self.assertIsNone(self.decide(
                "Bash", {"command": 'git commit -m "%s"' % body}), body)
            self.assertIsNone(self.decide(
                "Write", {"file_path": "docs/note.md", "content": body + "\n"}),
                body)

    def test_a_credit_inside_a_minus_m_value_is_denied_wherever_it_sits(self):
        # The unanchored read is what catches a credit buried in a `-m` value;
        # the price is that a message *describing* the forms is denied until it
        # rephrases. Both halves are pinned, because a future narrowing that
        # fixed only the first half would let `-m "Built by GPT"` through.
        self.assertIsNotNone(self.decide(
            "Bash", {"command": 'git commit -m "Built by GPT"'}))
        self.assertIsNotNone(self.decide(
            "Bash", {"command": 'git commit -m "change: this was generated by '
                                'AI during triage"'}))
        # the rephrase that clears it names the class rather than quoting a form
        self.assertIsNone(self.decide(
            "Bash", {"command": 'git commit -m "gate: the credit forms are '
                                'refused"'}))

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

    def test_attribution_denies_a_generator_named_as_the_author(self):
        # C04: the anchor set held "generated with" and not "generated by", so
        # the pack's mandated line passed while the Co-Authored-By control was
        # denied. The "... by ..." verbs now credit only a named model or the
        # machine itself, so every name the ban lists is caught.
        for credit in ("This was generated by AI during triage",
                       "generated by an LLM", "generated by Claude",
                       "generated by GPT", "generated by ChatGPT",
                       "generated by Copilot", "generated by Codex",
                       "generated by Cursor", "generated by Gemini",
                       "generated by DeepSeek", "written by AI",
                       "authored by AI"):
            command = 'git commit -m "change\n\n%s"' % credit
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, credit)
            self.assertIn("Attribution", reason)

    def test_attribution_denies_a_generator_line_added_by_a_patch(self):
        # the anchored twin, on the line a patch body adds: the credit owns the
        # line, so the `+` prefix is the marker and the form is caught
        for patch in ("*** Begin Patch\n+Generated by an LLM\n*** End Patch",
                      "*** Begin Patch\n+generated by AI during triage\n"
                      "*** End Patch"):
            reason = self.decide("apply_patch", {"patch": patch})
            self.assertIsNotNone(reason, patch)
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
        self.assertIn("codegraph_explore", first)
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

    def test_a_shell_write_that_disables_a_test_is_denied(self):
        # the route E7c measured: with the write tools refused, the armed arm
        # wrote the target with a heredoc. The tool rule never saw it - the write
        # tools and the shell are disjoint - so the body is read instead, and the
        # same predicate runs on what it would land.
        reason = self.decide("Bash", {"command":
            "cat > tests/test_api.py <<'EOF'\nimport pytest\n%s\ndef test_x(): "
            "pass\nEOF" % SKIP_MARK})
        self.assertIsNotNone(reason)
        self.assertIn("Test disable", reason)

    def test_a_shell_write_of_a_marker_outside_a_test_file_passes(self):
        # the twin keeps the tool rule's own gates: the write has to be a test
        # file, and a note that carries the marker disables nothing
        self.assertIsNone(self.decide("Bash", {"command":
            "cat > NOTES.md <<'EOF'\nwe added %s to x\nEOF" % SKIP_MARK}))

    def test_a_quoted_redirect_is_not_a_shell_write(self):
        # the shape test runs on the masked text, so a quoted `>` is not a
        # redirect; and a redirect with no heredoc body carries no content this
        # rule could read
        self.assertIsNone(self.decide("Bash", {"command":
            "echo '%s is what the rule bans' > notes.txt" % SKIP_MARK}))
        self.assertIsNone(self.decide("Bash", {"command":
            "grep -rn 'x' docs/ | tee notes.txt"}))

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

    # ---- loop guard: an identical call that already failed -----------------
    def seed_failure(self, command, session_id, times=1, error=None):
        """The rows a real PostToolUse hook writes after a failed call."""
        for _ in range(times):
            out, proc = run_json(
                [support.PROBE_INTEGRITY],
                {"fn": "note_tool", "session": session_id, "tool": "Bash",
                 "input": {"command": command}, "failed": True, "error": error,
                 "cwd": self.repo}, env=self.envv)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def new_turn(self, session_id, prompt="run the tests again",
                 id_key="session_id"):
        """One user prompt, driven through the real hook that injects the
        context - the same path that has to write the turn marker. `id_key` is
        the field the host names the session in (Cursor: conversation_id)."""
        out, proc = run_json([support.AUTO_INIT],
                             {"hook_event_name": "UserPromptSubmit",
                              "cwd": self.repo, id_key: session_id,
                              "prompt": prompt}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_an_identical_failed_call_is_denied_after_the_ceiling(self):
        self.seed_failure("pytest -q", "loop", times=2)
        reason = self.decide("Bash", {"command": "pytest -q"}, session_id="loop")
        self.assertIsNotNone(reason)
        self.assertIn("Loop guard", reason)
        self.assertIn("attempt 3", reason)

    def test_the_failure_class_does_not_widen_the_cap(self):
        # G7: the cap is the same number for every class. Before this, a
        # transient failure was the one class that bought an extra identical
        # attempt - the inverse of the row the checklist asks for ("at most 2 for
        # a transient error"), and a budget that then depended on whether the
        # host happened to report error text at all. The class names WHY the last
        # attempt failed and nothing more.
        for session, error in (("cap-transient", "Command timed out after 2m"),
                               ("cap-perm", "E   AssertionError: 1 != 2"),
                               ("cap-none", None)):
            for _ in range(2):
                self.seed_failure("pytest -q", session, error=error)
            reason = self.decide("Bash", {"command": "pytest -q"},
                                 session_id=session)
            self.assertIsNotNone(reason, session)
            self.assertIn("attempt 3", reason)
            self.assertIn("cap is 2 identical attempts", reason)
            self.assertIn("every failure class", reason)
        # the class is still named, and one failed attempt is still not a loop
        transient = "cap-transient-note"
        for _ in range(2):
            self.seed_failure("pytest -q", transient,
                              error="Command timed out after 2m")
        reason = self.decide("Bash", {"command": "pytest -q"},
                             session_id=transient)
        self.assertIn("(a transient failure)", reason)
        self.assertIn("host's own client may retry", reason)
        self.seed_failure("pytest -q", "cap-one", error="Command timed out after 2m")
        self.assertIsNone(self.decide("Bash", {"command": "pytest -q"},
                                      session_id="cap-one"))

    def test_a_fourth_identical_call_is_refused_whatever_the_outcome(self):
        # the half `loop` cannot see: it needs a failure, so a call that returns
        # 0 every time and never moves the work forward passes it forever. Three
        # runs are allowed - the edit/test loop reaches two, a session's third
        # `git status` passes - and the fourth is the ceiling.
        for n in range(3):
            reason = self.decide("Bash", {"command": "git status"},
                                 session_id="spin")
            self.assertIsNone(reason, "attempt %d of 3 must pass" % (n + 1))
            run_json([support.PROBE_INTEGRITY],
                     {"fn": "note_tool", "session": "spin", "tool": "Bash",
                      "input": {"command": "git status"}, "failed": False,
                      "cwd": self.repo}, env=self.envv)
        reason = self.decide("Bash", {"command": "git status"}, session_id="spin")
        self.assertIsNotNone(reason)
        self.assertIn("Retry ceiling", reason)
        self.assertIn("attempt 4", reason)
        # both repeat reasons are distinguishable, and a changed call is not a
        # repeat
        self.assertNotIn("Loop guard", reason)
        self.assertIsNone(
            self.decide("Bash", {"command": "git status --short"},
                        session_id="spin"))

    def test_the_two_repeat_reasons_are_distinguishable(self):
        # the failure-scoped guard is the narrower rule; its reason must not read
        # as the ceiling above it
        self.seed_failure("pytest -q", "distinct", times=2)
        reason = self.decide("Bash", {"command": "pytest -q"},
                             session_id="distinct")
        self.assertIn("Loop guard", reason)
        self.assertNotIn("Retry ceiling", reason)

    def test_the_session_ceiling_is_not_a_loop_guard(self):
        # a call that ran three times, none of them a failure: `loop` says
        # nothing, the session ceiling is the rule that fires
        for _ in range(3):
            run_json([support.PROBE_INTEGRITY],
                     {"fn": "note_tool", "session": "ceiling", "tool": "Bash",
                      "input": {"command": "pytest -q"}, "failed": False,
                      "cwd": self.repo}, env=self.envv)
        reason = self.decide("Bash", {"command": "pytest -q"},
                             session_id="ceiling")
        self.assertIn("past the ceiling of 3 attempts whatever their outcome",
                      reason)

    def test_the_session_ceiling_respects_verify_off(self):
        for _ in range(3):
            run_json([support.PROBE_INTEGRITY],
                     {"fn": "note_tool", "session": "spin-off", "tool": "Bash",
                      "input": {"command": "git status"}, "failed": False,
                      "cwd": self.repo}, env=self.envv)
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertIsNone(
            self.decide("Bash", {"command": "git status"}, session_id="spin-off"))

    def test_a_denial_does_not_disarm_the_ceiling(self):
        # the real sequence: fail, deny, identical call. The refusal writes its
        # own row with the same id and no exit, so counting rows by id alone left
        # the deny row newest, read as "no failure", and let every second repeat
        # through - the ceiling the plan claims was never enforced.
        self.seed_failure("pytest -q", "sticky", times=2)
        self.assertIsNotNone(
            self.decide("Bash", {"command": "pytest -q"}, session_id="sticky"))
        self.assertIsNotNone(
            self.decide("Bash", {"command": "pytest -q"}, session_id="sticky"))

    def test_a_changed_command_is_not_the_same_call(self):
        # the id is the collapsed command: a retry the agent already fixed is a
        # different action, not a repeat
        self.seed_failure("pytest tests/a.py", "loop", times=2)
        self.assertIsNone(self.decide("Bash", {"command": "pytest tests/b.py"},
                                      session_id="loop"))

    def test_a_prior_success_is_not_a_failure(self):
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": "loop", "tool": "Bash",
                  "input": {"command": "pytest -q"}, "failed": False,
                  "cwd": self.repo}, env=self.envv)
        self.assertIsNone(
            self.decide("Bash", {"command": "pytest -q"}, session_id="loop"))

    def test_an_interrupted_call_is_not_an_attempt(self):
        # `prior_calls` counts only the rows that carry an `exit`, and an
        # interrupted call has none: a call the user cancelled is not a rejected
        # call, so it spends neither the loop guard's allowance nor the session
        # ceiling - both ceilings count repeats of one call, and this call never
        # returned. Driven through the real hook, so the row under test is the
        # one a host writes rather than a seeded stand-in.
        for _ in range(2):
            _, proc = run_json([support.POSTTOOLUSE],
                               {"hook_event_name": "PostToolUseFailure",
                                "cwd": self.repo, "session_id": "interrupted",
                                "tool_name": "Bash",
                                "tool_input": {"command": "pytest -q"},
                                "is_interrupt": True}, env=self.envv)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(self.decide("Bash", {"command": "pytest -q"},
                                      session_id="interrupted"))

    def test_a_new_user_turn_resets_the_loop_guard(self):
        # "reset per user turn": the failures were spent on a call the user then
        # asked for again, so the marker the prompt path writes has to clear them.
        # Both id shapes: Claude/Codex/omp name it session_id, Cursor names it
        # conversation_id, and either way the marker has to land in the ledger
        # the gate reads for that id.
        for session, id_key in (("turn", "session_id"),
                                ("c-1", "conversation_id")):
            self.seed_failure("pytest -q", session, times=2)
            self.assertIsNotNone(
                self.decide("Bash", {"command": "pytest -q"},
                            session_id=session), session)
            self.new_turn(session, id_key=id_key)
            self.assertIsNone(
                self.decide("Bash", {"command": "pytest -q"},
                            session_id=session), session)

    def test_a_sibling_session_id_is_a_different_ledger(self):
        # _slug collapsed punctuation, so "abc-123" and "abc_123" shared one
        # file and one session's failures denied the other's call
        self.seed_failure("pytest -q", "abc-123", times=2)
        self.assertIsNone(
            self.decide("Bash", {"command": "pytest -q"}, session_id="abc_123"))

    def test_loop_guard_respects_verify_off(self):
        self.seed_failure("pytest -q", "loop", times=2)
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertIsNone(
            self.decide("Bash", {"command": "pytest -q"}, session_id="loop"))

    def seed_run(self, command, session_id, failed=False, error=None):
        """The row a real PostToolUse hook writes after the call ran: the same
        id and an outcome on it."""
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "note_tool", "session": session_id,
                              "tool": "Bash", "input": {"command": command},
                              "failed": failed, "error": error, "cwd": self.repo},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def rows(self, session_id):
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "events", "session": session_id},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    # ---- ordering: a commit while the newest check failed ------------------
    def test_a_commit_is_refused_while_the_newest_check_failed(self):
        # C9: the one relation between two actions this gate asserts. The state
        # is the Stop rule's own fold over the ledger tail, and the refusal names
        # the check that failed.
        self.seed_run("pytest -q", "order", failed=True)
        reason = self.decide("Bash", {"command": "git commit -m x"},
                             session_id="order")
        self.assertIsNotNone(reason)
        self.assertIn("pytest -q", reason)

    def test_the_ordering_refusal_names_no_command_that_lifts_it(self):
        # a refusal is a boundary or it is an instruction: E7 measured what
        # printing the unlock costs (the armed arm removed or disabled the gate in
        # 25 of 25 runs and obeyed it in none), so this refusal names the failed
        # check and nothing that would lift it
        self.seed_run("pytest -q", "order", failed=True)
        reason = self.decide("Bash", {"command": "git commit --amend --no-edit"},
                             session_id="order")
        self.assertIsNotNone(reason)
        for unlock in ("--no-verify", "verify-off",
                       "tezgah-task", "tezgah-setup"):
            self.assertNotIn(unlock, reason)

    def test_a_commit_passes_when_no_check_ran(self):
        # what keeps the rule from punishing a docs-only commit: no check at all
        # folds to None, and None is not "fail"
        self.assertIsNone(self.decide("Bash", {"command": "git commit -m docs"},
                                      session_id="order"))

    def test_a_commit_passes_after_the_newest_check_passed(self):
        # the NEWEST check decides, not any check: an older failure is not the
        # state the commit would freeze
        self.seed_run("pytest -q", "order", failed=True)
        self.seed_run("pytest -q", "order", failed=False)
        self.assertIsNone(self.decide("Bash", {"command": "git commit -m x"},
                                      session_id="order"))

    def test_a_check_that_ran_with_no_outcome_is_not_a_failure(self):
        # failed=None is a host that reported nothing: the row is a check that
        # ran, and this rule refuses only the state that says the tree was
        # rejected
        self.seed_run("pytest -q", "order")
        self.assertIsNone(self.decide("Bash", {"command": "git commit -m x"},
                                      session_id="order"))

    def test_the_ordering_rule_is_a_commit_rule(self):
        # the failure refuses the claim, not the session: every other command is
        # not this rule's
        self.seed_run("pytest -q", "order", failed=True)
        for command in ("git status", "pytest -q", "git push origin main"):
            self.assertIsNone(self.decide("Bash", {"command": command},
                                          session_id="order"), command)

    def test_the_ordering_refusal_is_its_own_rule_row(self):
        # the counters separate the rules by the deny row's name, so this one has
        # to be its own
        self.seed_run("pytest -q", "order", failed=True)
        self.decide("Bash", {"command": "git commit -m x"}, session_id="order")
        denial = [r for r in self.rows("order") if r["kind"] == "deny"][-1]
        self.assertEqual(denial["detail"].split(":", 1)[0], "order")

    def test_the_ordering_rule_rides_verify_off(self):
        # it rides the integrity rule's own switch instead of adding a switch:
        # the state it refuses is that rule's claim, one step earlier
        self.seed_run("pytest -q", "order", failed=True)
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertIsNone(self.decide("Bash", {"command": "git commit -m x"},
                                      session_id="order"))

    # ---- secret: a credential on its way into a file -----------------------
    def test_a_credential_written_to_a_file_denies(self):
        for command in (
                'echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" >> /tmp/run.log',
                'echo "api_key=sk-live-abc123" > out.txt',
                "printf 'token=%s\\n' \"$GITHUB_TOKEN\" | tee run.log",
                'curl --trace-ascii run.log -H "Authorization: Bearer $TOKEN" '
                "https://api.example.com/x"):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Credential", reason)

    def test_reading_a_credential_or_carrying_it_in_env_passes(self):
        # the normal work this rule must not touch: a read, a tool with the key
        # in its environment, and a request that saves only a response body
        for command in ("echo $OPENROUTER_API_KEY",
                        "env | grep OPENROUTER_API_KEY",
                        "OPENROUTER_API_KEY=xyz python3 audit.py",
                        'curl -H "Authorization: Bearer $TOKEN" '
                        "https://api.example.com/data",
                        'curl -H "Authorization: Bearer $TOKEN" -o data.json '
                        "https://api.example.com/data",
                        "grep -rn 'api_key=' src/",
                        "export API_KEY=abc && echo done"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_a_message_about_a_credential_write_passes(self):
        # a sink only carries its own simple command's text, so adding the files
        # and committing a message that mentions the shape is not a write
        self.assertIsNone(self.decide("Bash", {
            "command": 'git add -A && git commit -m "fix api_key= handling"'}))
        self.assertIsNone(self.decide("Bash", {"command": "git add .env"}))

    def test_a_credential_written_by_a_heredoc_is_denied(self):
        # mask() blanks heredoc bodies by design, so the text-level scan cannot
        # see a key that sits in one - measured on the first version of this
        # rule: this command passed it. The body is read instead.
        reason = self.decide("Bash", {"command":
            "cat > .env <<'EOF'\nOPENROUTER_API_KEY=sk-live-abc123\nEOF"})
        self.assertIsNotNone(reason)
        self.assertIn("Credential", reason)

    def test_a_credential_write_has_no_repeat_escape(self):
        # this rule keeps refusing: the deny text names the
        # rephrase (a name, a length, a fingerprint), so the write is replaced
        # rather than repeated
        command = 'echo "api_key=sk-live-abc123" > out.txt'
        for _ in range(2):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason)
            self.assertIn("Credential", reason)

    def test_secret_stays_armed_under_verify_off(self):
        # `verify-off` removes the shortcut and loop halves only; this is not
        # the integrity rule's, so it stays armed
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertIsNotNone(
            self.decide("Bash", {"command": 'echo "api_key=x" >> log'}))

    # ---- concurrent write: another session wrote this file -----------------
    def seed_write(self, session, path, tool="Edit"):
        """The row a real PostToolUse hook writes after a write: the gate reads
        the ledger, so the test seeds it through the writer, never by hand."""
        out, proc = run_json(
            [support.PROBE_INTEGRITY],
            {"fn": "note_tool", "session": session, "tool": tool,
             "input": {"file_path": path, "old_string": "a", "new_string": "b"},
             "cwd": self.repo},
            env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_write_to_a_file_another_session_wrote_is_refused(self):
        target = os.path.join(self.repo, "src", "a.py")
        self.seed_write("other", target)
        reason = self.decide("Edit", {"file_path": target, "old_string": "a",
                                      "new_string": "b"}, session_id="mine")
        self.assertIsNotNone(reason)
        self.assertIn("other", reason)    # names the other session
        self.assertIn(target, reason)     # and the file
        self.assertIn("Re-read", reason)  # and what to do about it

    def test_the_session_that_wrote_the_file_may_write_it_again(self):
        # the failure is a collision between two sessions, not a lock on a file,
        # so this session's own writes never refuse each other
        target = os.path.join(self.repo, "src", "a.py")
        self.seed_write("mine", target)
        for _ in range(2):
            self.assertIsNone(self.decide(
                "Edit", {"file_path": target, "old_string": "a",
                         "new_string": "b"}, session_id="mine"))

    def test_a_file_only_this_session_wrote_is_not_a_collision(self):
        self.seed_write("other", os.path.join(self.repo, "src", "a.py"))
        self.assertIsNone(self.decide(
            "Edit", {"file_path": os.path.join(self.repo, "src", "b.py"),
                     "old_string": "a", "new_string": "b"}, session_id="mine"))

    def test_another_sessions_write_does_not_block_a_read(self):
        # a read cannot overwrite anyone: only the write tools are this rule's
        target = os.path.join(self.repo, "src", "a.py")
        self.seed_write("other", target)
        self.assertIsNone(self.decide("Bash", {"command": "cat %s" % target},
                                      session_id="mine"))

    def test_the_patch_dialect_is_matched_by_its_own_paths(self):
        # apply_patch carries its paths in the body, not in file_path
        target = os.path.join(self.repo, "src", "a.py")
        self.seed_write("other", target)
        reason = self.decide("apply_patch", {"patch": (
            "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch"
            % target)}, session_id="mine")
        self.assertIsNotNone(reason)
        self.assertIn(target, reason)

    # ---- snapshot: the bytes a write is about to change --------------------
    def test_a_write_that_passes_is_captured_and_a_denied_one_is_not(self):
        # The gate keeps the pre-write bytes for an edit it lets through, and
        # for nothing else: a refused write changes no file, so capturing one
        # spends a copy on nothing. `capture` is imported behind a guard, so the
        # probe plants a stub in sys.modules - the same call site is pinned
        # whether or not hooks/tezgah_snapshot.py has landed.
        log = os.path.join(self.home, "capture.jsonl")

        def calls():
            if not os.path.exists(log):
                return []
            with open(log) as fh:
                return [json.loads(line) for line in fh if line.strip()]

        write = {"file_path": os.path.join(self.repo, "src", "a.py"),
                 "old_string": "a", "new_string": "b"}
        self.assertIsNone(self.decide("Edit", write, session_id="cap",
                                      capture_log=log))
        self.assertIsNotNone(self.decide("Edit", {
            "file_path": "src/a.py",
            "new_string": "Co-Authored-By: Claude <noreply@anthropic.com>"},
            session_id="cap", capture_log=log))
        self.assertEqual(len(calls()), 1, calls())
        self.assertEqual(calls()[0]["tool"], "Edit")
        self.assertEqual(calls()[0]["input"], write)
        self.assertEqual(calls()[0]["cwd"], self.repo)
        self.assertEqual(calls()[0]["session_id"], "cap")
        # and a bash command that writes nothing is not a write tool: there is no
        # file to keep
        self.assertIsNone(self.decide("Bash", {"command": "pytest -q"},
                                      session_id="cap", capture_log=log))
        self.assertEqual(len(calls()), 1, calls())

    def test_a_shell_write_is_handed_to_capture_like_a_write_tool(self):
        # The shell is a write route like any other, and the freshness rule reads
        # the same two halves for it: the gate keeps the pre-state of the file the
        # command redirects into, and the post hook hashes it (see
        # tezgah_integrity._post_write). Without this the after-state alone could
        # not tell a write that landed from a no-op.
        log = os.path.join(self.home, "shell-capture.jsonl")

        def calls():
            if not os.path.exists(log):
                return []
            with open(log) as fh:
                return [json.loads(line) for line in fh if line.strip()]

        self.assertIsNone(self.decide(
            "Bash", {"command": "printf x >> notes.md"}, session_id="shellcap",
            capture_log=log))
        self.assertEqual(len(calls()), 1, calls())
        # the target is the one the command writes, and it goes to capture in the
        # shape capture reads - a write tool's own path field
        self.assertEqual(calls()[0]["tool"], tg.SHELL_AS_WRITE)
        self.assertEqual(calls()[0]["input"], {"file_path": "notes.md"})
        self.assertEqual(calls()[0]["session_id"], "shellcap")
        # a quoted `>` is not a redirect and `> /dev/null` is not a file, so
        # neither is captured; neither is a command that writes no file
        for command in ("echo 'x > notes.md'", "pytest -q > /dev/null",
                        "sed -i s/a/b/ notes.md"):
            self.assertIsNone(self.decide("Bash", {"command": command},
                                          session_id="shellcap",
                                          capture_log=log))
        self.assertEqual(len(calls()), 1, calls())
        # and a shell call the gate refuses is captured nowhere, like a refused
        # write tool
        self.assertIsNotNone(self.decide(
            "Bash", {"command": "echo \"api_key=sk-live-abc123\" > b.md"},
            session_id="shellcap", capture_log=log))
        self.assertEqual(len(calls()), 1, calls())

    def test_a_chained_shell_write_names_the_file_and_not_the_separator(self):
        # `\S+` ran to the next whitespace, so the separator of a chained command
        # came with the name: this captured `x.txt;`, a path nothing is ever
        # written to. The pre-state was then never kept and the after-state never
        # hashed, so a chained write stayed invisible to the freshness rule while
        # a single one did not - the same hole, open only on half the shapes.
        log = os.path.join(self.home, "chained-capture.jsonl")

        def calls():
            if not os.path.exists(log):
                return []
            with open(log) as fh:
                return [json.loads(line) for line in fh if line.strip()]

        self.assertIsNone(self.decide(
            "Bash", {"command": "printf a > x.txt; printf b > y.txt"},
            session_id="chained", capture_log=log))
        self.assertEqual([c["input"] for c in calls()], [{"file_path": "x.txt"}],
                         calls())

    def test_a_notebook_write_names_its_notebook(self):
        # NotebookEdit is classified as an edit and so runs the write-tool rules,
        # but its target arrives in `notebook_path`, which the path reader did not
        # carry: no pre-state was captured and no after-state recorded, so the
        # write was un-rollbackable and invisible to the freshness fold at once.
        # The gate hands a write tool its own name and its whole input, so the
        # reader is what has to find the notebook - assert it there, and that the
        # call reaches capture at all.
        self.assertEqual(tg.write_paths({"notebook_path": "nb.ipynb"}),
                         ["nb.ipynb"])
        log = os.path.join(self.home, "notebook-capture.jsonl")

        def calls():
            if not os.path.exists(log):
                return []
            with open(log) as fh:
                return [json.loads(line) for line in fh if line.strip()]

        self.assertIsNone(self.decide(
            "NotebookEdit", {"notebook_path": "nb.ipynb", "new_source": "x"},
            session_id="notebook", capture_log=log))
        self.assertEqual([c["tool"] for c in calls()], ["NotebookEdit"], calls())
        # the same spelling the host sends is the one the rules classify as an
        # edit, so the write-tool branches (skip marker, attribution, secrets,
        # capture) all run for it
        self.assertEqual(ti.classify("NotebookEdit", {"notebook_path": "nb.ipynb"}),
                         "edit")

    def test_the_one_path_reader_covers_every_dialect_a_host_uses(self):
        # The single definition of "which paths does this call write", read by
        # the gate's own rules and by the ledger's write row: a dialect missing
        # here is a file neither of them can name. `file_path`/`filePath` are
        # Claude's, `path` is omp's, `notebook_path` a NotebookEdit's, and the
        # patch body is the one whose paths live in a string rather than a key -
        # every hunk of it, because the rule that gates a patch gates all of them.
        patch = ("*** Begin Patch\n*** Update File: p.py\n@@\n-a\n+b\n"
                 "*** Update File: q.py\n@@\n-c\n+d\n*** End Patch")
        for inp, want in (({"file_path": "a.py"}, ["a.py"]),
                          ({"filePath": "b.py"}, ["b.py"]),
                          ({"path": "c.py"}, ["c.py"]),
                          ({"notebook_path": "nb.ipynb"}, ["nb.ipynb"]),
                          ({"patch": patch}, ["p.py", "q.py"])):
            with self.subTest(inp=inp):
                self.assertEqual(tg.write_paths(inp), want)

    # ---- constraint drift: a long turn re-states the rules -----------------
    # Above the gate's DRIFT_STEPS whatever it is tuned to: this test is about a
    # turn long enough to have lost the prompt that armed the rules, not about
    # the exact number.
    LONG = 60

    def ledger(self, session, kind="turn"):
        """The ledger file a session's rows land in, found rather than derived:
        the stem is tezgah_integrity._slug's, and a test that re-implemented it
        would stop testing the file the hooks actually read. The file the marker
        row lands in is the one that grew, so one test may seed several sessions
        - and seed one session twice - without knowing any of their stems.

        `kind` is the row written to find the file: `turn` (the default) opens a
        new turn, a work kind appends to the turn already open, which is the one
        way a fixture reaches a turn longer than the drift count's window."""
        d = os.path.join(self.home, ".cache", "tezgah", "evidence")
        before = {}
        if os.path.isdir(d):
            before = {n: os.path.getsize(os.path.join(d, n))
                      for n in os.listdir(d)}
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": session, "kind": kind,
                  "detail": "seed"}, env=self.envv)
        grew = [n for n in sorted(os.listdir(d))
                if before.get(n) != os.path.getsize(os.path.join(d, n))]
        self.assertEqual(len(grew), 1, grew)
        return os.path.join(d, grew[0])

    def seed_turn(self, session, steps):
        """One user turn's ledger: the turn marker, then `steps` work rows."""
        path = self.ledger(session)
        with open(path, "a") as fh:
            for i in range(steps):
                fh.write(json.dumps({"kind": "run", "ts": int(time.time()),
                                     "detail": "step %d" % i}) + "\n")

    def write_call(self, session, path="a.py"):
        return self.decide("Edit", {"file_path": path, "old_string": "x",
                                    "new_string": "y"}, session_id=session)

    def notice(self, session, tool="Edit", inp=None, payload=None):
        """The line one result carries, through the writer Claude and dsh run
        (hooks/projects-posttooluse.py) - the channel the label and the notices
        ride, which is where the re-statement has to arrive."""
        data = {"hook_event_name": "PostToolUse", "tool_name": tool,
                "tool_input": inp if inp is not None else {
                    "file_path": "a.py", "old_string": "x", "new_string": "y"},
                "tool_response": "ok", "cwd": self.repo, "session_id": session}
        data.update(payload or {})
        out, proc = run_json([support.POSTTOOLUSE], data, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return (out or {}).get("hookSpecificOutput", {}).get(
            "additionalContext", "")

    def kinds(self, session):
        return [r.get("kind") for r in self.rows(session)]

    def test_a_long_turn_is_not_refused(self):
        # The notice is about the turn, not about the call it lands on. As a
        # refusal it spent that call: 128 of the corpus's 225 fires were
        # re-issued identically and 97 were never composed at all.
        self.seed_turn("long", self.LONG)
        self.assertIsNone(self.write_call("long"))
        # ... and the identical call passes again, with no deny row for either
        self.assertIsNone(self.write_call("long"))
        self.assertEqual([r for r in self.rows("long") if r["kind"] == "deny"],
                         [])

    def test_the_restatement_rides_the_result(self):
        self.seed_turn("long", self.LONG)
        text = self.notice("long")
        self.assertIn("Long turn", text)
        self.assertIn("still in force", text)
        # the text is tezgah_policy's own, not a second copy of the contract
        self.assertIn("Ponytail (minimal code)", text)
        self.assertIn("Deliver the whole ask", text)

    def test_the_notice_is_once_per_turn(self):
        # a re-statement on every call is noise the agent learns to skip
        self.seed_turn("long", self.LONG)
        self.assertIn("Long turn", self.notice("long"))
        self.assertEqual(self.notice("long", inp={
            "file_path": "b.py", "old_string": "x", "new_string": "y"}), "")
        # the marker is this rule's own state, and it keeps the shape the readers
        # fold: one row per turn, the turn's step count as its detail, and the
        # workspace it fired in
        drift = [r for r in self.rows("long") if r["kind"] == "drift"]
        self.assertEqual(len(drift), 1, drift)
        self.assertEqual(drift[0]["detail"], str(self.LONG))
        self.assertEqual(drift[0]["workspace"], self.roots)

    def test_a_short_turn_carries_nothing(self):
        self.seed_turn("short", 3)
        self.assertEqual(self.notice("short"), "")
        self.assertNotIn("drift", self.kinds("short"))

    def test_a_read_earns_nothing(self):
        self.seed_turn("long", self.LONG)
        self.assertEqual(self.notice("long", tool="Grep",
                                     inp={"pattern": "two words"}), "")
        self.assertNotIn("drift", self.kinds("long"))

    def test_a_git_write_result_carries_it(self):
        self.seed_turn("long", self.LONG)
        self.assertIn("Long turn", self.notice(
            "long", tool="Bash", inp={"command": 'git commit -m "fix: typo"'}))

    def test_the_next_turn_gets_its_own_restatement(self):
        # the mark is per turn: the prompt reminder decays the same way in the
        # turn after it, so the notice has to be able to fire again
        self.seed_turn("long", self.LONG)
        self.assertIn("Long turn", self.notice("long"))
        self.seed_turn("long", self.LONG)
        self.assertIn("Long turn", self.notice("long"))

    def test_a_turn_past_the_read_window_still_gets_one_notice(self):
        # The count reads a bounded window (`DRIFT_TAIL` rows), and a turn
        # longer than it puts the row that makes the notice once-per-turn - and
        # the turn's own marker beside it - outside what the tail sees. The
        # guard has to survive that: measured on ledger d13df660a2bc.jsonl, a
        # 254-row turn carried two drift markers, at rows 34 and 249.
        self.seed_turn("grew", self.LONG)
        self.assertIn("Long turn", self.notice("grew"))
        path = self.ledger("grew", kind="run")  # the same turn, one more step
        with open(path, "a") as fh:
            for i in range(tg.DRIFT_TAIL):
                fh.write(json.dumps({"kind": "run", "ts": int(time.time()),
                                     "detail": "more %d" % i}) + "\n")
        # the turn's own marker and the drift row are both older than the window
        self.assertEqual(self.notice("grew", inp={
            "file_path": "b.py", "old_string": "x", "new_string": "y"}), "")
        self.assertEqual([r["kind"] for r in self.rows("grew")
                          if r["kind"] == "drift"], ["drift"])
        # ... and the next turn is a new turn, with its own one notice
        self.seed_turn("grew", self.LONG)
        self.assertIn("Long turn", self.notice("grew", inp={
            "file_path": "c.py", "old_string": "x", "new_string": "y"}))
        self.assertEqual([r["kind"] for r in self.rows("grew")
                          if r["kind"] == "drift"], ["drift", "drift"])

    def test_the_restatement_respects_reminder_off(self):
        # it is the mid-turn half of the per-turn reminder, so that reminder's
        # own switch removes it
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        self.seed_turn("long", self.LONG)
        self.assertEqual(self.notice("long"), "")
        self.assertNotIn("drift", self.kinds("long"))

    def test_every_host_with_a_result_channel_carries_the_notice(self):
        # One case per host wired: the re-statement reuses each host's existing
        # result/notice path - the same line the untrusted label rides - instead
        # of a second channel or a new hook event. claude and dsh share one file
        # (hosts/dsh/hooks.json runs hooks/projects-posttooluse.py), and dsh
        # declares its outcome as unobservable, which is the one difference
        # between the two payloads.
        claude = {"hook_event_name": "PostToolUse", "tool_name": "Edit",
                  "tool_input": {"file_path": "a.py", "old_string": "x",
                                 "new_string": "y"},
                  "tool_response": "ok"}
        hosts = (
            ("claude", support.POSTTOOLUSE, claude, self.envv,
             lambda out: out.get("hookSpecificOutput", {}).get(
                 "additionalContext", "")),
            ("dsh", support.POSTTOOLUSE, claude,
             self.env(extra={"TEZGAH_CALL_OUTCOME": "none"}),
             lambda out: out.get("hookSpecificOutput", {}).get(
                 "additionalContext", "")),
            ("omp", support.OMP_HOOK,
             {"event": "post_tool_use", "tool": "edit",
              "input": {"file_path": "a.py", "old_string": "x",
                        "new_string": "y"},
              "failed": False}, self.envv,
             lambda out: out.get("label", "")),
            ("codex", support.CODEX_HOOK,
             {"hook_event_name": "PostToolUse", "tool_name": "apply_patch",
              "tool_input": {"patch": "..."},
              "tool_response": {"exit_code": 0}}, self.envv,
             lambda out: out.get("hookSpecificOutput", {}).get(
                 "additionalContext", "")),
            ("cursor", support.CURSOR_HOOK,
             {"hook_event_name": "postToolUse", "tool_name": "Write",
              "tool_input": {"file_path": "a.py", "content": "x"}}, self.envv,
             lambda out: out.get("additional_context", "")),
        )
        for name, hook, payload, env, line in hosts:
            with self.subTest(host=name):
                session = "host-" + name
                self.seed_turn(session, self.LONG)
                sent = dict(payload, cwd=self.repo, session_id=session,
                            conversation_id=session)
                out, proc = run_json([hook], sent, env=env)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                text = line(out or {})
                self.assertIn("Long turn", text)
                self.assertIn("Ponytail (minimal code)", text)
                # once per turn, on the state row this rule owns
                self.assertEqual(
                    [r["kind"] for r in self.rows(session)
                     if r["kind"] == "drift"], ["drift"])
                again, proc = run_json([hook], sent, env=env)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn("Long turn", line(again or {}))

    # ---- ledger rows the gate writes ---------------------------------------
    def test_a_denial_records_the_call_identity_and_the_workspace(self):
        # the PreToolUse writer carries the same id and workspace a PostToolUse
        # row does, so a refusal is attributable to an action, not to a rule
        self.decide("Bash", {"command": "git commit -m x --no-verify"},
                    session_id="rows")
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "events", "session": "rows"}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = out[-1]
        self.assertEqual(row["kind"], "deny")
        self.assertEqual(row["workspace"], self.roots)
        self.assertEqual(len(row["id"]), 12)

    def test_loop_guard_needs_a_session_ledger(self):
        # an id with no prior row is not a repeat: a fresh session passes
        self.assertIsNone(
            self.decide("Bash", {"command": "pytest -q"}, session_id="fresh"))

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
        self.assertIn("codegraph_explore", first)
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
        # an index at the ROOT is not this repo's index: a root is not a project
        path = os.path.join(self.home, ".codegraph", "codegraph.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
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
        self.assertIn("codegraph_explore", first)
        self.assertIsNone(
            self.decide("Grep", {"pattern": "some_identifier"}, session_id="sb"))


class TaskGate(TempHome):
    """The task rule: the user's own phase and allowlist, read from a plan file.

    Every case here seeds a real plan file under the repo's .tezgah/plans/open - the
    file bin/tezgah-task writes - and never a stubbed tezgah_task: what the rule
    is worth is that it reads what the user actually wrote, so a mock would only
    prove the mock."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.probe = support.PROBE_GATE

    def decide(self, inp, tool="Write", cwd=None, session_id="task-s"):
        out, proc = run_json([self.probe],
                             {"tool": tool, "input": inp,
                              "cwd": cwd or self.repo, "session_id": session_id},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def write_path(self, path):
        return self.decide({"file_path": path})

    def plan(self, phase=None, allowed=("hooks/**",), name="017-gate-rule.md",
             task_id="017"):
        """A plan file in the shape bin/tezgah-task leaves one: frontmatter
        (id, the optional phase and allowlist), then the body."""
        path = os.path.join(self.repo, ".tezgah", "plans", "open", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = ["---", "id: %s" % task_id, "title: the task rule",
                 "status: open"]
        if phase:
            lines.append("phase: %s" % phase)
        if allowed is not None:
            lines.append("allowed_paths:")
            lines += ["  - %s" % pattern for pattern in allowed]
        with open(path, "w") as fh:
            fh.write("\n".join(lines + ["---", "", "Body."]) + "\n")
        return path

    # ---- no record, no requirement ----------------------------------------
    def test_a_write_passes_with_no_active_task(self):
        # a plan that merely exists is not an activation - `phase:` is the key -
        # and with nothing active the rule refuses nothing at all
        self.assertIsNone(self.write_path(os.path.join(self.repo, "src/a.py")))
        self.plan(phase=None)
        self.assertIsNone(self.write_path(os.path.join(self.repo, "src/a.py")))

    def test_with_no_active_task_even_an_outside_path_passes(self):
        # the refusal has to come from the user's own record: with none, a scope
        # this rule invented - a repo boundary or an allowlist - would tax work
        # nobody bounded
        self.assertIsNone(
            self.write_path(os.path.join(self.home, "elsewhere.py")))

    # ---- the phase --------------------------------------------------------
    def test_a_reading_phase_refuses_a_write_inside_the_allowlist(self):
        # the phase dominates: discovery refuses even the path the task allows,
        # and it names the phase it is in and both phases that write
        self.plan(phase="discovery")
        reason = self.write_path(os.path.join(self.repo, "hooks/tezgah_gate.py"))
        self.assertIsNotNone(reason)
        self.assertIn("discovery", reason)
        self.assertIn("implementation", reason)
        self.assertIn("verification", reason)

    def test_neither_refusal_names_a_command_to_run(self):
        # What E7 measured, and the reason this test exists: the refusals used to
        # end with the command that lifts them, and the armed arm then removed or
        # disabled the gate in 25 of 25 runs and obeyed it in none. A refusal is a
        # boundary or it is an instruction; it cannot be both.
        self.plan(phase="discovery")
        phase_reason = self.write_path("hooks/x.py")
        self.plan(phase="implementation", allowed=("hooks/**",))
        scope_reason = self.write_path("src/y.py")
        self.assertIsNotNone(scope_reason)
        for reason in (phase_reason, scope_reason):
            for command in ("tezgah-task", "bin/tezgah"):
                self.assertNotIn(command, reason, reason)

    def test_both_write_phases_allow_a_write_inside_the_allowlist(self):
        for phase in ("implementation", "verification"):
            self.plan(phase=phase)
            self.assertIsNone(
                self.write_path(os.path.join(self.repo, "hooks/tezgah_gate.py")),
                phase)

    # ---- the shell is a write route too ------------------------------------
    def test_a_reading_phase_refuses_a_shell_write(self):
        # The route E7b measured: with the write tools refused (twelve `edit` and
        # six `write` calls), the armed arm wrote the target with a heredoc
        # redirect instead in 3 of 25 runs. The phase is the requirement, so it
        # covers the shell as well - and names no command, like the other two.
        self.plan(phase="discovery")
        for command in ("cat > app/api.py <<'EOF'\nx\nEOF",
                        "cat >> app/api.py <<'PYEOF'\nx\nPYEOF",
                        "echo x >> hooks/tezgah_gate.py",
                        "sed -i '' 's/a/b/' app/api.py",
                        "perl -pi -e 's/a/b/' app/api.py",
                        "printf 'x' | tee app/api.py",
                        "cp app/api.py app/other.py",
                        "git checkout -- app/api.py",
                        "git apply patch.diff"):
            reason = self.decide({"command": command}, tool="Bash")
            self.assertIsNotNone(reason, command)
            self.assertIn("discovery", reason, command)
            self.assertNotIn("tezgah-task", reason, command)

    def test_a_reading_phase_leaves_reading_alone(self):
        # the table reads redirects, not commands: a check, a search and a test
        # run are what a reading phase is for, and a discarded redirect (or the
        # `2>&1` a runner writes) is not a write to a file
        self.plan(phase="discovery")
        for command in ("python3 -m unittest discover -s tests",
                        "git status --short",
                        "grep -rn 'ROUTES' app/",
                        "python3 -m unittest discover -s tests 2>&1 | tail -20",
                        "uvx ruff check . > /dev/null 2>&1",
                        "cat app/api.py",
                        "sed -n '1,5p' app/api.py",
                        "grep -i routes app/api.py",
                        "git log --oneline -5"):
            self.assertIsNone(self.decide({"command": command}, tool="Bash"),
                              command)

    def test_a_write_phase_leaves_the_shell_alone(self):
        # a shell line's targets are not read, so the allowlist cannot be held
        # against them; the reading phases are the requirement, and in a phase
        # that writes the shell is not this rule's
        self.plan(phase="implementation", allowed=("app/**",))
        self.assertIsNone(
            self.decide({"command": "cat > src/x.py <<'EOF'\nx\nEOF"},
                        tool="Bash"))

    def test_the_shell_half_goes_with_the_same_switch(self):
        self.plan(phase="discovery")
        command = {"command": "cat > app/api.py <<'EOF'\nx\nEOF"}
        self.assertIsNotNone(self.decide(command, tool="Bash"))
        self.touch(os.path.join(self.home, ".config", "tezgah", "task-off"))
        self.assertIsNone(self.decide(command, tool="Bash"))

    # ---- the allowlist ----------------------------------------------------
    def test_a_path_outside_the_allowlist_refuses_and_names_what_it_knows(self):
        self.plan(phase="implementation", allowed=("hooks/**",))
        reason = self.write_path("src/a.py")
        self.assertIsNotNone(reason)
        self.assertIn("src/a.py", reason)
        self.assertIn("017", reason)
        self.assertIn("hooks/**", reason)
        self.assertIn("allow", reason)

    def test_the_allowlist_is_what_a_write_phase_allows(self):
        self.plan(phase="implementation",
                  allowed=("hooks/**", "tests/test_gate.py"))
        for rel in ("hooks/tezgah_gate.py", "hooks/deep/nested/x.py",
                    "tests/test_gate.py"):
            self.assertIsNone(self.write_path(rel), rel)

    def test_a_path_outside_the_repo_root_refuses_however_wide_the_allowlist(self):
        # `**` is a pattern inside the repo, not a licence to leave it: both a
        # traversal and a plain path above the root are refused
        self.plan(phase="implementation", allowed=("**",))
        self.assertIsNone(self.write_path(os.path.join(self.repo, "any.py")))
        for outside in (os.path.join(self.home, "outside.py"),
                        os.path.join(self.repo, "..", "..", "escaped.py")):
            reason = self.write_path(outside)
            self.assertIsNotNone(reason, outside)
            self.assertIn(os.path.basename(outside), reason)

    def test_an_absent_allowlist_gates_on_the_phase_alone(self):
        # the key is optional, so its absence is no scope asked for rather than
        # "nothing is allowed"; the phase is then the whole requirement
        self.plan(phase="implementation", allowed=None)
        self.assertIsNone(self.write_path("src/a.py"))
        self.plan(phase="discovery", allowed=None)
        self.assertIsNotNone(self.write_path("src/a.py"))

    def test_every_hunk_of_a_patch_is_checked(self):
        self.plan(phase="implementation", allowed=("hooks/**",))
        reason = self.decide(
            {"patch": "*** Begin Patch\n"
                      "*** Update File: hooks/tezgah_gate.py\n@@\n-a\n+b\n"
                      "*** Update File: src/other.py\n@@\n-c\n+d\n"
                      "*** End Patch"}, tool="apply_patch")
        self.assertIsNotNone(reason)
        self.assertIn("src/other.py", reason)

    # ---- the record is the user's, by both routes --------------------------
    def test_the_active_record_is_not_the_sessions_to_write(self):
        # The file route: the record is a file in the repo, so an agent that may
        # write files could retype the phase instead of running the CLI. Refused
        # even in a phase that writes and even when the allowlist covers .tezgah/plans/,
        # because a scope that can widen itself is not a scope.
        path = self.plan(phase="implementation", allowed=(".tezgah/plans/**",))
        for target in (path, ".tezgah/plans/open/017-gate-rule.md"):
            reason = self.write_path(target)
            self.assertIsNotNone(reason, target)
            self.assertIn("record", reason)

    def test_the_task_cli_is_not_the_sessions_to_run(self):
        # The command route, and the one E7 watched the armed arm take 24 times.
        self.plan(phase="discovery")
        for command in ("bin/tezgah-task phase implementation",
                        "python3 /opt/tezgah/bin/tezgah-task phase verification",
                        "tezgah-task allow '**'",
                        "cd /x && bin/tezgah-task stop",
                        "bin/tezgah-task start 001 --phase implementation"):
            reason = self.decide({"command": command}, tool="Bash")
            self.assertIsNotNone(reason, command)
            self.assertIn("record", reason)

    def test_naming_the_cli_in_prose_is_not_running_it(self):
        # the masked text again: a search, a read or a commit message that names
        # the CLI is not the CLI changing the record
        for command in ('grep -rn "tezgah-task phase" docs/',
                        'git commit -m "the phase is tezgah-task phase impl"',
                        "cat bin/tezgah-task",
                        "bin/tezgah-task --help"):
            self.assertIsNone(self.decide({"command": command}, tool="Bash"),
                              command)

    # ---- kill switch ------------------------------------------------------
    def test_task_off_removes_the_rule(self):
        self.plan(phase="discovery")
        self.touch(os.path.join(self.home, ".config", "tezgah", "task-off"))
        self.assertIsNone(self.write_path("hooks/tezgah_gate.py"))
        self.plan(phase="implementation", allowed=("hooks/**",))
        self.assertIsNone(self.write_path("src/a.py"))
        # and the two refusals that close the ways around it
        self.assertIsNone(self.write_path(".tezgah/plans/open/017-gate-rule.md"))
        self.assertIsNone(self.decide({"command": "bin/tezgah-task stop"},
                                      tool="Bash"))


class LangGate(TempHome):
    """The language rule: the git/gh commands that create an identifier.

    The detector is pinned in tests/test_lang.py; what is pinned here is the
    other half - which command shapes reach it, and which must not. A command
    that merely NAMES a Turkish word creates nothing, so it passes; a command
    that would create one is refused where it is issued, which is the only
    moment an identifier can still be renamed for free."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def decide(self, command, cwd=None, session_id="lang"):
        out, proc = run_json(
            [support.PROBE_GATE],
            {"tool": "Bash", "input": {"command": command},
             "cwd": cwd or self.repo, "session_id": session_id},
            env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    # ---- refused: the identifiers a command creates ------------------------
    def test_a_turkish_branch_name_is_refused(self):
        for command, token in (
                ("git checkout -b plan/004-admin-durum-onarimi", "durum"),
                ("git switch -c durum-onarimi", "onarimi"),
                ("git branch plan/004-admin-durum-onarimi", "durum"),
                ("git -C /tmp/x checkout --branch durum", "durum"),
                ("git switch -c veri-donusum", "veri")):
            reason = self.decide(command)
            self.assertIsNotNone(reason, command)
            self.assertIn("branch name", reason)
            self.assertIn(token, reason)

    def test_a_turkish_commit_subject_is_refused(self):
        for command in ('git commit -m "durum onarimi"',
                        "git commit --message 'hata raporu'",
                        'git -c user.name=x commit -m "kullanım sayfasi"',
                        "git commit --message=hazirla",
                        'git commit -am "durum onarimi"',
                        'git commit --amend -m "rapor ozeti"',
                        'git commit -m "kullanici yetki guvenlik"'):
            reason = self.decide(command)
            self.assertIsNotNone(reason, command)
            self.assertIn("commit subject", reason)

    def test_a_commit_message_file_is_read(self):
        with open(os.path.join(self.repo, "msg.txt"), "w") as fh:
            fh.write("durum onarimi\n\nuzun bir govde\n")
        reason = self.decide("git commit -F msg.txt")
        self.assertIsNotNone(reason)
        self.assertIn("durum", reason)

    def test_a_turkish_title_is_refused(self):
        for command, what in (
                ('gh pr create --title "durum onarimi" --body "x"', "PR title"),
                ('gh issue create --title "rapor ozeti"', "issue title"),
                ('gh pr create --title="hata raporu" --base main', "PR title")):
            reason = self.decide(command)
            self.assertIsNotNone(reason, command)
            self.assertIn(what, reason)

    def test_the_refusal_offers_the_english_to_write_instead(self):
        reason = self.decide("git checkout -b durum-onarimi")
        self.assertIn("`durum` -> `status`", reason)
        self.assertIn("`onarimi` -> `repair`", reason)

    # ---- allowed: English, and the commands that create nothing ------------
    def test_english_identifiers_pass(self):
        for command in ("git checkout -b plan/004-status-repair",
                        'git commit -m "fix: status repair"',
                        'git commit -am "fix: status repair"',
                        'git commit -m "verify the retry budget"',
                        "git commit --amend --no-edit"):
            self.assertIsNone(self.decide(command), command)
        # The title shapes are read in process for the language answer: the
        # rule allows the English title, and any gate refusal is another
        # rule's.
        for command in ('gh pr create --title "Add the status repair" --body "x"',
                        'gh issue create --title "Review the index"'):
            self.assertIsNone(tg.lang_reason(command, self.repo), command)

    def test_a_command_that_only_names_the_words_passes(self):
        # nothing is created: the words are read, never written, so none of
        # these may be denied
        for command in ('echo "plan/004-admin-durum-onarimi"',
                        "grep -rn onarim src/",
                        "git log --oneline --grep=durum",
                        "git branch --list",
                        "git checkout main"):
            self.assertIsNone(self.decide(command), command)

    def test_a_commit_message_file_that_cannot_be_read_passes(self):
        # the ceiling the rule declares: an unreadable path is skipped, not
        # guessed at
        self.assertIsNone(self.decide("git commit -F no-such-file.txt"))

    def test_a_subject_with_a_quoted_turkish_body_passes(self):
        # `-m` carries the subject; a word in a later paragraph is prose the
        # rule does not read (the ceiling the constant names)
        self.assertIsNone(self.decide(
            'git commit -m "fix: status repair" -m "the durum name was kept"'))

    def test_outside_the_roots_passes(self):
        self.assertIsNone(
            self.decide("git checkout -b durum-onarimi", cwd=self.home))

    # ---- kill switch -------------------------------------------------------
    def test_lang_off_removes_the_rule(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "lang-off"))
        self.assertIsNone(self.decide("git checkout -b durum-onarimi"))
        # the whole-gate switch still removes everything else with it
        self.touch(os.path.join(self.home, ".config", "tezgah",
                                "pretooluse-off"))
        self.assertIsNone(self.decide("git commit -m durum"))

if __name__ == "__main__":
    unittest.main()
