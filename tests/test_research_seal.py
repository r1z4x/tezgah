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
import shutil
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
                                 warnings, False)
        return errors, warnings

    def seal(self, repo, slug="q"):
        return tr.line_state(repo, slug).get(tr.SEAL)


class Agreement(SealCase):
    def test_a_sealed_line_s_order_is_the_check_s_order_on_every_shape(self):
        """The seal holds blob hashes and no verdict: while the blobs are intact
        the order is re-derived from git, so a done line reads exactly what the
        open line read."""
        for how in ("ordered", "both", "after", "uncommitted", "unrun"):
            with self.subTest(how=how):
                repo = self.repo(how)
                self.line(repo)
                self.shape(repo, how)
                errors, warnings = self.check_order(repo) if how != "unrun" \
                    else ([], [])
                left, problem = tr.close_line(repo, "q", "fixture", "2026-10-06")
                self.assertIsNone(problem)
                seal = self.seal(repo)
                self.assertEqual((seal["verdict"], seal["date"]),
                                 ("sealed", "2026-10-06"))
                row = seal["experiments"]["h1"]
                self.assertNotIn("order", row)
                d = self.exp_dir(repo)
                self.assertEqual(row["protocol"],
                                 tr._digest(os.path.join(d, "protocol.md")))
                results = os.path.join(d, "results.jsonl")
                self.assertEqual(row["results"], tr._digest(results)
                                 if os.path.isfile(results) else None)
                found_e, found_w = tr.check_line(repo, "q")
                for message in errors:
                    self.assertIn(message, found_e)
                for message in warnings:
                    self.assertIn(message, found_w)

    def test_close_then_commit_leaves_no_order_finding(self):
        """A seal made while the results were still uncommitted freezes no
        transient verdict: committing them afterwards clears the warning."""
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "uncommitted")
        self.assertTrue(hit("not committed yet", self.check_order(repo)[1]))
        tr.close_line(repo, "q", "fixture", "2026-10-06")
        self.commit(repo, "results", when=AFTER)
        errors, warnings = tr.check_line(repo, "q")
        self.assertFalse(hit("not committed", errors + warnings), warnings)
        self.assertFalse(hit("protocol", [e for e in errors if "order" in e]))
        self.assertFalse(hit("sealed", errors), errors)

    def test_an_ordered_seal_records_the_commits_as_information(self):
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "ordered")
        tr.close_line(repo, "q", "fixture", "2026-10-06")
        commits = self.seal(repo)["experiments"]["h1"]["commits"]
        self.assertRegex(commits["protocol"], "^[0-9a-f]{40}$")
        self.assertRegex(commits["results"], "^[0-9a-f]{40}$")
        self.assertNotEqual(commits["protocol"], commits["results"])

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
        self.assertIn("h1", self.seal(repo)["experiments"])


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
        shutil.rmtree(os.path.join(tr.line_dir(repo, "q"), "experiments", "h1"))
        self.assertTrue(hit("experiment h1 was removed after the line was sealed",
                            tr.check(repo)["q"]["errors"]))

    def test_an_intact_seal_adds_nothing(self):
        repo = self.sealed_line()
        self.assertFalse(hit("sealed", tr.check(repo)["q"]["errors"]))
        self.assertFalse(hit("sealed", [err for _slug, err in tr.failing(repo)]))

    def test_the_note_hashes_a_done_line_and_checks_an_open_one(self):
        """Plan 058 part 4: the session note verifies a line under done/ by its
        seal hashes alone, not by a full `check_line`, so a sealed line's other
        findings stay with `check` and the note keeps its cost budget."""
        repo = self.sealed_line()
        os.remove(os.path.join(tr.line_dir(repo, "q"), "findings.md"))
        self.line(repo, slug="o")
        os.remove(os.path.join(tr.line_dir(repo, "o"), "findings.md"))
        self.assertTrue(hit("findings.md is missing", tr.check(repo)["q"]["errors"]))
        rows = tr.failing(repo)
        self.assertEqual(sorted({slug for slug, _err in rows}), ["o"], rows)
        d = os.path.join(tr.line_dir(repo, "q"), "experiments", "h1")
        self.append_line(os.path.join(d, "results.jsonl"), {"run": 2, "p95": 0.1})
        self.assertTrue(hit("experiment h1: results.jsonl changed after the line "
                            "was sealed", [e for s, e in tr.failing(repo) if s == "q"]))


