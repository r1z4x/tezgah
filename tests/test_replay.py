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
import unittest

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

    def cli(self, *args):
        proc = subprocess.run([sys.executable, CLI, "replay", *args], capture_output=True,
                              text=True, env=self.env(), timeout=120)
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
        self.assertEqual((rep["stop_false_refusal"]["k"], rep["stop_false_refusal"]["n"]),
                         (1, 1))
        self.assertIn("fall back to log-only", self.cli("--report", *files))


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
