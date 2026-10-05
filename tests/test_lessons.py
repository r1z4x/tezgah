"""The lessons ledger as injected: rule-first lines, retirement, the tidy CLI.

A lesson is a rule sentence; a cut that keeps only the incident in front of it
shows the model what happened and not what to do. These tests pin the shown
text (the session block, the per-turn block and the digest read one helper),
the retirement of a line an enforcer already carries, the shrink stage the
budget runs before it drops the per-turn block, the `lesson` ledger row, and
the tidy CLI that proposes and never writes.
"""
import importlib
import json
import os
import re
import subprocess
import sys
import unittest

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402
import tezgah_gate  # noqa: E402
import tezgah_integrity  # noqa: E402
import tezgah_policy  # noqa: E402

CLI = os.path.join(support.REPO, "bin", "tezgah-lessons")
SEP = tc.LESSON_SEPARATOR
# a rule-first line whose separator sits late: its incident must not widen the cut
LATE = "Rotate the widget sprocket " + "w" * 230 + " - it jammed once " + "i" * 60
PIPED = "A piped check is not evidence - re-run it unpiped || enforced_by: piped"
RESEARCH = ("Keep one research line open at a time - init refuses a second "
            "|| enforced_by: tests.test_research.Unfinished")


class Child(TempHome):
    def write_lessons(self, repo, lines):
        path = os.path.join(repo, ".tezgah", "lessons.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path

    def child(self, body, extra=None):
        proc = subprocess.run(
            [sys.executable, "-c", "import json, sys\nsys.path.insert(0, %r)\n"
             "import tezgah_context as tc\n%s" % (support.HOOKS, body)],
            capture_output=True, text=True, env=self.env(extra=extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def call(self, fn, *args):
        return self.child("print(json.dumps(tc.%s(*%r)))\n" % (fn, list(args)))

    def switch(self, name):
        self.touch(os.path.join(self.home, ".config", "tezgah", name))

    def rows(self, session):
        return self.child("import tezgah_integrity as ti\n"
                          "p = ti._path(%r)\n"
                          "rows = [json.loads(r) for r in open(p)] "
                          "if __import__('os').path.exists(p) else []\n"
                          "print(json.dumps(rows))\n" % session)


class OneCut(Child):
    def test_no_shown_line_is_longer_than_the_plain_cut(self):
        repo = self.make_repo()
        recent = ["recent %s" % n for n in "abcd"] + [LATE + "!"]
        self.write_lessons(repo, [LATE] + recent)
        bound = len(tezgah_integrity.cut(LATE, tc.LESSON_CHARS))
        out = self.call("lessons", repo)
        block, keys = self.call("relevant_lessons", repo, "the widget sprocket", [])
        self.assertEqual(keys, [tc.lesson_key(LATE)])
        for text in (out, block):
            shown = [ln[2:] for ln in text.split("\n") if "widget" in ln]
            self.assertTrue(shown, text)
            for ln in shown:
                self.assertLessEqual(len(ln), bound + 1, ln)
        # the digest moves with the shown text, not with what lies past the cut
        # (same length, so the `...(+N chars)` marker is the same too)
        before = self.call("_lessons_state", repo)
        self.write_lessons(repo, [LATE] + recent[:-1] + [LATE + "?"])
        self.assertEqual(before, self.call("_lessons_state", repo))
        self.write_lessons(repo, [LATE] + recent[:-1] + ["x" + LATE])
        self.assertNotEqual(before, self.call("_lessons_state", repo))

    def test_the_separator_is_one_constant_quoted_by_every_copy(self):
        shape = "`<rule>%s<incident>`" % SEP
        with open(os.path.join(support.REPO, "skills", "tezgah-contract",
                               "SKILL.md"), encoding="utf-8") as fh:
            skill = fh.read()
        with open(os.path.join(support.REPO, "output-styles", "tezgah.md"),
                  encoding="utf-8") as fh:
            style = fh.read()
        with open(os.path.join(support.REPO, "bin", "tezgah-setup"),
                  encoding="utf-8") as fh:
            setup = fh.read()
        omp = re.search(r"OMP_LESSONS = \((.*?)\)\n", setup, re.S).group(1)
        omp = "".join(re.findall(r'"([^"]*)"', omp))
        for name, text in (("policy long", tezgah_policy.LESSONS),
                           ("policy short", tc.always_on_core()),
                           ("skill", skill), ("output style", style),
                           ("OMP_LESSONS", omp)):
            self.assertIn(shape, re.sub(r"\s+", " ", text), name)


class FormatAdvisory(Child):
    def test_a_line_without_its_rule_up_front_gets_the_advisory(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["Pin the pair" + SEP + "they drifted",
                                  "x" * 130 + SEP + "late separator",
                                  "no separator at all"])
        out = self.call("lessons", repo)
        self.assertIn("(2 of the lines above do not open with their rule; "
                      "run `tezgah-lessons` for rewrites)", out)

    def test_rule_first_lines_get_none(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["Pin the pair" + SEP + "they drifted"])
        self.assertNotIn("do not open with their rule", self.call("lessons", repo))


class Retirement(Child):
    def ledger(self, repo):
        self.write_lessons(repo, [PIPED, RESEARCH, "pipe the tail into a file, "
                                  "not the terminal", "keep the rule"])
        # the named test exists in this repository, so it enforces
        self.touch(os.path.join(repo, "tests", "test_research.py"))
        with open(os.path.join(repo, "tests", "test_research.py"), "w") as fh:
            fh.write("import unittest\n\n\nclass Unfinished(unittest.TestCase):\n"
                     "    pass\n")

    def test_enforced_lines_leave_every_reader(self):
        repo = self.make_repo()
        self.ledger(repo)
        out = self.call("lessons", repo)
        self.assertNotIn("piped check", out)
        self.assertNotIn("research line", out)
        self.assertIn("2 lessons enforced", out)
        self.assertEqual(len(self.call("_lesson_lines", repo)), 2)

    def test_lesson_three_comes_back_under_verify_off(self):
        repo = self.make_repo()
        self.ledger(repo)
        self.switch("verify-off")
        out = self.call("lessons", repo)
        self.assertIn("- A piped check is not evidence - re-run it unpiped\n", out)
        self.assertNotIn("enforced_by", out)
        self.assertNotIn("research line", out)
        self.assertIn("1 lesson enforced", out)

    def test_each_rule_switch_brings_its_lesson_back(self):
        repo = self.make_repo()
        for slug, switch in sorted(tezgah_gate.DENY_RULES.items()):
            for name in [switch, "pretooluse-off"] if switch else ["pretooluse-off"]:
                with self.subTest(slug=slug, switch=name):
                    self.write_lessons(repo, ["rule of %s || enforced_by: %s"
                                              % (slug, slug), "keep"])
                    path = os.path.join(self.home, ".config", "tezgah", name)
                    self.assertNotIn("rule of", self.call("lessons", repo))
                    self.switch(name)
                    try:
                        self.assertIn("- rule of %s\n" % slug,
                                      self.call("lessons", repo))
                    finally:
                        os.remove(path)

    def test_an_unknown_enforcer_keeps_the_line(self):
        repo = self.make_repo()
        self.ledger(repo)
        for value in ("nosuchrule", "tests.test_research.NoSuchClass",
                      "tests.test_nosuchmodule.Unfinished"):
            with self.subTest(value=value):
                self.write_lessons(repo, ["a rule || enforced_by: " + value])
                self.assertIn("- a rule\n", self.call("lessons", repo))


def known(value):
    """Whether `value` names a gate deny rule or an importable test.

    A test is named from the repository root (`tests.test_x.Class`) and imported
    from this directory: another `tests` package on the path shadows the
    namespace one, so the dotted import alone could not tell."""
    if value in tezgah_gate.DENY_RULES:
        return True
    module, _, name = value.rpartition(".")
    if not module.startswith("tests.test_"):
        return False
    try:
        return hasattr(importlib.import_module(module[len("tests."):]), name)
    except ImportError:
        return False


class EnforcerNames(unittest.TestCase):
    def test_every_deny_slug_is_in_the_tuple(self):
        with open(tezgah_gate.__file__, encoding="utf-8") as fh:
            src = fh.read()
        literal = set(re.findall(r'_deny\(\s*session_id,\s*"([a-z_-]+)"', src))
        self.assertTrue(literal)
        self.assertEqual(literal, set(tezgah_gate.DENY_RULES))
        self.assertNotIn("_deny(session_id, rule", src.replace("def _deny", ""))

    def test_every_enforced_by_value_names_a_slug_or_a_test(self):
        self.assertTrue(known("piped"))
        self.assertTrue(known("tests.test_research.Unfinished"))
        self.assertFalse(known("nosuchrule"))
        self.assertFalse(known("tests.test_research.NoSuchClass"))
        self.assertFalse(known("os.path"))
        for value in (tc.ENFORCED.search(PIPED).group(1),
                      tc.ENFORCED.search(RESEARCH).group(1)):
            self.assertTrue(known(value), value)
        for _needle, value in _cli().RETIRE:
            self.assertTrue(known(value), value)


class LessonsOnlyCap(Child):
    def test_a_common_word_ranks_no_lesson(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["the rule number %d about the thing" % i
                                  for i in range(12)])
        self.assertEqual(self.call("relevant_lessons", repo,
                                   "update the changelog", []), ["", []])


class ShrinkBeforeDrop(Child):
    OLD = ["pipe the suite output to a file %s" % n for n in "abc"]
    RECENT = ["recent lesson %s" % n for n in "vwxyz"]

    def prompt(self, repo, session, limit=None):
        patch = ("tc.CONTEXT_BUDGET['user_prompt'] = %d\n" % limit
                 if limit else "")
        return self.child(patch + "print(json.dumps(tc.context_for('user_prompt', "
                          "%r, {'session_id': %r, 'prompt': 'pipe the suite "
                          "output'})))\n" % (repo, session))

    def test_the_turn_block_shrinks_and_only_its_survivor_is_seen(self):
        repo = self.make_repo()
        self.write_lessons(repo, self.OLD + self.RECENT)
        whole = self.prompt(repo, "w")
        for line in self.OLD:
            self.assertIn(line, whole)
        out = self.prompt(repo, "s1", len(whole.encode()) - 1)
        shown = [line for line in self.OLD if line in out]
        self.assertEqual(len(shown), 1, out)
        self.assertIn("shortened lessons_turn", out)
        log = os.path.join(self.home, ".cache", "tezgah", "context-drops.log")
        with open(log) as fh:
            self.assertIn(" kind=truncated ", fh.read().splitlines()[-1])
        # the two that were cut were never shown: a later turn may carry them
        again = self.prompt(repo, "s1")
        self.assertNotIn(shown[0], again)
        self.assertEqual(sum(line in again for line in self.OLD), 2)
        rows = [r for r in self.rows("s1") if r["kind"] == "lesson"]
        self.assertEqual([r["block"] for r in rows], ["turn"] * 3)
        self.assertEqual(rows[0]["key"], tc.lesson_key(shown[0]))


class LessonRow(Child):
    def test_each_injected_lesson_leaves_a_row(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["first rule", "second rule"])
        self.child("print(json.dumps(tc.context_for('session_start', %r, "
                   "{'session_id': 'r1'})))\n" % repo)
        rows = [r for r in self.rows("r1") if r["kind"] == "lesson"]
        self.assertEqual([(r["key"], r["block"]) for r in rows],
                         [(tc.lesson_key("first rule"), "session"),
                          (tc.lesson_key("second rule"), "session")])
        self.assertTrue(all(re.fullmatch("[0-9a-f]{8}", r["key"]) for r in rows))

    def test_the_row_is_not_gate_evidence(self):
        self.assertIn(b"lesson", tc.NOT_TOOL_HOOK)
        self.assertTrue({"key", "block"} <= tezgah_integrity.LEDGER_FIELDS)


def _cli():
    """bin/tezgah-lessons as a module (it has no .py name of its own)."""
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_loader
    spec = spec_from_loader("tezgah_lessons_cli", SourceFileLoader(
        "tezgah_lessons_cli", CLI))
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TidyCli(Child):
    LINES = [
        "Two agents must not share one git branch: a worktree cannot hold it twice",
        "A read-only subagent cannot write files at all: brief it to return text",
        "A read-only scout has no shell either, not just no write: give command "
        "work to a shell-capable agent",
        "A piped check is not evidence: a run piped into tail records as ran",
        "Subagents in a git worktree edited the main checkout through relative "
        "paths; give every worktree subagent absolute paths",
        "Two subagents in a separate git worktree wrote into the main checkout "
        "through a relative path; give absolute worktree paths",
        "Pin the pair with a test" + SEP + "a write path and a checker drifted",
    ]

    def run_cli(self, *args):
        return subprocess.run([sys.executable, CLI] + list(args),
                              capture_output=True, text=True, env=self.env())

    def test_it_proposes_and_never_writes(self):
        repo = self.make_repo()
        path = self.write_lessons(repo, self.LINES)
        with open(path, "rb") as fh:
            before = fh.read()
        stamp = os.stat(path).st_mtime_ns
        proc = self.run_cli("--root", repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        # a rule-first rewrite for a line whose separator is missing...
        self.assertIn("rewrite 1:", out)
        self.assertIn("Two agents must not share one git branch - a worktree", out)
        # ...none for the line that already opens with its rule
        self.assertNotIn("rewrite 7:", out)
        # the two worktree lines are one lesson
        self.assertIn("merge 5, 6", out)
        self.assertIn("retire 4: append `|| enforced_by: piped`", out)
        with open(path, "rb") as fh:
            self.assertEqual(before, fh.read())
        self.assertEqual(stamp, os.stat(path).st_mtime_ns)

    def test_the_fixture_gate_remaps_the_ground_truth(self):
        repo = self.make_repo()
        self.write_lessons(repo, self.LINES)
        fixture = os.path.join(self.home, "fx.json")
        with open(fixture, "w") as fh:
            json.dump({"lessons_prompts": [
                {"q": "subagent worktree relative path", "gt": [6]},
                {"q": "pin the checker pair", "gt": [7]}]}, fh)
        proc = self.run_cli("--root", repo, "--fixture", fixture)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout, r"recall@5 1\.000 before, 1\.000 after "
                                      r"the merges: holds")

    def test_a_merge_proposal_is_derived_not_hand_listed(self):
        mod = _cli()
        self.assertEqual(mod.clusters(self.LINES), [[4, 5]])


if __name__ == "__main__":
    unittest.main()
