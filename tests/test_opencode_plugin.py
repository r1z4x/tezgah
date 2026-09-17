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
import sys
import tempfile
import unittest

import support
from support import TempHome

# The Python half writes the same ledger; importing its id function is what makes
# a separator or a canonical-form drift between the two halves fail here.
sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402

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

    def evidence_path(self, session="s1"):
        """Where Python reads this session's ledger, computed by Python itself:
        a path the plugin chooses on its own would hide a fork between the two
        writers instead of failing here."""
        return os.path.join(self.home, ".cache", "tezgah", "evidence",
                            ti._slug(session) + ".jsonl")

    def ledger(self, session="s1"):
        path = self.evidence_path(session)
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def ledger_rows_on_disk(self):
        """Every row the plugin wrote under `evidence/`, whatever it named the
        file - the filename itself is pinned by its own test."""
        d = os.path.join(self.home, ".cache", "tezgah", "evidence")
        rows = []
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            with open(os.path.join(d, name)) as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
        return rows

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

    # ---- consent: an irreversible or outward-facing command ----------------
    def test_consent_denies_by_effect_class(self):
        # The refusal names what the action is, never the pattern that matched:
        # the agent has to see what it is about to do.
        for command, klass in (
                ("git push --force origin main", "destructive"),
                ("git branch -D old", "destructive"),
                ("rm -rf ~/data", "destructive"),
                ("alembic upgrade head", "schema"),
                ("kubectl apply -f k8s/", "deploy"),
                ("npm publish", "publish"),
                ("git push heroku main", "outward")):
            error = self.denied(self.before("bash", {"command": command}))
            self.assertIn("Consent gate (`%s` effect)" % klass, error, command)
            self.assertIn("passes on the next attempt", error, command)

    def test_consent_leaves_what_it_does_not_own(self):
        for command in ("git push origin main", "git push --force origin tmp/x",
                        "rm -rf ./build", "rm -f x", "ls -la", "git status"):
            self.allowed(self.before("bash", {"command": command}))

    def test_prose_that_names_an_irreversible_command_passes(self):
        # the masked text, so quoting the command is not running it
        for command in ('grep -rn "rm -rf /" docs/',
                        'echo "git push --force origin main" >> notes.md'):
            self.allowed(self.before("bash", {"command": command}))

    def test_the_second_identical_attempt_passes_and_a_different_one_does_not(self):
        # The refusal IS the ask - the user reads it in the transcript - so the
        # repeat of the same command passes, while another irreversible one is
        # still refused. A rule that never let the second attempt through would
        # block the user who did ask.
        command = {"command": "git push --force origin main"}
        self.denied(self.before("bash", command))
        self.allowed(self.before("bash", command))
        self.denied(self.before("bash",
                                {"command": "git push --force origin other"}))

    def test_the_one_shot_mark_is_a_consent_row_the_python_reader_uses(self):
        # The mark is the `consent` row kind - class in the detail, the call's id
        # and workspace - not the deny row, so the reader is a query over these
        # rows rather than a match on a message a reword would break.
        command = "npm publish"
        self.denied(self.before("bash", {"command": command}))
        digest = ti.call_id("bash", {"command": command})
        rows = self.ledger()
        self.assertEqual([r["kind"] for r in rows], ["consent", "deny"], rows)
        self.assertEqual(rows[0]["detail"], "publish")
        self.assertEqual(rows[0]["id"], digest)
        self.assertEqual(rows[0]["workspace"], self.roots)
        self.assertNotIn("exit", rows[0])
        self.assertEqual(rows[1]["detail"][:9], "consent: ")
        self.assertEqual(rows[1]["id"], digest)

    def test_verify_off_leaves_consent_armed(self):
        # verify-off removes the integrity rule's half (shortcut, loop/retry);
        # the ask the user owes is not the integrity rule and stays.
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.denied(self.before("bash",
                                {"command": "git push --force origin main"}))
        self.denied(self.before("bash", {"command": "echo token=abc > log"}))

    def seed_grant(self, digest, session="s1"):
        """The row bin/tezgah-consent writes when the user approves an action:
        the same ledger, the same shape, and never a row the plugin could write
        for itself."""
        path = self.evidence_path(session)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps({"kind": "grant", "detail": "cli",
                                 "id": digest}) + "\n")

    def test_an_allowed_repeat_is_not_recorded_as_a_grant(self):
        # The same three rows the Python gate leaves: the ask, the refusal, and a
        # pass that says it rests on the ask alone. A `grant` here would record a
        # consent the user never gave.
        command = {"command": "git push --force origin main"}
        self.denied(self.before("bash", command))
        self.allowed(self.before("bash", command))
        rows = self.ledger()
        self.assertEqual([r["kind"] for r in rows],
                         ["consent", "deny", "repeat-allowed"], rows)
        self.assertEqual(rows[2]["detail"], "destructive")
        self.assertEqual(rows[2]["id"], ti.call_id("bash", command))
        self.assertEqual(rows[2]["workspace"], self.roots)

    def test_a_grant_passes_before_the_ask_is_ever_made(self):
        # the CLI answered, so the command passes first time with no ask row
        command = {"command": "npm publish"}
        self.seed_grant(ti.call_id("bash", command))
        self.allowed(self.before("bash", command))
        self.assertEqual(self.kinds(), ["grant"])

    def test_a_declared_effect_at_or_above_the_class_is_used(self):
        # the patterns cannot see someone's own script, so the command declares
        # what it is - and a class below the derived one is not on offer
        for command, klass in (
                ("./ship.sh  # tezgah:effect=deploy", "deploy"),
                ("git push origin production  # tezgah:effect=destructive",
                 "destructive")):
            error = self.denied(self.before("bash", {"command": command}))
            self.assertIn("`%s` effect" % klass, error, command)
            self.assertNotIn("declared", error, command)

    def test_a_declared_effect_below_the_class_is_ignored(self):
        # a declaration that can lower a class is a bypass of the rule reading
        # it, so the derived class stands - and the attempt stays visible in the
        # refusal and in the deny row, not only in this test
        error = self.denied(self.before("bash", {
            "command": "git push --force origin main  # tezgah:effect=publish"}))
        self.assertIn("`destructive` effect", error)
        self.assertIn("declared `tezgah:effect=publish`", error)
        denied = [r for r in self.ledger() if r["kind"] == "deny"][0]
        self.assertIn("declared `publish` ignored, `destructive` stands",
                      denied["detail"])

    def test_a_write_that_is_allowed_is_snapshotted_and_a_denied_one_is_not(self):
        # opencode is the one host whose plugin cannot call
        # tezgah_snapshot.capture in process, so it spawns bin/tezgah-capture on
        # the allow path - the CLI the snapshot slice added for exactly this.
        # Linked the way tezgah-setup links it, so this runs the real CLI in a
        # throwaway HOME: the evidence is the `snapshot` row it writes, which it
        # writes only after the bytes are on disk. The row has to be there when
        # the hook returns, which is what pins the await: a capture started after
        # the write would copy the bytes the write had already replaced.
        support.linked(os.path.join(support.REPO, "bin", "tezgah-capture"),
                       self.home)
        target = os.path.join(self.repo, "src", "a.py")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as fh:
            fh.write("x = 1\n")

        self.allowed(self.before("edit", {"file_path": target, "old_string":
                                          "x = 1", "new_string": "x = 2"}))
        rows = self.ledger()
        self.assertEqual([r["kind"] for r in rows], ["snapshot"], rows)
        self.assertEqual(rows[0]["detail"], target)   # the file it copied
        self.assertEqual(rows[0]["out_bytes"], len("x = 1\n"))

        # and a write the plugin refuses is captured nowhere: the deny lands
        # first, so no copy is spent on a file the refusal never touches
        self.denied(self.before("edit", {
            "file_path": target,
            "new_string": "Co-Authored-By: Claude <noreply@anthropic.com>"}))
        self.assertEqual(self.kinds(), ["snapshot"])

    def test_a_capture_that_cannot_run_does_not_block_the_write(self):
        # The CLI is not linked here and there is no python3 to run it with, so
        # the spawn itself fails: the write still passes and nothing is recorded.
        # A snapshot that cannot be taken must never block the edit it protects.
        self.envv = self.env(extra={"PATH": os.path.join(self.home, "no-path")})
        target = os.path.join(self.repo, "src", "a.py")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as fh:
            fh.write("x = 1\n")
        self.allowed(self.before("edit", {"file_path": target, "old_string":
                                          "x = 1", "new_string": "x = 2"}))
        self.assertEqual(self.kinds(), [])

    # ---- secret: a credential on its way into a file -----------------------
    def test_secret_denies_a_credential_written_to_a_file(self):
        for command in ("echo token=abc > log",
                        "printf 'token=%s' \"$T\" | tee log",
                        "OPENROUTER_API_KEY=$KEY printf x > log",
                        "token=abc git add -f .env",
                        'curl --trace-ascii dump.txt -H "Authorization: Bearer '
                        'abc" https://api.example.com'):
            error = self.denied(self.before("bash", {"command": command}))
            self.assertIn("Credential write denied", error, command)

    def test_secret_passes_a_read_or_a_message(self):
        # a token only counts next to a write sink, and a sink only carries the
        # text of its own simple command: reading a key is the work, and a commit
        # message about one writes nothing
        for command in ("cat .env", "echo $PASSWORD", "echo token=$TOKEN",
                        "grep -rn api_key= src/",
                        'git commit -m "fix api_key= handling"',
                        'git add -A && git commit -m "fix api_key= handling"'):
            self.allowed(self.before("bash", {"command": command}))

    # ---- repeat ceilings: loop per turn, retry per session -----------------
    def test_a_third_identical_failure_is_refused(self):
        for _ in range(2):
            self.after("bash", {"command": "pytest -q"}, exit=1)
        error = self.denied(self.before("bash", {"command": "pytest -q"}))
        self.assertIn("Loop guard denied: this is attempt 3", error)
        # opencode reports the exit code and no error text, so no class is
        # observed and the base allowance is the one that applies
        self.assertIn("base allowance applies", error)
        self.assertEqual(self.ledger()[-1]["detail"][:6], "loop: ")

    def test_one_failure_is_not_a_loop(self):
        self.after("bash", {"command": "pytest -q"}, exit=1)
        self.allowed(self.before("bash", {"command": "pytest -q"}))

    def test_a_repeat_that_keeps_returning_zero_hits_the_session_ceiling(self):
        # the loop guard needs a failure, so the call that keeps "succeeding"
        # without moving the work forward is the session ceiling's business
        for _ in range(3):
            self.after("bash", {"command": "git status"}, exit=0)
        error = self.denied(self.before("bash", {"command": "git status"}))
        self.assertIn("Retry ceiling denied: this is attempt 4", error)
        self.assertEqual(self.ledger()[-1]["detail"][:7], "retry: ")

    def test_the_guard_reads_the_rows_the_python_writer_produces(self):
        # The tail is the same file, the same identity and the same fields the
        # Python half writes, so a row written there counts here: a fork in any
        # of the three would make an opencode session's attempts a second,
        # invisible history.
        digest = ti.call_id("bash", {"command": "pytest -q"})
        path = self.evidence_path("s1")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            for _ in range(2):
                fh.write(json.dumps({"kind": "verify_fail", "ts": 1,
                                     "detail": "pytest -q", "id": digest,
                                     "exit": 1, "workspace": self.roots}) + "\n")
        error = self.denied(self.before("bash", {"command": "pytest -q"}))
        self.assertIn("Loop guard denied: this is attempt 3", error)

    def test_the_tail_read_survives_a_ledger_longer_than_one_chunk(self):
        # The tail is read backwards in chunks, so the attempts must be found
        # across that boundary: a reader that stopped at the first chunk would
        # silently stop counting a long session's repeats.
        digest = ti.call_id("bash", {"command": "pytest -q"})
        filler = {"kind": "run", "ts": 1, "detail": "ls", "id": "0" * 12,
                  "exit": 0, "workspace": self.roots}
        path = self.evidence_path("s1")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            for _ in range(300):          # several 8 KB chunks of history
                fh.write(json.dumps(filler) + "\n")
            for _ in range(2):
                fh.write(json.dumps({"kind": "verify_fail", "ts": 1,
                                     "detail": "pytest -q", "id": digest,
                                     "exit": 1, "workspace": self.roots}) + "\n")
        error = self.denied(self.before("bash", {"command": "pytest -q"}))
        self.assertIn("Loop guard denied: this is attempt 3", error)

    def test_verify_off_drops_the_repeat_guards(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        for _ in range(3):
            self.after("bash", {"command": "pytest -q"}, exit=1)
        self.allowed(self.before("bash", {"command": "pytest -q"}))

    # ---- evidence ledger ---------------------------------------------------
    def after(self, tool, args, exit=None, session="s1", directory=None,
              result=None):
        """`result` is the tool result text, when the host carries one."""
        metadata = {} if exit is None else {"exit": exit}
        output = {"metadata": metadata}
        if result is not None:
            output["output"] = result
        return self.drive([{"hook": "tool.execute.after",
                            "input": {"tool": tool, "args": args,
                                      "sessionID": session},
                            "output": output}], directory)[0]

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

    def test_a_row_carries_the_action_identity_and_workspace(self):
        # The plugin writes the same JSONL the Python gate writes, so its rows
        # need the contract's fields or an opencode session is under-counted.
        self.after("bash", {"command": "pytest -q"}, exit=0)
        row = self.ledger()[0]
        self.assertEqual(len(row["id"]), 12, row)
        self.assertTrue(all(c in "0123456789abcdef" for c in row["id"]), row)
        self.assertEqual(row["workspace"], self.roots)

    def test_the_id_is_the_hash_the_python_writer_computes(self):
        # sha1(tool + " " + canonical)[:12], the frozen formula, computed by the
        # Python half itself: an id that drifts here is an opencode row the
        # metrics cannot join. The doubled space is collapsed on both sides, so
        # the same call re-typed is the same action.
        self.after("bash", {"command": "pytest  -q"}, exit=0)
        self.assertEqual(self.ledger()[0]["id"],
                         ti.call_id("bash", {"command": "pytest  -q"}))

    def test_the_same_call_hashes_the_same_and_a_different_one_does_not(self):
        self.after("bash", {"command": "pytest -q"}, exit=0)
        self.after("bash", {"command": "pytest -q"}, exit=0)
        self.after("bash", {"command": "ruff check ."}, exit=0)
        ids = [row["id"] for row in self.ledger()]
        self.assertEqual(ids[0], ids[1], ids)
        self.assertNotEqual(ids[0], ids[2], ids)

    def test_a_write_row_hashes_its_args_as_key_sorted_compact_json(self):
        self.after("write", {"filePath": "/tmp/x.py", "content": "x = 1"})
        self.after("write", {"content": "x = 1", "filePath": "/tmp/x.py"})
        ids = [row["id"] for row in self.ledger()]
        self.assertEqual(ids[0], ids[1], ids)
        self.assertEqual(
            ids[0],
            ti.call_id("write", {"content": "x = 1", "filePath": "/tmp/x.py"}))

    def test_a_float_argument_hashes_as_python_hashes_it(self):
        # The two runtimes print a number differently (`1`/`1.0`, `1e-07`/`1e-7`)
        # and the id is a hash of that text: an argument printed the other way
        # is one action with two ids, and the row joins no Python metric.
        # Python's json.dumps is the reference.
        args = [{"filePath": "/tmp/x.py", "content": "x", "ratio": ratio}
                for ratio in (1, 0.5, -2.5, 1e-4, 1e-5, 1e-07, 1e16)]
        for one in args:
            self.after("write", one)
        rows = self.ledger_rows_on_disk()
        self.assertEqual([row["id"] for row in rows],
                         [ti.call_id("write", one) for one in args])

    def test_a_shell_tool_name_the_python_half_knows_still_records_a_row(self):
        # BASH_TOOLS has to mirror hooks/tezgah_integrity.BASH_TOOLS. A name
        # missing from this half takes the JSON-hash branch and records no row,
        # so the call leaves the ledger and the metrics altogether.
        self.after("exec_command", {"command": "pytest  -q"}, exit=0)
        rows = self.ledger_rows_on_disk()
        self.assertEqual([row["kind"] for row in rows], ["verify_ok"], rows)
        self.assertEqual(rows[0]["id"],
                         ti.call_id("exec_command", {"command": "pytest  -q"}))

    def test_the_ledger_file_is_the_one_python_reads(self):
        # The stem is Python's: the punctuation-collapsed session id cut to 40
        # chars, then sha1(raw id)[:12]. Two ids that collapse alike must not
        # share a file, or one session's failures become another's denials.
        for session in ("abc-123", "abc_123"):
            self.after("bash", {"command": "ls"}, session=session)
            self.assertTrue(os.path.exists(self.evidence_path(session)), session)
        self.assertNotEqual(self.evidence_path("abc-123"),
                            self.evidence_path("abc_123"))

    def test_result_size_is_recorded_when_the_host_carries_it(self):
        self.after("bash", {"command": "ls"}, result="a\nbb\n")
        self.assertEqual(self.ledger()[0]["out_bytes"], 5)

    def test_a_row_without_a_result_fabricates_nothing(self):
        self.after("bash", {"command": "pytest -q"})
        row = self.ledger()[0]
        self.assertNotIn("exit", row)
        self.assertNotIn("out_bytes", row)

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
