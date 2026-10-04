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
            # consult reads the session's own model from omp's record; pin the
            # lookup to a path that is not there so a case is deterministic on a
            # machine that has omp installed (SessionModel swaps in a fake).
            "TEZGAH_OMP_BIN": os.path.join(os.path.realpath(self.tmp.name), "no-omp"),
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

    def test_an_unstructured_verdict_is_not_printed_as_a_judgement(self):
        # The headings are the whole of stage two: the caller reads back named
        # fields instead of a paraphrase. A referee that answers in prose, or
        # one that is cut off, is not a cross-examination - printing its text
        # under "## referee (<model>)" made it indistinguishable from one, and
        # the panel's answers then read as if something had judged them.
        Fake.answers = {"a": "the only answer"}
        Fake.referee = "Both answers are fine. I would go with the first one."
        p = self.consult("q?", "--models", "a")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("the only answer", p.stdout)
        self.assertIn("referee: FAILED (unstructured)", p.stdout)
        self.assertIn("unjudged", p.stdout)
        self.assertIn("failed: referee (unstructured)", p.stdout)
        self.assertNotIn("I would go with the first one", p.stdout)

    def test_a_verdict_missing_one_heading_names_it_and_degrades(self):
        # Not a judge of the verdict: the check is that the field is THERE. A
        # reply that answers four of five has dropped the minority report the
        # heading exists for, and the caller has to be told which one.
        Fake.answers = {"a": "answer from a"}
        Fake.referee = DIGEST.replace("5. Requested evidence - the source.", "")
        p = self.consult("q?", "--models", "a")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("did not answer: requested evidence", p.stdout)
        self.assertIn("referee: FAILED (unstructured)", p.stdout)

    def test_a_well_formed_verdict_is_still_printed_whole(self):
        # The control: the check must not degrade a referee that did the work.
        Fake.answers = {"a": "alpha", "b": "beta"}
        p = self.consult("q?", "--models", "a,b")
        self.assertIn("referee: a", p.stdout)
        self.assertNotIn("FAILED", p.stdout)
        for field in FIELDS:
            self.assertIn(field, p.stdout.lower())

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


