"""tezgah_extension: a repository's own statusline chips, on tezgah's line.

An extension is a manifest under `<repo>/.tezgah/extension.json` naming a command
that prints structured segments. These tests pin the manifest walk, the merge
into `health_segments()` (the extension's group lands one past the built-ins),
and the failure contract: a missing manifest, a bad manifest, an absent command,
a non-zero exit, a timeout, malformed JSON, a wrong shape and an over-budget list
each cost the extension its chips and never the line.

The manifest's other keys - `checks`, `untrusted`, `agents`,
`statusline.override` - and the engagement-root discovery each get a class, and
each class has a broken value that costs that key and never the line or the
gate.
"""
import json
import os
import stat
import subprocess
import sys
import unittest
from unittest import mock

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402
import tezgah_extension as te  # noqa: E402
import tezgah_integrity as ti  # noqa: E402
import tezgah_models as tm  # noqa: E402
import tezgah_untrusted as tu  # noqa: E402

STATUS = os.path.join(os.path.dirname(support.HOOKS), "bin", "tezgah-status")


def write_script(path, body):
    """A small executable: `#!/usr/bin/env python3` plus `body`."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("#!/usr/bin/env python3\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


# The success-path tests assert the segment contract, not the latency budget. An
# interpreter start under a machine running the whole suite in parallel can
# outrun the default hang budget, so every manifest here carries its own
# generous one; a test that pins a budget of its own keeps it.
SLOW_MS = 60000


def with_slow_budget(spec):
    """`spec` with a generous `timeout_ms`, unless the test pinned one."""
    if isinstance(spec, dict):
        line = spec.get("statusline")
        if isinstance(line, dict) and "timeout_ms" not in line:
            line["timeout_ms"] = SLOW_MS
    return spec


class Manifest(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")

    def manifest(self, spec):
        path = os.path.join(self.repo, ".tezgah", "extension.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(with_slow_budget(spec), fh)
        return path

    def test_no_manifest_means_no_segments(self):
        self.assertEqual(te.segments(self.repo), [])
        self.assertEqual(te.manifest_path(self.repo), (None, None))

    def test_the_walk_finds_a_manifest_above_the_working_directory(self):
        self.manifest({"statusline": {"command": ["true"]}})
        deep = os.path.join(self.repo, "a", "b", "c")
        os.makedirs(deep, exist_ok=True)
        root, found = te.manifest_path(deep)
        self.assertEqual(root, self.repo)
        self.assertTrue(found.endswith(os.path.join(".tezgah", "extension.json")))

    def test_the_nearest_manifest_wins(self):
        inner = os.path.join(self.repo, "vendor", "lib")
        os.makedirs(os.path.join(inner, ".tezgah"), exist_ok=True)
        self.manifest({"statusline": {"command": ["true"]}})
        with open(os.path.join(inner, ".tezgah", "extension.json"), "w") as fh:
            json.dump({"statusline": {"command": ["true"]}}, fh)
        root, _found = te.manifest_path(os.path.join(inner, "src"))
        self.assertEqual(root, inner)

    def test_a_relative_command_resolves_against_the_repo_root(self):
        write_script(os.path.join(self.repo, "bin", "emit"),
                     "import json, sys\njson.dump({'segments': []}, sys.stdout)\n")
        self.manifest({"statusline": {"command": ["bin/emit"]}})
        # resolved from the repo root, not the caller's cwd, and [] is valid
        self.assertEqual(te.segments(os.path.join(self.repo, "unrelated")), [])

    def test_a_command_emits_segments_with_the_shape_tezgah_renders(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [{'key': 'eng', 'state': 'off',\n"
            "                         'text': 'eng acme', 'group': 0}]}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        segs = te.segments(self.repo)
        self.assertEqual([s["key"] for s in segs], ["eng"])
        self.assertEqual(segs[0]["state"], "off")

    def test_the_line_renders_the_extension_chips_after_the_built_ins(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [\n"
            "  {'key': 'eng', 'state': 'info', 'text': 'eng acme'},\n"
            "  {'key': 'run', 'state': 'on', 'text': 'run 2', 'glyph': '\\u25b6'}]},\n"
            "  sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        line = tc.health_lines(self.repo)
        self.assertIn("eng acme", line)
        self.assertIn("run 2\u25b6", line)
        # one cluster past the built-ins: the extension sorts after every mark,
        # so a chip never splits the armed/used run
        self.assertLess(line.index("adhd"), line.index("eng acme"))

    def test_the_core_fills_a_missing_glyph_from_the_state(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [{'key': 'a', 'state': 'off', 'text': 'halt'}]},\n"
            "  sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        segs = [s for s in tc.health_segments(self.repo) if s["key"] == "a"]
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["glyph"], tc.GLYPHS["off"])

    def test_a_custom_glyph_is_kept(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [{'key': 'a', 'state': 'on', 'text': 'live',\n"
            "                         'glyph': '\\u25b6'}]}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        segs = [s for s in tc.health_segments(self.repo) if s["key"] == "a"]
        self.assertEqual(segs[0]["glyph"], "\u25b6")


class Failure(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.manifest_path = os.path.join(self.repo, ".tezgah", "extension.json")

    def manifest(self, spec):
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w") as fh:
            if isinstance(spec, str):
                fh.write(spec)
            else:
                json.dump(with_slow_budget(spec), fh)

    def test_a_malformed_manifest_costs_the_extension_not_the_line(self):
        self.manifest("{ not json")
        self.assertEqual(te.segments(self.repo), [])
        self.assertTrue(tc.health_lines(self.repo))  # the line still draws

    def test_a_manifest_with_no_statusline_block_is_ignored(self):
        self.manifest({"other": 1})
        self.assertEqual(te.segments(self.repo), [])

    def test_a_missing_command_is_not_run(self):
        self.manifest({"statusline": {"command": ["bin/there-is-no-such-file"]}})
        self.assertEqual(te.segments(self.repo), [])

    def test_a_non_zero_exit_is_ignored(self):
        script = write_script(os.path.join(self.repo, "emit"),
                              "import sys\nsys.exit(3)\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(self.repo), [])

    def test_a_timeout_drops_the_segments_rather_than_blocking(self):
        script = write_script(os.path.join(self.repo, "emit"),
                              "import json, sys, time\ntime.sleep(5)\n"
                              "json.dump({'segments': [{'text': 'late'}]}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script], "timeout_ms": 200}})
        self.assertEqual(te.segments(self.repo), [])

    def test_malformed_json_on_stdout_is_ignored(self):
        script = write_script(os.path.join(self.repo, "emit"),
                              "import sys\nsys.stdout.write('not json')\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(self.repo), [])

    def test_a_wrong_shape_is_ignored(self):
        script = write_script(os.path.join(self.repo, "emit"),
                              "import json, sys\njson.dump({'segments': 'nope'}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(self.repo), [])

    def test_a_segment_without_text_is_dropped_and_the_rest_survive(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [{'text': ''}, {'key': 'ok', 'text': 'kept'}]},\n"
            "  sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual([s["key"] for s in te.segments(self.repo)], ["ok"])

    def test_an_unknown_state_becomes_info_not_a_guess(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [{'text': 'x', 'state': 'exploded'}]}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(self.repo)[0]["state"], "info")

    def test_the_per_extension_cap_bounds_the_line(self):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "json.dump({'segments': [{'text': 's%d' % i} for i in range(50)]},\n"
            "  sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(len(te.segments(self.repo)), te.MAX_SEGMENTS)

    def test_a_non_utf8_manifest_is_ignored(self):
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "wb") as fh:
            fh.write(b"\xff\xfe{}")
        self.assertEqual(te.segments(self.repo), [])


class Envelope(TempHome):
    """The call the child is handed: what tezgah tells an extension about it."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")

    def manifest(self, spec):
        path = os.path.join(self.repo, ".tezgah", "extension.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(with_slow_budget(spec), fh)

    def echo(self, expression):
        """A command that reads the envelope and prints what `expression` says."""
        return write_script(
            os.path.join(self.repo, "emit"),
            "import json, sys\n"
            "call = json.loads(sys.stdin.read() or '{}')\n"
            "json.dump({'segments': [{'key': 'k', 'text': %s}]}, sys.stdout)\n"
            % expression)

    def test_the_child_is_told_the_api_the_event_and_the_repository(self):
        script = self.echo("' '.join([str(call['api']), call['event'], "
                           "str(call['repo_root'] == %r)])" % self.repo)
        self.manifest({"statusline": {"command": [script]}})
        segs = te.segments(self.repo)
        self.assertEqual(segs[0]["text"], "1 statusline True")

    def test_the_child_is_told_the_directory_it_was_called_from(self):
        deep = os.path.join(self.repo, "a", "b")
        os.makedirs(deep, exist_ok=True)
        script = self.echo("'yes' if call['cwd'] == %r else call['cwd']"
                           % os.path.realpath(deep))
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(deep)[0]["text"], "yes")

    def test_the_session_reaches_the_child_and_is_null_without_one(self):
        script = self.echo("str(call['session_id'])")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(self.repo)[0]["text"], "None")
        self.assertEqual(te.segments(self.repo, session_id="s-42")[0]["text"],
                         "s-42")

    def test_through_the_line_the_session_is_the_renderers(self):
        script = self.echo("str(call['session_id'])")
        self.manifest({"statusline": {"command": [script]}})
        segs = [s for s in tc.health_segments(self.repo, session_id="s-9")
                if s["key"] == "k"]
        self.assertEqual(segs[0]["text"], "s-9")

    def test_a_command_that_ignores_stdin_still_works(self):
        script = write_script(
            os.path.join(self.repo, "emit"),
            "import json, sys\njson.dump({'segments': [{'text': 'blind'}]}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script]}})
        self.assertEqual(te.segments(self.repo)[0]["text"], "blind")


class KeyCase(TempHome):
    """A repo with a manifest the test writes, and no engagement root leaking in
    from the developer's shell."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop(te.ENGAGEMENTS_ENV, None)

    def manifest(self, spec, root=None):
        path = os.path.join(root or self.repo, ".tezgah", "extension.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            if isinstance(spec, str):
                fh.write(spec)
            else:
                json.dump(with_slow_budget(spec), fh)
        return path

    def ledger(self):
        """The evidence ledger redirected into this test's temp dir."""
        self.addCleanup(setattr, ti, "_path", ti._path)
        path = os.path.join(self.home, "evidence", "s.jsonl")
        ti._path = lambda session: path

    def ran(self, command, failed=False):
        """The two rows a checked shell call leaves: the gate's `began` (its
        check mark read with the call's cwd, as decision() does) and the
        PostToolUse row; returns the PostToolUse row."""
        inp = {"command": command}
        ti.note("s", ti.BEGAN_KIND, command, id=ti.call_id("Bash", inp), tool="Bash",
                check=1 if ti.verify_command(command, self.repo) else None)
        ti.note_tool("s", "Bash", inp, failed=failed, out_bytes=42, cwd=self.repo)
        return ti.events("s")[-1]


class Checks(KeyCase):
    def test_checks_a_declared_prefix_is_a_check_only_in_its_repo(self):
        self.manifest({"checks": ["./bin/run-tool", "bin/audit --strict"]})
        self.assertEqual(ti.verify_command("./bin/run-tool scan", self.repo),
                         "./bin/run-tool")
        self.assertEqual(ti.verify_command("bin/run-tool scan", self.repo),
                         "bin/run-tool")
        self.assertEqual(ti.verify_command("FOO=1 bin/audit --strict x", self.repo),
                         "bin/audit --strict")
        # a prefix is all of its words, and the repo is what declares it
        self.assertIsNone(ti.verify_command("bin/audit x", self.repo))
        self.assertIsNone(ti.verify_command("./bin/run-tool scan"))
        self.assertIsNone(ti.verify_command("./bin/run-tool scan",
                                            self.make_repo("other")))

    def test_checks_a_prefix_named_in_an_argument_is_not_a_run(self):
        self.manifest({"checks": ["./bin/run-tool"]})
        for cmd in ('git commit -m "./bin/run-tool scan"', "echo ./bin/run-tool",
                    "./bin/run-tool --help",
                    "cat <<'EOF'\n./bin/run-tool scan\nEOF"):
            self.assertIsNone(ti.verify_command(cmd, self.repo), cmd)

    def test_checks_a_run_backs_a_verify_ok_that_passing_check_accepts(self):
        self.manifest({"checks": ["./bin/run-tool"]})
        self.ledger()
        row = self.ran("./bin/run-tool scan")
        self.assertEqual(row["kind"], "verify_ok")
        self.assertTrue(ti.passing_check(row))
        self.assertEqual(self.ran("./bin/run-tool scan 2", failed=True)["kind"],
                         "verify_fail")

    def test_checks_a_status_another_command_owns_stays_a_run(self):
        self.manifest({"checks": ["./bin/run-tool"]})
        self.ledger()
        for cmd in ("./bin/run-tool scan; echo done", "./bin/run-tool scan | tail"):
            row = self.ran(cmd)
            self.assertEqual(row["kind"], "verify", cmd)
            self.assertFalse(ti.passing_check(row), cmd)

    def test_checks_a_broken_value_costs_the_key_never_the_gate(self):
        for spec in ({"checks": "./bin/run-tool"}, {"checks": [1, "", "'open"]},
                     "{ not json"):
            self.manifest(spec)
            self.assertEqual(te.repo_checks(self.repo), [], spec)
            self.assertIsNone(ti.verify_command("./bin/run-tool", self.repo), spec)
            # the built-in vocabulary is untouched
            self.assertEqual(ti.verify_command("pytest -q", self.repo), "pytest", spec)
        self.manifest({"checks": [7, "./bin/ok"]})
        self.assertEqual(te.repo_checks(self.repo), [["bin/ok"]])

    def test_checks_a_lone_no_op_program_is_dropped_and_one_with_words_stays(self):
        # a bare `echo` declared as a check would license a pass for any echo
        self.manifest({"checks": ["echo", "true", ["cat"], "/bin/printf", "./ls",
                                  "echo tested"]})
        self.assertEqual(te.repo_checks(self.repo), [["echo", "tested"]])
        for cmd in ("echo hi", "true", "cat x", "/bin/printf ok", "ls"):
            self.assertIsNone(ti.verify_command(cmd, self.repo), cmd)
        self.assertEqual(ti.verify_command("echo tested", self.repo), "echo tested")
        self.ledger()
        self.assertEqual(self.ran("true")["kind"], "run")
        row = self.ran("echo tested")
        self.assertEqual(row["kind"], "verify_ok")
        self.assertTrue(ti.passing_check(row))


class Untrusted(KeyCase):
    def test_untrusted_a_declared_program_is_the_repo_channel(self):
        self.manifest({"untrusted": ["nmap", "/opt/bin/sqlmap"]})
        for cmd in ("nmap -sV 10.0.0.1", "sudo sqlmap -u x", "cd x && nmap a"):
            self.assertEqual(ti.untrusted_source("Bash", {"command": cmd}, self.repo),
                             "repo", cmd)
        # the call's own cwd is read when the caller passes none
        self.assertEqual(ti.untrusted_source(
            "Bash", {"command": "nmap a", "cwd": self.repo}), "repo")
        # a mention is not a run, another repo declares nothing
        self.assertIsNone(ti.untrusted_source("Bash", {"command": "echo nmap"},
                                              self.repo))
        self.assertIsNone(ti.untrusted_source("Bash", {"command": "nmap a"},
                                              self.make_repo("other")))
        # a network read keeps its own channel
        self.assertEqual(ti.untrusted_source("Bash", {"command": "curl https://x"},
                                             self.repo), "network")

    def test_untrusted_labels_the_result_and_taints_the_next_effect(self):
        self.manifest({"untrusted": ["nmap"]})
        self.ledger()
        inp = {"command": "nmap -sV lab", "cwd": self.repo}
        source, line = tu.marks("Bash", inp, "s")
        self.assertEqual(source, "repo")
        self.assertIn("a tool this repository declares untrusted", line)
        ti.note_tool("s", "Bash", inp, failed=False, out_bytes=9, cwd=self.repo,
                     source=source)
        source, line = tu.marks("Write", {"file_path": "/tmp/x", "content": "y"}, "s")
        self.assertEqual(source, "repo")
        self.assertIn("already read a tool this repository declares untrusted", line)

    def test_untrusted_a_broken_value_costs_the_key_never_the_call(self):
        for spec in ({"untrusted": "nmap"}, {"untrusted": [3, "two words", ""]},
                     "{ not json"):
            self.manifest(spec)
            self.assertIsNone(ti.untrusted_source("Bash", {"command": "nmap a"},
                                                  self.repo), spec)


class Route(KeyCase):
    AGENTS = {"agents": [{"match": "(?i)\\brecon\\b", "agent": "recon"},
                         {"match": "exploit", "agent": "web-exploit"}]}

    def test_route_a_repo_agent_follows_the_harness_judgement(self):
        self.manifest(self.AGENTS)
        harness = tm.route("Recon the lab subnet", "code", cwd=self.home)
        out = tm.route("Recon the lab subnet", "code", cwd=self.repo)
        self.assertEqual(out["agent"], "recon")
        # the tier and what set it stay the harness's own
        self.assertEqual((out["tier"], out["via"]), (harness["tier"], harness["via"]))
        self.assertIn("repo agent recon", out["why"])
        self.assertEqual(tm.route("exploit tomcat", "code", cwd=self.repo)["agent"],
                         "web-exploit")
        self.assertEqual(tm.route("Add a --json flag", "code", cwd=self.repo)["agent"],
                         harness["agent"])

    def test_route_the_harness_override_keeps_its_agent(self):
        self.manifest(self.AGENTS)
        out = tm.route("recon the credential store on disk", cwd=self.repo)
        self.assertEqual((out["agent"], out["via"]), ("tezgah-frontier", "rule"))

    def test_route_a_broken_agents_value_keeps_the_harness_pick(self):
        for spec in ({"agents": {"match": "recon", "agent": "recon"}},
                     {"agents": [{"match": "(", "agent": "recon"},
                                 {"match": "recon", "agent": "two words"},
                                 {"match": 5, "agent": "recon"}, "recon"]},
                     "{ not json"):
            self.manifest(spec)
            self.assertEqual(tm.route("recon it", "code", cwd=self.repo)["agent"],
                             "tezgah-standard", spec)


class Override(KeyCase):
    def status(self, *args, payload=None, cwd=None):
        proc = subprocess.run(
            [sys.executable, STATUS, "--json"] + list(args), cwd=cwd or self.repo,
            input=json.dumps(payload) if payload is not None else "",
            capture_output=True, text=True, timeout=120, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def echo_session(self, override):
        script = write_script(
            os.path.join(self.repo, "emit"), "import json, sys\n"
            "call = json.loads(sys.stdin.read() or '{}')\n"
            "json.dump({'segments': [{'key': 'k', 'state': 'on',\n"
            "                         'text': str(call['session_id'])}]}, sys.stdout)\n")
        self.manifest({"statusline": {"command": [script], "override": override}})

    def test_override_keeps_the_built_ins_and_adds_the_repo_chips(self):
        self.echo_session(True)
        self.assertTrue(te.override(self.repo))
        # the project's statusLine runs the renderer: the host payload names the
        # directory and the session the line is for
        segs = self.status(payload={"session_id": "s-7",
                                    "workspace": {"current_dir": self.repo}})
        keys = [s["key"] for s in segs]
        self.assertIn("adhd", keys)
        self.assertEqual([s["text"] for s in segs if s["key"] == "k"], ["s-7"])
        self.assertLess(keys.index("adhd"), keys.index("k"))

    def test_override_a_value_that_is_not_true_reads_no_payload(self):
        for value in ("yes", 1, None):
            self.echo_session(value)
            self.assertFalse(te.override(self.repo), value)
            segs = self.status(payload={"session_id": "s-7"})
            self.assertEqual([s["text"] for s in segs if s["key"] == "k"], ["None"],
                             value)

    def test_override_a_broken_payload_still_draws_the_line(self):
        self.echo_session(True)
        proc = subprocess.run([sys.executable, STATUS, "--json"], cwd=self.repo,
                              input="{ not json", capture_output=True, text=True,
                              timeout=120, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("adhd", [s["key"] for s in json.loads(proc.stdout)])


class EngagementRoot(KeyCase):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.home, "engagements")
        self.engagement = os.path.join(self.root, "pentest-001")
        self.manifest({"statusline": {"command": ["true"]}}, root=self.engagement)
        # deeper than the walk climbs, so only the engagement rule can find it
        self.deep = os.path.join(self.engagement,
                                 *["d%d" % i for i in range(te.MAX_WALK + 2)])
        os.makedirs(self.deep)

    def test_engagement_root_resolves_a_cwd_inside_that_engagement(self):
        self.assertEqual(te.manifest_path(self.deep), (None, None))
        os.environ[te.ENGAGEMENTS_ENV] = self.root
        root, found = te.manifest_path(self.deep)
        self.assertEqual(root, os.path.realpath(self.engagement))
        self.assertTrue(found.endswith(os.path.join("pentest-001", ".tezgah",
                                                    "extension.json")))

    def test_engagement_root_reads_nothing_outside_or_at_the_root(self):
        os.environ[te.ENGAGEMENTS_ENV] = self.root
        self.assertEqual(te.manifest_path(self.root), (None, None))
        self.assertEqual(te.manifest_path(self.repo), (None, None))
        # an engagement without a manifest of its own reads nothing either
        os.makedirs(os.path.join(self.root, "other", "x"))
        self.assertEqual(te.manifest_path(os.path.join(self.root, "other", "x")),
                         (None, None))

    def test_engagement_root_a_broken_root_costs_nothing(self):
        os.environ[te.ENGAGEMENTS_ENV] = os.path.join(self.home, "no-such-root")
        self.assertEqual(te.manifest_path(self.deep), (None, None))
        self.assertEqual(te.segments(self.deep), [])

    def test_engagement_root_manifest_flag_names_the_manifest_outright(self):
        script = write_script(
            os.path.join(self.engagement, "emit"),
            "import json, sys\njson.dump({'segments': [{'key': 'eng', "
            "'text': 'pentest-001'}]}, sys.stdout)\n")
        found = self.manifest({"statusline": {"command": [script]}},
                              root=self.engagement)
        proc = subprocess.run(
            [sys.executable, STATUS, "--json", "--manifest=" + found, self.repo],
            capture_output=True, text=True, timeout=120, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        segs = json.loads(proc.stdout)
        self.assertIn("adhd", [s["key"] for s in segs])
        self.assertEqual([s["text"] for s in segs if s["key"] == "eng"],
                         ["pentest-001"])
        # a named manifest that is no file costs the chips, never the line
        proc = subprocess.run(
            [sys.executable, STATUS, "--json", "--manifest=/no/such.json", self.repo],
            capture_output=True, text=True, timeout=120, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("eng", [s["key"] for s in json.loads(proc.stdout)])


if __name__ == "__main__":
    unittest.main()
