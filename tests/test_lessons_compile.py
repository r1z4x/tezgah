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


if __name__ == "__main__":
    unittest.main()
