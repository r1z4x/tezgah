"""hooks/tezgah_research.py, bin/tezgah-research, and the session research note.

Every workspace lives in a throwaway git repo under a temp HOME, so the
protocol-before-results rule is exercised against real commit history and no
test touches the repository it runs from.
"""
import json
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_research as tr  # noqa: E402

import support  # noqa: E402
from support import TempHome, run_json  # noqa: E402

CLI = os.path.join(REPO, "bin", "tezgah-research")

BEFORE = "2020-01-01T00:00:00+0000"
AFTER = "2021-06-06T00:00:00+0000"
NOT_A_PREDICTION = "not a prediction"
NOT_COMMITTED = "is not committed"


def read(path):
    with open(path) as fh:
        return fh.read()


def hit(needles, errors):
    """True when some error carries the needle."""
    return any(n in e for e in errors for n in ([needles] if
                                                isinstance(needles, str) else needles))


def named(errors, needle):
    return [e for e in errors if needle in e]


class Workspace(TempHome):
    """A research line inside a throwaway git repo, committed at fixed dates."""

    def repo(self, name="repo"):
        path = self.make_repo(name)
        self.git(path, "init", "-q")
        self.git(path, "config", "user.email", "test@example.invalid")
        self.git(path, "config", "user.name", "Test")
        return path

    def git(self, repo, *args, when=None):
        env = dict(os.environ)
        if when:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
        proc = subprocess.run(["git", "-C", repo] + list(args),
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0,
                         "%s: %s" % (" ".join(args), proc.stderr))
        return proc.stdout

    def commit(self, repo, message, when=None):
        self.git(repo, "add", "-A", "-f")
        self.git(repo, "-c", "commit.gpgsign=false", "commit", "-q",
                 "-m", message, when=when)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def line(self, repo, slug="q", question="does the change help?"):
        tr.init(repo, slug, question=question, created="2026-01-01")
        return tr.line_dir(repo, slug)

    def exp_dir(self, repo, slug="q", h="h1"):
        return os.path.join(tr.line_dir(repo, slug), "experiments", h)

    def protocol(self, repo, slug="q", h="h1"):
        d = self.exp_dir(repo, slug, h)
        self.write(os.path.join(d, "protocol.md"),
                   "# Protocol\n\nchange: cache the lookups\nprediction: p95 drops\n")
        return d

    def results(self, repo, slug="q", h="h1", analysis=True):
        d = self.exp_dir(repo, slug, h)
        self.write(os.path.join(d, "results.jsonl"), '{"run": 1, "p95": 0.9}\n')
        if analysis:
            self.write(os.path.join(d, "analysis.md"),
                       "# Analysis\n\np95 dropped; the prediction held.\n")
        return d

    def claims(self, repo, *claims, slug="q"):
        body = "".join(json.dumps(c) + "\n" for c in claims)
        self.write(os.path.join(tr.line_dir(repo, slug), "claims.jsonl"), body)

    def errors(self, repo, slug="q", git=True):
        errors, _ = tr.check_line(repo, slug, git=git)
        return errors


CLAIM = {"id": "c1", "statement": "the cache cuts p95",
         "status": "supported", "provenance": "ai-executed",
         "falsification": "p95 does not drop",
         "proof": "experiments/h1/results.jsonl"}


class Init(Workspace):
    def test_init_scaffolds_the_workspace(self):
        repo = self.repo()
        made = tr.init(repo, "probe", question="does x help?", created="2026-01-01")
        base = tr.line_dir(repo, "probe")
        for sub in ("experiments", "literature", "to_human"):
            self.assertTrue(os.path.isdir(os.path.join(base, sub)), sub)
        for name in ("state.json", "log.md", "findings.md", "claims.jsonl"):
            self.assertTrue(os.path.isfile(os.path.join(base, name)), name)
        with open(os.path.join(base, "state.json")) as fh:
            state = json.load(fh)
        self.assertEqual(state["question"], "does x help?")
        self.assertEqual(state["created"], "2026-01-01")
        self.assertEqual((state["phase"], state["direction"]),
                         ("bootstrap", "undecided"))
        self.assertEqual(sorted(made),
                         sorted(os.path.join(base, n) for n in
                                ("state.json", "log.md", "findings.md",
                                 "claims.jsonl")))
        # a fresh line is structurally clean
        self.assertEqual(self.errors(repo, "probe"), [])
        self.assertEqual(tr.check(repo, "probe")["probe"]["warnings"],
                         ["no claims recorded yet"])

    def test_init_never_overwrites(self):
        repo = self.repo()
        base = self.line(repo, "probe", question="first")
        self.write(os.path.join(base, "findings.md"), "# mine\n\n## What we know\n")
        self.write(os.path.join(base, "state.json"),
                   json.dumps({"question": "kept", "phase": "inner",
                               "direction": "pivot"}))
        made = tr.init(repo, "probe", question="second")
        self.assertEqual(made, [])
        with open(os.path.join(base, "state.json")) as fh:
            self.assertEqual(json.load(fh)["question"], "kept")
        with open(os.path.join(base, "findings.md")) as fh:
            self.assertEqual(fh.read(), "# mine\n\n## What we know\n")


