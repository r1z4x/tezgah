"""hooks/tezgah_gate.py: the attribution, explore, shortcut, consent and secret
refusals, the first-grep nudge, the concurrent-write refusal, the long-turn
re-statement and the task-phase refusal."""
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

    # ---- consent: an irreversible or outward-facing call -------------------
    def test_a_force_push_denies_and_a_re_issue_is_not_an_answer(self):
        # The gate sees one call and cannot ask the user, so the refusal is the
        # ask: it lands in the transcript and names the digest the user approves.
        # What it must NOT do is treat the agent re-issuing the command as the
        # user's answer - that is the agent approving its own effect (B7).
        for command in ("git push --force origin main",
                        "git push -f origin main",
                        "git push --force-with-lease origin main",
                        "git push --force-with-lease=origin/main origin main",
                        "git -C /tmp/repo push --force origin master"):
            session = "ask-" + command
            for attempt in range(1, 4):
                reason = self.decide("Bash", {"command": command},
                                     session_id=session)
                self.assertIsNotNone(reason, "%s attempt %d" % (command, attempt))
                self.assertIn("Consent", reason)
                self.assertIn("tezgah-consent", reason)
                self.assertIn("re-issued command is not that decision", reason)
            # one ask row, then one deny row per attempt: no row claims a pass
            # the user never approved
            kinds = [r["kind"] for r in self.rows(session)]
            self.assertEqual(kinds, ["consent", "deny", "deny", "deny"], kinds)
            # the second refusal says the ask is already on record
            self.assertIn("The ask is on record already",
                          self.decide("Bash", {"command": command},
                                      session_id=session))

    def test_a_force_push_to_a_scratch_branch_passes(self):
        for command in ("git push -f origin tmp/scratch",
                        "git push --force origin wip-parser",
                        "git push origin main"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_branch_deletes_deny(self):
        for command in ("git branch -D main",
                        "git branch --delete feature",
                        "git branch -rd origin/feature",
                        "git push origin --delete feature",
                        "git push origin -d feature"):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Consent", reason)

    def test_branch_reads_are_not_deletes(self):
        # `--merged` carries a `d`, so the delete flag is matched by shape
        for command in ("git branch --merged", "git branch -a",
                        "git branch --contains HEAD", "git branch -vv"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_rm_rf_outside_the_run_directory_denies(self):
        # Every target is outside the run directory AND outside a temp root. A
        # path built from self.home would not be: the sandbox itself lives under
        # TMPDIR, so on Linux CI it sat inside the floor this rule carves out
        # (macOS hid that - the sandbox is under /var/folders there).
        for command in ("rm -rf /opt/data",
                        "rm -rf /etc/tezgah-elsewhere",
                        "rm -rf ~/Downloads/junk",
                        "rm -rf $BUILD_DIR",
                        "rm -rf .",
                        # the temp root itself is not scratch, a path that only
                        # escapes through it is not under it, and one scratch
                        # target does not license a second one
                        "rm -rf /tmp",
                        "rm -rf /tmp/../etc",
                        "rm -rf /tmp/scratch /opt/data"):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Consent", reason)

    def test_a_delete_inside_the_run_directory_passes(self):
        # both flags are required (`rm -f` / `rm -r` alone are not this rule's),
        # a path under the run directory is the agent's own workspace, and a path
        # under a temp root is scratch: the ask would protect nothing there
        for command in ("rm -rf build", "rm -rf node_modules && npm ci",
                        'rm -rf "./dist"', "rm -f /tmp/scratch", "rm -r /tmp/x",
                        "rm -rf /tmp/scratch",
                        "rm -rf /tmp/tezgah-fixture/nested"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_a_migration_or_a_deploy_denies(self):
        for command in ("alembic upgrade head", "python3 manage.py migrate",
                        "bin/rails db:migrate", "prisma migrate deploy",
                        "vercel deploy --prod", "terraform apply -auto-approve",
                        "kubectl apply -f k8s/",
                        "npm publish --access public",
                        "docker push registry/img:tag"):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Consent", reason)

    def test_a_shared_resource_destroyed_at_a_service_denies(self):
        # The four the table was blind to that leave this machine or take a
        # resource other people share: a remote repository, an S3 bucket or the
        # prefix under it, and a schema dropped by the runner's own verb. Each is
        # read as its class, not as the pattern that matched.
        for command, klass in (
                ("gh repo delete me/x --yes", "destructive"),
                ("gh repo archive me/x", "destructive"),
                ("aws s3 rb s3://bucket --force", "destructive"),
                ("aws s3 rm s3://bucket/prefix --recursive", "destructive"),
                ("flyway clean", "schema")):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("`%s` effect" % klass, reason)

    def test_a_command_that_only_names_a_shared_destroy_denies_nothing(self):
        # found on the masked text like the rest of the table, so a message that
        # describes the command is not the command
        for command in ('git commit -m "gate: deny gh repo delete me/x"',
                        "echo 'aws s3 rb s3://b' >> notes.md"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_a_local_or_narrow_delete_still_asks_nobody(self):
        # Deliberately left out of the class table: each is either local and
        # recoverable from disk, or narrow enough that the round-trip costs the
        # user more than the effect does. The rule the four added commands pass
        # is "the effect leaves this machine or destroys a resource others
        # share"; these fail it.
        for command in ("git reset --hard HEAD~3", "git tag -d v1",
                        "docker compose down -v", "chmod -R 000 /etc",
                        "git push origin main", "aws s3 rm s3://bucket/key.txt",
                        "gh repo view me/x", "aws s3 ls s3://bucket"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_ordinary_work_passes_the_consent_rule(self):
        for command in ("npm run build", "pytest -q", "git status",
                        "docker build -t img .", "alembic revision -m add_col",
                        "python3 manage.py makemigrations"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_a_message_that_names_an_irreversible_command_passes(self):
        # the patterns run on the masked text, so a commit message that describes
        # a force-push or an `rm -rf` is not doing it
        self.assertIsNone(self.decide("Bash", {
            "command": 'git commit -m "gate: ask before rm -rf /tmp/x"'}))

    def test_consent_is_a_command_rule(self):
        # writing a migration file is not applying it
        self.assertIsNone(self.decide("Write", {
            "file_path": "migrations/0002_add_col.py",
            "content": "def upgrade():\n    op.add_column('t', sa.Column('c'))\n"}))

    def test_the_refusal_names_the_effect_class_not_the_pattern(self):
        # what an action IS, not which regex caught it: one class per command,
        # and the deny says which
        for command, klass in (
                ("git push --force origin main", "destructive"),
                ("git branch -D main", "destructive"),
                ("git push origin --delete feature", "destructive"),
                ("rm -rf /opt/tezgah-sibling", "destructive"),
                ("alembic upgrade head", "schema"),
                ("python3 manage.py migrate", "schema"),
                ("vercel deploy --prod", "deploy"),
                ("terraform apply -auto-approve", "deploy"),
                ("npm publish --access public", "publish"),
                ("docker push registry/img:tag", "publish"),
                ("gh release create v1.2.0", "publish"),
                ("git push heroku main", "outward"),
                ("git push origin production", "outward")):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("`%s` effect" % klass, reason)
            self.assertNotIn("force-push to a shared branch", reason)

    def test_the_refusal_records_the_effect_class_as_a_consent_row(self):
        # "who was asked to confirm what" is a query over rows: kind consent, the
        # class in the detail, the action in the id - not a string match on a
        # deny message a later reword would silently break. The row's workspace
        # is the directory the call runs in - the scope the lease is bound to,
        # which is why the same text in another directory is another ask.
        self.decide("Bash", {"command": "git push --force origin main"},
                    session_id="asked")
        self.decide("Bash", {"command": "npm publish"}, session_id="asked")
        rows = [r for r in self.rows("asked") if r["kind"] == "consent"]
        self.assertEqual([r["detail"] for r in rows],
                         ["destructive", "publish"])
        self.assertEqual(rows[0]["workspace"], self.repo)
        for r in rows:
            self.assertEqual(len(r["id"]), 12)
            self.assertEqual(r["kind"], "consent")
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])
        # the row names the refused action: its id is the denial's id
        denials = [r for r in self.rows("asked") if r["kind"] == "deny"]
        self.assertEqual([r["id"] for r in denials], [r["id"] for r in rows])
        self.assertEqual(
            [r["detail"].split(":", 1)[0] for r in denials], ["consent", "consent"])

    def test_the_consent_row_is_the_ask_and_is_written_once(self):
        # the classification row IS the mark, so the ask cannot be answered and
        # the row fall out of step: one row per action, however many times the
        # command is re-issued. A second `consent` row would read as a second
        # question the user still has to answer.
        command = "npm publish --access public"
        for _ in range(3):
            reason = self.decide("Bash", {"command": command},
                                 session_id="oneshot")
            self.assertIsNotNone(reason)
        rows = [r for r in self.rows("oneshot") if r["kind"] == "consent"]
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["detail"], "publish")

    def test_a_grant_is_spent_by_the_effect_it_authorised(self):
        # B7 + D7, one code path: the user's approval is a lease on one effect,
        # not a standing permit. This is also the whole of the checkpoint a shell
        # effect can have - a force-push changes a remote this ledger holds no
        # pre-state for, so nothing here can be rolled back, and the row that
        # authorised the run is the record. The effect spends it (the PostToolUse
        # row a host writes after the run carries the same id and an outcome), and
        # the next identical command is asked about again.
        command = "git push --force origin main"
        session = "lease"
        digest = ti.call_id("Bash", {"command": command})
        self.assertIsNotNone(self.decide("Bash", {"command": command},
                                         session_id=session))       # the ask
        self.seed_grant(session, digest)                            # the answer
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id=session))
        # the effect ran: the row a real PostToolUse hook leaves for it
        self.seed_run(command, session)
        self.assertIsNotNone(self.decide("Bash", {"command": command},
                                         session_id=session))
        rows = self.rows(session)
        self.assertEqual([r["kind"] for r in rows],
                         ["consent", "deny", "grant", "run", "deny"], rows)
        # and the user can approve it again, by the digest the refusal names
        self.seed_grant(session, digest)
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id=session))
        self.assertNotIn("repeat-allowed",
                         [r["kind"] for r in self.rows(session)])

    def test_a_grant_is_spent_by_an_outcome_row_with_no_exit_on_it(self):
        # The spender is the outcome row, not the `exit` key inside it. Cursor's
        # `afterShellExecution` carries no outcome signal and records `run`/
        # `verify` with no key at all, so a lease only `exit` could spend never
        # was spent there - one approval became a standing permit, which is not
        # the documented model (one grant, one effect).
        command = "git push --force origin main"
        session = "no-exit-lease"
        digest = ti.call_id("Bash", {"command": command})
        self.decide("Bash", {"command": command}, session_id=session)
        self.seed_grant(session, digest)
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id=session))
        self.seed_run(command, session, failed=None)  # the cursor shape
        outcome = [r for r in self.rows(session) if r["kind"] == "run"][-1]
        self.assertNotIn("exit", outcome)
        self.assertIsNotNone(self.decide("Bash", {"command": command},
                                         session_id=session))

    def test_a_grant_does_not_answer_the_same_text_in_another_directory(self):
        # The action's identity cannot be the text alone: `call_id` has no cwd -
        # it is the loop guard's key too, so it stays what it is - while the
        # effect is resolved against the directory the call runs in, and
        # `rm -rf ../victim` from a checkout and the same text one directory
        # deeper drop different trees. The ask row records the directory, so the
        # grant answers the one it was asked about and the other call is asked
        # about afresh instead of running on an approval for somewhere else.
        command = "rm -rf ../victim"
        session = "lease-scope"
        digest = ti.call_id("Bash", {"command": command})
        deeper = os.path.join(self.repo, "sub")
        os.makedirs(deeper, exist_ok=True)
        self.assertIsNotNone(self.decide("Bash", {"command": command},
                                         session_id=session))     # the ask
        self.seed_grant(session, digest)                          # the answer
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id=session))
        reason = self.decide("Bash", {"command": command}, cwd=deeper,
                             session_id=session)
        self.assertIn("`destructive` effect", reason)
        # one ask per (action, directory), so the user can answer this one too
        asks = [r for r in self.rows(session) if r["kind"] == "consent"]
        self.assertEqual([r["workspace"] for r in asks], [self.repo, deeper])
        self.seed_grant(session, digest)
        self.assertIsNone(self.decide("Bash", {"command": command}, cwd=deeper,
                                      session_id=session))

    # ---- consent: the rows it may leave behind ----------------------------
    def seed_grant(self, session_id, digest):
        """The row bin/tezgah-consent writes when the user approves an action:
        the same writer, the same shape, and never a row the gate could write
        for itself."""
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "note", "session": session_id,
                              "kind": "grant", "detail": "cli", "id": digest},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def seed_run(self, command, session_id, failed=False, error=None):
        """The row a real PostToolUse hook writes after the call ran: the same
        id, an outcome on it, and no `grant`. It is what spends a grant."""
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "note_tool", "session": session_id,
                              "tool": "Bash", "input": {"command": command},
                              "failed": failed, "error": error, "cwd": self.repo},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_grant_answers_the_ask_the_gate_recorded(self):
        # ask, then the user's grant, then the command: the grant is the record
        # of the pass, and the gate writes no `repeat-allowed` beside it - that
        # row named a repeat where the user had in fact approved the action, and
        # the action is the same one row whether they approved it or not.
        command = "git push --force origin main"
        session = "granted-late"
        self.assertIsNotNone(self.decide("Bash", {"command": command},
                                         session_id=session))
        asked = [r for r in self.rows(session) if r["kind"] == "consent"][0]
        self.seed_grant(session, asked["id"])
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id=session))
        self.assertEqual([r["kind"] for r in self.rows(session)],
                         ["consent", "deny", "grant"])

    def test_a_grant_the_agent_could_forge_is_not_this_rule_s(self):
        # The lease rests on one row the gate cannot write: a `consent` ask (the
        # gate's own) never lifts the refusal, however many of them there are.
        # Only `grant` - bin/tezgah-consent's row - is an answer.
        command = "npm publish"
        session = "forged"
        digest = ti.call_id("Bash", {"command": command})
        for _ in range(3):
            self.assertIsNotNone(self.decide("Bash", {"command": command},
                                             session_id=session))
        rows = self.rows(session)
        self.assertEqual([r["kind"] for r in rows if r["kind"] == "consent"],
                         ["consent"])
        self.assertEqual(rows[0]["id"], digest)
        self.assertEqual(rows[0]["workspace"], self.repo)
        self.assertNotIn("exit", rows[0])

    # ---- consent: a declared effect, which may only tighten the class ------
    def test_a_declared_effect_at_or_above_the_class_is_used(self):
        # The patterns here cannot see someone's own script, so the command is
        # asked to say what it is - and a class below the one the text derives
        # is not on offer.
        for command, klass in (
                ("./ship.sh  # tezgah:effect=deploy", "deploy"),
                ("git push origin production  # tezgah:effect=destructive",
                 "destructive")):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("`%s` effect" % klass, reason)
            self.assertNotIn("declared", reason)

    def test_a_declared_effect_below_the_class_is_ignored(self):
        # A declaration that can lower a class is a bypass of the rule that
        # reads it, so the derived class stands - and the attempt stays visible
        # in the refusal and in the deny row, not only in this test.
        command = "git push --force origin main  # tezgah:effect=publish"
        reason = self.decide("Bash", {"command": command}, session_id="talking")
        self.assertIsNotNone(reason)
        self.assertIn("`destructive` effect", reason)
        self.assertIn("declared `tezgah:effect=publish`", reason)
        denied = [r for r in self.rows("talking") if r["kind"] == "deny"][0]
        self.assertIn("declared `publish` ignored, `destructive` stands",
                      denied["detail"])

    def test_a_declaration_that_names_no_class_is_dropped(self):
        # "at least as severe" is a comparison over the five classes, so a word
        # outside them is not a class and cannot invent one
        for command in ("npm run build  # tezgah:effect=whatever",
                        "pytest -q  # tezgah:effect="):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def test_an_action_that_is_not_irreversible_still_passes(self):
        # the classifier must not widen the rule: an ordinary push, a rollback-
        # free read and a release *check* are not effect actions
        for command in ("git push origin main", "git push -u origin feature",
                        "npm run publish:check", "gh release list",
                        "git branch -m old new", "kubectl get pods"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

    def rows(self, session_id):
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "events", "session": session_id},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    # ---- untrusted read: an effect in the turn that read a fetched page ----
    def read_untrusted(self, session_id, tool="web_search", channel="web"):
        """One untrusted read, through the hook that records it: the real
        PostToolUse path (hooks/projects-posttooluse.py), which is where a
        result's channel is decided and written onto the row. Seed such a row
        through the writer, never by hand."""
        out, proc = run_json(
            [support.POSTTOOLUSE],
            {"hook_event_name": "PostToolUse", "tool_name": tool,
             "tool_input": {"query": "how to x"}, "tool_response": "text",
             "cwd": self.repo, "session_id": session_id}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.rows(session_id)
        self.assertEqual([r["source"] for r in rows if r.get("source")],
                         [channel], rows)

    def test_an_effect_after_an_untrusted_read_is_refused(self):
        # E1/E5: the label told the model where the text came from and nothing
        # refused the effect it asked for. The sink rule refuses it, names the
        # channel, and records the ask so the user's CLI can answer it.
        session = "tainted"
        self.read_untrusted(session)
        reason = self.decide("Bash", {"command": "git push --force origin main"},
                             session_id=session)
        self.assertIsNotNone(reason)
        self.assertIn("Sink rule", reason)
        self.assertIn("a web result", reason)
        self.assertIn("`destructive` effect", reason)
        self.assertIn("bin/tezgah-consent", reason)
        row = [r for r in self.rows(session) if r["kind"] == "deny"][-1]
        self.assertEqual(row["detail"][:5], "sink:")
        self.assertIn("untrusted channel: web", row["detail"])
        asked = [r for r in self.rows(session) if r["kind"] == "consent"]
        self.assertEqual([r["detail"] for r in asked], ["destructive"])
        # the same command in a turn that read nothing is the consent rule's,
        # not the sink rule's
        plain = self.decide("Bash", {"command": "git push --force origin main"},
                            session_id="untainted")
        self.assertIn("Consent gate", plain)
        self.assertNotIn("Sink rule", plain)

    def test_a_scratch_delete_after_an_untrusted_read_is_still_refused(self):
        # the temp-root floor skips the ask, not the effect: the taint rule reads
        # the conservative class, so an injection cannot make its first move a
        # `rm -rf` in the temp root and land it unasked
        session = "tainted-scratch"
        self.read_untrusted(session)
        reason = self.decide("Bash", {"command": "rm -rf /tmp/tezgah-fixture"},
                             session_id=session)
        self.assertIsNotNone(reason)
        self.assertIn("Sink rule", reason)
        # the same command in a turn that read nothing is scratch: no ask
        self.assertIsNone(self.decide("Bash",
                                      {"command": "rm -rf /tmp/tezgah-fixture"},
                                      session_id="clean-scratch"))

    def test_an_approval_written_before_the_read_does_not_cover_it(self):
        # The half that gives the sink rule teeth: a grant the user wrote before
        # the page arrived is an answer about the command, not about what the
        # page asked for, so it does not lift the refusal - the taxonomy's
        # "the user's own word", which is the only exemption reachable from here
        # (the prompt itself is not: no host hook sees it, and the ledger keeps
        # only sha1(prompt)[:12]).
        session = "stale-grant"
        command = "npm publish"
        digest = ti.call_id("Bash", {"command": command})
        self.seed_grant(session, digest)
        self.read_untrusted(session)
        stale = self.decide("Bash", {"command": command}, session_id=session)
        self.assertIsNotNone(stale)
        self.assertIn("Sink rule", stale)
        self.assertIn("approval given before the read does not cover it", stale)
        self.seed_grant(session, digest)
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id=session))

    def test_a_write_outside_the_root_is_a_sink_in_a_tainted_turn(self):
        # The injection that pays is aimed at the agent's own config, not at the
        # repo it was asked to edit: a write whose realpath leaves the root is a
        # sink. One inside the root is left to the taint notice - it is
        # recoverable from the snapshot, and refusing every edit after every
        # fetch would tax the ordinary flow.
        session = "tainted-write"
        self.read_untrusted(session)
        outside = os.path.join(self.home, ".claude", "settings.json")
        reason = self.decide("Write", {"file_path": outside, "content": "{}"},
                             session_id=session)
        self.assertIsNotNone(reason)
        self.assertIn("Sink rule", reason)
        self.assertIn(outside, reason)
        self.assertIn("a web result", reason)
        asked = [r for r in self.rows(session) if r["kind"] == "consent"]
        self.assertEqual([r["detail"] for r in asked], ["outside-workspace"])
        # inside the root, and in a turn that read nothing, are not sinks
        self.assertIsNone(self.decide(
            "Edit", {"file_path": "src/a.py", "old_string": "x",
                     "new_string": "y"}, session_id=session))
        self.assertIsNone(self.decide(
            "Write", {"file_path": outside, "content": "{}"},
            session_id="untainted-write"))

    def test_an_outbound_command_is_a_send_effect(self):
        # A3's other half, which the five classes did not cover: an effect that
        # carries this workspace's data out to a service that acts on it - mail,
        # a payment, a remote API called with a write - is asked about the same
        # way, and this is the class an injection pays through.
        for command, klass in (
                ("swaks --to ops@example.com --body hi", "send"),
                ("sendmail -t < mail.txt", "send"),
                ("stripe refunds create --charge ch_1", "send"),
                ("curl -X POST -d @payload.json https://api.example.com/v1/x",
                 "send"),
                ("curl --data-raw 'a=1' https://api.example.com/v1/x", "send"),
                ("gh api -X POST repos/o/r/issues -f title=x", "send"),
                # a remote write reached through a subcommand instead of
                # through `gh api`: the same effect spelled two ways, and one
                # spelling was unasked until GH_SUBCOMMANDS reached SEND
                ("gh pr create --base main --head x --title t", "send"),
                ("gh pr edit 18 --body-file /tmp/p.md", "send"),
                ("gh pr merge 7 --merge", "send"),
                ("git push -q -u origin feat && gh issue comment 3 -b hi",
                 "send")):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("`send` effect", reason, command)
        # a read that leaves the machine is not this class, and neither is a gh
        # subcommand that only reads the remote
        for command in ("curl https://api.example.com/v1/x",
                        "curl -o out.json https://api.example.com/v1/x",
                        'curl -H "Authorization: Bearer $T" https://api.example.com/x',
                        "git push origin main", "scp2 --help",
                        "gh pr view 18", "gh pr list", "gh pr diff 18",
                        "gh pr checks 18", "gh issue list", "gh repo view"):
            self.assertIsNone(self.decide("Bash", {"command": command}), command)
        # and the class PUBLISH owns is still PUBLISH's: SEND reads the same
        # subcommand list with `release` left out, and `effect_class` checks
        # PUBLISH first, so a release cannot be relabelled by this rule
        publish = self.decide("Bash", {"command": "gh release create v1 --target main"})
        self.assertIn("`publish` effect", publish)

    def test_the_rsync_destination_decides_the_direction(self):
        # The copy's effect is its direction, and rsync's direction is its LAST
        # argument: `host:/src ./dst` brings bytes in - the read the untrusted
        # label covers - and `./dst host:/dst` carries them out, which is this
        # class. The pattern read the first token with a colon instead, so the
        # read was refused and the egress passed, and options in front of the
        # arguments defeated it in both directions.
        for command, klass in (
                ("rsync host:/src ./dst", None),
                ("rsync ./dst host:/dst", "send"),
                ("rsync -avz host:/src ./dst", None),
                ("rsync -avz ./dst host:/dst", "send"),
                # options sit on either side of the arguments
                ("rsync --exclude .git ./dst host:/dst", "send"),
                ("rsync -avz ./dst host:/dst --delete", "send"),
                # a copy between two local paths is nobody's effect
                ("rsync -avz ./src ./dst", None),
                # scp keeps the shape match its own branch documents: both
                # directions, which is the safe one and a single re-ask
                ("scp host:/src ./dst", "send"),
                ("scp -r ./dst host:/dst", "send")):
            self.assertEqual(tg.effect_class(command, self.repo, self.roots),
                             klass, command)
        # and the two results reach the caller: the egress is refused as `send`,
        # the read of the same shape passes
        self.assertIn("`send` effect",
                      self.decide("Bash", {"command": "rsync -avz ./dst host:/dst"}))
        self.assertIsNone(self.decide("Bash", {"command": "rsync -avz host:/src ./dst"}))

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
        for unlock in ("tezgah-consent", "--no-verify", "verify-off",
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

    # ---- the gate's own blind spot, mined (bin/tezgah-status) --------------
    def test_the_miner_folds_the_calls_the_class_table_cannot_place(self):
        # C15: the reader the class table grows from, and the three shapes have to
        # come apart - a shell call the table cannot read, one it reads, and one
        # the gate refused (a refused call was never an allowed one, and counting
        # it would report a closed hole as open).
        self.seed_run("gh repo view me/x", "mine", failed=False)
        self.seed_run("gh repo delete me/x --yes", "mine", failed=False)
        digest = ti.call_id("Bash", {"command": "spin -x"})
        for kind, detail in (("run", "spin -x"), ("deny", "loop: too many")):
            run_json([support.PROBE_INTEGRITY],
                     {"fn": "note", "session": "mine", "kind": kind,
                      "detail": detail, "id": digest}, env=self.envv)
        out, proc = run_json(
            [os.path.join(support.REPO, "bin", "tezgah-status"),
             "--unclassified", "--json"], None, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["rows"], 1, out)
        self.assertEqual(list(out["commands"]), ["gh repo view me/x"])
        self.assertEqual(out["programs"].get("gh"), 1)

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
        # unlike consent, this rule keeps refusing: the deny text names the
        # rephrase (a name, a length, a fingerprint), so the write is replaced
        # rather than repeated
        command = 'echo "api_key=sk-live-abc123" > out.txt'
        for _ in range(2):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason)
            self.assertIn("Credential", reason)

    def test_consent_and_secret_are_their_own_rules(self):
        # `verify-off` removes the shortcut and loop halves only; these are not
        # the integrity rule's, so they stay armed
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertIsNotNone(
            self.decide("Bash", {"command": "git push --force origin main"}))
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
        # and a bash command is not a write tool: there is no file to keep
        self.assertIsNone(self.decide("Bash", {"command": "pytest -q"},
                                      session_id="cap", capture_log=log))
        self.assertEqual(len(calls()), 1, calls())

    # ---- constraint drift: a long turn re-states the rules -----------------
    # Above the gate's DRIFT_STEPS whatever it is tuned to: this test is about a
    # turn long enough to have lost the prompt that armed the rules, not about
    # the exact number.
    LONG = 60

    def ledger(self, session):
        """The ledger file a session's rows land in, found rather than derived:
        the stem is tezgah_integrity._slug's, and a test that re-implemented it
        would stop testing the file the hooks actually read."""
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": session, "kind": "turn",
                  "detail": "seed"}, env=self.envv)
        d = os.path.join(self.home, ".cache", "tezgah", "evidence")
        names = os.listdir(d)
        self.assertEqual(len(names), 1, names)
        return os.path.join(d, names[0])

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

    def test_a_long_turn_restates_the_constraints_before_a_write(self):
        self.seed_turn("long", self.LONG)
        reason = self.write_call("long")
        self.assertIsNotNone(reason)
        self.assertIn("Long turn", reason)
        self.assertIn("still in force", reason)
        # the text is tezgah_policy's own, not a second copy of the contract
        self.assertIn("Ponytail (minimal code)", reason)
        self.assertIn("Deliver the whole ask", reason)

    def test_the_restatement_is_once_per_turn(self):
        # a re-statement on every call is noise the agent learns to skip
        self.seed_turn("long", self.LONG)
        self.assertIsNotNone(self.write_call("long"))
        self.assertIsNone(self.write_call("long", path="b.py"))

    def test_a_short_turn_is_left_alone(self):
        self.seed_turn("short", 3)
        self.assertIsNone(self.write_call("short"))

    def test_a_read_does_not_earn_the_restatement(self):
        self.seed_turn("long", self.LONG)
        self.assertIsNone(self.decide("Grep", {"pattern": "two words"},
                                      session_id="long"))

    def test_a_git_write_is_effectful_enough(self):
        self.seed_turn("long", self.LONG)
        reason = self.decide("Bash", {"command": 'git commit -m "fix: typo"'},
                             session_id="long")
        self.assertIsNotNone(reason)
        self.assertIn("Long turn", reason)

    def test_the_next_turn_gets_its_own_restatement(self):
        # the mark is per turn: the prompt reminder decays the same way in the
        # turn after it, so the notice has to be able to fire again
        self.seed_turn("long", self.LONG)
        self.assertIsNotNone(self.write_call("long"))
        self.seed_turn("long", self.LONG)
        self.assertIsNotNone(self.write_call("long", path="b.py"))

    def test_the_restatement_respects_reminder_off(self):
        # it is the mid-turn half of the per-turn reminder, so that reminder's
        # own switch removes it
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        self.seed_turn("long", self.LONG)
        self.assertIsNone(self.write_call("long"))

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