class DefaultCheck(SealCase):
    """ADR 015: the no-slug `check` reports the open lines in full and a line
    under done/ by its seal hashes plus a one-line count; `--all-lines` runs
    every line in full, and `check <slug>` stays that line's full answer."""

    def done_and_open(self, name="repo"):
        repo = self.repo(name)
        self.line(repo)
        self.shape(repo, "ordered")
        tr.close_line(repo, "q", "fixture", "2026-10-06")
        os.remove(os.path.join(tr.line_dir(repo, "q"), "findings.md"))
        self.line(repo, slug="o")
        return repo

    def test_the_default_skips_a_done_line_s_findings_and_counts_it(self):
        repo = self.done_and_open()
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("FAIL q", proc.stdout)
        self.assertIn("research: 1 line(s) ok", proc.stdout)
        self.assertIn("research: 1 done line(s): 1 checked by their seal, 0 unsealed "
                      "(not checked); `check --all-lines` runs them in full",
                      proc.stdout)
        self.assertEqual(sorted(tr.check(repo, all_lines=False)), ["o"])

    def test_all_lines_and_a_slug_run_the_done_line_in_full(self):
        repo = self.done_and_open()
        for args in (("check", "--all-lines"), ("check", "q")):
            with self.subTest(args=args):
                proc = self.cli(repo, *args)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("FAIL q: findings.md is missing", proc.stdout)
                self.assertNotIn("done line(s)", proc.stdout)

    def test_a_broken_seal_still_reaches_the_default(self):
        repo = self.done_and_open()
        d = os.path.join(tr.line_dir(repo, "q"), "experiments", "h1")
        self.append_line(os.path.join(d, "results.jsonl"), {"run": 2, "p95": 0.1})
        proc = self.cli(repo, "check", "--json")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        out = proc.stdout.splitlines()
        start = [n for n, line in enumerate(out) if line.startswith("{")]
        report = json.loads("\n".join(out[start[0]:]))
        self.assertEqual(sorted(report), ["o", "q"])
        self.assertEqual(report["q"]["errors"], [
            "experiment h1: results.jsonl changed after the line was sealed "
            "(2026-10-06) - a sealed line's plan and run are its record"])

    def set_state(self, repo, edit):
        """Rewrite the done line's state.json with `edit(state)`, or with the
        raw text `edit` when it is a string."""
        path = os.path.join(tr.line_dir(repo, "q"), "state.json")
        if isinstance(edit, str):
            self.write(path, edit)
            return
        state = json.loads(read(path))
        edit(state)
        self.write(path, json.dumps(state))

    def test_an_unsealed_done_line_is_counted_apart_and_not_failed(self):
        repo = self.done_and_open()
        self.set_state(repo, lambda s: s.pop(tr.SEAL))
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("research: 1 done line(s): 0 checked by their seal, 1 unsealed "
                      "(not checked)", proc.stdout)
        self.assertEqual(tr.failing(repo), [])

    def test_a_done_line_whose_seal_cannot_be_read_fails_the_default(self):
        """A broken state.json or a seal of the wrong shape must not silence a
        done line: it is a FAIL row in the default check and in the note."""
        shapes = {"unparseable state.json": "{not json",
                  "seal not an object": lambda s: s.update({tr.SEAL: "sealed"}),
                  "seal without experiments": lambda s: s.update(
                      {tr.SEAL: {"verdict": "sealed", "experiments": []}})}
        for n, (label, edit) in enumerate(shapes.items()):
            with self.subTest(label):
                repo = self.done_and_open("repo%d" % n)
                self.set_state(repo, edit)
                proc = self.cli(repo, "check")
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("FAIL q: ", proc.stdout)
                self.assertEqual({s for s, _e in tr.failing(repo)}, {"q"})

    def test_status_reads_a_done_line_by_its_seal(self):
        """Plan 058 part 4: `status` (`summary`) reads a done line the way the
        default check does, so its other findings stay with --all-lines."""
        repo = self.done_and_open()
        self.assertIn("q: done, seal ok", tr.summary(repo))
        d = os.path.join(tr.line_dir(repo, "q"), "experiments", "h1")
        self.append_line(os.path.join(d, "results.jsonl"), {"run": 2, "p95": 0.1})
        self.assertIn("q: done, 1 seal problem(s)", tr.summary(repo))
        self.set_state(repo, lambda s: s.pop(tr.SEAL))
        self.assertIn("q: done, unsealed (not checked)", tr.summary(repo))


