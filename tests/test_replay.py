"""hooks/tezgah_replay.py through `bin/tezgah-gate replay`: the replay corpus.

The corpus is synthetic - ledgers and omp transcripts under a throwaway HOME -
so the machine's own ledgers never enter an assertion. Every exclusion the
corpus spec names (REPORT.md §4.4.3) has one fixture row the corpus must drop,
and the replay runs the real CLI, which runs the real sandbox child.
"""
import ast
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_gate as tg  # noqa: E402
import tezgah_integrity as ti  # noqa: E402
import tezgah_replay as tr  # noqa: E402

CLI = os.path.join(support.REPO, "bin", "tezgah-gate")
T0 = 1791194400          # 2026-10-05T10:00:00Z, after 34f63e3
CUTOFF = T0 + 500
SID = "01a0aaaa-0000-7000-8000-000000000001"
CHILD = "01a0aaaa-0000-7000-8000-000000000002"
OLD = "01a0aaaa-0000-7000-8000-000000000003"   # a ledger named before the hash suffix
PIPED = "python3 -m unittest discover -s tests | tail -5"
REPLY = "Tamamlandı, testler geçti."


def iso(ts):
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


def jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            # compact, the way omp writes: its cwd reader looks for `"type":"session"`
            fh.write((row if isinstance(row, str) else json.dumps(
                row, separators=(",", ":"))) + "\n")


def assistant(ts, *parts):
    return {"type": "message", "timestamp": iso(ts),
            "message": {"role": "assistant", "content": list(parts)}}


def call(name, args):
    return {"type": "toolCall", "id": "c", "name": name, "arguments": args}


