"""bin/tezgah-taste: mine on a fixture HOME, measure and rate on a loopback judge.

The judge is a local fake of the evaluation endpoint (TEZGAH_TYPESAFE_URL) that
labels each question by a word in its prompt, so the confusion, precision and
recall the CLI prints are checked against arithmetic done here by hand.
"""
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

sys.path.insert(0, support.HOOKS)
import tezgah_taste_ledger as tl  # noqa: E402

CLI = os.path.join(support.REPO, "bin", "tezgah-taste")
TOKEN = "ghp_" + "a" * 36


def jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write((row if isinstance(row, str) else json.dumps(row)) + "\n")


def omp_user(text):
    return {"type": "message", "message": {"role": "user",
                                           "content": [{"type": "text", "text": text}]}}


def omp_tool(name, error=False):
    return {"type": "message", "message": {"role": "toolResult", "toolName": name,
                                           "isError": error, "content": []}}


class Mine(support.TempHome):
    def setUp(self):
        super().setUp()
        app = self.make_repo("app")
        os.makedirs(os.path.join(app, ".git"))
        sessions = os.path.join(self.home, ".omp", "agent", "sessions", "-app-")
        jsonl(os.path.join(sessions, "s1.jsonl"), [
            {"type": "title"},
            '{"type":"session","id":"s1","cwd":%s}' % json.dumps(os.path.join(app, "sub")),
            omp_user("build it"),
            omp_tool("write"), omp_tool("edit"), omp_tool("bash"),
            omp_user("rename it to foo"),                  # row: 2 writes
            omp_tool("edit", error=True),
            omp_user("next"),                              # no write before it
            omp_tool("write"),
            omp_user("<system-reminder>injected</system-reminder>"),
            omp_user("thanks"),                            # the harness reset the turn
            omp_tool("write"),
            omp_user("use this key %s instead" % TOKEN),   # row: 1 write, redacted
        ])
        # a subagent session nests below its parent's directory: not counted
        jsonl(os.path.join(sessions, "s1", "sub.jsonl"), [
            '{"type":"session","id":"sub","cwd":%s,"parentSession":"s1"}' % json.dumps(app),
            omp_tool("write"), omp_user("child prompt")])
        # a session outside the root: not counted
        jsonl(os.path.join(self.home, ".omp", "agent", "sessions", "-tmp-", "s2.jsonl"), [
            '{"type":"session","id":"s2","cwd":"/tmp/elsewhere"}',
            omp_tool("write"), omp_user("outside")])
        claude = os.path.join(self.home, ".claude", "projects", "-app")
        jsonl(os.path.join(claude, "c1.jsonl"), [
            {"type": "user", "cwd": app, "message": {"role": "user", "content": "start"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Edit"},
                {"type": "tool_use", "id": "t2", "name": "Read"}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1"},
                {"type": "tool_result", "tool_use_id": "t2"}]}},
            {"type": "user", "message": {"role": "user",
                                         "content": "[Request interrupted by user]"}},
            {"type": "user", "message": {"role": "user", "content": "use tabs"}},
        ])
        jsonl(os.path.join(claude, "c1", "subagents", "agent-x.jsonl"), [
            {"type": "user", "cwd": app, "message": {"role": "user", "content": "x"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t9", "name": "Write"}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t9"}]}},
            {"type": "user", "message": {"role": "user", "content": "child"}}])
        self.app = app

    def run_cli(self, *args):
        proc = support.run([CLI, *args], env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_stats_count_top_level_sessions_under_the_root(self):
        self.assertEqual(self.run_cli("mine", "--stats").splitlines(), [
            "omp: sessions=1 writes=4 prompts_after_write=2",
            "claude: sessions=1 writes=1 prompts_after_write=1"])

    def test_rows_are_the_prompts_after_a_writing_turn(self):
        rows = [json.loads(line) for line in self.run_cli("mine").splitlines()]
        self.assertEqual([(r["host"], r["prompt"], r["writes_in_turn"]) for r in rows], [
            ("omp", "rename it to foo", 2),
            ("omp", "use this key [redacted:40] instead", 1),
            ("claude", "use tabs", 1)])
        self.assertEqual({(r["session"], r["repo"]) for r in rows},
                         {("s1", self.app), ("c1", self.app)})
        self.assertEqual(rows[0]["cwd"], os.path.join(self.app, "sub"))

    def test_out_file_and_host_filter(self):
        out = os.path.join(self.home, "mined.jsonl")
        self.assertEqual(self.run_cli("mine", "--host", "claude", "--out", out), "")
        with open(out, encoding="utf-8") as fh:
            self.assertEqual([json.loads(line)["prompt"] for line in fh], ["use tabs"])

    def test_root_excludes_sessions_outside_it(self):
        other = os.path.join(self.home, "Other")
        self.assertEqual(self.run_cli("mine", "--stats", "--host", "omp", "--root", other),
                         "omp: sessions=0 writes=0 prompts_after_write=0\n")

    def test_nested_subagent_files_and_tool_inputs_are_walked(self):
        # plan 055 part 1a-1b: the replay corpus joins transcript tool inputs to
        # ledger rows by call_id, so it walks nested subagent files and drops
        # omp's `i` key, which the hook payload the gate hashed never carried
        import importlib.machinery
        import importlib.util
        from unittest import mock
        sys.path.insert(0, support.HOOKS)
        import tezgah_integrity as ti
        loader = importlib.machinery.SourceFileLoader("taste_under_test", CLI)
        spec = importlib.util.spec_from_loader("taste_under_test", loader)
        taste = importlib.util.module_from_spec(spec)
        loader.exec_module(taste)
        sessions = os.path.join(self.home, ".omp", "agent", "sessions", "-app-")
        nested = os.path.join(sessions, "s1", "deeper", "worker.jsonl")
        args = {"path": "a.py", "content": "x = 1\n"}
        jsonl(nested, [
            {"type": "title"},
            '{"type":"session","id":"w1","cwd":%s,"parentSession":"s1"}'
            % json.dumps(self.app),
            {"type": "message", "timestamp": "2026-10-05T10:00:00.000Z",
             "message": {"role": "assistant", "content": [
                 {"type": "text", "text": "writing it"},
                 {"type": "toolCall", "id": "c1", "name": "write",
                  "arguments": dict(args, i="Writing the file")}]}}])
        with mock.patch.dict(os.environ, {"HOME": self.home}):
            top = [p for p, _ in taste.sessions("omp", self.roots)]
            every = [p for p, _ in taste.sessions("omp", self.roots, nested=True)]
        self.assertNotIn(nested, top)
        self.assertIn(nested, every)
        self.assertIn(os.path.join(sessions, "s1", "sub.jsonl"), every)
        self.assertEqual(taste.session_id("omp", nested), ("w1", "s1"))
        events = list(taste.walk_omp(nested, calls=True))
        calls = [e for e in events if e[0] == "call"]
        self.assertEqual(calls, [("call", "write", args, 1791194400.0)])
        self.assertEqual(ti.call_id(calls[0][1], calls[0][2]), ti.call_id("write", args))
        self.assertIn(("reply", "writing it", 1791194400.0), events)
        # without `calls` the walk is the frozen `mine` stream
        self.assertEqual(list(taste.walk_omp(nested)), [])


class Labeller(BaseHTTPRequestHandler):
    """The evaluation endpoint: a prompt with PREF is a preference, BROKEN a
    defect, anything else none."""
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append(body)
        answers = {}
        for qid, q in body["questions"].items():
            text = q["instructions"]
            answers[qid] = {"choice": "preference" if "PREF" in text
                            else "defect" if "BROKEN" in text else "none"}
        out = json.dumps({"answers": answers,
                          "usage": {"input_tokens": 1000, "output_tokens": 10}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class Judged(support.TempHome):
    def setUp(self):
        super().setUp()
        Labeller.seen = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Labeller)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%d/v1/systemone" % self.server.server_port

    def run_cli(self, *args, key=True):
        extra = {"TEZGAH_TYPESAFE_URL": self.url}
        if key:
            extra["TYPESAFE_API_KEY"] = "k"
        return support.run([CLI, *args], env=self.env(extra=extra))

    def samples(self):
        gold = [("preference", "PREF a"), ("preference", "PREF b"), ("preference", "c"),
                ("defect", "BROKEN d"), ("defect", "PREF e"),
                ("none", "f"), ("none", "PREF g")]
        samples = os.path.join(self.home, "samples.jsonl")
        labels = os.path.join(self.home, "labels.jsonl")
        jsonl(samples, [{"set": "s", "n": i, "text": t} for i, (_g, t) in enumerate(gold)]
              + [{"set": "s", "n": 99, "text": "unlabelled"}])
        jsonl(labels, [{"set": "s", "n": i, "label": g} for i, (g, _t) in enumerate(gold)])
        return samples, labels

    def test_measure_confusion_precision_recall(self):
        samples, labels = self.samples()
        proc = self.run_cli("measure", "--samples", samples, "--labels", labels, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["n"], 7)
        self.assertEqual(report["confusion"], {
            "preference": {"preference": 2, "defect": 0, "none": 1},
            "defect": {"preference": 1, "defect": 1, "none": 0},
            "none": {"preference": 1, "defect": 0, "none": 1}})
        self.assertEqual(report["per_class"], {
            "preference": {"precision": 0.5, "recall": 0.6667},
            "defect": {"precision": 1.0, "recall": 0.5},
            "none": {"precision": 0.5, "recall": 0.5}})
        self.assertEqual(report["usage"]["input_tokens"], 1000)
        self.assertEqual(report["usage"]["cost_usd"], 0.000042)
        # one request for the seven, the unlabelled sample never sent
        self.assertEqual(len(Labeller.seen), 1)
        self.assertEqual(len(Labeller.seen[0]["questions"]), 7)

    def test_measure_redacts_before_sending(self):
        token = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
        samples = os.path.join(self.home, "s.jsonl")
        labels = os.path.join(self.home, "l.jsonl")
        jsonl(samples, [{"set": "s", "n": 0, "text": "PREF use key " + token}])
        jsonl(labels, [{"set": "s", "n": 0, "label": "preference"}])
        proc = self.run_cli("measure", "--samples", samples, "--labels", labels)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        sent = json.dumps(Labeller.seen)
        self.assertIn("PREF use key", sent)
        self.assertNotIn(token, sent)

    def test_rate_per_repo_and_overall(self):
        mined = os.path.join(self.home, "mined.jsonl")
        rows = [("a", "PREF x"), ("a", "plain")] + [("b", "PREF %d" % i) for i in range(20)] \
            + [("c", "PREF last")]
        jsonl(mined, [{"repo": r, "prompt": p} for r, p in rows])
        proc = self.run_cli("rate", "--in", mined, "--limit", "22", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual((report["n"], report["preference"], report["rate"]), (22, 21, 0.9545))
        self.assertEqual(report["repos"], {
            "a": {"n": 2, "preference": 1, "rate": 0.5},
            "b": {"n": 20, "preference": 20, "rate": 1.0}})
        # twenty questions per request: 22 rows are two requests
        self.assertEqual([len(b["questions"]) for b in Labeller.seen], [20, 2])
        self.assertEqual(report["usage"]["input_tokens"], 2000)

    def test_no_judge_exits_2_and_sends_nothing(self):
        samples, labels = self.samples()
        mined = os.path.join(self.home, "mined.jsonl")
        jsonl(mined, [{"repo": "a", "prompt": "PREF"}])
        for args in (("measure", "--samples", samples, "--labels", labels),
                     ("rate", "--in", mined)):
            proc = self.run_cli(*args, key=False)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("no judge", proc.stderr)
        self.assertEqual(Labeller.seen, [])


class Decider(BaseHTTPRequestHandler):
    """TypeSafe and the chat fallback in one fake: the decision reads the state -
    PREF is a preference, BROKEN a defect - and every learning relation is
    `supports` for a preference. A `text` question is answered on the chat path."""
    seen = []
    typesafe_down = False

    def answers(self, state, questions):
        out = {}
        for qid, q in questions.items():
            if q["type"] == "text":
                out[qid] = {"text": "Name things in snake_case."}
                continue
            if qid == "kind":
                pick = "preference" if "PREF" in state else "defect" if "BROKEN" in state \
                    else "none"
            elif qid == "category":
                pick = "naming"
            elif qid == "scope":
                pick = "repository"
            else:
                pick = "supports" if "PREF" in state else "unrelated"
            out[qid] = {"choice": pick, "probabilities": {pick: 0.9}}
        return out

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        if type(self).typesafe_down and not self.path.endswith("/chat/completions"):
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.endswith("/chat/completions"):
            asked = json.loads(body["messages"][1]["content"])
            content = json.dumps({"answers": self.answers(asked["state"], asked["questions"])})
            reply = {"choices": [{"message": {"content": content}}],
                     "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
        else:
            reply = {"answers": self.answers(body["state"], body["questions"]),
                     "usage": {"input_tokens": 100, "output_tokens": 0}}
        out = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class Learn(support.TempHome):
    def setUp(self):
        super().setUp()
        Decider.seen, Decider.typesafe_down = [], False
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Decider)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        base = "http://127.0.0.1:%d" % self.server.server_port
        self.urls = {"TEZGAH_TYPESAFE_URL": base + "/v1/systemone",
                     "TEZGAH_OPENROUTER_URL": base + "/v1/chat/completions"}
        self.repo = self.make_repo("app")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        with open(os.path.join(self.repo, "a.py"), "w") as fh:
            fh.write("x = 1\n")
        self.store = os.path.join(self.repo, ".tezgah", "taste")
        rows = []
        for session, text in (("A", "PREF name it snake_case"), ("B", "PREF snake_case again"),
                              ("B", "BROKEN the test fails"), ("C", "thanks")):
            rows += [{"kind": "edit", "session": session, "path": "a.py",
                      "old": "x = 1", "new": "X = 1"},
                     {"kind": "prompt", "session": session, "text": text,
                      "ts": "2026-10-0%dT10:00:00Z" % (len(rows) // 2 + 1)}]
        for row in rows:
            tl.append(self.repo, "signals", row, strict=True)

    def cli(self, *args, typesafe=True, openrouter=False):
        extra = dict(self.urls)
        if typesafe:
            extra["TYPESAFE_API_KEY"] = "k"
        if openrouter:
            extra["OPENROUTER_API_KEY"] = "o"
        repo = [] if "--repo" in args else ["--repo", self.repo]
        return support.run([CLI, *args, *repo], env=self.env(extra=extra))

    def listed(self):
        proc = self.cli("list", "--json", "--all")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def rows(self, table):
        return tl.rows(self.repo, table)

    def learnings(self):
        """The listed learnings without their confidence, which moves with the clock."""
        return [dict(v, confidence=None) for v in self.listed()]

    def test_two_sessions_of_one_preference_make_one_active_learning(self):
        proc = self.cli("learn", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual((report["signals"], report["jev"], report["preference"],
                          report["defect"], report["none"]), (4, 4, 2, 1, 1))
        [learning] = self.listed()
        self.assertEqual((learning["state"], learning["category"], learning["sessions"]),
                         ("active", "naming", ["A", "B"]))
        self.assertEqual(learning["evidence"][0]["paths"], ["a.py"])
        # the defect went to its own table and never into the ledger
        [defect] = self.rows("defects")
        self.assertIn("BROKEN", defect["text"])
        # every decision required TypeSafe: the chat fallback was never asked a decision
        self.assertTrue(all(p.endswith("/v1/systemone") for p, b in Decider.seen
                            if "kind" in b.get("questions", {})))
        # a second run decides nothing again
        again = json.loads(self.cli("learn", "--json").stdout)
        self.assertEqual(again["signals"], 0)
        with open(os.path.join(self.store, "naming", "taste.md")) as fh:
            self.assertIn("Confidence:", fh.read())

    def test_a_decision_from_another_provider_is_unverified_and_unapplied(self):
        proc = self.cli("learn", "--json", typesafe=False, openrouter=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual((report["jev"], report["unverified"]), (0, 4))
        self.assertEqual(self.listed(), [])
        self.assertTrue(all(r["verified"] is False and r["provider"] == "openrouter"
                            for r in self.rows("decisions")))
        self.assertEqual(self.rows("defects"), [])

    def test_a_decision_from_any_jev_carrier_is_verified_and_applied(self):
        # the caller's logic apart from any carrier's transport: Jev reached
        # through OpenRouter's System One endpoint is as typed as TypeSafe
        import contextlib
        import importlib.machinery
        import importlib.util
        import io
        from unittest import mock
        sys.path.insert(0, support.HOOKS)
        import tezgah_judge as tj
        loader = importlib.machinery.SourceFileLoader("taste_jev", CLI)
        taste = importlib.util.module_from_spec(importlib.util.spec_from_loader("taste_jev",
                                                                                loader))
        loader.exec_module(taste)
        asked = []

        def ask(state, questions, only=None, **_kw):
            asked.append(only)
            if only != ("jev",):
                return None
            return {"answers": Decider.answers(None, state, questions),
                    "usage": {"input_tokens": 100, "output_tokens": 0},
                    "model": "jev-latest", "provider": "jev-openrouter", "fallback": None}

        def cli(*args):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = taste.main(["tezgah-taste", *args, "--repo", self.repo])
            self.assertEqual(code, 0)
            return out.getvalue()

        with mock.patch.dict(os.environ, {"HOME": self.home}), \
                mock.patch.object(tj, "JEV_CARRIERS", ("typesafe", "jev-openrouter")), \
                mock.patch.object(tj, "available", lambda: False), \
                mock.patch.object(tj, "named", lambda only: [("jev-openrouter", "o")]
                                  if "jev" in only else []), \
                mock.patch.object(tj, "ask", ask):
            report = json.loads(cli("learn", "--json"))
            self.assertEqual((report["signals"], report["jev"], report["unverified"],
                              report["preference"]), (4, 4, 0, 2))
            self.assertNotIn("typesafe", report)
            self.assertTrue(all(r["verified"] and r["provider"] == "jev-openrouter"
                                for r in self.rows("decisions")))
            [learning] = self.listed()
            self.assertEqual(learning["state"], "active")
            # the typed rows label, calibrate and gate as TypeSafe's did
            for row in self.rows("decisions"):
                if row["kind"] == "preference":
                    cli("label", row["id"], "preference")
            self.assertEqual(json.loads(cli("calibrate", "--json"))["agree"], 2)
            gate = json.loads(cli("gate", "--json"))
            self.assertEqual(gate["after"]["turns"] + gate["before"]["turns"], 4)
        self.assertIn(("jev",), asked)

    def test_an_activated_learning_gets_a_written_line_from_a_generative_provider(self):
        self.cli("learn", typesafe=True, openrouter=True)
        [learning] = self.listed()
        self.assertEqual((learning["text"], learning["written"]),
                         ("Name things in snake_case.", True))

    def test_the_user_controls_each_learning(self):
        self.cli("learn")
        [learning] = self.listed()
        lid = learning["id"]
        self.assertEqual(self.cli("edit", lid, "--text", "Use snake_case.").returncode, 0)
        self.assertEqual(self.cli("accept", lid).returncode, 0)
        self.assertEqual(self.cli("export").returncode, 0)
        with open(os.path.join(self.repo, "AGENTS.md")) as fh:
            self.assertIn("- Use snake_case.", fh.read())
        self.assertEqual(self.cli("reject", lid).returncode, 0)
        self.assertEqual(self.listed()[0]["state"], "retired")
        self.assertEqual(self.cli("show", "nope").returncode, 2)

    def test_label_calibrate_and_gate(self):
        self.cli("learn")
        sample = self.cli("label", "--n", "2")
        self.assertEqual(sample.returncode, 0, sample.stderr)
        ids = [line.split()[0] for line in sample.stdout.splitlines()[:-1]]
        self.assertEqual(len(ids), 2)
        for row in self.rows("decisions"):
            if row["kind"] == "preference":
                self.assertEqual(self.cli("label", row["id"], "preference").returncode, 0)
        cal = json.loads(self.cli("calibrate", "--json").stdout)
        self.assertEqual((cal["agree"], cal["labelled_preference_decisions"]), (2, 2))
        self.assertFalse(cal["rules_allowed"])
        self.assertEqual(self.cli("label", "nope", "preference").returncode, 2)
        gate = json.loads(self.cli("gate", "--json").stdout)
        self.assertEqual(gate["after"]["turns"] + gate["before"]["turns"], 4)
        self.assertFalse(gate["stopped"])

    def test_learn_from_transcripts_reads_this_repository_s_sessions(self):
        sessions = os.path.join(self.home, ".omp", "agent", "sessions", "-app-")
        call = {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "edit", "arguments": {"path": "a.py"}}]}}
        for sid in ("t1", "t2"):
            jsonl(os.path.join(sessions, sid + ".jsonl"), [
                '{"type":"session","id":"%s","cwd":%s}' % (sid, json.dumps(self.repo)),
                omp_user("build it"), call, omp_tool("edit"),
                omp_user("PREF use snake_case")])
        proc = self.cli("learn", "--from-transcripts", "--host", "omp", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["signals"], 2)
        [learning] = self.listed()
        self.assertEqual((learning["state"], learning["sessions"]), ("active", ["t1", "t2"]))
        self.assertEqual(learning["evidence"][0]["paths"], ["a.py"])
        # a new session that sorts first shifts no earlier id: nothing is re-decided
        jsonl(os.path.join(sessions, "a0.jsonl"), [
            '{"type":"session","id":"a0","cwd":%s}' % json.dumps(self.repo),
            omp_user("build"), call, omp_tool("edit"), omp_user("PREF snake_case")])
        again = json.loads(self.cli("learn", "--from-transcripts", "--host", "omp",
                                    "--json").stdout)
        self.assertEqual(again["signals"], 1)
        [learning] = self.listed()
        self.assertEqual(len(learning["evidence"]), 3, "a signal was applied twice")

    def test_judge_off_sends_nothing_although_a_typesafe_key_resolves(self):
        config = os.path.join(self.home, ".config", "tezgah")
        os.makedirs(config, exist_ok=True)
        open(os.path.join(config, "judge-off"), "w").close()
        proc = self.cli("learn")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(Decider.seen, [])

    def test_no_fallback_never_asks_another_provider(self):
        # every signal once through TypeSafe, two of them preferences in two
        # sessions: one learning goes active, and no line is written for it
        proc = self.cli("learn", "--no-fallback", "--json", openrouter=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        [learning] = self.listed()
        self.assertEqual((learning["state"], learning["written"]), ("active", False))
        self.assertFalse(any(p.endswith("/chat/completions") for p, _b in Decider.seen),
                         "--no-fallback asked the chat provider for the line")
        # TypeSafe down: nothing is asked of the chat provider, nothing recorded
        tl.append(self.repo, "signals", {"kind": "edit", "session": "D", "path": "a.py"},
                  strict=True)
        tl.append(self.repo, "signals", {"kind": "prompt", "session": "D", "text": "PREF tabs",
                                         "ts": "2026-10-07T10:00:00Z"}, strict=True)
        Decider.seen, Decider.typesafe_down = [], True
        report = json.loads(self.cli("learn", "--no-fallback", "--json",
                                     openrouter=True).stdout)
        self.assertEqual((report["unanswered"], report["unverified"]), (1, 0))
        self.assertFalse(any(p.endswith("/chat/completions") for p, _b in Decider.seen))
        self.assertFalse(any(r.get("verified") is False for r in self.rows("decisions")))

    def test_no_taste_mark_refuses_to_learn(self):
        open(os.path.join(self.repo, ".no-taste"), "w").close()
        self.assertEqual(self.cli("learn").returncode, 2)
        self.assertEqual(Decider.seen, [])
        self.assertFalse(os.path.exists(
            os.path.join(self.home, ".config", "tezgah", "taste", "ledger.lock")))

    def test_a_workspace_that_came_with_the_clone_is_never_opened(self):
        # `.tezgah` a symlink, the shape a tracked `.tezgah -> notes` checks out
        # as: its files are the project's data, so no command imports, renames
        # or creates anything in it
        cloned = self.make_repo("cloned")
        subprocess.run(["git", "init", "-q", cloned], check=True)
        legacy = os.path.join(cloned, "notes", "taste", "ledger.json")
        os.makedirs(os.path.dirname(legacy))
        with open(legacy, "w") as fh:
            json.dump({"v": 1, "learnings": {}, "meta": {}}, fh)
        os.symlink("notes", os.path.join(cloned, ".tezgah"))
        for args in (("learn",), ("list",), ("show", "t0001"), ("accept", "t0001"),
                     ("reject", "t0001"), ("edit", "t0001", "--text", "x"), ("export",),
                     ("label",), ("calibrate",), ("gate",)):
            proc = self.cli(*args, "--repo", cloned)
            self.assertEqual(proc.returncode, 2, (args, proc.stdout))
            self.assertIn("came with the repository", proc.stderr)
        self.assertEqual(os.listdir(os.path.dirname(legacy)), ["ledger.json"])
        self.assertEqual(Decider.seen, [])

    def test_a_second_writer_exits_2_while_the_ledger_is_held(self):
        self.cli("learn")
        [learning] = self.listed()
        before = self.learnings()
        # another writer holds the lock: a child process, as a real learn would be
        holder = subprocess.Popen(
            [sys.executable, "-c",
             "import sys, time; sys.path.insert(0, %r); import tezgah_taste_ledger as tl\n"
             "with tl.locked():\n    print('held', flush=True); time.sleep(30)"
             % support.HOOKS],
            stdout=subprocess.PIPE, text=True, env=self.env())
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        seen = len(Decider.seen)
        # one lock for the machine: another repository's learn waits on it too,
        # since every command also rewrites the user ledger
        other = self.make_repo("other")
        subprocess.run(["git", "init", "-q", other], check=True)
        for args in (("learn",), ("reject", learning["id"]), ("learn", "--repo", other)):
            proc = self.cli(*args)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("in use (pid %d)" % holder.pid, proc.stderr)
        self.assertEqual(len(Decider.seen), seen, "a refused learn still asked the judge")
        self.assertEqual(self.learnings(), before)
        holder.kill()
        holder.wait()
        holder.stdout.close()
        self.assertEqual(self.cli("reject", learning["id"]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
