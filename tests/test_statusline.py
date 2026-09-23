"""statusline.py: the pony/exec/adhd/consult/research/graph/orch/judge segment.

Rendered for Claude Code and for Cursor, whose own tool-call store feeds the
`used` marks instead of a transcript."""
import json
import os
import sys
import unittest

import support
from support import TempHome, run

SEGMENT = ("pony\u25cb exec\u2713 adhd\u25cb  \u00b7  consult\u25cb research\u2717 graph\u25cb"
           " orch\u25cb judge\u25cb  \u00b7  idx\u2013")
NO_ROOT = ("pony\u25cb exec\u2713 adhd\u25cb  \u00b7  consult\u25cb research\u2717 graph\u25cb"
           " orch\u25cb judge\u25cb")
# Cursor reads the store, which sees tool calls and no skill read, so those two
# marks state nothing there instead of claiming the skill is unused.
CURSOR_SEGMENT = ("pony exec\u2713 adhd  \u00b7  consult\u25cb research\u2717 graph\u25cb"
                  " orch\u25cb judge\u25cb  \u00b7  idx\u2013")


class Statusline(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))
        # the judgement seam's own credential channel, so its mark is armed in
        # the pinned lines; the missing-credential state is JudgeMark's case
        with open(self.key_path(), "w") as fh:
            fh.write("test-key\n")
        self.envv = self.env()
        self.envv["NO_COLOR"] = "1"  # the plain-form assertions below

    def key_path(self):
        path = os.path.join(self.home, ".config", "typesafe", "key")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def test_claude_mode_segment(self):
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), PREFIX + SEGMENT)

    def test_cursor_mode_segment(self):
        proc = run([support.STATUSLINE, "--cursor"],
                   {"cwd": self.repo, "session_id": "s"}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), PREFIX + CURSOR_SEGMENT)

    def test_no_consult_key_flips_consult(self):
        os.remove(os.path.join(self.home, ".config", "openrouter", "key"))
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("consult\u2717", proc.stdout)

    def test_outside_roots_still_shows_segment(self):
        # Global indicator: cwd outside every root still prints the checklist
        # (no repo marks, idx or plan count, but not a blank line).
        proc = run([support.STATUSLINE], {"cwd": self.home}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), PREFIX + NO_ROOT)

    def orx_env(self):
        """The plain environment plus an `orx` on the PATH lookup: without it the
        research mark is `off` (no tool installed) and can never light, which is
        not what these tests are about."""
        return self.env(extra={"TEZGAH_ORX_BIN": sys.executable})

    def test_a_real_orx_run_lights_the_research_mark(self):
        # Claude's half derives its used kinds from the transcript. The token it
        # reads has to be the command the shell actually ran, or the mark never
        # lights at all (the defect this pins: `research` had no reader).
        tp = os.path.join(self.home, "transcript.jsonl")
        with open(tp, "w") as fh:
            fh.write(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "orx experiment run --tree t"}}]}}) + "\n")
        proc = run([support.STATUSLINE],
                   {"cwd": self.repo, "session_id": "s", "transcript_path": tp},
                   env=self.orx_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("research\u2713", proc.stdout)

    def test_a_tezgah_research_run_lights_the_research_mark(self):
        # The layer's own CLI, not only the tool its rule routes to: `check` reads
        # the line's own artifacts, and a run of it has to be classified the way a
        # run of `orx` is.
        tp = os.path.join(self.home, "transcript.jsonl")
        with open(tp, "w") as fh:
            fh.write(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "tezgah-research check"}}]}}) + "\n")
        proc = run([support.STATUSLINE],
                   {"cwd": self.repo, "session_id": "s", "transcript_path": tp},
                   env=self.orx_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("research\u2713", proc.stdout)

    def test_mentioning_the_tool_in_an_argument_marks_nothing(self):
        # The other half of that defect: a mention used to be enough, which made
        # the line report a run that never happened. The layer's own CLI is the
        # case most likely to be mentioned without being run - this repository's
        # own docs name it on nearly every page - so the tokenizer has to reject
        # it there too.
        for command in ("echo 'orx and consult are CLIs'",
                        "grep -rn tezgah-research docs/"):
            tp = os.path.join(self.home, "transcript.jsonl")
            with open(tp, "w") as fh:
                fh.write(json.dumps({"message": {"content": [
                    {"type": "tool_use", "name": "Bash",
                     "input": {"command": command}}]}}) + "\n")
            proc = run([support.STATUSLINE],
                       {"cwd": self.repo, "session_id": "s",
                        "transcript_path": tp},
                       env=self.orx_env())
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("research\u25cb", proc.stdout)
            self.assertIn("consult\u25cb", proc.stdout)

    def test_colors_by_state(self):
        env = dict(self.envv)
        env.pop("NO_COLOR")
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("\033[33mpony\u25cb\033[0m", proc.stdout)      # armed
        self.assertIn("\033[32mexec\u2713\033[0m", proc.stdout)      # always-on
        self.assertIn("\033[33mconsult\u25cb\033[0m", proc.stdout)   # on demand
        self.assertIn("\033[31mresearch\u2717\033[0m", proc.stdout)  # off
        self.assertIn("\033[2m  \u00b7  \033[0m", proc.stdout)       # dim separator

    def test_status_color_env_off_strips_ansi(self):
        env = dict(self.envv)
        env.pop("NO_COLOR")
        env["TEZGAH_STATUS_COLOR"] = "0"
        self.assertNotIn("\033[", run([support.STATUSLINE],
                                      {"cwd": self.repo}, env=env).stdout)


class JudgeMark(TempHome):
    """J3: the `judge` mark, decided from the seam's switch and a real used-kind.

    The four states are the spec's acceptance. The last case is the precedence
    `off` over `info`: a surface that cannot write the used-kinds store would
    otherwise claim `ready` forever for a seam the kill switch disarmed, which
    `docs/status-line.md` calls a bug in the layer and not a cosmetic one."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.cli = os.path.join(support.REPO, "bin", "tezgah-status")
        self.envv = dict(self.env(), NO_COLOR="1")

    def key_file(self):
        """The credential channel that survives a non-interactive shell - the
        file, not the export - as a dummy: no case here reaches TypeSafe."""
        path = os.path.join(self.home, ".config", "typesafe", "key")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("test-key\n")

    def judge(self, *extra):
        out, proc = support.run_json([self.cli, self.repo, "s", "--json", *extra],
                                     env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return next(s for s in out if s["key"] == "judge")

    def test_off_with_no_credential_and_no_use(self):
        mark = self.judge()
        self.assertEqual((mark["state"], mark["glyph"], mark["group"]),
                         ("off", "\u2717", 1))

    def test_ready_with_a_credential_and_no_use(self):
        self.key_file()
        mark = self.judge()
        self.assertEqual((mark["state"], mark["glyph"]), ("ready", "\u25cb"))

    def test_on_after_a_use_the_store_carries(self):
        # the used-kinds store is what every host but Claude reads, so the mark
        # lights from the same record a host writes, never from a guess
        self.key_file()
        support.run_json([support.PROBE_CONTEXT],
                         {"fn": "record", "session_id": "s", "kind": "judge"},
                         env=self.envv)
        self.assertEqual(self.judge()["state"], "on")

    def test_off_under_the_kill_switch(self):
        self.key_file()
        self.touch(os.path.join(self.home, ".config", "tezgah", "judge-off"))
        self.assertEqual(self.judge()["state"], "off")

    def test_info_where_this_surface_cannot_see_the_measure(self):
        self.key_file()
        mark = self.judge("--observable=consult,research,graph,orch")
        self.assertEqual((mark["state"], mark["glyph"]), ("info", ""))

    def test_the_switch_beats_the_observable_carve_out(self):
        self.key_file()
        self.touch(os.path.join(self.home, ".config", "tezgah", "judge-off"))
        self.assertEqual(
            self.judge("--observable=consult,research,graph,orch")["state"], "off")

    def transcript_chip(self, command):
        """The judge chip on Claude's line for one shell call.

        Claude's channel is the transcript, and the token it reads comes from the
        shared tokenizer (`shell_kind`): the program the shell really ran, never
        a substring of the command.
        """
        tp = os.path.join(self.home, "transcript.jsonl")
        with open(tp, "w") as fh:
            fh.write(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": command}}]}}) + "\n")
        proc = run([support.STATUSLINE],
                   {"cwd": self.repo, "session_id": "s", "transcript_path": tp},
                   env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return next(t for t in proc.stdout.split() if t.startswith("judge"))

    def test_a_real_triage_run_lights_the_mark(self):
        self.key_file()
        self.assertEqual(self.transcript_chip("bin/tezgah-triage --select s.txt"),
                         "judge\u2713")

    def test_naming_the_caller_is_not_running_it(self):
        self.key_file()
        self.assertEqual(self.transcript_chip("grep -n tezgah-triage docs/"),
                         "judge\u25cb")


def changelog_version():
    """The newest release heading in CHANGELOG.md - the source the line's prefix
    reads its number from. The three pinned lines above stay the marks and this
    prefixes them, rather than folding the number into each: `docs/testing.md`
    cites those constants by line, so a release would otherwise move them."""
    with open(os.path.join(support.REPO, "CHANGELOG.md"), encoding="utf-8") as fh:
        for line in fh:
            # A version-shaped heading only, the way the product's own reader
            # matches (`RELEASE`, hooks/tezgah_context.py:1411): an `Unreleased`
            # section is a heading this file keeps at the top, and taking it for
            # the version pins the expected prefix to a string no status line
            # ever prints.
            if line.startswith("## [") and line[4:5].isdigit():
                return line[4:line.index("]")]
    return "unknown"


# The line's first chip: the product's own name and version, its own group, so
# the marks separate from it with the separator they already use.
PREFIX = "tezgah v%s  \u00b7  " % changelog_version()


if __name__ == "__main__":
    unittest.main()