class HistoryLost(SealCase):
    """ADR 009: the lines concluded before seals existed take a `history-lost`
    verdict - built here, applied to a real workspace only by the owner. Only an
    order the lost history left undecidable takes it; a real violation stays."""

    LOST = "added in different histories"

    def ws_commit(self, repo, *paths, when=BEFORE):
        ws = os.path.join(repo, ".tezgah")
        self.git(ws, "add", "-f", *[os.path.relpath(p, ws) for p in paths])
        self.git(ws, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                 "commit", "-q", "-m", "ws", when=when)

    def unseal(self, repo):
        path = os.path.join(tr.line_dir(repo, "q"), "state.json")
        state = json.loads(read(path))
        del state[tr.SEAL]
        self.write(path, json.dumps(state))

    def pre_seal_line(self):
        """A line under done/ with no seal: h1's protocol is committed only in the
        project and its results only in the private repository (the history
        that ordered them is gone), h2 is ordered in the private repository."""
        repo = self.repo()
        self.line(repo)
        shutil.rmtree(os.path.join(repo, ".tezgah", ".git"))
        self.protocol(repo)
        self.commit(repo, "protocol, in the project", when=BEFORE)
        self.git(os.path.join(repo, ".tezgah"), "init", "-q")
        d1 = self.results(repo, analysis=False)
        self.ws_commit(repo, os.path.join(d1, "results.jsonl"), when=AFTER)
        d2 = self.protocol(repo, h="h2")
        self.ws_commit(repo, os.path.join(d2, "protocol.md"))
        self.results(repo, h="h2", analysis=False)
        self.ws_commit(repo, os.path.join(d2, "results.jsonl"), when=AFTER)
        tr.close_line(repo, "q", "fixture", "2026-10-01")
        self.unseal(repo)
        return repo

    def test_the_verdict_replaces_the_lost_order_and_keeps_what_was_found(self):
        repo = self.pre_seal_line()
        before = tr.check_line(repo, "q")[0]
        self.assertTrue(hit(self.LOST, before), before)
        record, problem = tr.retro_seal(repo, "q", ACK, "2026-10-06")
        self.assertIsNone(problem)
        self.assertEqual((record["verdict"], record["ack"]), (tr.HISTORY_LOST, ACK))
        rows = record["experiments"]
        self.assertEqual(rows["h1"]["order"], tr.HISTORY_LOST)
        self.assertIn(self.LOST, rows["h1"]["finding"])
        # an order that still checks is not written off: it stays re-derived
        self.assertNotIn("order", rows["h2"])
        errors, warnings = tr.check_line(repo, "q")
        self.assertFalse(hit(self.LOST, errors), errors)
        self.assertTrue(hit("experiment h1: the protocol order is not provable - the "
                            "history that held it was lost", warnings), warnings)
        self.assertTrue(hit(ACK, warnings))
        strict = tr.check_line(repo, "q", strict=True)[0]
        self.assertTrue(hit("history that held it was lost", strict), strict)
        self.assertIn("sealed: history lost", read(
            os.path.join(tr.line_dir(repo, "q"), "log.md")))

    def test_a_real_violation_is_refused_and_stays_an_error(self):
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "both")
        tr.close_line(repo, "q", "fixture", "2026-10-01")
        self.unseal(repo)
        record, problem = tr.retro_seal(repo, "q", ACK)
        self.assertIsNone(record)
        self.assertIn(BOTH_TOGETHER, problem)
        self.assertNotIn(tr.SEAL, tr.line_state(repo, "q"))
        self.assertTrue(hit(BOTH_TOGETHER, tr.check_line(repo, "q")[0]))
        proc = self.cli(repo, "seal", "q", "--history-lost", "--ack", ACK)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(BOTH_TOGETHER, proc.stdout)

    def test_a_line_whose_order_still_checks_has_nothing_lost(self):
        repo = self.repo()
        self.line(repo)
        self.shape(repo, "ordered")
        tr.close_line(repo, "q", "fixture", "2026-10-01")
        self.unseal(repo)
        self.assertIn("nothing to seal as lost", tr.retro_seal(repo, "q", ACK)[1])

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
