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

    def test_the_failure_class_scopes_the_loop_allowance(self):
        # a transient failure (timeout, connection, rate limit, 5xx) can clear on
        # its own, so the identical call gets one more attempt than a permanent
        # one; a permanent failure and a host that reports no error text at all
        # keep the base allowance. The class is observable only where the host
        # sends the error as text (Claude's PostToolUseFailure `error`).
        transient = "ceil-transient"
        for n in (1, 2):
            self.seed_failure("pytest -q", transient,
                              error="Command timed out after 2m")
            self.assertIsNone(
                self.decide("Bash", {"command": "pytest -q"},
                            session_id=transient),
                "transient attempt %d of 3 must pass" % (n + 1))
        self.seed_failure("pytest -q", transient,
                          error="Command timed out after 2m")
        reason = self.decide("Bash", {"command": "pytest -q"},
                             session_id=transient)
        self.assertIsNotNone(reason)
        self.assertIn("attempt 4", reason)
        self.assertIn("transient", reason)
        self.assertIn("allows 3 identical attempts", reason)
        for session, error, note in (
                ("ceil-perm", "E   AssertionError: 1 != 2", "bad argument"),
                ("ceil-none", None, "no error text")):
            for _ in range(2):
                self.seed_failure("pytest -q", session, error=error)
            reason = self.decide("Bash", {"command": "pytest -q"},
                                 session_id=session)
            self.assertIsNotNone(reason, session)
            self.assertIn("attempt 3", reason)
            self.assertIn("allows 2 identical attempts", reason)
            self.assertIn(note, reason)

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
    def test_a_force_push_denies_once_then_the_identical_call_passes(self):
        # The gate sees one call and cannot ask the user, so the refusal is the
        # ask: it lands in the transcript, and the identical command passes on
        # the next attempt - which is what a user who did ask re-issues.
        for command in ("git push --force origin main",
                        "git push -f origin main",
                        "git push --force-with-lease origin main",
                        "git push --force-with-lease=origin/main origin main",
                        "git -C /tmp/repo push --force origin master"):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Consent", reason)
            self.assertIsNone(self.decide("Bash", {"command": command}), command)

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
        for command in ("rm -rf /tmp/scratch",
                        'rm -rf "%s"' % os.path.join(self.home, "elsewhere"),
                        "rm -rf ~/Downloads/junk",
                        "rm -rf ../sibling-artifact",
                        "rm -rf $BUILD_DIR",
                        "rm -rf ."):
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, command)
            self.assertIn("Consent", reason)

    def test_a_delete_inside_the_run_directory_passes(self):
        # both flags are required (`rm -f` / `rm -r` alone are not this rule's),
        # and a path under the run directory is the agent's own workspace
        for command in ("rm -rf build", "rm -rf node_modules && npm ci",
                        'rm -rf "./dist"', "rm -f /tmp/scratch", "rm -r /tmp/x"):
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
                ("rm -rf ../sibling", "destructive"),
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
        # deny message a later reword would silently break
        self.decide("Bash", {"command": "git push --force origin main"},
                    session_id="asked")
        self.decide("Bash", {"command": "npm publish"}, session_id="asked")
        rows = [r for r in self.rows("asked") if r["kind"] == "consent"]
        self.assertEqual([r["detail"] for r in rows],
                         ["destructive", "publish"])
        self.assertEqual(rows[0]["workspace"], self.roots)
        for r in rows:
            self.assertEqual(len(r["id"]), 12)
            self.assertEqual(r["kind"], "consent")
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])
        # the row names the refused action: its id is the denial's id
        denials = [r for r in self.rows("asked") if r["kind"] == "deny"]
        self.assertEqual([r["id"] for r in denials], [r["id"] for r in rows])
        self.assertEqual(
            [r["detail"].split(":", 1)[0] for r in denials], ["consent", "consent"])

    def test_the_consent_row_is_what_spends_the_one_shot(self):
        # the classification row IS the mark, so the ask cannot be answered and
        # the row fall out of step: one refusal, one row, one pass
        command = "npm publish --access public"
        self.assertIsNotNone(self.decide("Bash", {"command": command},
                                         session_id="oneshot"))
        rows = [r for r in self.rows("oneshot") if r["kind"] == "consent"]
        self.assertEqual(len(rows), 1)
        self.assertIsNone(self.decide("Bash", {"command": command},
                                      session_id="oneshot"))
        self.assertEqual(len([r for r in self.rows("oneshot")
                              if r["kind"] == "consent"]), 1)

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


if __name__ == "__main__":
    unittest.main()