class TaskGate(TempHome):
    """The task rule: the user's own phase and allowlist, read from a plan file.

    Every case here seeds a real plan file under the repo's plans/open - the
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
        path = os.path.join(self.repo, "plans", "open", name)
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
            for command in ("tezgah-task", "tezgah-consent", "bin/tezgah"):
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
        # even in a phase that writes and even when the allowlist covers plans/,
        # because a scope that can widen itself is not a scope.
        path = self.plan(phase="implementation", allowed=("plans/**",))
        for target in (path, "plans/open/017-gate-rule.md"):
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
        self.assertIsNone(self.write_path("plans/open/017-gate-rule.md"))
        self.assertIsNone(self.decide({"command": "bin/tezgah-task stop"},
                                      tool="Bash"))


class RmOutsideFloor(unittest.TestCase):
    """`rm_outside`'s scratch floor, read in process.

    A gate test that builds its targets from the sandbox cannot see this floor:
    the sandbox lives under TMPDIR, so on Linux every path it can name is
    scratch and the floor swallows the case. Absolute targets against an
    explicit run directory are the same answer on every platform."""

    def outside(self, target, cwd="/srv/app", scratch_ok=True):
        command = "rm -rf %s" % target
        return tg.rm_outside(tg.mask(command), command, cwd, cwd, scratch_ok)

    def test_a_target_under_a_temp_root_is_scratch(self):
        for target in ("/tmp/x", "/tmp/tezgah-fixture/nested", "/tmp/a/b/c"):
            self.assertFalse(self.outside(target), target)

    def test_a_target_outside_the_temp_root_is_an_effect(self):
        for target in ("/srv/other", "../sibling", "/etc/x", "/opt/data",
                       "/tmp/../etc", "/tmp", "$VAR/x", "~/Downloads/x"):
            self.assertTrue(self.outside(target), target)

    def test_the_run_directory_itself_is_always_an_effect(self):
        # even when it sits under a temp root: deleting where the command runs
        # is not a delete inside it, and a repo checked out in /tmp is work
        for cwd in ("/srv/app", "/tmp/app"):
            self.assertTrue(self.outside(cwd, cwd=cwd), cwd)
            self.assertTrue(self.outside(".", cwd=cwd), cwd)

    def test_a_target_inside_the_run_directory_is_not_this_rule(self):
        for target in ("build", "./dist", "/srv/app/sub"):
            self.assertFalse(self.outside(target), target)

    def test_the_conservative_reader_keeps_scratch_as_an_effect(self):
        # the taint rule's half: a scratch delete is still an effect there, which
        # is what stops an injection making its first move a `rm -rf` in /tmp
        self.assertTrue(self.outside("/tmp/x", scratch_ok=False))


if __name__ == "__main__":
    unittest.main()
