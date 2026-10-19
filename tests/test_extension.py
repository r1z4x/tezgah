"""tezgah_extension: a repository's own statusline chips, on tezgah's line.

An extension is a manifest under `<repo>/.tezgah/extension.json` naming a command
that prints structured segments. These tests pin the manifest walk, the merge
into `health_segments()` (the extension's group lands one past the built-ins),
and the failure contract: a missing manifest, a bad manifest, an absent command,
a non-zero exit, a timeout, malformed JSON, a wrong shape and an over-budget list
each cost the extension its chips and never the line.
"""
import json
import os
import stat
import sys
import unittest

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402
import tezgah_extension as te  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
