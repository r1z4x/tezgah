"""hooks/tezgah_judge.py, and the docs fallback that calls it.

Every case talks to a local fake evaluation endpoint (TEZGAH_TYPESAFE_URL), so
no case needs a key and none reaches TypeSafe. The assertions are on what the
endpoint was asked - URL, bearer, state, model, every question in one body - and
on the documented return, not on the client's prose about it. What leaves the
machine is pinned the same way (`Egress`): the body's exact keys, the headers,
and that no repo-local file can repoint the endpoint (`EndpointOverride`).

The credential is exercised on the two channels it really has: the env var, and
the key file a non-interactive hook shell must fall back to because `~/.zshenv`
never ran there.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_judge  # noqa: E402

import support  # noqa: E402

DOCS = os.path.join(REPO, "bin", "tezgah-docs")
TRIAGE = os.path.join(REPO, "bin", "tezgah-triage")
INDEX = os.path.join(REPO, "docs", "index.json")
MODEL = "jev-latest"
# A query no index entry carries a word of, so the deterministic match is empty
# by construction rather than by luck.
UNMATCHED = "zzz-nothing-matches"
# Two units, one of them marked, is the least the triage will judge - enough to
# run the caller that shares the seam with `bin/tezgah-docs` without a second copy
# of test_triage's parsing fixture.
SNAPSHOT = ('- generic [ref=e1]:\n'
            '  - button "Retry" [ref=e2]\n')
# The proxy variables would send a loopback request somewhere else; the tests
# promise that nothing but 127.0.0.1 is ever opened.
PROXIES = ("http_proxy", "https_proxy", "all_proxy",
           "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


class Fake(BaseHTTPRequestHandler):
    """The TypeSafe evaluation endpoint, on loopback.

    `reply` is the body to answer with, `status` the code, `delay` stalls before
    answering so a case can ask for a timeout. Every request is recorded whole,
    so a case asserts on the call rather than on a paraphrase of it.
    """

    reply = {}
    reply_fn = None      # a case that must answer per question sets this
    status = 200
    status_fn = None     # a case that must answer a different code per request
                         # sets this: it gets the 1-based request number
    delay = 0.0
    seen = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) or b"{}"
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw.decode("utf-8", "replace")
        type(self).seen.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type"),
            # Every header, verbatim, so a case can assert that nothing beyond
            # the bearer and the content type rides out on the wire.
            "headers": dict(self.headers.items()),
            "body": body,
        })
        if type(self).delay:
            time.sleep(type(self).delay)
        reply = type(self).reply_fn(body) if type(self).reply_fn else type(self).reply
        out = json.dumps(reply).encode()
        status = (type(self).status_fn(len(type(self).seen))
                  if type(self).status_fn else type(self).status)
        if status != 200:
            self.send_error(status, "no")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        try:
            self.wfile.write(out)
        except OSError:
            pass          # the client gave up first: the timeout case

    def log_message(self, *args):
        pass


class Redirector(BaseHTTPRequestHandler):
    """Answers every POST with one 302 to `location`, counting what it answered."""

    location = ""
    hits = 0

    def do_POST(self):
        type(self).hits += 1
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.send_response(302)
        self.send_header("Location", type(self).location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class JudgeCase(unittest.TestCase):
    """A fake endpoint, a throwaway HOME, and no credential of this machine."""

    def setUp(self):
        Fake.seen, Fake.status, Fake.delay, Fake.reply_fn = [], 200, 0.0, None
        Fake.status_fn = None
        # A well-formed default reply, so a case about anything other than the
        # reply itself still exercises the documented return.
        Fake.reply = {"model": MODEL, "answers": {"urgent": {"type": "noul",
                                                             "noul": 0.5}},
                      "usage": {"input_tokens": 10, "output_tokens": 2}}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.realpath(self.tmp.name)
        patch = mock.patch.dict(os.environ, {"HOME": self.home,
                                            "TEZGAH_TYPESAFE_URL": self.url})
        patch.start()
        self.addCleanup(patch.stop)
        # The seam has two providers, so "no credential of this machine" means
        # both env channels: leaving OPENROUTER_API_KEY set here made the
        # fallback reach the live network from a case that promises it does not.
        for name in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY",
                     "TEZGAH_JUDGE_MODEL"):
            os.environ.pop(name, None)
        for name in PROXIES:
            os.environ.pop(name, None)

    @property
    def url(self):
        return "http://127.0.0.1:%d/v1/systemone" % self.server.server_address[1]

    def key_file(self, value="file-secret\n"):
        path = os.path.join(self.home, ".config", "typesafe", "key")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(value)
        os.chmod(path, 0o600)
        return path

    def ask(self, state="STATE", questions=None, **kw):
        return tezgah_judge.ask(state, questions or {
            "urgent": {"type": "noul", "instructions": "Is it urgent?"}}, **kw)

    def env(self, **extra):
        """A subprocess environment: this machine's key must not leak in."""
        env = support.base_env(self.home)
        env["TEZGAH_TYPESAFE_URL"] = self.url
        env.update(extra)
        return env

    def switch(self, name):
        """Arm one kill switch in the throwaway HOME's tezgah config."""
        path = os.path.join(self.home, ".config", "tezgah", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

    def ledger(self):
        """Every row this run's ledger holds, oldest first.

        The cache is the temp HOME's, so nothing this machine's is read - and a
        caller that wrote no row reads as an empty list rather than as the last
        run's leftovers."""
        rows = []
        for path in glob.glob(os.path.join(self.home, ".cache", "tezgah",
                                           "evidence", "*.jsonl")):
            with open(path, encoding="utf-8") as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
        return rows

    def snapshot_file(self):
        """The triage fixture, written where the subprocess can read it."""
        path = os.path.join(self.home, "snapshot.txt")
        with open(path, "w") as fh:
            fh.write(SNAPSHOT)
        return path

    def triage(self, *args, **extra):
        return subprocess.run([sys.executable, TRIAGE] + list(args),
                              capture_output=True, text=True, timeout=60,
                              env=self.env(**extra))


class Credential(JudgeCase):
    def test_the_env_var_wins_over_the_key_file(self):
        self.key_file()
        os.environ["TYPESAFE_API_KEY"] = "env-secret"
        self.assertIsNotNone(self.ask(), "ask did not reach the endpoint")
        self.assertEqual(Fake.seen[0]["authorization"], "Bearer env-secret")

    def test_the_key_file_is_the_fallback_a_non_interactive_shell_needs(self):
        # The env var is absent here, as it is in the shell a hook runs in - and
        # the file is 108 bytes with a trailing newline, which must not reach the
        # header.
        self.key_file()
        self.assertIsNotNone(self.ask(), "the key file did not resolve")
        self.assertEqual(Fake.seen[0]["authorization"], "Bearer file-secret")

    def test_no_credential_returns_none_without_calling_out(self):
        self.assertIsNone(self.ask())
        self.assertEqual(Fake.seen, [])

    def test_an_empty_key_file_is_no_credential(self):
        self.key_file("")
        self.assertIsNone(self.ask())
        self.assertEqual(Fake.seen, [])


class Request(JudgeCase):
    def test_one_call_carries_every_question(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        questions = {"one": {"type": "noul", "instructions": "First?"},
                     "two": {"type": "choice", "instructions": "Second?",
                             "criteria": {"a": "A", "b": "B"}},
                     "three": {"type": "score", "instructions": "Third?",
                               "criteria": ["low", "high"]}}
        Fake.reply = {"model": MODEL, "answers": {}, "usage":
                      {"input_tokens": 1, "output_tokens": 1}}
        out = self.ask(state="THE STATE", questions=questions)
        self.assertIsNotNone(out)
        self.assertEqual(len(Fake.seen), 1, "more than one request went out")
        seen = Fake.seen[0]
        self.assertEqual(seen["path"], "/v1/systemone")
        self.assertEqual(seen["authorization"], "Bearer test")
        self.assertEqual(seen["content_type"], "application/json")
        self.assertEqual(seen["body"]["state"], "THE STATE")
        self.assertEqual(seen["body"]["model"], MODEL)
        self.assertEqual(sorted(seen["body"]["questions"]), ["one", "three", "two"])
        self.assertEqual(seen["body"]["questions"], questions)

    def test_the_reply_parses_into_answers_usage_and_latency(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        answers = {"urgent": {"type": "noul", "noul": 0.92}}
        Fake.reply = {"model": MODEL, "answers": answers,
                      "usage": {"input_tokens": 312, "output_tokens": 48}}
        out = self.ask(questions={"urgent": {"type": "noul",
                                             "instructions": "Is it urgent?"}})
        self.assertEqual(out["answers"], answers)
        self.assertEqual(out["usage"], {"input_tokens": 312, "output_tokens": 48})
        self.assertIsInstance(out["latency_ms"], int)
        self.assertGreaterEqual(out["latency_ms"], 0)

    def test_a_refused_request_returns_none(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        Fake.status = 401
        self.assertIsNone(self.ask())

    def test_a_stalled_request_returns_none_at_the_timeout(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        Fake.reply = {"answers": {}, "usage": {"input_tokens": 0, "output_tokens": 0}}
        Fake.delay = 2.0
        started = time.monotonic()
        self.assertIsNone(self.ask(timeout=0.3))
        self.assertLess(time.monotonic() - started, 2.0,
                        "the call waited for the stalled reply")
        # A timeout is the transient class the retry exists for, so the endpoint
        # saw the second attempt - both of them inside the stall, which is why
        # the bound above still holds at twice the per-attempt timeout.
        self.assertEqual(len(Fake.seen), 2, "a timeout was not retried once")

    def test_a_reply_that_is_not_the_documented_shape_returns_none(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        Fake.reply = {"model": MODEL, "answers": {"urgent": {"noul": 0.5}}}
        self.assertIsNone(self.ask(), "a reply with no usage is not an answer")
        # It parsed, so the same request would parse the same way again: the
        # retry is for the link, not for a reply this module cannot read.
        self.assertEqual(len(Fake.seen), 1, "a malformed reply was retried")


class Retry(JudgeCase):
    """The one extra attempt, and the failures that must never get it.

    The second request is the same prepared body sent again, so what these cases
    read is the count the endpoint saw: two for a 5xx that clears, one for
    anything the endpoint would answer identically - above all a refused
    credential, which is the case a retry would turn into a lockout."""

    def test_a_5xx_is_retried_once_and_the_answer_is_kept(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        Fake.status_fn = lambda n: 503 if n == 1 else 200
        out = self.ask()
        self.assertIsNotNone(out, "the retry did not recover the answer")
        self.assertEqual(out["answers"], Fake.reply["answers"])
        self.assertEqual(len(Fake.seen), 2,
                         "the endpoint was not asked exactly twice")

    def test_a_401_is_never_retried(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        Fake.status = 401
        self.assertIsNone(self.ask())
        self.assertEqual(len(Fake.seen), 1, "a refused credential was retried")

    def test_a_422_is_never_retried(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        Fake.status = 422
        self.assertIsNone(self.ask())
        self.assertEqual(len(Fake.seen), 1, "a rejected body was retried")


class Egress(JudgeCase):
    """What leaves the machine, read off the fake rather than off the prose.

    A judgement is third-party processing of the state, so the request is pinned
    to the documented map and the documented headers: an extra field - a session
    id, a workspace path, an environment dump - is a leak, and this case would
    have to be told about it rather than discover it in the wild."""

    # urllib adds these itself. Any other name is a field nobody documented, so
    # the pin fails loudly instead of widening on the next Python release.
    HEADERS = {"Host", "Accept-Encoding", "Content-Length", "User-Agent",
               "Authorization", "Content-Type", "Connection"}

    def test_the_body_is_the_state_the_model_and_the_questions_and_nothing_else(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        self.assertIsNotNone(self.ask(state="ADMIN TABLE ROW"))
        body = Fake.seen[0]["body"]
        self.assertEqual(sorted(body), ["model", "questions", "state"])
        self.assertEqual(body["state"], "ADMIN TABLE ROW")
        self.assertEqual(body["model"], MODEL)
        self.assertEqual(sorted(body["questions"]), ["urgent"])

    def test_the_headers_are_the_bearer_and_the_content_type_over_urllib_only(self):
        os.environ["TYPESAFE_API_KEY"] = "test"
        self.assertIsNotNone(self.ask())
        headers = Fake.seen[0]["headers"]
        self.assertEqual(set(headers) - self.HEADERS, set(),
                         "an undocumented header went out")
        self.assertEqual(headers["Authorization"], "Bearer test")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_nothing_on_the_wire_names_this_machine(self):
        # TEZGAH_SESSION is real: opencode's plugin exports it into every shell
        # it runs, which is exactly the kind of ambient value a leak would carry.
        os.environ["TYPESAFE_API_KEY"] = "test"
        os.environ["TEZGAH_SESSION"] = "session-nobody-asked-for"
        self.assertIsNotNone(self.ask())
        seen = Fake.seen[0]
        wire = json.dumps([seen["path"], seen["headers"], seen["body"]])
        for leak in (self.home, REPO, "session-nobody-asked-for"):
            self.assertNotIn(leak, wire)

    def test_the_state_is_sent_verbatim_and_not_redacted(self):
        # Refused on purpose: the caller decides what is worth sending, and a
        # scrubber here would hide the risk instead of stating it.
        os.environ["TYPESAFE_API_KEY"] = "test"
        state = "row 3 | ana@example.com | " + self.home + "/report.txt"
        self.assertIsNotNone(self.ask(state=state))
        self.assertEqual(Fake.seen[0]["body"]["state"], state)


class EndpointOverride(JudgeCase):
    """`TEZGAH_TYPESAFE_URL` is an environment variable, and only that.

    It exists as the tests' seam, and a hostile repository must not be able to
    repoint the endpoint the state travels to: nothing on this path reads a
    repo-local file into the environment - no `.env`, no repo config - so only an
    export made before the process starts can reach it."""

    def test_the_env_var_is_the_only_way_to_repoint_it(self):
        repo = os.path.join(self.home, "hostile-checkout")
        os.makedirs(os.path.join(repo, ".tezgah"))
        for name in (".env", ".env.local", "tezgah.env",
                     ".tezgah/config.json", ".tezgah/env"):
            with open(os.path.join(repo, name), "w") as fh:
                fh.write("TEZGAH_TYPESAFE_URL=http://127.0.0.1:9/exfil\n")
        code = ("import json, os, tezgah_judge as j; "
                "print(json.dumps({'env': os.environ.get('TEZGAH_TYPESAFE_URL'), "
                "'endpoint': j.endpoint()}))")
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, env=support.base_env(self.home),
                              cwd=repo, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIsNone(out["env"], "a repo-local file reached the environment")
        self.assertEqual(out["endpoint"], tezgah_judge.URL)
        # The other half of the claim, in this process: the variable does
        # repoint it, which is what makes it a seam rather than a setting.
        self.assertEqual(tezgah_judge.endpoint(), self.url)


class Redirect(JudgeCase):
    """A redirect must not carry the credential to another host.

    urllib follows a 302 by re-issuing the request, and it keeps the
    Authorization header while doing it, so a redirecting endpoint would hand the
    key to whatever host it names - and the endpoint is repointable, so that host
    is not necessarily TypeSafe's."""

    def test_a_cross_host_redirect_is_refused_and_the_key_never_arrives(self):
        target = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=target.serve_forever, daemon=True).start()
        self.addCleanup(target.server_close)
        self.addCleanup(target.shutdown)
        Fake.seen = []
        Redirector.location = "http://127.0.0.1:%d/v1/systemone" \
            % target.server_address[1]
        Redirector.hits = 0
        redir = ThreadingHTTPServer(("127.0.0.1", 0), Redirector)
        threading.Thread(target=redir.serve_forever, daemon=True).start()
        self.addCleanup(redir.server_close)
        self.addCleanup(redir.shutdown)
        os.environ["TEZGAH_TYPESAFE_URL"] = \
            "http://127.0.0.1:%d/v1/systemone" % redir.server_address[1]
        self.key_file()
        self.assertIsNone(self.ask(), "a cross-host redirect was followed")
        self.assertEqual(Redirector.hits, 1, "the configured endpoint was not asked")
        self.assertEqual(Fake.seen, [],
                         "the credential reached a host the endpoint redirected to")

    def test_a_same_host_redirect_is_still_allowed(self):
        # The guard refuses on the network location, not on redirects as such: a
        # same-origin hop is urllib's business and this module does not change it.
        handler = tezgah_judge._NoCrossHostRedirect()
        req = urllib.request.Request(self.url, data=b"{}")
        same = handler.redirect_request(req, None, 302, "Found", {}, self.url)
        self.assertIsNotNone(same, "a same-host redirect was refused")
        other = handler.redirect_request(req, None, 302, "Found", {},
                                         "https://example.invalid/v1/systemone")
        self.assertIsNone(other, "a cross-host redirect was allowed")


class Availability(JudgeCase):
    def test_no_key_means_not_available(self):
        self.assertFalse(tezgah_judge.available())

    def available(self, env):
        code = ("import json, tezgah_judge as j; "
                "print(json.dumps(j.available()))")
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_key_with_no_switch_is_available(self):
        # In a subprocess because the kill-switch dir is resolved at import: a
        # fresh HOME is what makes the switch answerable here at all.
        self.assertTrue(self.available(self.env(TYPESAFE_API_KEY="test")))

    def test_the_kill_switch_makes_it_unavailable(self):
        self.switch("judge-off")
        self.assertFalse(self.available(self.env(TYPESAFE_API_KEY="test")))

    def test_a_per_caller_switch_leaves_the_seam_available(self):
        # The seam keeps one master, `judge-off`: a caller's own name answers for
        # that caller alone, so `triage-off` must not make `available()` false and
        # silence the docs page and the skill picker with it.
        self.switch("triage-off")
        self.switch("docs-judge-off")
        self.assertTrue(self.available(self.env(TYPESAFE_API_KEY="test")))


class DocsFallback(JudgeCase):
    """`bin/tezgah-docs`: the judged page, and the output it must not change."""

    def pages(self):
        with open(INDEX, encoding="utf-8") as fh:
            return json.load(fh)["pages"]

    def docs(self, query, **extra):
        return subprocess.run([sys.executable, DOCS, query], capture_output=True,
                              text=True, env=self.env(**extra), timeout=60)

    def test_the_judge_names_the_page_when_the_index_matches_nothing(self):
        Fake.reply = {"model": MODEL,
                      "answers": {"page": {"type": "choice",
                                           "choice": "docs/gate.md",
                                           "probabilities": {"docs/gate.md": 0.9},
                                           "confidence": 0.9}},
                      "usage": {"input_tokens": 900, "output_tokens": 4}}
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("docs/gate.md", proc.stdout)
        self.assertEqual(len(Fake.seen), 1)
        asked = Fake.seen[0]["body"]
        self.assertEqual(asked["state"], UNMATCHED)
        self.assertEqual(asked["model"], MODEL)
        question = asked["questions"]["page"]
        self.assertEqual(question["type"], "choice")
        # Every page is an option, so the question can only answer with a page
        # that exists - plus `none`, for the query no page covers.
        self.assertEqual(sorted(question["criteria"]),
                         sorted([p["path"] for p in self.pages()] + ["none"]))

    def test_a_query_the_index_cannot_place_exits_1_when_the_judge_is_off(self):
        proc = self.docs(UNMATCHED)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nothing matches", proc.stderr)
        self.assertEqual(Fake.seen, [])

    def test_an_answer_of_none_still_exits_1(self):
        Fake.reply = {"model": MODEL,
                      "answers": {"page": {"type": "choice", "choice": "none",
                                           "probabilities": {"none": 0.9},
                                           "confidence": 0.9}},
                      "usage": {"input_tokens": 900, "output_tokens": 4}}
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nothing matches", proc.stderr)

    def test_a_matching_query_is_byte_identical_with_and_without_the_judge(self):
        judged = self.docs("status mark", TYPESAFE_API_KEY="test")
        plain = self.docs("status mark")
        self.assertEqual(judged.returncode, 0, judged.stderr)
        self.assertEqual(judged.stdout, plain.stdout)
        self.assertEqual(Fake.seen, [], "the judge ran for a query that matched")

    def test_a_switch_for_this_caller_leaves_the_triage_judging(self):
        # The bug a per-caller switch introduces, in this direction: the docs page
        # goes quiet while the triage sharing its seam still asks and answers.
        # `docs-judge-off` may not be a second front for the master switch.
        self.switch("docs-judge-off")
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nothing matches", proc.stderr)
        self.assertEqual(Fake.seen, [], "docs-judge-off did not stop the call")
        triage = self.triage("--select", self.snapshot_file(), "--task", "retry",
                             TYPESAFE_API_KEY="test")
        self.assertEqual(triage.returncode, 0, triage.stderr)
        self.assertEqual(len(Fake.seen), 1, "the triage went quiet with the docs")

    def test_the_master_switch_silences_both_callers_of_the_seam(self):
        self.switch("judge-off")
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test")
        triage = self.triage("--select", self.snapshot_file(), "--task", "retry",
                             TYPESAFE_API_KEY="test")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nothing matches", proc.stderr)
        self.assertEqual(triage.returncode, 1)
        self.assertIn("judge-off", triage.stderr)
        self.assertEqual(Fake.seen, [],
                         "a request went out with the master switch armed")

    def test_a_refused_call_prints_what_it_always_printed_and_writes_no_row(self):
        # The seam answers `None` for a refused request, and this command has to
        # read that as "nothing matches" rather than crash on it - the reader the
        # answer now goes through is handed a `None` here, not a dict.
        Fake.status = 401
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test", TEZGAH_SESSION="s-401")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("nothing matches", proc.stderr)
        self.assertEqual(len(Fake.seen), 1, "the call was made and refused")
        self.assertEqual(self.ledger(), [], "a failed call was recorded as a spend")

    def test_a_judged_page_writes_one_judge_row_with_its_cost(self):
        # J4: the spend lands on the ledger as one `judge` row carrying which
        # caller, which model and what it cost - the shape the status counters fold
        # on - and it is a cost row, never a step or a check.
        Fake.reply = {"model": MODEL,
                      "answers": {"page": {"type": "choice",
                                           "choice": "docs/gate.md",
                                           "probabilities": {"docs/gate.md": 0.9},
                                           "confidence": 0.9}},
                      "usage": {"input_tokens": 900, "output_tokens": 4}}
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test", TEZGAH_SESSION="s-docs")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.ledger()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["kind"], "judge")
        self.assertRegex(rows[0]["detail"],
                         r"^tezgah-docs jev-latest in=900 out=4 ms=\d+$")
        # An answer of `none` still bought a call, so that query writes its own
        # row: what the ledger counts is the spend, not the page it landed on.
        Fake.reply["answers"]["page"] = {
            "type": "choice", "choice": "none",
            "probabilities": {"none": 0.9}, "confidence": 0.9}
        self.assertEqual(self.docs(UNMATCHED, TYPESAFE_API_KEY="test",
                                   TEZGAH_SESSION="s-docs-2").returncode, 1)
        self.assertEqual(len(self.ledger()), 2, self.ledger())


class OpenRouterFallback(JudgeCase):
    """No TypeSafe key: the same questions go to the chat fallback instead.

    The fallback's host is the same fake (`TEZGAH_OPENROUTER_URL`), so no case
    here reaches OpenRouter either. What is asserted is the call's shape - the
    chat body, the model, the key channel - and the mapping back into the
    answers `choice()`/`noul()` already read, because a fallback that answered in
    a shape the callers could not read would be worse than no answer at all.
    """

    def setUp(self):
        super().setUp()
        os.environ["TEZGAH_OPENROUTER_URL"] = self.url.replace(
            "/v1/systemone", "/v1/chat/completions")

    def chat(self, answers, prompt_tokens=11, completion_tokens=3):
        """Point the fake at a chat reply carrying `answers` as JSON text."""
        Fake.reply = {
            "choices": [{"message": {"content": json.dumps({"answers": answers})}}],
            "usage": {"prompt_tokens": prompt_tokens,
                      "completion_tokens": completion_tokens}}
        return Fake.reply

    def openrouter_file(self, value="chat-secret\n"):
        path = os.path.join(self.home, ".config", "openrouter", "key")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(value)
        return path

    def test_without_any_key_the_seam_is_still_unavailable(self):
        self.assertFalse(tezgah_judge.available())
        self.assertIsNone(self.ask())
        self.assertEqual(Fake.seen, [])

    def test_an_empty_openrouter_key_file_is_no_credential(self):
        self.openrouter_file("")
        self.assertFalse(tezgah_judge.available())
        self.assertIsNone(self.ask())
        self.assertEqual(Fake.seen, [])

    def test_an_openrouter_key_alone_makes_the_seam_available(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        self.assertTrue(tezgah_judge.available())

    def test_the_key_file_is_the_channel_for_the_fallback_too(self):
        self.openrouter_file()
        self.assertTrue(tezgah_judge.available())
        self.chat({"urgent": {"noul": 0.5}})
        self.assertIsNotNone(self.ask())
        self.assertEqual(Fake.seen[0]["authorization"], "Bearer chat-secret")

    def test_the_fallback_asks_the_chat_endpoint_in_its_own_shape(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        self.chat({"urgent": {"noul": 0.8}})
        out = self.ask(state="THE STATE")
        self.assertEqual(len(Fake.seen), 1, "more than one request went out")
        body = Fake.seen[0]["body"]
        self.assertEqual(Fake.seen[0]["path"], "/v1/chat/completions")
        self.assertEqual(body["model"], tezgah_judge.FALLBACK_MODEL)
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual([m["role"] for m in body["messages"]],
                         ["system", "user"])
        asked = json.loads(body["messages"][1]["content"])
        self.assertEqual(asked["state"], "THE STATE")
        self.assertEqual(sorted(asked["questions"]), ["urgent"])
        self.assertEqual(out["answers"], {"urgent": {"noul": 0.8}})
        self.assertEqual(out["usage"], {"input_tokens": 11, "output_tokens": 3})
        self.assertEqual(out["model"], tezgah_judge.FALLBACK_MODEL)
        self.assertIsInstance(out["latency_ms"], int)

    def test_a_choice_answer_maps_into_what_the_callers_read(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        self.chat({"page": {"choice": "docs/gate.md", "confidence": 0.6,
                            "probabilities": {"docs/gate.md": 0.7, "none": 0.3}}})
        out = self.ask(questions={"page": {
            "type": "choice", "instructions": "Which page?",
            "criteria": {"none": "no page answers this"}}})
        self.assertEqual(tezgah_judge.choice(out, "page"), "docs/gate.md")
        self.assertEqual(tezgah_judge.noul(out, "page", "docs/gate.md"), 0.7)
        self.assertEqual(tezgah_judge.noul(out, "page", "none"), 0.3)

    def test_an_answer_of_the_wrong_type_reads_as_unanswered(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        self.chat({"urgent": {"choice": "yes"}})
        out = self.ask()
        self.assertEqual(out["answers"], {})
        self.assertIsNone(tezgah_judge.noul(out, "urgent"))

    def test_a_message_that_is_not_json_is_no_judgement_and_is_not_retried(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        Fake.reply = {"choices": [{"message": {"content": "not json"}}],
                      "usage": {}}
        self.assertIsNone(self.ask())
        self.assertEqual(len(Fake.seen), 1, "a malformed reply was retried")

    def test_a_reply_without_message_content_is_no_judgement(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        Fake.reply = {"choices": [], "usage": {}}
        self.assertIsNone(self.ask())
        self.assertEqual(len(Fake.seen), 1, "a malformed reply was retried")

    def test_the_fallback_model_comes_from_the_environment_and_is_reported(self):
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        os.environ["TEZGAH_JUDGE_MODEL"] = "vendor/cheap-judge"
        self.chat({"urgent": {"noul": 0.5}})
        out = self.ask(model="jev-latest")
        self.assertEqual(Fake.seen[0]["body"]["model"], "vendor/cheap-judge")
        self.assertEqual(out["model"], "vendor/cheap-judge")

    def test_a_type_safe_key_still_wins_when_both_resolve(self):
        self.key_file()
        os.environ["OPENROUTER_API_KEY"] = "or-secret"
        Fake.reply = {"model": MODEL, "answers": {"urgent": {"noul": 0.5}},
                      "usage": {"input_tokens": 4, "output_tokens": 2}}
        self.assertIsNotNone(self.ask())
        seen = Fake.seen[0]
        self.assertEqual(seen["path"], "/v1/systemone")
        self.assertEqual(seen["authorization"], "Bearer file-secret")
        self.assertNotIn("messages", seen["body"])
        self.assertEqual(seen["body"]["model"], MODEL)

    def test_the_judge_switch_still_answers_for_the_fallback(self):
        # In a subprocess, like the seam's own availability cases: the kill-switch
        # directory is resolved at import, so only a fresh HOME makes the switch
        # answerable at all.
        code = ("import json, tezgah_judge as j; "
                "print(json.dumps(j.available()))")
        self.switch("judge-off")
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            timeout=60, env=self.env(OPENROUTER_API_KEY="or-secret"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(json.loads(proc.stdout))
        self.assertEqual(Fake.seen, [])

    def test_the_triage_reports_both_channels_when_none_resolves(self):
        # The caller's own message, not the seam's: with neither key the triage
        # must name the fallback's channels too, or a reader who has only an
        # OpenRouter key would be told there is no way to judge.
        path = self.snapshot_file()
        out = self.triage("--states", path)
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertIn("OPENROUTER_API_KEY", out.stderr)


if __name__ == "__main__":
    unittest.main()
