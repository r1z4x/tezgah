"""The order seal a concluded or closed research line carries (plan 058, ADR 009).

A line sealed by `close` or `conclude` holds, per experiment, the sha256 of its
`protocol.md` and `results.jsonl` and the order verdict `_check_protocol_order`
gave when it was sealed. These cases pin that the seal agrees with the check on
the same fixtures, that an edit after the seal is reported by the default
no-slug `check` and by `failing()` (the session note), and that a line concluded
before seals existed takes the owner's `history-lost` verdict only on request.
Every workspace is a throwaway git repository under a temp HOME.
"""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tezgah_research as tr  # noqa: E402
from test_research import AFTER, BEFORE, BOTH_TOGETHER, Workspace, hit, read  # noqa: E402

ACK = "ADR 009: the owner chose history lost for the lines concluded before seals"


class SealCase(Workspace):
    def shape(self, repo, how, h="h1"):
        """One experiment of line `q` committed in the order `how` names."""
        if how == "ordered":
            self.protocol(repo, h=h)
            self.commit(repo, "protocol", when=BEFORE)
            self.results(repo, h=h)
            self.commit(repo, "results", when=AFTER)
        elif how == "both":
            self.protocol(repo, h=h)
            self.results(repo, h=h)
            self.commit(repo, "both", when=BEFORE)
        elif how == "after":
            self.results(repo, h=h)
            self.commit(repo, "results", when=BEFORE)
            self.protocol(repo, h=h)
            self.commit(repo, "protocol", when=AFTER)
        elif how == "uncommitted":
            self.protocol(repo, h=h)
            self.commit(repo, "protocol", when=BEFORE)
            self.results(repo, h=h)
        elif how == "unrun":
            self.protocol(repo, h=h)
            self.commit(repo, "protocol", when=BEFORE)

    def check_order(self, repo, h="h1"):
        """(errors, warnings) of `_check_protocol_order` on the open line now."""
        d = self.exp_dir(repo, h=h)
        errors, warnings = [], []
        tr._check_protocol_order(repo, h, os.path.join(d, "protocol.md"),
                                 os.path.join(d, "results.jsonl"), errors,
                                 warnings, False, [])
        return errors, warnings

    def seal(self, repo, slug="q"):
        return tr.line_state(repo, slug).get(tr.SEAL)


class Agreement(SealCase):
    def test_the_seal_verdict_is_the_check_s_verdict_on_every_shape(self):
        expected = {"ordered": "ordered", "both": "refused", "after": "refused",
                    "uncommitted": "undecided"}
        for how, order in expected.items():
            with self.subTest(how=how):
                repo = self.repo(how)
                self.line(repo)
                self.shape(repo, how)
                errors, warnings = self.check_order(repo)
                left, problem = tr.close_line(repo, "q", "fixture", "2026-10-06")
                self.assertIsNone(problem)
                seal = self.seal(repo)
                self.assertEqual(seal["verdict"], "sealed")
                self.assertEqual(seal["date"], "2026-10-06")
                row = seal["experiments"]["h1"]
                self.assertEqual(row["order"], order)
                self.assertEqual(row.get("finding"), (errors or warnings or [None])[0])
                d = self.exp_dir(repo)
                self.assertEqual(row["protocol"],
                                 tr._digest(os.path.join(d, "protocol.md")))
                self.assertEqual(row["results"],
                                 tr._digest(os.path.join(d, "results.jsonl")))
                # the done line's check reads the sealed verdict, in the class the
                # re-derivation gave it on the open line
                found_e, found_w = tr.check_line(repo, "q")
                for message in errors:
                    self.assertIn(message, found_e)
                for message in warnings:
                    self.assertIn(message, found_w)

    def test_an_ordered_seal_records_the_commits_as_information(self):
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "ordered")
        tr.close_line(repo, "q", "fixture", "2026-10-06")
        commits = self.seal(repo)["experiments"]["h1"]["commits"]
        self.assertRegex(commits["protocol"], "^[0-9a-f]{40}$")
        self.assertRegex(commits["results"], "^[0-9a-f]{40}$")
        self.assertNotEqual(commits["protocol"], commits["results"])

    def test_an_experiment_with_no_run_is_sealed_unrun(self):
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "unrun")
        tr.close_line(repo, "q", "fixture", "2026-10-06")
        row = self.seal(repo)["experiments"]["h1"]
        self.assertEqual((row["order"], row["results"]), ("unrun", None))

    def test_conclude_seals_the_line_too(self):
        repo = self.repo()
        base = self.line(repo)
        state = json.loads(read(os.path.join(base, "state.json")))
        state["success"] = [{"id": "S1", "criterion": "p95 drops",
                             "verdict": "met", "evidence": "experiments/h1"}]
        self.write(os.path.join(base, "state.json"), json.dumps(state))
        self.shape(repo, "ordered")
        problems, _state = tr.conclude_line(repo, "q", "2026-10-06")
        self.assertEqual(problems, [])
        self.assertTrue(tr.sealed(repo, "q"))
        self.assertEqual(self.seal(repo)["experiments"]["h1"]["order"], "ordered")