class State(Workspace):
    def test_missing_line_is_an_error(self):
        repo = self.repo()
        errors = self.errors(repo, "nope")
        self.assertTrue(hit("does not exist", errors), errors)

    def test_missing_state_file_is_an_error(self):
        repo = self.repo()
        base = self.line(repo)
        os.remove(os.path.join(base, "log.md"))
        self.assertIn("log.md is missing", self.errors(repo))

    def test_state_json_that_does_not_parse(self):
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "state.json"), "{not json\n")
        self.assertTrue(hit("state.json does not parse", self.errors(repo)))

    def test_state_json_without_a_question(self):
        repo = self.repo()
        self.line(repo, question="")
        self.assertIn("state.json records no question", self.errors(repo))

    def test_phase_outside_the_enum(self):
        repo = self.repo()
        base = self.line(repo)
        state = json.loads(read(os.path.join(base, "state.json")))
        state["phase"] = "observing"
        self.write(os.path.join(base, "state.json"), json.dumps(state))
        self.assertTrue(hit("phase 'observing' is not one of", self.errors(repo)))

    def test_direction_outside_the_enum(self):
        repo = self.repo()
        base = self.line(repo)
        state = json.loads(read(os.path.join(base, "state.json")))
        state["direction"] = "sideways"
        self.write(os.path.join(base, "state.json"), json.dumps(state))
        self.assertTrue(hit("direction 'sideways' is not one of",
                            self.errors(repo)))


class Findings(Workspace):
    def test_every_required_section_is_checked(self):
        repo = self.repo()
        base = self.line(repo)
        path = os.path.join(base, "findings.md")
        full = read(path)
        # the four names are pinned here, not read off the module: a shorter
        # FINDINGS_SECTIONS tuple must fail this test
        for section in ("What we know", "Patterns", "Lessons", "Open questions"):
            self.write(path, full.replace("## " + section, ""))
            errors = self.errors(repo)
            self.assertEqual(len(named(errors, "does not answer")), 1, section)
            self.assertEqual(named(errors, "does not answer"),
                             ["findings.md does not answer: %s" % section])
        self.write(path, full.replace("## Patterns", "## patterns"))
        self.assertTrue(hit("does not answer: Patterns", self.errors(repo)))


class Claims(Workspace):
    def test_no_claims_warns_but_is_not_an_error(self):
        repo = self.repo()
        self.line(repo)
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(tr.check(repo, "q")["q"]["warnings"],
                         ["no claims recorded yet"])

    def test_a_complete_claim_is_clean(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, CLAIM)
        report = tr.check(repo, "q")["q"]
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"], [])

    def test_a_line_that_does_not_parse(self):
        repo = self.repo()
        self.line(repo)
        self.write(os.path.join(tr.line_dir(repo, "q"), "claims.jsonl"),
                   json.dumps(CLAIM) + "\n{broken\n")
        self.assertTrue(hit("claims.jsonl:2 does not parse", self.errors(repo)))

    def test_claim_without_a_statement(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, statement=" "))
        self.assertIn("claim c1 states nothing", self.errors(repo))

    def test_claim_without_a_falsification_criterion(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, falsification=""))
        self.assertIn("claim c1 carries no falsification criterion",
                      self.errors(repo))

    def test_claim_without_evidence(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, proof=""))
        self.assertIn("claim c1 cites no evidence", self.errors(repo))

    def test_claim_with_an_unknown_provenance(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, provenance="ai"))
        self.assertTrue(hit("provenance 'ai' is not one of", self.errors(repo)))

    def test_claim_with_an_unknown_status(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, status="true"))
        self.assertTrue(hit("status 'true' is not one of", self.errors(repo)))

    def test_the_first_claim_reported_is_the_first_line(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, proof=""), dict(CLAIM, id="c2", status=""))
        self.assertEqual(named(self.errors(repo), "cites no evidence"),
                         ["claim c1 cites no evidence"])


