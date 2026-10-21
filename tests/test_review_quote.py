"""bin/tezgah-review-quote: findings placed on a diff by their quoted code."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from support import REPO

TOOL = os.path.join(REPO, "bin", "tezgah-review-quote")

A_OLD = ["header_line", "", "second_line"] + [f"filler_{i}" for i in range(4, 10)] + [
    "value = 1", "keep_11", "removed_call()"] + [f"tail_{i}" for i in range(13, 21)]
A_NEW = [x for x in A_OLD if x != "removed_call()"]
A_NEW[A_NEW.index("value = 1")] = "value = 2"

# git's own config must not reach the fixture repository (tests/test_task.py)
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")


class ReviewQuoteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.repo = cls._tmp.name

        def git(*args):
            subprocess.run(["git", "-C", cls.repo, "-c", "user.name=t",
                            "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                           check=True, capture_output=True, env=GIT_ENV)

        def write(name, lines):
            os.makedirs(os.path.dirname(os.path.join(cls.repo, name)), exist_ok=True)
            with open(os.path.join(cls.repo, name), "w") as f:
                f.write("\n".join(lines) + "\n")

        git("init", "-q")
        # a prefix-free diff (and a top-level `a/`) must not shift the paths
        git("config", "diff.noprefix", "true")
        write("a.py", A_OLD)
        write("a/x.py", ["x_old_line"])
        for name in ("b.py", "c.py", "d.py", "e.py"):
            write(name, [f"# {name}"])
        write("f.py", ["# f.py", "  ws_call()"])
        git("add", "-A")
        git("commit", "-qm", "one")
        write("a.py", A_NEW)
        write("b.py", ["# b.py", "def unique_b():", "    return 'b'"])
        write("c.py", ["# c.py", "shared_boilerplate()"])
        write("d.py", ["# d.py", "shared_boilerplate()"])
        write("a/x.py", ["x_new_line"])
        write("e.py", ["# e.py", "dup_call()", "middle", "dup_call()"])
        # a whitespace-only change: the same normalised line on both sides
        write("f.py", ["# f.py", "    ws_call()"])
        git("commit", "-qam", "two")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_tool(self, *args, stdin=None):
        return subprocess.run([sys.executable, TOOL, "--repo", self.repo, *args],
                              input=stdin, capture_output=True, text=True, env=GIT_ENV)

    def place(self, path, quote, **cited):
        r = self.run_tool("--from", "HEAD~1", "-", stdin=json.dumps(
            [dict(cited, path=path, quote=quote, id=7)]))
        self.assertEqual(r.returncode, 0, r.stderr)
        [out] = json.loads(r.stdout)
        self.assertEqual(out["id"], 7)
        return out

    def test_new_side_with_plus_marker(self):
        out = self.place("a.py", "+value = 2")
        self.assertEqual((out["status"], out["start_line"], out["end_line"]),
                         ("located", 10, 10))
        self.assertNotIn("side", out)

    def test_old_side_deleted_line(self):
        out = self.place("a.py", "-removed_call()")
        self.assertEqual((out["status"], out["start_line"], out.get("side")),
                         ("located", 12, "old"))

    def test_full_file_outside_hunk_skips_blank_lines(self):
        out = self.place("a.py", "header_line\n\n\nsecond_line")
        self.assertEqual((out["status"], out["start_line"], out["end_line"]),
                         ("located", 1, 3))

    def test_indentation_and_blank_quote_lines_ignored(self):
        out = self.place("b.py", "\n  def unique_b():\n\n        return 'b'   \n")
        self.assertEqual((out["status"], out["path"], out["start_line"], out["end_line"]),
                         ("located", "b.py", 2, 3))

    def test_relocated_on_unique_match(self):
        out = self.place("a.py", "def unique_b():\n    return 'b'")
        self.assertEqual((out["status"], out["path"], out["start_line"]),
                         ("relocated", "b.py", 2))

    def test_ambiguous_match_is_unlocated(self):
        out = self.place("a.py", "shared_boilerplate()")
        self.assertEqual((out["status"], out["path"]), ("unlocated", "a.py"))
        self.assertNotIn("start_line", out)

    def test_cited_line_picks_among_repeats(self):
        out = self.place("e.py", "dup_call()", start_line=4)
        self.assertEqual((out["status"], out["start_line"], out["end_line"]),
                         ("located", 4, 4))

    def test_repeats_without_cited_line_are_ambiguous(self):
        out = self.place("e.py", "dup_call()")
        self.assertEqual((out["status"], out.get("reason")),
                         ("unlocated", "ambiguous: 2 matches"))
        self.assertNotIn("end_line", out)

    def test_repeats_cited_line_covering_neither_are_ambiguous(self):
        out = self.place("e.py", "dup_call()", start_line=3)
        self.assertEqual((out["status"], out.get("reason"), out["start_line"]),
                         ("unlocated", "ambiguous: 2 matches", 3))

    def test_context_line_is_not_doubled_by_old_side(self):
        out = self.place("a.py", "keep_11")
        self.assertEqual((out["status"], out["start_line"]), ("located", 11))

    def test_whitespace_only_change_is_one_new_side_hit(self):
        out = self.place("f.py", "ws_call()")
        self.assertEqual((out["status"], out["start_line"], out.get("side")),
                         ("located", 2, None))

    def test_noprefix_config_and_top_level_a_dir(self):
        out = self.place("a/x.py", "x_new_line")
        self.assertEqual((out["status"], out["path"], out["start_line"]),
                         ("located", "a/x.py", 1))

    def test_absent_quote_is_unlocated(self):
        self.assertEqual(self.place("a.py", "no_such_code()")["status"], "unlocated")

    def test_misuse_exits_2(self):
        self.assertEqual(self.run_tool("-", stdin="[]").returncode, 2)
        self.assertEqual(self.run_tool("--from", "HEAD~1", "-", stdin="{").returncode, 2)
        self.assertEqual(self.run_tool("--from", "HEAD~1", "-",
                                       stdin='[{"path": "a.py"}]').returncode, 2)
        self.assertEqual(self.run_tool("--from", "nope", "-", stdin="[]").returncode, 2)


if __name__ == "__main__":
    unittest.main()