class Mutation(SealCase):
    """Falsification 1 of the R11 experiment: an edit to a sealed line's results
    and protocol must reach the default check and the session note."""

    def sealed_line(self):
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "ordered")
        tr.close_line(repo, "q", "fixture", "2026-10-06")
        self.assertEqual(tr._check_seal(tr.line_dir(repo, "q")), (
            [], {"h1": dict(self.seal(repo)["experiments"]["h1"],
                            date="2026-10-06", ack=None)}))
        return repo

    def test_an_edit_after_the_seal_reaches_check_and_failing(self):
        repo = self.sealed_line()
        d = os.path.join(tr.line_dir(repo, "q"), "experiments", "h1")
        self.append_line(os.path.join(d, "results.jsonl"), {"run": 2, "p95": 0.1})
        with open(os.path.join(d, "protocol.md"), "a") as fh:
            fh.write("prediction: rewritten after the run\n")
        want = ("experiment h1: protocol.md and results.jsonl changed after the "
                "line was sealed (2026-10-06)")
        self.assertTrue(hit(want, tr.check(repo)["q"]["errors"]),
                        tr.check(repo)["q"]["errors"])
        self.assertTrue(hit(want, [err for _slug, err in tr.failing(repo)]))
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(want, proc.stdout)

    def test_an_experiment_added_or_removed_after_the_seal_is_reported(self):
        repo = self.sealed_line()
        self.protocol(repo, h="h2")
        self.assertTrue(hit("experiment h2 was added after the line was sealed",
                            [err for _slug, err in tr.failing(repo)]))
        import shutil
        shutil.rmtree(os.path.join(tr.line_dir(repo, "q"), "experiments", "h1"))
        self.assertTrue(hit("experiment h1 was removed after the line was sealed",
                            tr.check(repo)["q"]["errors"]))

    def test_an_intact_seal_adds_nothing(self):
        repo = self.sealed_line()
        self.assertFalse(hit("sealed", tr.check(repo)["q"]["errors"]))
        self.assertFalse(hit("sealed", [err for _slug, err in tr.failing(repo)]))


class HistoryLost(SealCase):
    """ADR 009: the lines concluded before seals existed take a `history-lost`
    verdict - built here, applied to a real workspace only by the owner."""

    def pre_seal_line(self, how="both"):
        """A line under done/ with no seal: the shape of the 33 existing lines."""
        repo = self.repo()
        self.line(repo)
        self.shape(repo, how)
        self.protocol(repo, h="h2")
        self.commit(repo, "protocol h2", when=BEFORE)
        self.results(repo, h="h2")
        self.commit(repo, "results h2", when=AFTER)
        tr.close_line(repo, "q", "fixture", "2026-10-01")
        path = os.path.join(tr.line_dir(repo, "q"), "state.json")
        state = json.loads(read(path))
        del state[tr.SEAL]
        self.write(path, json.dumps(state))
        return repo

    def test_the_verdict_replaces_the_lost_order_and_keeps_what_was_found(self):
        repo = self.pre_seal_line()
        before = tr.check_line(repo, "q")[0]
        self.assertTrue(hit(BOTH_TOGETHER, before), before)
        record, problem = tr.retro_seal(repo, "q", ACK, "2026-10-06")
        self.assertIsNone(problem)
        self.assertEqual((record["verdict"], record["ack"]), (tr.HISTORY_LOST, ACK))
        rows = record["experiments"]
        self.assertEqual(rows["h1"]["order"], tr.HISTORY_LOST)
        self.assertIn(BOTH_TOGETHER, rows["h1"]["finding"])
        # an order that still checks is not written off
        self.assertEqual(rows["h2"]["order"], "ordered")
        errors, warnings = tr.check_line(repo, "q")
        self.assertFalse(hit(BOTH_TOGETHER, errors), errors)
        self.assertTrue(hit("experiment h1: the protocol order is not provable - the "
                            "history that held it was lost", warnings), warnings)
        self.assertTrue(hit(ACK, warnings))
        strict = tr.check_line(repo, "q", strict=True)[0]
        self.assertTrue(hit("history that held it was lost", strict), strict)
        self.assertIn("sealed: history lost", read(
            os.path.join(tr.line_dir(repo, "q"), "log.md")))

    def test_it_is_refused_without_an_ack_on_an_open_line_and_twice(self):
        repo = self.pre_seal_line()
        self.assertIn("--ack", tr.retro_seal(repo, "q", "  ")[1])
        self.line(repo, "open-one", question="another question")
        self.assertIn("not under research/done/",
                      tr.retro_seal(repo, "open-one", ACK)[1])
        self.assertIsNone(tr.retro_seal(repo, "q", ACK)[1])
        self.assertIn("already carries an order seal",
                      tr.retro_seal(repo, "q", ACK)[1])

    def test_the_cli_seals_with_the_owner_s_words(self):
        repo = self.pre_seal_line()
        proc = self.cli(repo, "seal", "q", "--history-lost")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        proc = self.cli(repo, "seal", "q", "--history-lost", "--ack", ACK)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("sealed q: 2 experiment(s), history lost for h1", proc.stdout)
        self.assertEqual(self.seal(repo)["ack"], ACK)


if __name__ == "__main__":
    unittest.main()
