"""bin/codegen: what the draft guard vouches for, and what it says it cannot.

Every case talks to a local fake chat-completions endpoint (CODEGEN_URL), so no
case needs a key and none reaches a provider. The assertions are on the exit code
and on the footer, because that is what the router reads before it applies a
draft - a diff printed with exit 0 is the go-ahead.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEGEN = os.path.join(REPO, "bin", "codegen")
SHEBANG = "#!/usr/bin/env python3\n"
# A body no parser accepts, in the shape that matters: it looks like a file.
BROKEN = "def f(:\n    return 1\n"


class Fake(BaseHTTPRequestHandler):
    """The chat-completions endpoint, answering with one canned reply."""

    reply = ""

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        out = json.dumps({"choices": [{"finish_reason": "stop",
                                       "message": {"content": type(self).reply}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class CodegenCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.path.realpath(self.tmp.name),
            "OPENROUTER_API_KEY": "test",
            "CODEGEN_URL": "http://127.0.0.1:%d/v1/chat/completions"
                           % self.server.server_address[1],
        }

    def draft(self, name, current, body):
        """A file on disk plus the draft that would replace it, run through
        bin/codegen. The reply names the file the caller asked for, which is the
        only path this tool will diff."""
        path = os.path.join(self.tmp.name, name)
        with open(path, "w") as fh:
            fh.write(current)
        Fake.reply = "=== FILE: %s ===\n```\n%s\n```\n" % (path, body)
        return subprocess.run([sys.executable, CODEGEN, "t", "--files", path],
                              capture_output=True, text=True, env=self.env)


class DraftGuard(CodegenCase):
    def test_a_python_draft_that_does_not_parse_is_refused(self):
        # The control for the two cases below: the check still fires where it
        # always did, so a widened guard cannot be one that never parses.
        p = self.draft("a.py", "x = 1\n", BROKEN)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn("not valid Python", p.stderr)

    def test_a_python_draft_with_no_suffix_is_refused_by_its_shebang(self):
        # This repo's own tools are bin/* scripts with no `.py`, and they are
        # exactly what the router hands codegen. A suffix-only guard vouched for
        # none of them: a broken draft came back as exit 0 with a diff.
        p = self.draft("tool", SHEBANG + "x = 1\n", SHEBANG + BROKEN)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn("not valid Python", p.stderr)

    def test_a_language_no_checker_here_parses_is_named_not_passed_silently(self):
        # Nothing in this tool parses TypeScript, so the draft cannot be
        # vouched for - and exit 0 is the router's go-ahead. The note is the
        # whole mitigation: whoever reviews the diff learns which file nothing
        # read before applying it.
        p = self.draft("ui.tsx", "export const A = () => null\n",
                       "export const A = () => {\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("ui.tsx was not parsed", p.stderr)

    def test_a_parsed_draft_wears_no_note(self):
        p = self.draft("b.py", "x = 1\n", "x = 2\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("was not parsed", p.stderr)


if __name__ == "__main__":
    unittest.main()
