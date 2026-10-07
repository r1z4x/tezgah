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
    """The chat-completions endpoint, answering with one canned reply. `hits`
    counts every request of any method, so a case can assert none arrived."""

    reply = ""
    hits = 0

    def do_GET(self):
        type(self).hits += 1
        self.send_error(405)

    def do_POST(self):
        type(self).hits += 1
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


class Redirector(BaseHTTPRequestHandler):
    """Answers every POST with one 302 to `location`."""

    location = ""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(302)
        self.send_header("Location", type(self).location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class CodegenCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        Fake.hits = 0
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


class Egress(CodegenCase):
    """What codegen refuses to send, and where: the files go whole to a third
    party, so the guard is on the endpoint and on the bodies before any request."""

    def test_a_cross_host_redirect_is_refused_and_the_target_never_hears(self):
        redir = ThreadingHTTPServer(("127.0.0.1", 0), Redirector)
        threading.Thread(target=redir.serve_forever, daemon=True).start()
        self.addCleanup(redir.server_close)
        self.addCleanup(redir.shutdown)
        # another port is another host for the guard: netloc is host:port
        Redirector.location = self.env["CODEGEN_URL"]
        self.env["CODEGEN_URL"] = "http://127.0.0.1:%d/v1/chat/completions" \
            % redir.server_address[1]
        p = self.draft("b.py", "x = 1\n", "x = 2\n")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(Fake.hits, 0, "the redirect was followed")

    def test_a_file_carrying_a_credential_is_refused_before_any_request(self):
        p = self.draft("c.py", "TOKEN = 'ghp_%s'\n" % ("a" * 36), "x = 2\n")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("carries a credential", p.stderr)
        self.assertIn("write this one yourself", p.stderr)
        self.assertEqual(Fake.hits, 0, "the file was sent")

    def test_a_plain_http_endpoint_off_this_machine_is_refused(self):
        self.env["CODEGEN_URL"] = "http://example.invalid/v1/chat/completions"
        p = self.draft("b.py", "x = 1\n", "x = 2\n")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("plain http", p.stderr)

    def test_loopback_http_is_still_accepted(self):
        for host in ("127.0.0.1", "localhost"):
            with self.subTest(host=host):
                self.env["CODEGEN_URL"] = "http://%s:%d/v1/chat/completions" % (
                    host, self.server.server_address[1])
                p = self.draft("b.py", "x = 1\n", "x = 2\n")
                self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == "__main__":
    unittest.main()
