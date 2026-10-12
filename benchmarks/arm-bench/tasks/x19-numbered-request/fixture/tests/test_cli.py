import io
import unittest
from contextlib import redirect_stdout

from notes import cli


def run(*argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = cli.main(["notes.json", *argv])
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def test_list(self):
        code, out = run("list")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "  1 2024-01-15 Kickoff")
        self.assertEqual(len(out.splitlines()), 4)

    def test_search_is_case_insensitive(self):
        code, out = run("search", "BUDGET")
        self.assertEqual(out, "  2 2024-02-29 Budget\n  3 2024-03-01 Retro\n")

    def test_export_header(self):
        code, out = run("export")
        self.assertTrue(out.startswith("# 4 notes\n\n## Kickoff (2024-01-15)\n"))


if __name__ == "__main__":
    unittest.main()