class Landing(BaseHTTPRequestHandler):
    """Where a redirect lands: records each request's headers and answers.

    urllib turns a POST answered with 302 into a GET, so this answers GET."""

    seen = []

    def do_GET(self):
        type(self).seen.append(dict(self.headers))
        out = json.dumps({"choices": [{"message": {"content": "landed"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class CrossHostRedirect(ArenaCase):
    """The audit's L-9: a 302 to another host must not carry the key along."""

    def serve(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]

    def test_the_bearer_token_is_dropped_on_a_redirect_to_another_host(self):
        Landing.seen = []
        # `localhost` on another port is another netloc than 127.0.0.1:<port>,
        # which is the comparison the handler makes.
        target = "http://localhost:%d/v1/chat/completions" % self.serve(Landing)

        class Bounce(BaseHTTPRequestHandler):
            seen = []

            def do_POST(self):
                type(self).seen.append(dict(self.headers))
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(302)
                self.send_header("Location", target)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.env["CONSULT_URL"] = ("http://127.0.0.1:%d/v1/chat/completions"
                                   % self.serve(Bounce))
        self.env["OPENROUTER_API_KEY"] = "sk-secret"
        p = self.consult("q?", "--models", "a", "--no-referee")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(Bounce.seen[0].get("Authorization"), "Bearer sk-secret")
        self.assertEqual(len(Landing.seen), 1, p.stdout)
        self.assertNotIn("Authorization", Landing.seen[0])


class Credit(ArenaCase):
    def test_a_402_is_classed_credit_not_a_key_failure(self):
        # 402 is an empty account: read as http-4xx, the hint sent the caller
        # to rotate a key that was fine.
        Fake.answers = {"a": 402}
        p = self.consult("q?", "--models", "a")
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertIn("failed: a (credit)", p.stdout)


# A stand-in omp: answers `config get modelRoles --json` with FAKE_OMP_DEFAULT
# and logs its argv, so a case asserts consult made the documented read.
FAKE_OMP = '''#!%s
import json, os, sys
with open(os.environ["FAKE_OMP_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({"value": {"default": os.environ.get("FAKE_OMP_DEFAULT", "")}}))
''' % sys.executable


class SessionModel(ArenaCase):
    """The session's own model, read from omp's record: the recorded member that
    runs on it is skipped and named, --use still asks it, the referee is never
    it, and no read at all means no exclusion."""

    def setUp(self):
        super().setUp()
        self.fake_omp("a")

    def fake_omp(self, default):
        path = os.path.join(self.tmp.name, "omp")
        with open(path, "w") as fh:
            fh.write(FAKE_OMP)
        os.chmod(path, 0o755)
        self.env["TEZGAH_OMP_BIN"] = path
        self.env["FAKE_OMP_LOG"] = os.path.join(self.tmp.name, "omp.log")
        self.env["FAKE_OMP_DEFAULT"] = default

    def omp_runs(self):
        try:
            with open(self.env["FAKE_OMP_LOG"]) as fh:
                return [json.loads(line) for line in fh]
        except OSError:
            return []

    def record(self, members):
        p = self.consult("--use", members)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_omp_record_skips_the_member_on_the_session_model_and_names_it(self):
        self.record("openrouter:a,openrouter:b")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(["config", "get", "modelRoles", "--json"], self.omp_runs())
        self.assertIn("skipped: a (runs on this session's own model)", p.stdout)
        # a is never asked; b answers and referees
        self.assertEqual(self.models(), ["b", "b"])

    def test_use_naming_it_asks_it_anyway_with_the_note(self):
        p = self.consult("q?", "--use", "openrouter:a")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(Fake.seen[0]["model"], "a")
        self.assertIn("asked anyway: a", p.stdout)

    def test_the_referee_is_a_member_that_is_not_the_session_model(self):
        p = self.consult("q?", "--use", "openrouter:a,openrouter:b")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(self.models()[:2]), ["a", "b"])
        self.assertTrue(Fake.seen[-1]["messages"][0]["content"].startswith(REFEREE))
        self.assertEqual(Fake.seen[-1]["model"], "b")
        self.assertIn("## referee (b)", p.stdout)

    def test_no_session_model_skips_nothing_and_says_so(self):
        self.fake_omp("")  # an omp record with no modelRoles.default
        self.record("openrouter:a,openrouter:b")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("no session model", p.stdout)
        self.assertEqual(sorted(self.models()[:2]), ["a", "b"])

    def test_a_missing_omp_is_also_no_session_model(self):
        self.env["TEZGAH_OMP_BIN"] = os.path.join(self.tmp.name, "no-omp")
        self.record("openrouter:a,openrouter:b")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("no session model", p.stdout)
        self.assertEqual(sorted(self.models()[:2]), ["a", "b"])

    def test_the_env_knob_names_the_session_model_ahead_of_the_record(self):
        self.env["CONSULT_SESSION_MODEL"] = "a"
        self.fake_omp("b")  # the record disagrees; the knob wins
        self.record("openrouter:a,openrouter:b")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("skipped: a", p.stdout)
        self.assertEqual(self.models(), ["b", "b"])

    def test_a_member_of_the_session_s_model_family_is_skipped_too(self):
        # another DeepSeek model is not a second opinion on a DeepSeek session
        self.fake_omp("deepseek/deepseek-flash:high")
        self.record("openrouter:deepseek/deepseek-v4.1-flash,openrouter:openai/gpt-6.1-sol")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("skipped: deepseek/deepseek-v4.1-flash (same model family as this "
                      "session's: deepseek)", p.stdout)
        self.assertEqual(self.models(), ["openai/gpt-6.1-sol"] * 2)

    def test_one_vendor_through_two_providers_is_one_family(self):
        self.fake_omp("anthropic/claude-opus-5-5:high")
        self.record("openrouter:anthropic/claude-sonnet-5,openrouter:z-ai/glm-5.3-flash")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("skipped: anthropic/claude-sonnet-5", p.stdout)
        self.assertEqual(self.models(), ["z-ai/glm-5.3-flash"] * 2)


class ModelFamily(unittest.TestCase):
    """The family the independence skip compares, from the id alone."""

    def test_a_stem_counts_at_any_token_boundary_and_only_there(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("consult_under_test", CONSULT)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        consult = importlib.util.module_from_spec(spec)
        loader.exec_module(consult)
        cases = {
            # Bedrock spells the vendor with dots in front of the model
            "amazon-bedrock/anthropic.claude-sonnet-4": "anthropic",
            "us.anthropic.claude-sonnet-4-20250514-v1:0": "anthropic",
            # OpenAI's o-series, bare and behind a router
            "o3": "openai", "github-copilot/o3": "openai", "openai/o4-mini": "openai",
            "openai/gpt-oss-120b": "openai", "gpt-5": "openai",
            # a `gpt` that is not OpenAI's, and an `o` that is not a model series
            "EleutherAI/gpt-j-6b": None, "eleutherai/gpt-neox-20b": None,
            "openrouter/omni-x": None,
            # an `o1` inside another vendor's name is not OpenAI's o-series
            "AIDC-AI/Marco-o1": None, "Skywork/Skywork-o1": None, "o1-preview": "openai",
            "deepseek/deepseek-flash:high": "deepseek", "z-ai/glm-5.3-flash": "zai",
        }
        self.assertEqual({m: consult.model_family(m) for m in cases}, cases)

# A stand-in agent CLI: logs its argv and cwd, then answers, referees or fails
# as FAKE_<NAME> says. The prompt is its last argument.
FAKE_CLI = '''#!%s
import json, os, sys
name = os.path.basename(sys.argv[0])
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({"name": name, "argv": sys.argv[1:], "cwd": os.getcwd(),
                         "nested": os.environ.get("TEZGAH_NESTED")}) + "\\n")
if os.environ.get("FAKE_" + name.upper()) == "fail":
    sys.stderr.write("not logged in\\n")
    sys.exit(1)
prompt = sys.argv[-1]
print(%r if prompt.startswith(%r) else "cli answer from " + name)
''' % (sys.executable, DIGEST, REFEREE)


class CliMembers(ArenaCase):
    """Recorded members, agent CLIs among them: the offer, the record, the
    run, the OpenRouter fallback and the reoffer. PATH holds only the fakes and
    the system dirs, so the developer's own CLIs cannot answer for a case."""

    def setUp(self):
        super().setUp()
        self.bin = os.path.join(self.tmp.name, "fakebin")
        os.makedirs(self.bin)
        self.env["PATH"] = self.bin + ":/usr/bin:/bin"
        self.env["FAKE_LOG"] = os.path.join(self.tmp.name, "cli.log")
        self.config = os.path.join(self.env["HOME"], ".config", "tezgah", "config.json")

    def cli(self, *names):
        for name in names:
            path = os.path.join(self.bin, name)
            with open(path, "w") as fh:
                fh.write(FAKE_CLI)
            os.chmod(path, 0o755)

    def runs(self):
        try:
            with open(self.env["FAKE_LOG"]) as fh:
                return [json.loads(line) for line in fh]
        except OSError:
            return []

    def recorded(self):
        with open(self.config) as fh:
            return json.load(fh)

    def lines(self, out, word):
        return [ln.split(":", 1)[1].split(" - ")[0].strip()
                for ln in out.splitlines() if ln.startswith(word + ":")]

    def test_no_record_offers_what_is_available_and_asks_nobody(self):
        self.cli("codex", "claude")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertEqual(self.lines(p.stdout, "offer"),
                         ["cli:claude", "cli:codex", "openrouter"])
        self.assertEqual([], Fake.seen)
        self.assertEqual([], self.runs())

    def test_the_calling_host_s_own_cli_is_offered_last(self):
        self.cli("claude", "omp", "codex")
        self.env["OMPCODE"] = "1"
        p = self.consult("q?")
        self.assertEqual(self.lines(p.stdout, "offer")[-1], "cli:omp")

    def test_nothing_available_is_exit_2(self):
        del self.env["OPENROUTER_API_KEY"]
        p = self.consult("q?")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual([], self.runs())

    def test_use_records_the_choice_beside_the_other_keys_and_asks_nobody(self):
        self.cli("codex", "claude")
        os.makedirs(os.path.dirname(self.config))
        with open(self.config, "w") as fh:
            json.dump({"hosts": ["omp"]}, fh)
        p = self.consult("--use", "cli:codex:gpt-x,openrouter", "--judge", "cli:claude")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.recorded(), {
            "hosts": ["omp"],
            "consult": {"members": ["cli:codex:gpt-x", "openrouter"],
                        "judge": "cli:claude"}})
        self.assertEqual([], Fake.seen)
        self.assertEqual([], self.runs())
        before = os.stat(self.config).st_mtime_ns
        self.consult("--use", "cli:codex:gpt-x,openrouter", "--judge", "cli:claude")
        self.assertEqual(os.stat(self.config).st_mtime_ns, before)

    def test_use_refuses_a_member_this_machine_cannot_run(self):
        self.cli("codex")
        for member in ("cli:claude", "cli:nope", "deepseek"):
            with self.subTest(member=member):
                p = self.consult("--use", "cli:codex," + member)
                self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
                self.assertFalse(os.path.exists(self.config))

    def test_recorded_cli_members_answer_from_an_empty_dir_and_the_judge_referees(self):
        self.cli("codex", "claude")
        self.consult("--use", "cli:codex:gpt-x,cli:claude", "--judge", "cli:claude")
        p = self.consult("q about X?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual([], Fake.seen)
        runs = self.runs()
        # the panel runs in parallel, so only the referee's place is fixed
        self.assertEqual(sorted(r["name"] for r in runs[:2]), ["claude", "codex"])
        self.assertEqual(runs[2]["name"], "claude")
        codex = next(r["argv"] for r in runs if r["name"] == "codex")
        self.assertEqual(codex[codex.index("-m") + 1], "gpt-x")
        self.assertIn("q about X?", codex[-1])
        self.assertTrue(runs[2]["argv"][-1].startswith(REFEREE))
        for run in runs:  # never the caller's dir, and gone afterwards
            self.assertNotEqual(run["cwd"], os.getcwd())
            self.assertFalse(os.path.exists(run["cwd"]))
            # the child's own tezgah hooks read this to skip the reply-shape rules
            self.assertEqual(run["nested"], "1")
        self.assertIn("cli answer from codex", p.stdout)
        self.assertIn("referee: cli:claude", p.stdout)
        self.assertNotIn("reoffer:", p.stdout)

    def test_a_failed_member_leaves_the_rest_answering(self):
        self.cli("codex", "claude")
        self.env["FAKE_CODEX"] = "fail"
        self.consult("--use", "cli:codex,cli:claude")
        p = self.consult("q?", "--no-referee")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("cli:codex (cli-exit-1)", p.stdout)
        self.assertIn("cli answer from claude", p.stdout)

    def test_openrouter_answers_last_when_every_recorded_member_failed(self):
        self.cli("codex")
        self.env["FAKE_CODEX"] = "fail"
        self.consult("--use", "cli:codex")
        p = self.consult("q?", "--no-referee")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(self.models()),
                         ["google/gemini-3.8-flash", "openai/gpt-6.1-sol"])
        self.assertIn("fallback: openrouter", p.stdout)

    def test_every_member_failed_reoffers_only_what_did_not_fail(self):
        # openrouter is recorded and out of credit, so it is neither asked a
        # second time as the fallback nor offered again
        self.cli("codex", "claude")
        self.env["FAKE_CODEX"] = "fail"
        Fake.answers = {"openai/gpt-6.1-sol": 402, "google/gemini-3.8-flash": 402}
        self.consult("--use", "cli:codex,openrouter")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 5, p.stdout + p.stderr)
        self.assertEqual(len(Fake.seen), 2)
        self.assertIn("(credit)", p.stdout)
        self.assertEqual(self.lines(p.stdout, "reoffer"), ["cli:claude"])

    def test_a_member_gone_since_the_record_is_reported_and_reoffered_around(self):
        self.cli("codex")
        del self.env["OPENROUTER_API_KEY"]
        self.consult("--use", "cli:codex")
        os.remove(os.path.join(self.bin, "codex"))
        self.cli("claude")
        p = self.consult("q?")
        self.assertEqual(p.returncode, 5, p.stdout + p.stderr)
        self.assertIn("cli:codex (missing)", p.stdout)
        self.assertEqual(self.lines(p.stdout, "reoffer"), ["cli:claude"])


class UnknownCliModel(ArenaCase):
    """A bare `cli:<name>` member: consult cannot read which model the CLI is
    configured for, so it counts as unknown - asked, and named as unknown."""

    def setUp(self):
        super().setUp()
        self.bin = os.path.join(self.tmp.name, "fakebin")
        os.makedirs(self.bin)
        self.env["PATH"] = self.bin + ":/usr/bin:/bin"
        for path in (os.path.join(self.bin, "claude"), os.path.join(self.tmp.name, "omp")):
            with open(path, "w") as fh:
                fh.write(FAKE_CLI if path.endswith("claude") else FAKE_OMP)
            os.chmod(path, 0o755)
        self.env["FAKE_LOG"] = os.path.join(self.tmp.name, "cli.log")
        self.env["TEZGAH_OMP_BIN"] = os.path.join(self.tmp.name, "omp")
        self.env["FAKE_OMP_LOG"] = os.path.join(self.tmp.name, "omp.log")
        self.env["FAKE_OMP_DEFAULT"] = "a"

    def test_a_cli_whose_model_is_unreadable_is_named_unknown_and_still_asked(self):
        p = self.consult("--use", "cli:claude")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.consult("q?", "--no-referee")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("unknown: cli:claude", p.stdout)
        self.assertIn("cli answer from claude", p.stdout)

    def test_a_bare_cli_whose_vendor_is_the_session_s_family_is_skipped(self):
        # `claude` answers with some Claude model whichever one it is configured for
        self.env["FAKE_OMP_DEFAULT"] = "anthropic/claude-opus-5-5"
        p = self.consult("--use", "cli:claude,openrouter:openai/gpt-6.1-sol")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.consult("q?", "--no-referee")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("skipped: cli:claude (same model family as this session's: "
                      "anthropic)", p.stdout)
        self.assertNotIn("cli answer from claude", p.stdout)


if __name__ == "__main__":
    unittest.main()
