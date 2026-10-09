"""bin/tezgah-research record, due, commit --product and check's product key,
run as the real CLI in a throwaway repo (the Workspace fixture of test_research)."""
import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_research import CLI, Workspace  # noqa: E402

OBSERVATION = {"topic": "onboarding-drop", "from": [], "class": "user-verbatim",
               "source": "interview 3", "quote": "I gave up at step 2"}

# Hand-written rows dated in the past, so a decision can already be due: the
# writer stamps today and refuses an observe_after before it.
LEDGER = [
    dict(OBSERVATION, id="O1", type="O", date="2026-01-01"),
    {"id": "I1", "type": "I", "date": "2026-01-01", "topic": "onboarding-drop",
     "from": ["O1"], "statement": "step 2 loses users", "confidence": "high"},
    {"id": "M1", "type": "M", "date": "2026-01-01", "topic": "onboarding-drop",
     "from": ["I1"], "goal": "users finish onboarding", "signal": "step 2 done",
     "definition": "step 2 completions / step 2 views", "window": "7 days",
     "baseline": "31%", "direction": "up", "leading": True, "logged": "yes",
     "data": "events.step2"},
    {"id": "D2", "type": "D", "date": "2026-01-01", "topic": "onboarding-later",
     "from": ["I1", "M1"], "statement": "shorten step 2", "outcome": "fix",
     "metric": "M1", "threshold": ">= 40%", "observe_after": "2026-03-01",
     "reopen": "below 35% after a month"},
    {"id": "D1", "type": "D", "date": "2026-01-01", "topic": "onboarding-drop",
     "from": ["I1", "M1"], "statement": "split step 2", "outcome": "bet",
     "metric": "M1", "threshold": ">= 45%", "observe_after": "2026-02-01",
     "reopen": "below 35% after a month"},
]


class ProductCli(Workspace):
    def ledger(self, repo):
        return os.path.join(os.path.realpath(repo), ".tezgah", "product", "ledger.jsonl")

    def held(self, repo, rows):
        path = self.ledger(repo)
        self.write(path, "".join(json.dumps(r) + "\n" for r in rows))
        return path

    def raw(self, repo, *args, stdin=""):
        """The CLI with `stdin` as given, so a test can hand it text that is not JSON."""
        return subprocess.run([sys.executable, CLI] + list(args), input=stdin,
                              capture_output=True, text=True, env=self.env(),
                              cwd=repo, timeout=60)

    def report(self, repo):
        """`check --json`'s payload: the text lines come first and the JSON last,
        which is how test_research's --json case reads it too."""
        out = self.raw(repo, "check", "--json").stdout.splitlines()
        start = [n for n, line in enumerate(out) if line.startswith("{")]
        self.assertTrue(start, out)
        return json.loads("\n".join(out[start[0]:]))

    def test_record_prints_the_id_it_assigned(self):
        repo = self.repo()
        proc = self.raw(repo, "record", "O", stdin=json.dumps(OBSERVATION))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.strip(), "recorded O1")
        rows = [json.loads(line) for line in open(self.ledger(repo))]
        self.assertEqual([(r["id"], r["type"]) for r in rows], [("O1", "O")])

    def test_misuse_exits_2(self):
        repo = self.repo()
        for args, stdin in ((["record", "O"], "{not json"),
                            (["record", "O"], "[1, 2]"),
                            (["record"], json.dumps(OBSERVATION)),
                            (["record", "X"], json.dumps(OBSERVATION)),
                            (["due", "--yaml"], "")):
            proc = self.raw(repo, *args, stdin=stdin)
            self.assertEqual(proc.returncode, 2, (args, stdin, proc.stdout))
        self.assertFalse(os.path.exists(self.ledger(repo)))

    def test_a_refused_row_is_not_written(self):
        repo = self.repo()
        for kind, row in (("O", dict(OBSERVATION, **{"class": "rumour"})),
                          ("O", dict(OBSERVATION, type="I"))):
            proc = self.raw(repo, "record", kind, stdin=json.dumps(row))
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            lines = proc.stdout.strip().splitlines()
            self.assertTrue(lines)
            self.assertTrue(all(line.startswith("FAIL product: ") for line in lines),
                            lines)
        path = self.ledger(repo)
        self.assertFalse(os.path.exists(path) and open(path).read().strip())

    def test_due_lists_oldest_first_in_text_and_json(self):
        repo = self.repo()
        proc = self.raw(repo, "due")
        self.assertEqual((proc.returncode, proc.stdout.strip()),
                         (0, "product: nothing due"))
        self.held(repo, LEDGER)
        proc = self.raw(repo, "due")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertRegex(lines[0], r"^D1 onboarding-drop metric=M1 threshold=>= 45% "
                                   r"since 2026-02-01 \(\d+ days\)$")
        self.assertRegex(lines[1], r"^D2 onboarding-later metric=M1 ")
        proc = self.raw(repo, "due", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = json.loads(proc.stdout)
        self.assertEqual([r["id"] for r in rows], ["D1", "D2"])
        self.assertEqual(set(rows[0]), {"id", "topic", "metric", "threshold",
                                        "observe_after", "days_overdue"})

    def test_commit_product_stages_only_the_product_ledger(self):
        repo = self.repo()
        proc = self.raw(repo, "record", "O", stdin=json.dumps(OBSERVATION))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        ws = os.path.join(repo, ".tezgah")
        self.write(os.path.join(ws, "plans", "open", "001-x.md"), "# x\n")
        proc = self.raw(repo, "commit", "--product", "product: O1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.git(ws, "show", "--name-only", "--format=", "HEAD").split(),
                         ["product/ledger.jsonl"])
        self.assertIn("?? plans/", self.git(ws, "status", "--porcelain"))
        proc = self.raw(repo, "commit", "--product", "again")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("nothing to commit", proc.stdout)
        self.assertEqual(self.raw(repo, "commit", "--product").returncode, 2)

    def test_check_reports_the_product_ledger_only_when_there_is_one(self):
        repo = self.repo()
        self.line(repo)
        proc = self.raw(repo, "check")
        self.assertNotIn("product", proc.stdout)
        report = self.report(repo)
        self.assertNotIn("product", report)
        self.assertEqual(list(report), ["q"])
        self.held(repo, [dict(OBSERVATION, id="O1", type="O", date="2026-01-01",
                              **{"class": "rumour"})])
        proc = self.raw(repo, "check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertTrue(re.search(r"^FAIL product: ", proc.stdout, re.M), proc.stdout)
        report = self.report(repo)
        self.assertTrue(report["product"]["errors"])

    def test_check_resolves_a_product_token_with_no_ledger(self):
        repo = self.repo()
        self.write(os.path.join(repo, ".tezgah", "plans", "open", "001-x.md"),
                   "# x\n\nrests on product:D9 and a bare D62\n")
        proc = self.raw(repo, "check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        fails = [line for line in proc.stdout.splitlines()
                 if line.startswith("FAIL product: ")]
        self.assertTrue(fails and "D9" in fails[0], proc.stdout)
        self.assertFalse(any("D62" in line for line in fails), fails)


if __name__ == "__main__":
    unittest.main()
