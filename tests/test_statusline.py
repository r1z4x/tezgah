"""statusline.py: the pony/exec/adhd/consult/research/graph/orch/judge segment.

Rendered for Claude Code and for Cursor, whose own tool-call store feeds the
`used` marks instead of a transcript."""
import json
import os
import sys
import unittest

import support
from support import TempHome, run

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_context as tc  # noqa: E402
import tezgah_paths as tp  # noqa: E402

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

    def test_a_disarmed_gate_heads_the_line_only_when_marked(self):
        # Audit Phase 1.3: the prompt hook leaves this mark when the transcript
        # shows gated tool calls and the ledger no tool-hook row (see
        # test_context.GateLiveness); the Claude line shows it, and only then.
        payload = {"cwd": self.repo, "session_id": "s"}
        before = run([support.STATUSLINE], payload, env=self.envv).stdout
        self.assertNotIn("gate", before)
        self.touch(os.path.join(self.home, ".cache", "tezgah", "gate-inactive", "s"))
        after = run([support.STATUSLINE], payload, env=self.envv).stdout
        self.assertIn("gate\u2717", after)

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

    def test_a_non_utf8_plan_still_draws_the_line(self):
        path = os.path.join(self.repo, ".tezgah", "plans", "open", "001-bad.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"---\nid: 001\n---\n\xff\n")
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("plans 1", proc.stdout)

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
        self.assertIn("\033[33m\u2702 pony\u25cb\033[0m", proc.stdout)      # armed
        self.assertIn("\033[32m\u25b6 exec\u2713\033[0m", proc.stdout)      # always-on
        self.assertIn("\033[33m\u2696 consult\u25cb\033[0m", proc.stdout)   # on demand
        self.assertIn("\033[31m\u2697 research\u2717\033[0m", proc.stdout)  # off
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

    def test_after_a_double_dash_a_flag_shaped_session_id_is_an_id(self):
        # Audit L-7 (SEC-07): the dsh route and the MCP tool hand caller-chosen
        # strings to this argv, and `--failure-shapes` there ran the machine-wide
        # report. After `--` it is the session id and the line is the answer.
        out, proc = support.run_json(
            [self.cli, "--json", "--", self.repo, "--failure-shapes"],
            env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsInstance(out, list)
        self.assertIn("judge", [s["key"] for s in out])

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
            # matches (`RELEASE`, hooks/tezgah_context.py:1416): an `Unreleased`
            # section is a heading this file keeps at the top, and taking it for
            # the version pins the expected prefix to a string no status line
            # ever prints.
            if line.startswith("## [") and line[4:5].isdigit():
                return line[4:line.index("]")]
    return "unknown"


# The line's first chip: the product's own name and version, its own group, so
# the marks separate from it with the separator they already use.
PREFIX = "tezgah v%s  \u00b7  " % changelog_version()


class SkillRecording(TempHome):
    """Which skill a read opened, and the report over the recorded sessions.

    `SKILL_MARKS` is the two skills the always-on core tells a session to read -
    a mark whose skill the core never names can never flip, so the table cannot
    be widened to the shipped list - and every other shipped skill records
    `skill:<name>` instead, a kind no mark reads. The report is a measurement,
    not a gate: the skill nobody opened is invisible from reading the skill, and
    this is the one reader that names it."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.cache = os.path.join(self.home, ".cache", "tezgah")
        # cache_dir() reads tezgah_paths.CACHE at call time, which is the one
        # place a test repoints so the real store is never read or written
        self.addCleanup(setattr, tp, "CACHE", tp.CACHE)
        tp.CACHE = self.cache
        self.envv = self.env()
        self.cli = os.path.join(support.REPO, "bin", "tezgah-status")

    def session(self, name, kinds, mtime=None):
        """One recorded session file: the store's own row, `{"kind": kind}`."""
        d = os.path.join(self.cache, "sessions")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name + ".jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for kind in kinds:
                fh.write(json.dumps({"kind": kind}) + "\n")
        if mtime is not None:
            # the window is files by mtime, so a test that picks the newest has
            # to set it rather than hope two writes land in different clock ticks
            os.utime(path, (mtime, mtime))
        return path

    def opened(self, *sessions):
        """The rows the CLI prints for the sessions given, `--skill-fitness`."""
        for name, kinds in sessions:
            self.session(name, kinds)
        proc = run([self.cli, "--skill-fitness"], env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_a_read_of_a_shipped_skill_records_its_name(self):
        # the mark table keeps its two entries; every other shipped skill reaches
        # the store under `skill:<name>` so the report can see it at all
        skill = os.path.join(support.REPO, "skills", "harness", "SKILL.md")
        kind = tc.skill_read_kind("read", {"file_path": skill})
        self.assertEqual(kind, "skill:harness")
        tc.record("s", kind)
        self.assertEqual(tc.used("s"), {"skill:harness"})
        # omp's read tool takes the internal URL, the same SKILL.md
        self.assertEqual(tc.skill_read_kind("read", {"path": "skill://harness"}),
                         "skill:harness")

    def test_the_two_marked_skills_keep_their_marks(self):
        # the status line's own input: a change here would move a pinned mark
        for path, mark in (("skills/ponytail/SKILL.md", "pony"),
                           ("skill://i-have-adhd", "adhd"),
                           ("skill://i-have-adhd/SKILL.md", "adhd"),
                           ("skill://not-a-shipped-skill", None),
                           ("skills/not-a-shipped-skill/SKILL.md", None)):
            self.assertEqual(tc.skill_read_kind("read", {"file_path": path}), mark,
                             path)

    def test_a_new_kind_lights_no_mark(self):
        # the line is unchanged by a `skill:` kind, and the control below proves
        # the assertion can fail: `graph` is a kind the line does read, and the
        # one measure no machine can turn off (consult, research and judge all
        # need an option the host may not have, so a control using one of those
        # passed locally and failed on a bare runner)
        line = lambda: tc.render_line(tc.health_segments(  # noqa: E731
            self.repo, "s", observable=tc.TOOL_USE_MEASURES))
        before = line()
        tc.record("s", "skill:harness")
        self.assertEqual(line(), before)
        tc.record("s", "graph")
        self.assertNotEqual(line(), before)

    def test_the_report_counts_the_sessions_that_opened_a_skill(self):
        self.session("a", ["skill:harness", "skill:harness"])
        self.session("b", ["pony"])
        self.session("c", ["consult"])
        fit = tc.skill_fitness()
        # a session counts once however many times it recorded the kind, and a
        # marked skill counts under its own name - the reads recorded before
        # `skill:` existed are not lost
        self.assertEqual(fit["skills"],
                         [{"name": "harness", "mark": None, "sessions": 1},
                          {"name": "ponytail", "mark": "pony", "sessions": 1}])
        # every shipped skill is in exactly one of the two lists
        self.assertEqual(set(fit["never"]) | {s["name"] for s in fit["skills"]},
                         set(tc.shipped_skills()))
        self.assertNotIn("harness", fit["never"])
        self.assertNotIn("ponytail", fit["never"])
        self.assertIn("tezgah-contract", fit["never"])
        self.assertTrue(fit["never"], "a fresh store opened nothing, so every "
                                      "skill it never opened has to be named")

    def test_the_window_is_the_newest_sessions_and_says_so(self):
        self.session("old", ["skill:harness"], mtime=1000)
        self.session("mid", ["pony"], mtime=2000)
        self.session("new", ["consult"], mtime=3000)
        fit = tc.skill_fitness(window=2)
        self.assertEqual((fit["sessions"], fit["recorded"]), (2, 3))
        self.assertEqual([s["name"] for s in fit["skills"]], ["ponytail"])
        self.assertIn("harness", fit["never"])

    def test_the_cli_prints_the_report_and_its_json(self):
        for name, kinds in (("a", ["skill:harness"]), ("b", ["pony"])):
            self.session(name, kinds)
        out = self.opened()
        self.assertIn("sessions read: 2 of 2 recorded", out)
        self.assertIn("harness", out)
        self.assertIn("never opened:", out)
        parsed, proc = support.run_json([self.cli, "--skill-fitness", "--json"],
                                        env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(parsed["skills"],
                         [{"name": "harness", "mark": None, "sessions": 1},
                          {"name": "ponytail", "mark": "pony", "sessions": 1}])

    def test_all_is_a_misuse_wherever_it_is_written_without_counters(self):
        # `--all` is a modifier of the counters fold, so it means the same thing in
        # every other position: the same misuse the bare flag is. A report branch
        # used to swallow it and answer a different question with exit 0, which
        # read as a success for a flag the user never got.
        for extra in (("--all",), ("--skill-fitness", "--all"),
                      ("--failure-shapes", "--all"), ("--all", "--json"),
                      ("--skill-fitness", "--trend"),
                      ("--skill-fitness", "--weeks=3")):
            proc = run([self.cli] + list(extra), env=self.envv)
            self.assertEqual(proc.returncode, 2, extra)
            self.assertIn("only means something with --counters", proc.stderr)
        # and the report itself is untouched by the check
        proc = run([self.cli, "--skill-fitness"], env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("sessions read:", proc.stdout)

    def test_the_session_store_keeps_the_kind_a_host_writes(self):
        # end to end through the CLI the report reads: what `record` wrote is
        # what the report names, with no second reader of the store
        tc.record("s1", "skill:design-contract")
        rows = tc.skill_fitness()
        self.assertEqual([s["name"] for s in rows["skills"]], ["design-contract"])


if __name__ == "__main__":
    unittest.main()
