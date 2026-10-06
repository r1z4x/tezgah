"""bin/tezgah-taste: mine on a fixture HOME, measure and rate on a loopback judge.

The judge is a local fake of the evaluation endpoint (TEZGAH_TYPESAFE_URL) that
labels each question by a word in its prompt, so the confusion, precision and
recall the CLI prints are checked against arithmetic done here by hand.
"""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