class Corpus(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("app")
        evidence = os.path.join(self.home, ".cache", "tezgah", "evidence")
        self.evidence = evidence
        sessions = os.path.join(self.home, ".omp", "agent", "sessions", "-app-")
        self.race_args = {"path": os.path.join(self.repo, "c.py"), "content": "z = 3\n"}
        top = os.path.join(sessions, "s.jsonl")
        jsonl(top, [
            {"type": "title"},
            {"type": "session", "id": SID, "cwd": self.repo},
            {"type": "message", "message": {"role": "user", "content": "run the tests"}},
            assistant(T0 + 1, call("bash", {"command": "ls", "i": "Listing"})),
            assistant(T0 + 2, call("bash", {"command": PIPED, "i": "Testing"})),
            assistant(T0 + 5, call("write", dict(self.race_args, i="Writing"))),
            assistant(T0 + 6, {"type": "text", "text": REPLY})])
        self.write_args = {"path": os.path.join(self.repo, "a.py"), "content": "x = 1\n"}
        jsonl(os.path.join(sessions, "s", "worker.jsonl"), [
            {"type": "title"},
            {"type": "session", "id": CHILD, "cwd": self.repo, "parentSession": top},
            assistant(T0 + 3, call("write", dict(self.write_args, i="Writing")))])
        ws = self.repo
        bash = {"tool": "bash", "workspace": ws}
        jsonl(os.path.join(evidence, ti._slug(SID) + ".jsonl"), [
            {"kind": "turn", "ts": T0, "detail": "t1", "workspace": ws},
            dict(bash, kind="began", ts=T0 + 1, detail="ls",
                 id=ti.call_id("bash", {"command": "ls"})),
            {"kind": "run", "ts": T0 + 1, "detail": "ls", "exit": 0},
            {"kind": "deny", "ts": T0 + 2, "detail": "piped: a check piped into tail",
             "id": ti.call_id("bash", {"command": PIPED}), "workspace": ws},
            {"kind": "edit", "ts": T0 + 4, "detail": "a.py", "workspace": ws},
            {"kind": "route", "ts": T0 + 4, "detail": "tezgah-route tier=cheap"},
            {"kind": "deny", "ts": T0 + 4, "detail": "consent: destructive", "id": "c0",
             "workspace": ws},
            dict(bash, kind="began", ts=T0 + 4, detail="x" * ti.DETAIL_MAX, id="c1"),
            dict(bash, kind="began", ts=T0 + 4, detail="export K=[redacted:40]", id="c2"),
            # a race deny from before the ledger stored `target`: no edit row here
            # carries one, so the sheet cannot show its writer and leaves it off
            {"kind": "deny", "ts": T0 + 5, "detail": "race: Concurrent write refused",
             "id": ti.call_id("write", self.race_args), "workspace": ws},
            {"kind": "claim", "ts": T0 + 6, "detail": "blocked: no verify_ok",
             "id": ti._claim_key(REPLY, 1)},
            {"kind": "deny", "ts": CUTOFF + 100, "detail": "drift: long turn", "id": "c3",
             "workspace": ws}])
        jsonl(os.path.join(evidence, ti._slug(CHILD) + ".jsonl"), [
            {"kind": "began", "ts": T0 + 3, "detail": self.write_args["path"],
             "tool": "write", "workspace": ws,
             "id": ti.call_id("write", self.write_args)}])
        jsonl(os.path.join(evidence, ti._slug("fixture-sid") + ".jsonl"), [
            {"kind": "began", "ts": T0, "detail": "ls", "tool": "bash", "id": "f1",
             "workspace": "/tmp/fixture-tree"}])
        jsonl(os.path.join(evidence, ti._slug("probe-1") + ".jsonl"), [
            {"kind": "began", "ts": T0, "detail": "ls", "tool": "bash", "id": "p1",
             "workspace": ws}])
        old_args = {"path": os.path.join(self.repo, "b.py"), "content": "y = 2\n"}
        jsonl(os.path.join(sessions, "old.jsonl"), [
            {"type": "title"}, {"type": "session", "id": OLD, "cwd": self.repo},
            assistant(T0 + 7, call("write", dict(old_args, i="Writing")))])
        jsonl(os.path.join(evidence, OLD + ".jsonl"), [
            {"kind": "began", "ts": T0 + 7, "detail": old_args["path"], "tool": "write",
             "workspace": ws, "id": ti.call_id("write", old_args)}])

    def tree(self, root):
        out = {}
        for d, _, files in os.walk(root):
            for name in files:
                with open(os.path.join(d, name), "rb") as fh:
                    out[os.path.join(d, name)] = fh.read()
        return out

    def cli(self, *args, extra=None):
        proc = subprocess.run([sys.executable, CLI, "replay", *args], capture_output=True,
                              text=True, env=self.env(extra=extra), timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def replay(self):
        return json.loads(self.cli("--cutoff", str(CUTOFF), "--json"))

    def test_exclusions_join_and_fidelity(self):
        s = self.replay()
        self.assertEqual(s["ledgers"], {"read": 5, "fixture": 1, "test-polluted": 1,
                                        "kept": 3})
        self.assertEqual(s["excluded"], {"test-row": 1, "after-cutoff": 1,
                                         "retired-rule": 1, "capped": 1, "redacted": 1})
        self.assertEqual(s["cutoff"], CUTOFF)
        self.assertEqual((s["items"], s["joined"]), (6, 6))
        self.assertEqual(s["join"]["began:write:joined"], 2,
                         "omp's `i` key is dropped, and a legacy ledger name still joins")
        self.assertEqual(s["stop_text_fidelity"], 1)
        fid = s["fidelity"]
        self.assertEqual((fid["ledger/piped"]["agree"], fid["ledger/piped"]["n"]), (1, 1))
        self.assertEqual((fid["allow"]["agree"], fid["allow"]["n"]), (3, 3))
        self.assertEqual((fid["stop"]["agree"], fid["stop"]["n"]), (1, 1))
        self.assertEqual(fid["ledger"]["n_since"], 2)

    def test_writes_only_under_the_replay_cache(self):
        before_repo = self.tree(self.repo)
        before_ledgers = self.tree(self.evidence)
        status = subprocess.run(["git", "-C", support.REPO, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        s = self.replay()
        root = os.path.join(self.home, ".cache", "tezgah", "replay")
        self.assertTrue(s["run"].startswith(root + os.sep))
        self.assertEqual(os.path.realpath(s["run"]).split(os.sep)[:-1],
                         os.path.realpath(root).split(os.sep))
        self.assertEqual(sorted(os.listdir(s["run"])),
                         ["corpus.jsonl", "results.jsonl", "summary.json"])
        self.assertEqual(self.tree(self.repo), before_repo)
        self.assertEqual(self.tree(self.evidence), before_ledgers)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".tezgah")))
        self.assertEqual(subprocess.run(["git", "-C", support.REPO, "status", "--porcelain"],
                                        capture_output=True, text=True).stdout, status)
        self.assertEqual(os.stat(s["run"]).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(os.path.join(s["run"], "corpus.jsonl")).st_mode & 0o777,
                         0o600)

    def test_blind_sheet_and_report(self):
        s = self.replay()
        out = self.cli("--sheet")
        self.assertIn("(5 rows)", out)
        self.assertIn("left off (written before the ledger stored `target`): 1", out)
        with open(os.path.join(s["run"], "sheet.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        with open(os.path.join(s["run"], "sheet-key.jsonl"), encoding="utf-8") as fh:
            key = [json.loads(line) for line in fh]
        self.assertEqual(sorted(r["n"] for r in rows), [1, 2, 3, 4, 5])
        text = json.dumps(rows)
        for leak in ("piped", "blocked", "deny", "no verify_ok", "allow"):
            self.assertNotIn(leak, text)
        self.assertEqual(sorted(k["bucket"] for k in key),
                         ["allow", "allow", "allow", "deny:piped", "stop:block"])
        self.assertTrue(os.path.exists(os.path.join(s["run"], "instructions.md")))
        print_report = self.cli("--report")
        self.assertIn("no labels file", print_report)
        self.assertIn("race exemption bar", print_report)
        self.assertIn("not measurable on this corpus", print_report)
        labels = {"deny:piped": "allow", "stop:block": "honest", "allow": "allow"}
        files = []
        for rater, flip in (("owner", None), ("second", "allow")):
            path = os.path.join(self.home, rater + ".jsonl")
            done = set()
            rows_out = []
            for k in key:
                label = labels[k["bucket"]]
                if flip == k["bucket"] and flip not in done:
                    label, _ = "refuse", done.add(flip)
                rows_out.append({"set": k["set"], "n": k["n"], "label": label,
                                 "rater": rater})
            jsonl(path, rows_out)
            files += ["--labels", path]
        rep = json.loads(self.cli("--report", "--json", *files))
        # 5 pairs, 4 agree; rater 1 allow 4 honest 1, rater 2 allow 3 honest 1 refuse 1
        self.assertAlmostEqual(rep["kappa"], (0.8 - 13 / 25) / (1 - 13 / 25))
        self.assertEqual(rep["false_block"]["piped"]["k"], 1)
        self.assertEqual(rep["false_block"]["piped"]["n"], 1)
        # A rule with no item on the sheet is neither pooled nor rated (H2
        # amendment 2026-10-06); one with fewer items than its quota is pooled.
        self.assertEqual(rep["pooled"], ["piped"])
        self.assertEqual(rep["not_measurable"], ["drift", "race"])
        self.assertNotIn("race", rep["false_block"])
        self.assertNotIn("drift", rep["false_block"])
        self.assertEqual(rep["false_block"]["pooled"]["n"], 1)
        self.assertIn("false-block race     not measurable: no item of this rule is on "
                      "the sheet", self.cli("--report", *files))
        self.assertEqual((rep["stop_false_refusal"]["k"], rep["stop_false_refusal"]["n"]),
                         (1, 1))
        self.assertIn("fall back to log-only", self.cli("--report", *files))

    def test_label_model_through_the_judge_seam(self):
        """Rater 2 (H2 amendment 2026-10-07): one choice question per sheet row
        through the judge seam, against a local stub endpoint; secrets leave
        redacted, a reply without a valid label stays unlabelled, a second run
        asks only the unlabelled rows, and a one-rater report prints no rate."""
        s = self.replay()
        self.cli("--sheet")
        sheet = os.path.join(s["run"], "sheet.jsonl")
        with open(sheet, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        secret = "ghp_" + "a" * 36
        rows[0]["text"] += "\nexport K=" + secret
        jsonl(sheet, rows)
        prompt = os.path.join(self.home, "prompt.json")
        with open(prompt, "w", encoding="utf-8") as fh:
            json.dump({
                "replay-gate": {"instructions": "GATE RULES",
                                "criteria": {"refuse": "r", "allow": "a", "unsure": "u"}},
                "replay-stop": {"instructions": "STOP RULES",
                                "criteria": {"honest": "h", "false": "f", "unsure": "u"}}},
                fh)
        Stub.seen, Stub.bad = [], True
        server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        extra = {"TYPESAFE_API_KEY": "stub", "TEZGAH_TYPESAFE_URL":
                 "http://127.0.0.1:%d/v1/systemone" % server.server_address[1]}
        out = self.cli("--label-model", "--run", s["run"], "--prompt", prompt, extra=extra)
        self.assertEqual(len(Stub.seen), 5)
        self.assertIn("labelled 4 of 5 asked, 1 unanswered", out)
        self.assertIn("typesafe/jev-stub", out)
        self.assertIn("50 input tokens", out)
        sent = json.dumps(Stub.seen)
        self.assertNotIn(secret, sent)
        self.assertIn("[redacted:", sent)
        for body in Stub.seen:
            self.assertEqual(body["model"], "jev-latest")
            q = body["questions"]["label"]
            self.assertEqual(q["type"], "choice")
            self.assertEqual(q["instructions"], "GATE RULES" if "This call:" in body["state"]
                             else "STOP RULES")
        path = os.path.join(s["run"], "labels-model.jsonl")
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        with open(path, encoding="utf-8") as fh:
            got = [json.loads(line) for line in fh]
        self.assertEqual(sorted(r["n"] for r in got),
                         sorted(r["n"] for r in rows if r is not rows[0]))
        self.assertEqual({(r["rater"], r["model"], r["provider"]) for r in got},
                         {("model", "jev-stub", "typesafe")})
        self.assertEqual({r["set"] for r in rows}, {"replay-gate", "replay-stop"})
        for r in got:
            self.assertEqual(r["label"], "refuse" if r["set"] == "replay-gate" else "honest")
        Stub.seen, Stub.bad = [], False
        out = self.cli("--label-model", "--run", s["run"], "--prompt", prompt, extra=extra)
        self.assertEqual(len(Stub.seen), 1, "only the unlabelled row is asked again")
        self.assertIn("labelled 1 of 1 asked, 0 unanswered", out)
        report = self.cli("--report", "--run", s["run"], "--labels", path)
        self.assertIn("raters: model", report)
        self.assertIn("one rater", report)
        self.assertNotIn("Wilson", report)
        self.assertNotIn("stop missed-violation", report)
        # A run that dies mid-way keeps the rows already paid for: each answered
        # row is on disk before the next one is read. The prompt lacks the Stop
        # set, and the sheet puts its Stop row last, so the run raises there.
        os.remove(path)
        jsonl(sheet, sorted(rows, key=lambda r: r["set"] == "replay-stop"))
        with open(prompt, "w", encoding="utf-8") as fh:
            json.dump({"replay-gate": {"instructions": "GATE RULES", "criteria": {
                "refuse": "r", "allow": "a", "unsure": "u"}}}, fh)
        proc = subprocess.run([sys.executable, CLI, "replay", "--label-model", "--run",
                               s["run"], "--prompt", prompt], capture_output=True,
                              text=True, env=self.env(extra=extra), timeout=120)
        self.assertNotEqual(proc.returncode, 0)
        with open(path, encoding="utf-8") as fh:
            kept = [json.loads(line) for line in fh]
        self.assertEqual(sorted(r["n"] for r in kept),
                         sorted(r["n"] for r in rows if r["set"] == "replay-gate"))


class Stub(BaseHTTPRequestHandler):
    """A TypeSafe-shaped endpoint: `refuse` for a gate row, `honest` for a Stop
    row, and, while `bad`, a label outside the criteria for the row that carried
    a secret (so the failing row is fixed whatever order the rows are asked in)."""

    seen, bad = [], False

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append(body)
        gate = "This call:" in body["state"]
        label = ("maybe" if type(self).bad and "[redacted:" in body["state"]
                 else "refuse" if gate else "honest")
        data = json.dumps({"model": "jev-stub", "answers": {"label": {"choice": label}},
                           "usage": {"input_tokens": 10, "output_tokens": 0}}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class Pure(unittest.TestCase):
    def test_wilson_and_kappa(self):
        lo, hi = tr.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=4)
        self.assertAlmostEqual(hi, 0.7634, places=4)
        self.assertIsNone(tr.wilson(0, 0))
        self.assertAlmostEqual(tr.kappa([("a", "a"), ("b", "b"), ("a", "b"), ("a", "a")]),
                               0.5)
        self.assertIsNone(tr.kappa([]))

    def test_the_rule_label_is_deny_rule_only(self):
        # plan 055 part 3: `_deny_rule` is the one rule label; a third derivation
        # (a text-to-rule mapping inside the replay) fails here
        self.assertIs(tr.rule_of, ti._deny_rule)
        with open(tr.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=tr.__file__)
        rules = set(tg.DENY_RULES) | {"consent", "sink"}
        # SIDE_KINDS names row kinds (a `drift` mark row), not rules
        allowed = {"STRATA", "QUOTA", "RACE_RULE", "SIDE_KINDS"}
        for node in tree.body:
            if isinstance(node, ast.Assign) and {t.id for t in node.targets
                                                 if isinstance(t, ast.Name)} & allowed:
                continue
            # a rule name compared against, or listed in a literal, outside the
            # strata tables is a mapping; a field read (`row.get("workspace")`) is not
            for sub in ast.walk(node):
                parts = ([sub.left, *sub.comparators] if isinstance(sub, ast.Compare)
                         else [*sub.keys, *sub.values] if isinstance(sub, ast.Dict)
                         else sub.elts if isinstance(sub, (ast.Tuple, ast.List, ast.Set))
                         else sub.args if isinstance(sub, ast.Call) and getattr(
                             sub.func, "attr", "") in ("startswith", "endswith", "search",
                                                       "match", "split")
                         else [])
                for part in parts:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        self.assertNotIn(part.value, rules, "line %d" % part.lineno)

    def test_the_output_root_is_under_the_cache(self):
        import tezgah_paths as tp
        self.assertEqual(tr.replay_root(), os.path.join(tp.CACHE, "replay"))


if __name__ == "__main__":
    unittest.main()
