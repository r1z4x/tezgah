"""hooks/tezgah_research.py, bin/tezgah-research, and the session research note.

Every workspace lives in a throwaway git repo under a temp HOME, so the
protocol-before-results rule is exercised against real commit history and no
test touches the repository it runs from. Every git and hook subprocess gets a
fresh HOME and a null global/system git config, so the developer's git config,
aliases and GIT_* environment cannot reach a fixture.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

try:
    import fcntl
except ImportError:  # not POSIX: the held-lock case cannot be exercised
    fcntl = None

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
BOTH_TOGETHER = "one commit added both protocol.md and results.jsonl"


def read(path):
    with open(path) as fh:
        return fh.read()


def hit(needles, errors):
    """True when some error carries the needle."""
    return any(n in e for e in errors for n in ([needles] if
                                                isinstance(needles, str) else needles))


def named(errors, needle):
    return [e for e in errors if needle in e]


GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_EDITOR": "true",
}


class Workspace(TempHome):
    """A research line inside a throwaway git repo, committed at fixed dates."""

    def setUp(self):
        super().setUp()
        if shutil.which("git") is None:
            self.skipTest("git is not installed")

    def env(self, roots=None, extra=None):
        """The throwaway environment every subprocess gets: no inherited GIT_DIR
        or GIT_WORK_TREE, no global git config, a HOME of our own."""
        clean = dict(GIT_ENV)
        clean.update(extra or {})
        return super().env(roots, clean)

    def repo(self, name="repo"):
        path = self.make_repo(name)
        self.git(path, "init", "-q")
        self.git(path, "config", "user.email", "test@example.invalid")
        self.git(path, "config", "user.name", "Test")
        return path

    def git(self, repo, *args, when=None):
        # built from scratch, never dict(os.environ): a developer's GIT_DIR,
        # GIT_WORK_TREE or GIT_CONFIG_GLOBAL must not decide what a fixture is
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
               "HOME": self.home, "LANG": "C.UTF-8"}
        env.update(GIT_ENV)
        if when:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
        proc = subprocess.run(["git", "-C", repo] + list(args),
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0,
                         "%s: %s" % (" ".join(args), proc.stderr))
        return proc.stdout

    def rel(self, repo, *paths):
        return [os.path.relpath(p, repo) for p in paths]

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
         "proof": "to_human/report.md (p95 -12% over 7 runs)"}


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

    def test_an_unreadable_findings_file_is_an_error_not_a_crash(self):
        repo = self.repo()
        base = self.line(repo)
        path = os.path.join(base, "findings.md")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o600)
        errors, warnings = tr.check_line(repo, "q")
        self.assertTrue(hit("findings.md cannot be read", errors), errors)
        self.assertEqual(tr.check(repo, "q")["q"]["errors"], errors)
        self.assertTrue(hit("cannot be read",
                            [e for _, e in tr.failing(repo, git=True)]))


class Claims(Workspace):
    def test_no_claims_warns_but_is_not_an_error(self):
        repo = self.repo()
        self.line(repo)
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(tr.check(repo, "q")["q"]["warnings"],
                         ["no claims recorded yet"])

    def test_a_complete_claim_is_clean(self):
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# report\n")
        self.claims(repo, CLAIM)
        report = tr.check(repo, "q")["q"]
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"], [])

    def test_a_claim_citing_evidence_the_line_does_not_have_is_refused(self):
        """The fabricated-evidence failure: `proof` is prose, so what a checker
        can decide is whether the paths in it exist. A bare filename, a glob or a
        `ref:path` pair stays out of it; a path the line never produced does not."""
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# report\n")
        self.claims(repo, dict(CLAIM, proof="experiments/ghost/results.jsonl (7 runs)"))
        self.assertEqual(named(self.errors(repo), "which is not in this line"),
                         ["claim c1 cites experiments/ghost/results.jsonl, "
                          "which is not in this line"])
        self.claims(repo, dict(CLAIM, proof="to_human/report.md and analysis.md; 8/10"))
        self.assertEqual(self.errors(repo), [])

    def test_a_line_that_does_not_parse(self):
        repo = self.repo()
        self.line(repo)
        self.write(os.path.join(tr.line_dir(repo, "q"), "claims.jsonl"),
                   json.dumps(CLAIM) + "\n{broken\n")
        self.assertTrue(hit("claims.jsonl:2 does not parse", self.errors(repo)))

    def test_a_claims_file_that_is_not_utf8_is_an_error_not_a_crash(self):
        repo = self.repo()
        base = self.line(repo)
        with open(os.path.join(base, "claims.jsonl"), "wb") as fh:
            fh.write(b'{"id": "c1", "statement": "caf\xe9"}\n')
        errors, warnings = tr.check_line(repo, "q")
        self.assertTrue(hit("claims.jsonl cannot be read", errors), errors)
        self.assertEqual(tr.check(repo, "q")["q"]["errors"], errors)
        self.assertTrue(hit("cannot be read",
                            [e for _, e in tr.failing(repo, git=True)]))

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

    def test_protocol_and_results_committed_in_the_same_second(self):
        # two commits in the same second are still two commits: ancestry decides
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=BEFORE)
        self.assertEqual(self.errors(repo), [])

    def test_protocol_edited_and_committed_after_the_results(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.assertEqual(self.errors(repo), [])
        self.write(os.path.join(self.exp_dir(repo), "protocol.md"),
                   "# Protocol\n\nchange: cache the lookups\nprediction: p95 drops\n"
                   "outcome: p95 dropped, so the cache stays\n")
        self.commit(repo, "protocol edited after the run", when=AFTER)
        self.assertTrue(hit("changed after the run", self.errors(repo)),
                        self.errors(repo))

    def test_a_rebased_history_stays_ordered(self):
        # a rebase rewrites hashes and dates but not the order of the plan
        repo = self.repo()
        self.write(os.path.join(repo, "README.md"), "the old base\n")
        self.commit(repo, "old base", when=BEFORE)
        base = self.git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        self.git(repo, "checkout", "-q", "-b", "work")
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.git(repo, "checkout", "-q", base)
        self.write(os.path.join(repo, "newer.txt"), "the base moved on\n")
        self.commit(repo, "newer base", when=AFTER)
        self.git(repo, "checkout", "-q", "work")
        self.git(repo, "rebase", base)
        self.assertEqual(self.errors(repo), [])

    def test_a_renamed_results_file_still_faces_the_order_rule(self):
        # the rename is how the path enters the history, so renaming the results
        # into place before the protocol does not hide them from the rule
        repo = self.repo()
        self.line(repo)
        d = self.exp_dir(repo)
        self.write(os.path.join(d, "results-v1.jsonl"), '{"run": 1}\n')
        self.write(os.path.join(d, "analysis.md"), "# Analysis\n\nheld.\n")
        self.commit(repo, "results under a working name", when=BEFORE)
        self.git(repo, "mv", *self.rel(repo, os.path.join(d, "results-v1.jsonl"),
                                       os.path.join(d, "results.jsonl")))
        self.commit(repo, "rename the results into place", when=BEFORE)
        self.protocol(repo)
        self.commit(repo, "protocol", when=AFTER)
        errors, warnings = tr.check_line(repo, "q")
        self.assertTrue(hit("entered the history after results.jsonl", errors),
                        errors)
        self.assertFalse(hit("not committed yet", warnings), warnings)

    def test_a_rename_after_the_protocol_keeps_the_line_clean(self):
        # a rename into the path counts as the results being committed, so it is
        # ordered, not skipped as "not committed yet"
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        d = self.exp_dir(repo)
        self.write(os.path.join(d, "results-v1.jsonl"), '{"run": 1}\n')
        self.write(os.path.join(d, "analysis.md"), "# Analysis\n\nheld.\n")
        self.commit(repo, "results under a working name", when=BEFORE)
        self.git(repo, "mv", *self.rel(repo, os.path.join(d, "results-v1.jsonl"),
                                       os.path.join(d, "results.jsonl")))
        self.commit(repo, "rename the results into place", when=AFTER)
        errors, warnings = tr.check_line(repo, "q")
        self.assertEqual(errors, [])
        self.assertFalse(hit("not committed yet", warnings), warnings)

    def test_untracked_results_only_warn(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        errors, warnings = tr.check_line(repo, "q")
        self.assertEqual(errors, [])
        self.assertTrue(hit("results.jsonl is not committed yet, so the protocol "
                            "order cannot be checked", warnings), warnings)

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
        self.assertTrue(hit(BOTH_TOGETHER, self.errors(repo)),
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
        self.results(repo)
        self.commit(repo, "results only", when=BEFORE)
        self.protocol(repo)
        self.assertTrue(hit(NOT_COMMITTED, self.errors(repo, git=True)))
        self.assertEqual(self.errors(repo, git=False), [])

    def test_a_repo_with_no_commit_at_all_cannot_be_ordered(self):
        # git log has nothing to answer with, so the line warns instead of
        # accusing: the order is unverifiable, not violated
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        errors, warnings = tr.check_line(repo, "q")
        self.assertEqual(errors, [])
        self.assertTrue(hit("git could not be asked about the order", warnings),
                        warnings)


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
        self.assertTrue(hit(BOTH_TOGETHER, [e for _, e in rows]))
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

    def test_check_json_prints_the_report_of_a_broken_line(self):
        repo = self.repo()
        self.line(repo, question="")
        proc = self.cli(repo, "check", "--json")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        out = proc.stdout.splitlines()
        start = [n for n, line in enumerate(out) if line.startswith("{")]
        self.assertTrue(start, out)
        payload = json.loads("\n".join(out[start[0]:]))
        # the payload is what the caller reads: the slug keyed report, with the
        # problems in it - not a copy of a call the test made for itself
        self.assertEqual(list(payload), ["q"])
        self.assertTrue(payload["q"]["errors"], payload)
        self.assertIn("state.json records no question", payload["q"]["errors"])
        self.assertIn("no claims recorded yet", payload["q"]["warnings"])

    def test_check_for_an_unknown_slug_exits_one(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        proc = self.cli(repo, "check", "nope")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL nope: no such research line", proc.stdout)
        self.assertIn("have: alpha", proc.stdout)

    def test_misuse_exits_two_on_stderr(self):
        repo = self.repo()
        cases = ((("init",), "init needs a slug"),
                 (("init", "q", "--question"), "init <slug>"),
                 (("nonsense",), "unknown command"),
                 ((), "tezgah-research"))
        for args, message in cases:
            proc = self.cli(repo, *args)
            self.assertEqual(proc.returncode, 2, (args, proc.stdout, proc.stderr))
            self.assertIn(message, proc.stderr, args)
            self.assertEqual(proc.stdout, "", args)

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


class ClaimAppend(Workspace):
    """`claim <slug>`: one validated JSON object from stdin onto claims.jsonl."""

    def cli(self, repo, *args, payload=None):
        """`Cli.cli` plus stdin: `payload` is the object, or the raw text, the
        command reads from it."""
        data = None if payload is None else (
            payload if isinstance(payload, str) else json.dumps(payload) + "\n")
        return subprocess.run([sys.executable, CLI] + list(args), input=data,
                              capture_output=True, text=True, env=self.env(),
                              cwd=repo, timeout=60)

    def valid(self, **over):
        claim = {"id": "C1", "statement": "the cache cuts p95",
                 "status": "supported", "provenance": "ai-executed",
                 "falsification": "p95 does not drop",
                 "proof": "to_human/report.md (p95 -12% over 7 runs)"}
        claim.update(over)
        return claim

    def evidence(self, repo, slug="q"):
        """A line whose proof cites a file the line really has, so a refusal
        reports the rule the claim broke and nothing else."""
        base = self.line(repo, slug)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        return os.path.join(base, "claims.jsonl")

    def test_a_valid_claim_is_recorded_and_check_accepts_it(self):
        repo = self.repo()
        path = self.evidence(repo)
        proc = self.cli(repo, "claim", "q", payload=self.valid())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("claim C1 recorded", proc.stdout)
        lines = read(path).splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(json.loads(lines[0]), self.valid())
        row = tr.check(repo)["q"]
        self.assertEqual(row["errors"], [])
        self.assertNotIn("no claims recorded yet", row["warnings"])

    def test_a_claim_without_an_id_keeps_it_that_way(self):
        # numbering is the writer's business: the command records what it is
        # handed and says so without inventing an id
        repo = self.repo()
        path = self.evidence(repo)
        claim = self.valid()
        del claim["id"]
        proc = self.cli(repo, "claim", "q", payload=claim)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("claim recorded", proc.stdout)
        self.assertNotIn("id", json.loads(read(path).splitlines()[0]))

    def test_a_claim_without_a_falsification_is_refused(self):
        repo = self.repo()
        path = self.evidence(repo)
        proc = self.cli(repo, "claim", "q", payload=self.valid(falsification=""))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL q: ", proc.stdout)
        self.assertIn("falsification", proc.stdout)
        self.assertEqual(read(path), "")

    def test_a_provenance_outside_the_list_is_refused(self):
        repo = self.repo()
        path = self.evidence(repo)
        proc = self.cli(repo, "claim", "q",
                        payload=self.valid(provenance="remembered"))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL q: ", proc.stdout)
        self.assertIn("provenance", proc.stdout)
        self.assertEqual(read(path), "")

    def test_a_proof_citing_a_path_the_line_lacks_is_refused(self):
        repo = self.repo()
        path = self.evidence(repo)
        proof = "experiments/nowhere/results.jsonl"
        proc = self.cli(repo, "claim", "q", payload=self.valid(proof=proof))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL q: ", proc.stdout)
        self.assertIn(proof, proc.stdout)
        self.assertEqual(read(path), "")

    def test_an_append_after_a_line_without_a_trailing_newline_keeps_both(self):
        # a hand edit can leave the file ending mid-line; the next append must
        # still produce one whole claim per line
        repo = self.repo()
        path = self.evidence(repo)
        self.write(path, json.dumps(self.valid()))
        proc = self.cli(repo, "claim", "q", payload=self.valid(id="C2"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = read(path).splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertEqual([json.loads(line)["id"] for line in lines], ["C1", "C2"])

    def test_a_refused_claim_never_creates_the_file(self):
        repo = self.repo()
        path = self.evidence(repo)
        os.remove(path)
        proc = self.cli(repo, "claim", "q", payload=self.valid(falsification=""))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL q: ", proc.stdout)
        self.assertFalse(os.path.exists(path))

    def test_misuse_exits_two_with_nothing_on_stdout(self):
        repo = self.repo()
        path = self.evidence(repo, "alpha")
        cases = ((("claim",), self.valid(), None),          # no slug
                 (("claim", "nope"), self.valid(), "alpha"),  # unknown slug
                 (("claim", "alpha"), "{not json", None),     # not JSON
                 (("claim", "alpha"), [1, 2], None))          # not an object
        for args, payload, needle in cases:
            proc = self.cli(repo, *args, payload=payload)
            self.assertEqual(proc.returncode, 2, (args, proc.stdout, proc.stderr))
            self.assertEqual(proc.stdout, "", args)
            if needle:
                self.assertIn(needle, proc.stderr, args)
        self.assertEqual(read(path), "")

    def test_eight_processes_appending_at_once_all_land(self):
        repo = self.repo()
        path = self.evidence(repo)
        env = self.env()
        claims = [self.valid(id="C%d" % n, statement="statement %d" % n)
                  for n in range(1, 9)]
        procs = [subprocess.Popen([sys.executable, CLI, "claim", "q"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=env,
                                  cwd=repo) for _ in claims]

        def cleanup():
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                for fh in (proc.stdin, proc.stdout, proc.stderr):
                    if fh is not None and not fh.closed:
                        fh.close()

        self.addCleanup(cleanup)
        # every process is started and gets its whole input, and no stdin is
        # left open, before any of them is waited on: the eight appends overlap
        for proc, claim in zip(procs, claims):
            proc.stdin.write(json.dumps(claim) + "\n")
            proc.stdin.close()
        codes = [proc.wait(timeout=60) for proc in procs]
        results = [(proc.stdout.read(), proc.stderr.read()) for proc in procs]
        self.assertEqual(codes, [0] * len(claims), results)
        for (out, err), claim in zip(results, claims):
            self.assertIn("claim %s recorded" % claim["id"], out, (out, err))
        rows = [json.loads(line) for line in read(path).splitlines()]
        self.assertEqual(len(rows), len(claims), read(path))
        self.assertEqual(sorted(row["id"] for row in rows),
                         sorted(claim["id"] for claim in claims))

    def test_a_held_lock_refuses_the_claim(self):
        if fcntl is None:
            self.skipTest("fcntl is unavailable")
        repo = self.repo()
        path = self.evidence(repo)
        before = read(path)
        holder = open(path, "a")
        self.addCleanup(holder.close)
        fcntl.flock(holder, fcntl.LOCK_EX)
        # LOCK_WAIT is read by the process that appends: the CLI keeps its own
        # bound, so this waits out one default - a refusal, not an unlocked write
        saved = tr.LOCK_WAIT
        tr.LOCK_WAIT = 0.05
        try:
            proc = self.cli(repo, "claim", "q", payload=self.valid())
        finally:
            tr.LOCK_WAIT = saved
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL q: ", proc.stdout)
        self.assertIn("claims.jsonl", proc.stdout)
        self.assertEqual(read(path), before)


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

    def test_research_off_suppresses_the_note(self):
        repo = self.repo()
        self.line(repo, "beta", question="")
        self.assertIn("Research: beta has 1 problem(s), first: "
                      "state.json records no question", self.session(repo))
        self.touch(os.path.join(self.home, ".config", "tezgah", "research-off"))
        self.assertNotIn("problem(s)", self.session(repo))


if __name__ == "__main__":
    unittest.main()
