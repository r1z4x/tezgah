"""hooks/tezgah_shapes.py + bin/tezgah-status --failure-shapes: the recurring
refusal fold.

The corpus is synthetic ledgers under a throwaway HOME, so the machine's own
ledgers never enter an assertion. Every case here reads the report a maintainer
reads; none of them expects a refusal, because the fold is a report and not a
gate.
"""
import json
import os
import sys
import unittest

import support
from support import TempHome, run_json

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402
import tezgah_shapes as ts  # noqa: E402


class FailureShapes(TempHome):
    """The fold over a synthetic corpus, read through the CLI."""

    def setUp(self):
        super().setUp()
        self.evidence = os.path.join(self.home, ".cache", "tezgah", "evidence")
        os.makedirs(self.evidence)
        self.envv = self.env()
        self.cli = os.path.join(support.REPO, "bin", "tezgah-status")

    def deny(self, session, count, rule="loop", tail="identical call"):
        """`count` deny rows under one rule in one session's ledger, written by
        the real writer so the rows the fold reads are the rows a host writes."""
        path = os.path.join(self.evidence, session + ".jsonl")
        for _ in range(count):
            ti.note_path(path, "deny", "%s: %s" % (rule, tail))

    def report(self):
        out, proc = run_json([self.cli, "--failure-shapes", "--json"],
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_a_shape_in_five_sessions_is_reported_and_one_in_four_is_not(self):
        for i in range(5):
            self.deny("loop-%d" % i, 1, rule="loop")
        for i in range(4):
            self.deny("race-%d" % i, 1, rule="race")
        found = self.report()
        self.assertEqual(found["ledgers"], 9)
        self.assertEqual(found["recurring_sessions"], 5)
        self.assertEqual([s["rule"] for s in found["shapes"]], ["loop"])

    def test_one_damaged_ledger_costs_its_own_rows_not_the_report(self):
        # audit M-7: a committed line that is not a row raised out of every
        # cross-session reader, so one bad file killed the whole fold
        for i in range(5):
            self.deny("loop-%d" % i, 1, rule="loop")
        with open(os.path.join(self.evidence, "broken.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write("{not json\n[1, 2]\n")
        found = self.report()
        self.assertEqual(found["recurring_sessions"], 5)
        self.assertEqual([s["rule"] for s in found["shapes"]], ["loop"])

    def test_the_report_names_the_row_contracts_it_read(self):
        # A shape can move because the rule changed or because the row's meaning
        # did. A fold that read pre-version rows beside current ones has to say
        # so, for the same reason it prints the ledger count: an answer that
        # cannot tell the two apart attributes one to the other.
        self.deny("current", 1)
        with open(os.path.join(self.evidence, "older.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "deny", "ts": 1,
                                 "detail": "loop: hand written"}) + "\n")
        found = self.report()
        # The label is derived from the constant, not written down: this test is
        # about the report NAMING the contracts it read, and pinning the current
        # number would turn a version bump into a failure of a test about
        # something else.
        current = "v%d" % ti.ROW_VERSION
        self.assertEqual(sorted(found["row_versions"]), sorted([current, "unversioned"]))
        self.assertEqual(found["row_versions"][current], 1)
        self.assertEqual(found["row_versions"]["unversioned"], 1)

    def test_the_session_count_is_distinct_sessions_and_not_rows(self):
        # five rows in one session are one session, not five: a rule a single
        # long session kept tripping is not a shape that recurs across sessions
        self.deny("only", 5)
        self.assertEqual(self.report()["shapes"], [])
        for i in range(4):
            self.deny("more-%d" % i, 1)
        shape = self.report()["shapes"][0]
        self.assertEqual(shape["sessions"], 5)
        self.assertEqual(shape["fires"], 9)
        self.assertEqual(shape["fires_per_session"], 1.8)

    def test_the_rank_is_distinct_sessions_and_not_raw_fires(self):
        # the precision proxy's whole point: a rule firing 30 times inside 5
        # sessions must not outrank one firing once in each of 6, because a
        # count inflated by repeats within a session is not a recurring shape
        for i in range(6):
            self.deny("wide-%d" % i, 1, rule="wide")
        for i in range(5):
            self.deny("deep-%d" % i, 6, rule="deep")
        shapes = self.report()["shapes"]
        self.assertEqual([s["rule"] for s in shapes], ["wide", "deep"])
        self.assertEqual(shapes[1]["fires"], 30)
        self.assertEqual(shapes[1]["fires_per_session"], 6.0)

    def test_the_corpus_size_is_printed_so_an_empty_fold_reads_as_empty(self):
        path = os.path.join(self.evidence, "quiet.jsonl")
        ti.note_path(path, "run", "ls")
        found = self.report()
        self.assertEqual(found["shapes"], [])
        self.assertEqual(found["ledgers"], 1)
        proc = support.run([self.cli, "--failure-shapes"], env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1 ledgers", proc.stdout)

    def test_every_shape_carries_the_fields_and_types_the_report_promises(self):
        for i in range(5):
            self.deny("sink-%d" % i, 1, rule="sink", tail="a write to /tmp/x")
        shape = self.report()["shapes"][0]
        self.assertEqual(sorted(shape), ["commands", "fires",
                                         "fires_per_session", "rule",
                                         "sessions"])
        self.assertIsInstance(shape["rule"], str)
        self.assertIsInstance(shape["sessions"], int)
        self.assertIsInstance(shape["fires"], int)
        self.assertIsInstance(shape["fires_per_session"], float)
        self.assertIsInstance(shape["commands"], list)
        self.assertTrue(all(isinstance(c, str) for c in shape["commands"]))

    def test_the_three_most_common_command_shapes_most_common_first(self):
        # six sessions, four distinct refusal texts: the report keeps the three
        # that recur and drops the one that does not
        common = "Verification neutered: chained with `|| true`"
        second = "Test disable denied: adds a skip"
        third = "Test disable denied: rewrites a check"
        once = "Verification bypass denied: an env var skips the hooks"
        for session, rows in (("s0", [common, common]), ("s1", [common]),
                              ("s2", [second, second]), ("s3", [third]),
                              ("s4", [third]), ("s5", [once])):
            for tail in rows:
                self.deny(session, 1, rule="shortcut", tail=tail)
        shape = self.report()["shapes"][0]
        self.assertEqual(shape["sessions"], 6)
        self.assertEqual(shape["fires"], 8)
        self.assertEqual(shape["commands"],
                         [common, second, third])

    def test_a_credential_in_a_refusal_detail_is_reported_as_a_marker(self):
        token = "sk-live-abcdefghijklmnopqrstuv0123456789"
        for i in range(5):
            self.deny("secret-%d" % i, 1, rule="secret",
                      tail="would land a credential: Bearer " + token)
        shape = self.report()["shapes"][0]
        self.assertNotIn(token, json.dumps(shape))
        self.assertIn("[redacted:", shape["commands"][0])

    def test_the_fire_count_agrees_with_the_counters_fold(self):
        # two readers of one derivation - the label before the first colon of a
        # deny row's detail - pinned against each other here, so one rule name
        # cannot mean two things
        for i in range(5):
            self.deny("loop-%d" % i, 1, rule="loop")
        for i in range(5):
            self.deny("race-%d" % i, 2 if i == 0 else 1, rule="race")
        counts, proc = run_json([self.cli, "--counters", "--all", "--json"],
                                env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual({s["rule"]: s["fires"] for s in self.report()["shapes"]},
                         counts["denies"])
        self.assertEqual(counts["denies"], {"loop": 5, "race": 6})

    def test_the_shape_count_agrees_with_the_counters_fold(self):
        # P5: two readers of one derivation - a row whose kind is `shape` -
        # pinned against each other here, so the session reading and the corpus
        # fold cannot disagree about how often a reply shape fired. The `shape`
        # key is read off the row's kind, not a `detail` substring the way
        # `consult` and `codegen` are, so the `kinds` fold a `detail`-matching
        # implementation would still satisfy is checked beside it.
        session = "shapes"
        path = os.path.join(self.evidence, ti._slug(session) + ".jsonl")
        for detail in ("table-open,recap-close", "recap-close", "table-open"):
            ti.note_path(path, "shape", detail)
        one, proc = run_json([self.cli, "--counters", "--json"],
                             env=dict(self.envv, TEZGAH_SESSION=session))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(one["shape"], 3)
        counts, proc = run_json([self.cli, "--counters", "--all", "--json"],
                                env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(counts["ledgers"], 1)
        self.assertEqual(counts["shape"], one["shape"])
        self.assertEqual(counts["kinds"]["shape"], one["shape"])
        # and the plain printer carries it, not only the --json fold
        plain = support.run([self.cli, "--counters"],
                            env=dict(self.envv, TEZGAH_SESSION=session))
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertRegex(plain.stdout, r"(?m)^\s+shape\s+3$")


class RuleYield(TempHome):
    """The per-rule yield over a synthetic corpus: which live gate rules stopped
    firing, read against how many real ledgers they could have fired in."""

    SHIPPED = 1_000_000

    def setUp(self):
        super().setUp()
        self.evidence = os.path.join(self.home, "evidence")
        os.makedirs(self.evidence)
        self.files = []

    def ledger(self, name, when, rows=(), workspace=None):
        """One ledger whose last write is `when`, holding `rows` (kind, detail)."""
        path = os.path.join(self.evidence, name + ".jsonl")
        extra = {"workspace": workspace} if workspace else {}
        support.seed_ledger(path, [dict(kind=kind, detail=detail, ts=when, **extra)
                                   for kind, detail in [("run", "ls")] + list(rows)])
        self.files.append(path)
        return path

    def corpus(self, n, since, rows=()):
        for i in range(n):
            self.ledger("s%s-%d" % (since, i), since + 10 + i, rows)

    def rule(self, found, name):
        return next(r for r in found["rules"] if r["rule"] == name)

    def test_yield_zero_fires_over_a_wide_window_is_a_retire_candidate(self):
        self.corpus(ts.MIN_EXPOSURE, self.SHIPPED)
        found = ts.rule_yield(self.files, {"plan": self.SHIPPED})
        row = self.rule(found, "plan")
        self.assertEqual((row["fires"], row["exposure"]), (0, ts.MIN_EXPOSURE))
        self.assertEqual(row["mark"], "retire-candidate")

    def test_yield_zero_fires_in_a_new_rule_is_low_exposure_not_dead(self):
        # the ledgers written before the rule shipped are no exposure at all: a
        # rule a day old over a corpus of hundreds must not read as dead
        self.corpus(ts.MIN_EXPOSURE, self.SHIPPED - 10_000)
        self.corpus(3, self.SHIPPED)
        found = ts.rule_yield(self.files, {"plan": self.SHIPPED})
        row = self.rule(found, "plan")
        self.assertEqual((row["fires"], row["exposure"]), (0, 3))
        self.assertEqual(row["mark"], "low-exposure")
        self.assertEqual(found["real"], ts.MIN_EXPOSURE + 3)

    def test_yield_a_firing_rule_carries_no_mark(self):
        self.corpus(ts.MIN_EXPOSURE, self.SHIPPED)
        self.ledger("fired", self.SHIPPED + 5,
                    [("deny", "loop: identical call")] * 2)
        found = ts.rule_yield(self.files, {"loop": self.SHIPPED})
        row = self.rule(found, "loop")
        self.assertEqual((row["fires"], row["exposure"]),
                         (2, ts.MIN_EXPOSURE + 1))
        self.assertIsNone(row["mark"])

    def test_yield_fixture_ledgers_are_no_exposure(self):
        # a probe tree's ledger measures the harness, not use: the same exclusion
        # `counters_all` applies, so a thousand test runs cannot age a rule
        for i in range(ts.MIN_EXPOSURE):
            self.ledger("probe-%d" % i, self.SHIPPED + 10, workspace="/tmp/probe")
        found = ts.rule_yield(self.files, {"plan": self.SHIPPED})
        self.assertEqual((found["ledgers"], found["fixtures"], found["real"]),
                         (ts.MIN_EXPOSURE, ts.MIN_EXPOSURE, 0))
        self.assertEqual(self.rule(found, "plan")["mark"], "low-exposure")

    def test_yield_an_unknown_ship_date_is_never_read_as_dead(self):
        self.corpus(ts.MIN_EXPOSURE, self.SHIPPED)
        row = self.rule(ts.rule_yield(self.files, {"plan": None}), "plan")
        self.assertIsNone(row["exposure"])
        self.assertEqual(row["mark"], "low-exposure")

    def test_yield_a_rule_dates_from_its_last_reintroduction(self):
        # a rule removed and brought back has been live only since it came back
        def gate(*rules):
            return "".join("_deny(s, %r, r)\n" % rule for rule in rules)
        since = ts.continuous_since([(1, gate("loop", "task")),
                                     (2, gate("loop")),
                                     (3, gate("loop", "task"))])
        self.assertEqual(since, {"loop": 1, "task": 3})

    def test_yield_cli_exits_0_and_prints_the_corpus_it_read(self):
        evidence = os.path.join(self.home, ".cache", "tezgah", "evidence")
        os.makedirs(evidence)
        ti.note_path(os.path.join(evidence, "one.jsonl"), "run", "ls")
        cli = os.path.join(support.REPO, "bin", "tezgah-status")
        proc = support.run([cli, "--rule-yield"], env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1 ledgers read", proc.stdout)
        out, proc = run_json([cli, "--rule-yield", "--json"], env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["ledgers"], 1)
        self.assertIn("plan", [r["rule"] for r in out["rules"]])


class DenyRuns(unittest.TestCase):
    """Plan 055 part 8(a): the denial-budget fold is a report, never a gate."""

    @staticmethod
    def deny(rule):
        return {"kind": "deny", "detail": "%s: refused" % rule}

    def test_runs_of_three_per_rule_inside_one_turn(self):
        turn, began = {"kind": "turn"}, {"kind": "began", "detail": "ls"}
        rows = [turn, self.deny("drift"), {"kind": "drift", "detail": "25"},
                self.deny("drift"), self.deny("drift"),       # run of 3: counted
                began, self.deny("race"), self.deny("race"),  # 2: not a run
                turn, self.deny("race"),                      # a turn ends it
                self.deny("piped"), self.deny("piped"), self.deny("loop")]
        out = ts.deny_runs([rows])
        self.assertEqual(out["runs"], {"drift": 1})
        self.assertEqual(out["longest"], {"drift": 3, "race": 2, "piped": 2, "loop": 1})
        self.assertEqual((out["run_min"], out["session_min"], out["ledgers"]), (3, 20, 1))
        self.assertEqual(out["sessions_over"], 0)

    def test_a_refused_call_s_early_began_does_not_break_the_run(self):
        # the gate writes a call's `began` before its rules (plan 051), so
        # every deny row follows its own call's `began`; an allowed call's
        # outcome row still ends the run
        began = {"kind": "began", "detail": "pytest -q", "id": "c"}
        rows = [began, self.deny("loop")] * 3
        self.assertEqual(ts.deny_runs([rows])["runs"], {"loop": 1})
        rows = [began, self.deny("loop"), began, {"kind": "verify_ok", "id": "c"},
                began, self.deny("loop"), began, self.deny("loop")]
        self.assertEqual(ts.deny_runs([rows])["runs"], {})

    def test_sessions_with_twenty_denies(self):
        busy = [self.deny("drift"), {"kind": "run"}] * 20
        quiet = [self.deny("drift")] * 19
        out = ts.deny_runs([busy, quiet])
        self.assertEqual(out["sessions_over"], 1)
        self.assertEqual(out["runs"], {"drift": 1})

    def test_the_fold_changes_no_gate_behaviour(self):
        # the fold is not read by the gate: nothing in tezgah_gate names it
        with open(os.path.join(support.REPO, "hooks", "tezgah_gate.py"),
                  encoding="utf-8") as fh:
            self.assertNotIn("deny_runs", fh.read())


if __name__ == "__main__":
    unittest.main()
