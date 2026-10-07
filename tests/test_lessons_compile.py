"""The lesson ledger's one reader (plan 061 Phase A).

Every surface that reads `.tezgah/lessons.md` - the session block, the per-turn
block, the per-turn digest, the gate and the tidy CLI - reads it through
`hooks/tezgah_lessons.py`, and the gate never imports `tezgah_context` to do so.
"""
import json
import os
import subprocess
import sys
import unittest

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402
import tezgah_lessons  # noqa: E402


class Reader(TempHome):
    def write_lessons(self, repo, lines):
        path = tezgah_lessons.ledger(repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def child(self, body):
        proc = subprocess.run(
            [sys.executable, "-c", "import json, sys\nsys.path.insert(0, %r)\n%s"
             % (support.HOOKS, body)],
            capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)


class OneModule(Reader):
    def test_context_has_no_reader_of_its_own(self):
        for name in ("_lesson_lines", "ENFORCED", "_enforced", "_test_names"):
            self.assertFalse(hasattr(tc, name), name)
        self.assertIs(tc.lesson_lines, tezgah_lessons.lines)
        self.assertIs(tc.lesson_key, tezgah_lessons.lesson_key)

    def test_the_gate_reads_through_it_without_the_context(self):
        self.assertEqual(self.child(
            "import tezgah_gate\nprint(json.dumps(['tezgah_context' in sys.modules, "
            "tezgah_gate.tezgah_lessons is sys.modules['tezgah_lessons']]))"),
            [False, True])

    def test_the_cli_reads_through_it(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["- first rule - once", "# heading", "",
                                  "1. second rule - twice"])
        proc = subprocess.run(
            [sys.executable, os.path.join(support.REPO, "bin", "tezgah-lessons"),
             "--root", repo], capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.child(
            "import tezgah_lessons\nprint(json.dumps(tezgah_lessons.lines(%r)))"
            % repo), ["first rule - once", "second rule - twice"])


PLAIN = "Never stash with nothing to stash - a pop took another session's stash"
CHECK = " || check: argv(git stash push)"
STAMP = " @0123abc hooks/tezgah_gate.py"
VARIANTS = {"suffix": PLAIN + CHECK, "stamp": PLAIN + STAMP,
            "both": PLAIN + STAMP + CHECK + " || enforced_by: nosuchrule"}


class SuffixAndStamp(Reader):
    """A `|| check: ...` suffix and an `@sha path` stamp are the line's metadata,
    never its text: they enter no key, no digest, no cut and no ranking."""

    def state(self, repo, ledger, *calls):
        self.write_lessons(repo, ledger)
        return self.child("import tezgah_context as tc\nprint(json.dumps([%s]))"
                          % ", ".join(calls))

    def test_the_key_of_a_suffixed_line_is_the_plain_key(self):
        repo = self.make_repo()
        for name, line in VARIANTS.items():
            with self.subTest(name):
                got, = self.state(repo, [line], "tc.lesson_lines(%r)" % repo)
                self.assertEqual(got, [PLAIN])
                self.assertEqual(tezgah_lessons.lesson_key(got[0]),
                                 tezgah_lessons.lesson_key(PLAIN))

    def test_the_digest_and_the_cut_do_not_move(self):
        repo = self.make_repo()
        long = PLAIN + " " + "x" * (tc.LESSON_CHARS - len(PLAIN) - 1)
        calls = ("tc._lessons_state(%r)" % repo, "tc.lessons(%r)" % repo)
        base = self.state(repo, ["first rule - once", long], *calls)
        self.assertNotIn("…", base[1])
        for name, tail in (("suffix", CHECK), ("stamp", STAMP),
                           ("both", STAMP + CHECK)):
            with self.subTest(name):
                self.assertEqual(self.state(repo, ["first rule - once", long + tail],
                                            *calls), base)

    def test_a_word_only_in_the_suffix_ranks_nothing(self):
        repo = self.make_repo()
        recent = ["recent rule %d - shown in the session block" % i
                  for i in range(tc.LESSON_LINES)]
        call = "tc.relevant_lessons(%r, %%r, [])" % repo
        got = self.state(repo, [PLAIN + " @0123abc okapi.py"
                                + " || check: argv(zebra quagga)"] + recent,
                         call % "zebra quagga okapi", call % "stash nothing")
        self.assertEqual(got[0], ["", []])
        self.assertEqual(got[1][1], [tezgah_lessons.lesson_key(PLAIN)])
        self.assertNotIn("check:", got[1][0])

    def test_enforced_by_still_retires_after_a_check(self):
        repo = self.make_repo()
        self.write_lessons(repo, [PLAIN + CHECK + " || enforced_by: piped", "keep"])
        self.assertEqual(self.child(
            "import tezgah_lessons as tl\nr = []\n"
            "print(json.dumps([tl.lines(%r, r), len(r)]))" % repo), [["keep"], 1])

    def test_a_double_pipe_in_the_prose_is_text(self):
        repo = self.make_repo()
        line = "Never run `pytest || true` - it hides the failure"
        self.write_lessons(repo, [line, "a rule @notahexsha path"])
        self.assertEqual(tezgah_lessons.lines(repo),
                         [line, "a rule @notahexsha path"])

    def test_only_a_path_after_the_sha_and_a_clause_outside_code_is_cut(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["the fix landed at @deadbeef hooks/x.py",
                                  "run git show @cafebabe1 HEAD",
                                  "keep `a||check:b` intact",
                                  "keep `a||check:b` intact || check: argv(x)"])
        self.assertEqual(tezgah_lessons.lines(repo),
                         ["the fix landed at", "run git show @cafebabe1 HEAD",
                          "keep `a||check:b` intact", "keep `a||check:b` intact"])


if __name__ == "__main__":
    unittest.main()
