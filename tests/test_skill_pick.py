"""hooks/tezgah_skill_pick.py: one judgement, one line, and the text it rides.

Every case talks to a local fake evaluation endpoint (TEZGAH_TYPESAFE_URL), so no
case needs a key and none reaches TypeSafe. The assertions are on what the
endpoint was asked - the roster in the Choice, the gate question, one request per
prompt per session - and on the appended line, never on the client's prose about
it. `ContextLine` runs the whole hook path in a child process
(bin/tezgah-context -> context_for -> the pick -> the loopback endpoint) with the
credential on the file channel a non-interactive hook shell really has.
"""
import glob
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_paths as tp  # noqa: E402
import tezgah_skill_pick as sp  # noqa: E402

import support  # noqa: E402

SKILLS_DIR = os.path.join(REPO, "skills")
# The proxy variables would send a loopback request somewhere else; the tests
# promise that nothing but 127.0.0.1 is ever opened.
PROXIES = ("http_proxy", "https_proxy", "all_proxy",
           "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
PROMPT = "Refactor this module: give me the simplest thing that works"


class Fake(BaseHTTPRequestHandler):
    """The TypeSafe evaluation endpoint, on loopback. Every request is recorded
    whole, so a case asserts on the call rather than on a paraphrase of it."""

    reply = {}
    status = 200
    delay = 0.0
    seen = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            body = None
        type(self).seen.append(body)
        if type(self).delay:
            time.sleep(type(self).delay)
        if type(self).status != 200:
            self.send_error(type(self).status, "no")
            return
        out = json.dumps(type(self).reply).encode()
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


class SkillPick(unittest.TestCase):
    """A fake endpoint, a throwaway HOME, and no credential of this machine."""

    def setUp(self):
        Fake.seen, Fake.status, Fake.delay = [], 200, 0.0
        self.answer()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.realpath(self.tmp.name)
        # The arming marker and the kill switches are read from OFF_DIRS, which on
        # a real machine is the user's config: point it at the throwaway HOME so a
        # case can arm and disarm without touching anyone's tezgah.
        self.config_dir = os.path.join(self.home, ".config", "tezgah")
        for patch in (mock.patch.dict(os.environ, {"HOME": self.home,
                                                  "TEZGAH_TYPESAFE_URL": self.url}),
                      # the real cache dir would keep this case's answers between runs
                      mock.patch.object(tp, "CACHE",
                                        os.path.join(self.home, ".cache", "tezgah")),
                      mock.patch.object(tp, "OFF_DIRS", (self.config_dir,))):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("TYPESAFE_API_KEY", None)
        # The seam's second provider reads its own env channel; leaving it set
        # made `test_no_credential_asks_nothing` reach the live network from a
        # case whose whole point is that no request goes out.
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("TEZGAH_JUDGE_MODEL", None)
        for name in PROXIES:
            os.environ.pop(name, None)
        # Opt-in is the product decision (`docs/contract.md`); these cases are about
        # what the picker does once a user has made it, and `test_an_unarmed_picker`
        # covers the default.
        self.arm()

    @property
    def url(self):
        return "http://127.0.0.1:%d/v1/systemone" % self.server.server_address[1]

    def answer(self, choice="ponytail", gate=0.9):
        """The reply the endpoint gives: one Choice over the roster, one gate Noul."""
        probabilities = {name: 0.0 for name, _clause in sp.roster()}
        probabilities["none"] = 0.0
        probabilities[choice] = 1.0
        Fake.reply = {"model": "jev-latest",
                      "answers": {"which": {"type": "choice", "choice": choice,
                                            "confidence": 0.9,
                                            "probabilities": probabilities},
                                  "needs_skill": {"type": "noul", "noul": gate}},
                      "usage": {"input_tokens": 900, "output_tokens": 160}}

    def key_file(self):
        """The channel a non-interactive hook shell has, since `~/.zshenv` never
        ran there."""
        path = os.path.join(self.home, ".config", "typesafe", "key")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("file-secret\n")
        os.chmod(path, 0o600)

    def switch(self, name):
        path = os.path.join(self.home, ".config", "tezgah", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

    def ledger(self):
        """Every ledger row this run wrote, oldest first.

        The cache is the throwaway HOME's, so a case reads the picker's own rows
        and never this machine's."""
        rows = []
        for path in glob.glob(os.path.join(self.home, ".cache", "tezgah",
                                           "evidence", "*.jsonl")):
            with open(path, encoding="utf-8") as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
        return rows

    def arm(self):
        """Opt the picker in. Every case below is about what it does ONCE ARMED,
        so setUp arms it and the opt-in case disarms it again."""
        self.switch(sp.ARM)

    def disarm(self):
        try:
            os.remove(os.path.join(self.home, ".config", "tezgah", sp.ARM))
        except OSError:
            pass


class Suggestion(SkillPick):
    """What the judgement turns into."""

    def test_a_named_skill_becomes_one_line_saying_what_it_is_for(self):
        self.key_file()
        line = sp.suggest(PROMPT, "s1")
        self.assertTrue(line.startswith("<skill_relevance>\nRelevant to the "
                                        "current request: ponytail"), line)
        self.assertIn("hint, not an instruction to load", line)
        # what it is for, not just its name: the same clause the judge ranked on
        self.assertIn(sp.clause(os.path.join(SKILLS_DIR, "ponytail", "SKILL.md")),
                      line)
        self.assertLess(len(line), 560,
                        "the hint must not cost more than a line and an address")

    def test_the_hint_names_the_matching_section_not_just_the_skill(self):
        # a skill name still leaves the session to guess which PART answers the
        # request; the local ranking turns the name into a `skill://` range plus
        # the path a host without that transport opens
        self.key_file()
        line = sp.suggest(PROMPT, "s1")
        self.assertRegex(line, r"Start at skill://ponytail:\d+-\d+")
        self.assertIn(os.path.join(SKILLS_DIR, "ponytail", "SKILL.md"), line)
        start, end = (int(n) for n in
                      re.search(r"skill://ponytail:(\d+)-(\d+)", line).groups())
        with open(os.path.join(SKILLS_DIR, "ponytail", "SKILL.md")) as fh:
            rows = fh.read().splitlines()
        self.assertTrue(rows[start - 1].startswith("#"), rows[start - 1])
        self.assertLess(start, end, "an address, not a point")

    def test_the_request_carries_every_installed_skill_and_a_none_option(self):
        self.key_file()
        sp.suggest(PROMPT, "s1")
        body = Fake.seen[0]
        self.assertEqual(body["state"], {"request": PROMPT})
        self.assertEqual(sorted(body["questions"]), ["needs_skill", "which"])
        criteria = body["questions"]["which"]["criteria"]
        self.assertEqual(sorted(criteria),
                         sorted(sorted(os.listdir(SKILLS_DIR)) + ["none"]))
        self.assertEqual(body["questions"]["which"]["type"], "choice")
        self.assertEqual(body["questions"]["needs_skill"]["type"], "noul")

    def test_none_is_not_a_suggestion(self):
        self.key_file()
        self.answer(choice="none")
        self.assertEqual(sp.suggest(PROMPT, "s1"), "")
        self.assertEqual(len(Fake.seen), 1, "the call was made and answered")

    def test_the_gate_suppresses_a_confident_pick(self):
        # the Choice picked a skill; the turn's own question says it wants none
        self.key_file()
        self.answer(gate=0.29)
        self.assertEqual(sp.suggest(PROMPT, "s1"), "")

    def test_a_name_outside_the_roster_is_not_a_suggestion(self):
        self.key_file()
        self.answer(choice="not-a-skill")
        self.assertEqual(sp.suggest(PROMPT, "s1"), "")

    def test_no_credential_asks_nothing(self):
        self.assertEqual(sp.suggest(PROMPT, "s1"), "")
        self.assertEqual(Fake.seen, [])

    def test_an_unarmed_picker_asks_nothing(self):
        """The default: without `skill-suggest-on` there is no request and no line.

        A labelled set of 28 prompts through an independent chooser was measured at
        0 of 20 wrong with no hint at all, so the hint's benefit on this roster is
        unproven while its cost is measured - which is why arming it is the user's
        decision and an unarmed install pays nothing."""
        self.disarm()
        self.key_file()
        self.assertEqual(sp.suggest(PROMPT, "s1"), "")
        self.assertEqual(Fake.seen, [], "nothing may be asked before it is armed")

    def test_a_slash_command_is_not_asked(self):
        self.key_file()
        self.assertEqual(sp.suggest("/tezgah:plan-add track the work", "s1"), "")
        self.assertEqual(Fake.seen, [])

    def test_one_prompt_is_paid_for_once_per_session(self):
        self.key_file()
        first = sp.suggest(PROMPT, "s1")
        again = sp.suggest(PROMPT, "s1")
        self.assertEqual(first, again)
        self.assertEqual(len(Fake.seen), 1)
        sp.suggest(PROMPT, "s2")            # another session is another question
        self.assertEqual(len(Fake.seen), 2)

    def test_a_failed_call_costs_the_line_and_not_the_turn(self):
        # The 401 goes last: it arms the provider-down marker, which would skip
        # the two malformed-reply calls before it ever reached them.
        self.key_file()
        Fake.reply.pop("usage")
        self.assertEqual(sp.suggest(PROMPT, "s2"), "")
        Fake.reply = {"answers": {}, "usage": {"input_tokens": 1, "output_tokens": 1}}
        self.assertEqual(sp.suggest(PROMPT, "s3"), "")
        Fake.status = 401
        self.assertEqual(sp.suggest(PROMPT, "s1"), "")
        self.assertEqual(len(Fake.seen), 3, "a call was skipped or repeated")

    def test_a_stalled_call_returns_at_its_deadline_after_one_attempt(self):
        # One attempt and a wall-clock cap: the per-socket timeout alone let a
        # retried stall run 2 x the timeout past omp's 10 s hook kill.
        self.key_file()
        Fake.delay = 2.0
        with mock.patch.object(sp, "ASK_DEADLINE", 0.3):
            started = time.monotonic()
            self.assertEqual(sp.suggest(PROMPT, "s1"), "")
            self.assertLess(time.monotonic() - started, 1.5,
                            "the turn waited past the hint's deadline")
        self.assertEqual(len(Fake.seen), 1, "the hint retried a stalled call")

    def test_the_shipped_deadline_stays_well_under_the_host_hook_budget(self):
        # The real constant, not a patched one: omp kills the hook at 10 s and
        # the rest of the prompt hook runs after the hint.
        self.assertLessEqual(sp.ASK_DEADLINE, 4.0)
        self.assertFalse(hasattr(sp, "ASK_TIMEOUT"),
                         "the dead per-socket constant is back")

    def test_the_prompt_goes_out_redacted_and_capped(self):
        self.key_file()
        secret = "sk-" + "a" * 40
        prompt = "Rotate this key %s then refactor. %s" % (secret, "x" * 5000)
        sp.suggest(prompt, "s1")
        sent = Fake.seen[0]["state"]["request"]
        self.assertNotIn(secret, sent)
        self.assertIn("[redacted:", sent)
        self.assertLessEqual(len(sent), sp.PROMPT_MAX)
        self.assertEqual(sp.PROMPT_MAX, 2000)

    def test_a_judged_prompt_writes_one_judge_row_with_its_cost(self):
        # J4, the half no shell row can carry: the prompt-path caller is counted
        # too, with the host's session id, and the row is the spend rather than the
        # suggestion - it lands whether or not a skill was named. The model is the
        # one the reply names, and `judge=` says which provider answered.
        self.key_file()
        Fake.reply["model"] = "jev-1.12"
        sp.suggest(PROMPT, "s-j4")
        rows = self.ledger()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["kind"], "judge")
        self.assertRegex(rows[0]["detail"],
                         r"^tezgah-skill-pick jev-1\.12 in=900 out=160 ms=\d+ "
                         r"judge=typesafe/jev-1\.12$")

    def test_a_prompt_with_no_session_id_writes_no_row(self):
        # `suggest` is reachable with no session id; the hint is unchanged by that
        # and no ledger row is invented for a session nobody named.
        self.key_file()
        self.assertTrue(sp.suggest(PROMPT, ""))
        self.assertEqual(self.ledger(), [])

    def test_every_installed_skill_has_a_clause_for_the_judge(self):
        roster = sp.roster()
        self.assertEqual(len(roster), len(os.listdir(SKILLS_DIR)))
        for name, text in roster:
            self.assertTrue(text, name)
            self.assertLessEqual(len(text), sp.CLAUSE_CAP, name)


class ContextLine(SkillPick):
    """The line in the text context_for returns, through the real hook path."""

    def prompt(self, repo, env=None, session="s1", text=PROMPT):
        out, proc = support.run_json(
            [support.PROBE_CONTEXT],
            {"fn": "context_for", "event": "user_prompt", "cwd": repo,
             "payload": {"prompt": text, "session_id": session}},
            env=env or self.child_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def child_env(self, endpoint=False):
        env = support.base_env(self.home)
        if endpoint:
            env["TEZGAH_TYPESAFE_URL"] = self.url
        return env

    def baseline(self, repo):
        """The per-turn text with no judgement available at all: no credential, so
        nothing is asked and nothing is appended. Its own session: an armed
        paragraph is paid in full once per session, so a second turn of the same
        session would carry the one-line repeat instead."""
        return self.prompt(repo, env=self.child_env(), session="baseline")

    def test_the_line_is_appended_and_the_rest_is_byte_identical(self):
        repo = os.path.join(self.home, "Projects", "repo")
        os.makedirs(repo)
        baseline = self.baseline(repo)
        # without a judgement the model-free section search answers this
        # prompt (`section_hint`); the judgement's line takes its place, so a
        # turn carries one skill line, never two
        local = re.search(r"\n\n<skill_relevance>\nA local skill search.*"
                          r"</skill_relevance>$", baseline, re.S)
        self.assertTrue(local, baseline)
        baseline = baseline[:local.start()]
        self.key_file()
        with_hint = self.prompt(repo, env=self.child_env(endpoint=True))
        self.assertEqual(with_hint[:len(baseline)], baseline)
        rest = with_hint[len(baseline):]
        self.assertTrue(rest.startswith("\n\n<skill_relevance>\nRelevant to the "
                                        "current request: ponytail"), rest)
        self.assertTrue(rest.endswith("</skill_relevance>"), rest)
        self.assertEqual(1, with_hint.count("<skill_relevance>"))

    def test_an_unarmed_picker_appends_nothing(self):
        repo = os.path.join(self.home, "Projects", "repo")
        os.makedirs(repo)
        baseline = self.baseline(repo)
        self.key_file()
        self.disarm()
        self.assertEqual(self.prompt(repo, env=self.child_env(endpoint=True)),
                         baseline)
        self.assertEqual(Fake.seen, [], "an unarmed picker must make no request")

class OmpHintPath(SkillPick):
    """The hint through omp's own dispatch: hosts/omp/hook.py is the envelope
    the extension really calls, so this is the check that a turn on omp
    appends the sectioned line - not only that `suggest` returns it when a
    test calls the picker directly."""

    def prompt(self, repo):
        out, proc = support.run_json(
            [support.OMP_HOOK],
            {"event": "user_prompt", "cwd": repo, "prompt": PROMPT,
             "session_id": "s-omp"},
            env=dict(support.base_env(self.home),
                     TEZGAH_TYPESAFE_URL=self.url))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_user_prompt_event_appends_the_sectioned_hint(self):
        repo = os.path.join(self.home, "Projects", "repo")
        os.makedirs(repo)
        self.key_file()
        out = self.prompt(repo)
        self.assertIn("skill_relevance", out.get("context") or "",
                      "omp's prompt path dropped the hint: %r" % out)
        self.assertRegex(out["context"], r"Start at skill://ponytail:\d+-\d+")


if __name__ == "__main__":
    unittest.main()