class Experiments(Workspace):
    def test_experiment_without_a_protocol(self):
        repo = self.repo()
        self.line(repo)
        self.results(repo)
        self.assertIn("experiment h1 has no protocol.md", self.errors(repo))

    def test_results_without_an_analysis(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo, analysis=False)
        self.assertIn("experiment h1 has results but no analysis.md",
                      self.errors(repo))

    def test_protocol_committed_after_the_results(self):
        repo = self.repo()
        self.line(repo)
        self.results(repo)
        self.commit(repo, "results", when=BEFORE)
        self.protocol(repo)
        self.commit(repo, "protocol", when=AFTER)
        self.assertTrue(hit(NOT_A_PREDICTION, self.errors(repo)),
                        self.errors(repo))

    def test_protocol_and_results_committed_together(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.commit(repo, "protocol and results", when=BEFORE)
        self.assertTrue(hit(NOT_A_PREDICTION, self.errors(repo)),
                        self.errors(repo))

    def test_protocol_committed_before_the_results(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        # a results file dated before the protocol still passes: the commit
        # order decides, not the mtime
        os.utime(os.path.join(self.exp_dir(repo), "results.jsonl"),
                 (1577836800, 1577836800))
        self.commit(repo, "results", when=AFTER)
        self.assertEqual(self.errors(repo), [])

    def test_an_uncommitted_protocol_is_an_error(self):
        repo = self.repo()
        self.line(repo)
        self.results(repo)
        self.commit(repo, "results only", when=BEFORE)
        self.protocol(repo)
        self.assertTrue(hit(NOT_COMMITTED, self.errors(repo)),
                        self.errors(repo))

    def test_git_false_skips_the_git_dependent_checks(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.assertTrue(hit(NOT_COMMITTED, self.errors(repo, git=True)))
        self.assertEqual(self.errors(repo, git=False), [])


class Reports(Workspace):
    def test_check_is_keyed_by_slug(self):
        repo = self.repo()
        self.line(repo, "alpha", question="does alpha help?")
        self.line(repo, "beta", question="")
        report = tr.check(repo)
        self.assertEqual(sorted(report), ["alpha", "beta"])
        self.assertEqual(report["alpha"],
                         {"errors": [], "warnings": ["no claims recorded yet"]})
        self.assertEqual(report["beta"]["errors"],
                         ["state.json records no question"])
        self.assertEqual(list(tr.check(repo, "beta")), ["beta"])

    def test_failing_pairs_skip_git_by_default(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.commit(repo, "protocol and results", when=BEFORE)
        rows = tr.failing(repo, git=True)
        self.assertEqual([s for s, _ in rows], ["q"])
        self.assertTrue(hit(NOT_A_PREDICTION, [e for _, e in rows]))
        self.assertEqual(tr.failing(repo), [])

    def test_summary_is_one_line_per_line(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.line(repo, "beta", question="")
        self.assertEqual(tr.summary(repo), ["alpha: ok", "beta: 1 problem(s)"])


class Cli(Workspace):
    def cli(self, repo, *args):
        return support.run([CLI] + list(args), env=self.env(), cwd=repo)

    def test_init_scaffolds_and_exits_zero(self):
        repo = self.repo()
        proc = self.cli(repo, "init", "probing", "--question", "does x help?")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        base = tr.line_dir(repo, "probing")
        self.assertIn(base, proc.stdout)
        with open(os.path.join(base, "state.json")) as fh:
            self.assertEqual(json.load(fh)["question"], "does x help?")

    def test_check_clean_exits_zero(self):
        repo = self.repo()
        self.line(repo)
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("research: 1 line(s) ok", proc.stdout)

    def test_check_prints_fail_per_error_and_exits_one(self):
        repo = self.repo()
        base = self.line(repo, question="")
        os.remove(os.path.join(base, "log.md"))
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL q: log.md is missing", proc.stdout)
        self.assertIn("FAIL q: state.json records no question", proc.stdout)
        self.assertIn("warn q: no claims recorded yet", proc.stdout)

    def test_check_json_prints_the_report(self):
        repo = self.repo()
        self.line(repo, question="")
        out = self.cli(repo, "check", "--json").stdout.splitlines()
        start = [n for n, line in enumerate(out) if line.startswith("{")]
        self.assertTrue(start, out)
        payload = json.loads("\n".join(out[start[0]:]))
        self.assertEqual(payload, tr.check(repo))

    def test_check_with_a_slug_reports_only_that_line(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.line(repo, "beta", question="")
        proc = self.cli(repo, "check", "beta")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL beta: state.json records no question", proc.stdout)
        self.assertNotIn("alpha", proc.stdout)

    def test_check_without_a_line_says_so(self):
        repo = self.repo()
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no research line under", proc.stdout)

    def test_status_prints_one_line_per_line(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.line(repo, "beta", question="")
        proc = self.cli(repo, "status")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(),
                         ["alpha: ok", "beta: 1 problem(s)"])


class SessionNote(Workspace):
    def session(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsInstance(out, str)
        return out

    def test_a_broken_line_is_reported(self):
        repo = self.repo()
        self.line(repo, "beta", question="")
        self.assertIn("Research: beta has 1 problem(s), first: "
                      "state.json records no question", self.session(repo))

    def test_a_clean_line_is_silent(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.assertNotIn("problem(s)", self.session(repo))

    def test_no_line_is_silent(self):
        repo = self.repo()
        self.assertNotIn("problem(s)", self.session(repo))

    def test_an_uncommitted_protocol_is_not_reported(self):
        # the session note pays for structure only: no git history
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.assertNotIn("problem(s)", self.session(repo))


if __name__ == "__main__":
    unittest.main()
