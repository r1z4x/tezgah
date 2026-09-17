"""bin/consult: the referee stage, the failure classes and the stdin packet.

Every case talks to a local fake chat-completions endpoint (CONSULT_URL), so no
case needs a key and none reaches a provider. The assertions are on what the
endpoint was actually asked and on the footer, not on the prose in between.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSULT = os.path.join(REPO, "bin", "consult")
REFEREE = "You are the referee"
# The fields the contract tells the agent to read back. Kept as data so a test
# can fail when the tool's referee prompt stops asking for one of them.
FIELDS = ("recommendation", "key disagreements", "unchecked assumptions",
          "what would change my mind", "requested evidence")
DIGEST = ("1. Recommendation - pick A.\n"
          "2. Key disagreements - a says X, b says Y.\n"
          "3. Unchecked assumptions - neither checked Z.\n"
          "4. What would change my mind - a benchmark.\n"
          "5. Requested evidence - the source.")


class Fake(BaseHTTPRequestHandler):
    """A chat-completions endpoint the case configures per model.

    `answers` maps a model to its content, or to an HTTP status when the case
    wants that model to fail; `referee` does the same for the referee call.
    Every request body is recorded, so a case asserts on the call graph - how
    many calls, to which model, carrying which packet - rather than on prose.
    """

    answers = {}
    referee = None
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append(body)
        is_referee = body["messages"][0]["content"].startswith(REFEREE)
        model = body["model"]
        if is_referee:
            value = DIGEST if self.referee is None else self.referee
        else:
            value = self.answers.get(model, "answer from " + model)
        if isinstance(value, int):
            self.send_response(value)
            self.end_headers()
            self.wfile.write(b"boom")
            return
        out = json.dumps({"choices": [{"message": {"content": value}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class ArenaCase(unittest.TestCase):
    def setUp(self):
        Fake.answers, Fake.referee, Fake.seen = {}, None, []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.path.realpath(self.tmp.name),
            "OPENROUTER_API_KEY": "test",
            "CONSULT_URL": "http://127.0.0.1:%d/v1/chat/completions"
                           % self.server.server_address[1],
        }

    def consult(self, *args, stdin=None):
        return subprocess.run([sys.executable, CONSULT] + list(args),
                              capture_output=True, text=True, env=self.env,
                              input=stdin)

    def models(self):
        return [b["model"] for b in Fake.seen]


class RefereeStage(ArenaCase):
    def test_the_referee_is_one_call_after_the_panel_and_sees_every_answer(self):
        Fake.answers = {"a": "alpha says A", "b": "beta says B"}
        p = self.consult("q?", "--models", "a,b")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(self.models()[:2]), ["a", "b"])
        self.assertEqual(len(Fake.seen), 3)
        self.assertTrue(Fake.seen[2]["messages"][0]["content"].startswith(REFEREE))
        packet = Fake.seen[2]["messages"][1]["content"]
        for held in ("alpha says A", "beta says B", "q?"):
            self.assertIn(held, packet)
        self.assertIn("## referee (a)", p.stdout)
        self.assertIn("2. Key disagreements", p.stdout)

    def test_judge_picks_which_model_referees(self):
        Fake.answers = {"a": "x", "b": "y"}
        p = self.consult("q?", "--models", "a,b", "--judge", "b")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(Fake.seen[2]["model"], "b")

    def test_the_env_names_the_referee_model_too(self):
        Fake.answers = {"a": "x", "b": "y"}
        self.env["CONSULT_JUDGE"] = "b"
        p = self.consult("q?", "--models", "a,b")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(Fake.seen[2]["model"], "b")

    def test_the_referee_is_asked_for_every_field_the_rule_names(self):
        Fake.answers = {"a": "x"}
        self.consult("q?", "--models", "a")
        prompt = Fake.seen[-1]["messages"][0]["content"].lower()
        for field in FIELDS:
            self.assertIn(field, prompt)

    def test_no_referee_stops_after_the_panel(self):
        Fake.answers = {"a": "x", "b": "y"}
        p = self.consult("q?", "--models", "a,b", "--no-referee")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(Fake.seen), 2)
        self.assertNotIn("referee", p.stdout)

    def test_no_answer_to_referee_means_no_referee_call(self):
        Fake.answers = {"a": 500, "b": 500}
        p = self.consult("q?", "--models", "a,b")
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertEqual(len(Fake.seen), 2)
        self.assertNotIn("referee", p.stdout)


class Failures(ArenaCase):
    def test_a_failure_is_classed_and_one_retry_variable_is_named(self):
        Fake.answers = {"a": "fine", "bad": 500}
        p = self.consult("q?", "--models", "a,bad")
        self.assertIn("failed: bad (http-500)", p.stdout)
        self.assertIn("retry: ", p.stdout)

    def test_an_empty_reply_is_classed_empty(self):
        # 200 with a null content field is a refusal, not an answer.
        Fake.answers = {"a": "fine", "b": None}
        p = self.consult("q?", "--models", "a,b")
        self.assertIn("failed: b (empty)", p.stdout)

    def test_a_scheme_less_endpoint_is_reported_not_raised(self):
        # CONSULT_URL is caller-supplied now, and Request() raises ValueError
        # for a URL with no scheme: caught inside ask() it is one more failure
        # class, uncaught it killed the run with a traceback.
        self.env["CONSULT_URL"] = "localhost/v1/chat/completions"
        Fake.answers = {"a": "x", "b": "y"}
        p = self.consult("q?", "--models", "a,b")
        self.assertNotIn("Traceback", p.stderr)
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertIn("(malformed-reply)", p.stdout)

    def test_a_dead_referee_is_disclosed_and_leaves_the_panel_standing(self):
        Fake.answers = {"a": "the only answer"}
        Fake.referee = 503
        p = self.consult("q?", "--models", "a")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("referee: FAILED (http-503)", p.stdout)
        self.assertIn("unjudged", p.stdout)
        self.assertIn("failed: referee (http-503)", p.stdout)
        self.assertIn("retry: ", p.stdout)


class StdinPacket(ArenaCase):
    def test_a_packet_can_be_piped_as_the_question(self):
        p = self.consult("-", "--models", "a", stdin="a long packet\nline two")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(Fake.seen[0]["messages"][1]["content"],
                         "a long packet\nline two")

    def test_a_missing_question_stays_a_usage_error_not_a_stdin_read(self):
        # Reading stdin for an absent argument would turn a stray open pipe into
        # a paid prompt where the caller expected the misuse error.
        p = self.consult("--models", "a", stdin="stray pipe contents")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertEqual([], Fake.seen)
        self.assertIn("Usage:", p.stderr)


class Help(ArenaCase):
    """--help is answered locally. Without that arm the flag fell into the
    question position and the panel answered it as an engineering question."""

    def test_help_prints_usage_and_asks_nobody(self):
        for flag in ("--help", "-h"):
            p = self.consult(flag)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("Usage:", p.stdout, flag)
        self.assertEqual([], Fake.seen)


class Stall(threading.Thread):
    """Accepts, sends headers, then sends no body at all.

    urllib wraps OSError around the request only, so the read that times out
    here surfaces as a bare TimeoutError rather than as a URLError.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()
        self.conns = []

    def run(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            self.conns.append(conn)
            try:
                conn.recv(65536)
                conn.sendall(b"HTTP/1.1 200 OK\r\n"
                             b"Content-Type: application/json\r\n"
                             b"Transfer-Encoding: chunked\r\n\r\n")
            except OSError:
                pass

    def close(self):
        self.stop.set()
        for conn in self.conns:
            try:
                conn.close()
            except OSError:
                pass
        try:
            self.sock.close()
        except OSError:
            pass


class StalledBody(ArenaCase):
    def test_a_stalled_read_is_classed_timeout_and_names_the_timeout_lever(self):
        stall = Stall()
        stall.start()
        self.addCleanup(stall.close)
        self.env["CONSULT_URL"] = ("http://127.0.0.1:%d/v1/chat/completions"
                                   % stall.port)
        p = self.consult("q?", "--models", "a,b", "--timeout", "1")
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertIn("failed: a (timeout), b (timeout)", p.stdout)
        self.assertIn("retry: raise --timeout", p.stdout)


if __name__ == "__main__":
    unittest.main()
