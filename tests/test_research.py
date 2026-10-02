"""hooks/tezgah_research.py, bin/tezgah-research, and the session research note.

Every workspace lives in a throwaway git repo under a temp HOME, so the
protocol-before-results rule is exercised against real commit history and no
test touches the repository it runs from. Every git and hook subprocess gets a
fresh HOME and a null global/system git config, so the developer's git config,
aliases and GIT_* environment cannot reach a fixture.
"""
import json
import os
import re
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


def component_keys():
    """The keys the manifest defines, read from the module that defines them: a
    fixture must name a component the layer really has, and this slice does not
    own the names."""
    import tezgah_components as tc
    return list(tc.keys())


def component_labels():
    """{key: label} the manifest carries, for the cases about the report's own
    headers: a fixture reads the label rather than spelling one."""
    import tezgah_components as tc
    return {c["key"]: c["label"] for c in tc.COMPONENTS}


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
        """One commit in each history: the line's files in `.tezgah`'s private
        repository when `init` made one, everything else in the project's - which
        is where a session's own two commits land."""
        ws = os.path.join(repo, ".tezgah")
        if os.path.isdir(os.path.join(ws, ".git")):
            self.git(ws, "add", "-A", "-f")
            self.git(ws, "-c", "commit.gpgsign=false", "-c", "user.name=Test",
                     "-c", "user.email=test@example.invalid", "commit", "-q",
                     "--allow-empty", "-m", message, when=when)
            self.git(repo, "add", "-A", "-f", "--", ".", ":(exclude).tezgah")
        else:
            self.git(repo, "add", "-A", "-f")
        self.git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty",
                 "-m", message, when=when)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def append_line(self, path, row):
        """One more row, appended the way another session would: its own
        descriptor and no lock, which is what a racing writer looks like here."""
        with open(path, "a") as fh:
            fh.write(json.dumps(row) + "\n")

    def race_at_the_lock(self, racing):
        """Run `racing` at the instant the writer's lock is taken.

        The window the order rule is about: a writer's judgement about a file has
        to be made while it holds that file's lock, so this hands the writer the
        state another session would have landed in between - which the pre-change
        order could not see, because it judged before the lock was asked for."""
        saved = tr._locked

        def locked(handle, label="claims.jsonl"):
            problem = saved(handle, label)
            if problem is None:
                racing()
            return problem

        tr._locked = locked
        self.addCleanup(setattr, tr, "_locked", saved)

    def line(self, repo, slug="q", question="does the change help?",
             phase="bootstrap"):
        """A scaffolded line with its evaluation locked and its deliverable
        declared as findings, so a test about one rule does not have to read past
        the warning that says it is not locked yet or owes no variants."""
        tr.init(repo, slug, question=question, created="2026-01-01")
        base = tr.line_dir(repo, slug)
        state = json.loads(read(os.path.join(base, "state.json")))
        state["phase"] = phase
        state["evaluation"].update({"metric": "p95", "baseline": "the bare build",
                                    "locked_at": "2026-01-01"})
        state["deliverable"] = {"kind": "finding"}
        self.write(os.path.join(base, "state.json"), json.dumps(state))
        return base

    def exp_dir(self, repo, slug="q", h="h1"):
        return os.path.join(tr.line_dir(repo, slug), "experiments", h)

    def protocol(self, repo, slug="q", h="h1"):
        d = self.exp_dir(repo, slug, h)
        self.write(os.path.join(d, "protocol.md"),
                   "# Protocol\n\nchange: cache the lookups\nprediction: p95 drops\n"
                   "falsification: p95 holds or rises\n")
        return d

    def results(self, repo, slug="q", h="h1", analysis=True, row=None):
        d = self.exp_dir(repo, slug, h)
        body = row if row is not None else {"run": 1, "p95": 0.9, "scope": "real",
                                            "source": "run.py run 1"}
        self.write(os.path.join(d, "results.jsonl"), json.dumps(body) + "\n")
        if analysis:
            self.write(os.path.join(d, "analysis.md"),
                       "# Analysis\n\np95 dropped; the prediction held.\n")
        return d

    def note(self, repo, name, text, slug="q"):
        """One literature note, saved the way the skill asks for it."""
        path = os.path.join(tr.line_dir(repo, slug), "literature", name)
        self.write(path, text)
        return path

    def index(self, repo, *rows, slug="q"):
        path = os.path.join(tr.line_dir(repo, slug), "literature", "INDEX.jsonl")
        self.write(path, "".join(json.dumps(r) + "\n" for r in rows))
        return path

    def review(self, repo, review, slug="q"):
        """A review written by a reader other than the producer, unless the case
        names either of them."""
        review = dict({"producer": "session-a", "reviewer": "session-b"}, **review)
        path = os.path.join(tr.line_dir(repo, slug), "to_human", "review.json")
        self.write(path, json.dumps(review))
        return path

    def patterns(self, repo, *bullets, slug="q"):
        base = tr.line_dir(repo, slug)
        self.write(os.path.join(base, "findings.md"),
                   "# Findings\n\n## What we know\n\n## Patterns\n"
                   + "".join("- %s\n" % b for b in bullets)
                   + "\n## Lessons\n\n## Open questions\n")

    def deliver(self, repo, slug="q"):
        """The report and an independent review with one finding, both complete:
        what a line holding `to_human/report.md` owes whatever its phase."""
        base = tr.line_dir(repo, slug)
        self.write(os.path.join(base, "to_human", "report.md"), REPORT)
        self.review(repo, {"dimensions": {n: 3 for n in tr.REVIEW_DIMENSIONS},
                           "findings": [{"severity": "minor",
                                         "target": "to_human/report.md",
                                         "quote": "held.", "status": "accepted"}]},
                    slug=slug)

    def clean(self, repo, slug="q"):
        """A line every rule is satisfied by: strict-clean, so a test can assert
        that turning the unverifiable class into a refusal changes nothing for a
        line that has nothing left unprovable. It holds a report, so it holds the
        review a report owes, and its phase is the one those artifacts show
        (`concluded`), so the fixture is also clean of the rule that reads the
        phase against them."""
        base = self.line(repo, slug, phase="concluded")
        self.deliver(repo, slug)
        self.protocol(repo, slug)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo, slug)
        self.commit(repo, "results", when=AFTER)
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="experiments/h1/results.jsonl (p95 -12%)"),
                    slug=slug)
        self.patterns(repo, "the cache cuts p95 [c1]", slug=slug)
        return base

    def stub_orx(self, repo, projects="[]", view="", logs="", name="orx",
                 projects_exit=0, view_exit=0, logs_exit=0):
        """An `orx` on PATH that answers the calls `check --orx` and `source --run`
        make, so both are exercised end to end without the real CLI. Each answer
        carries its own exit code, so a failing subcommand can be told from a
        failing tool."""
        path = os.path.join(self.home, "bin", name)
        self.write(path, "#!/bin/sh\n"
                         'case "$1" in\n'
                         '  projects) cat <<\'EOF\'\n%s\nEOF\nexit %d ;;\n'
                         '  project) cat <<\'EOF\'\n%s\nEOF\nexit %d ;;\n'
                         '  logs) cat <<\'EOF\'\n%s\nEOF\nexit %d ;;\n'
                         "esac\nexit 2\n"
                         % (projects, projects_exit, view, view_exit, logs,
                            logs_exit))
        os.chmod(path, 0o755)
        return path

    def claims(self, repo, *claims, slug="q"):
        body = "".join(json.dumps(c) + "\n" for c in claims)
        self.write(os.path.join(tr.line_dir(repo, slug), "claims.jsonl"), body)

    def errors(self, repo, slug="q", git=True, strict=False):
        errors, _ = tr.check_line(repo, slug, git=git, strict=strict)
        return errors

    def warnings(self, repo, slug="q", git=True, strict=False):
        _, warnings = tr.check_line(repo, slug, git=git, strict=strict)
        return warnings

    def cli(self, repo, *args, env=None):
        return support.run([CLI] + list(args), env=env or self.env(), cwd=repo)

    def session_note(self, repo, event="session_start"):
        """The context text the hook would inject for `repo` on `event`, out of a
        fresh interpreter so the fixture's HOME, roots and marks are what it
        sees."""
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": event,
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsInstance(out, str)
        return out


CLAIM = {"id": "c1", "statement": "the cache cuts p95",
         "status": "supported", "provenance": "ai-executed",
         "kind": "evidence",
         "falsification": "p95 does not drop",
         "proof": "to_human/report.md (p95 -12% over 7 runs)"}

# A report with everything a delivered line's report is read for: what the
# evidence does not show, and the four validity threats by name.
REPORT = ("# Report\n\nheld.\n\n## What this does not show\n\n- one seed.\n\n"
          "## Validity\n\n- internal validity: one machine ran both arms.\n"
          "- external validity: one workload.\n"
          "- construct validity: p95 is the latency the ask names.\n"
          "- conclusion validity: seven runs, no interval.\n")


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
        # a fresh line is structurally clean, and the two warnings it carries are
        # the honest state of a line that has not locked its evaluation yet
        self.assertEqual(self.errors(repo, "probe"), [])
        self.assertEqual(tr.check(repo, "probe")["probe"]["warnings"],
                         ["state.json evaluation locks no metric, baseline, "
                          "locked_at: a criterion chosen after seeing the results "
                          "is not a criterion",
                          "no claims recorded yet"])

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


class Unfinished(Workspace):
    """`init` over the lines that are not finished, and the reasons they name.

    E6: on 2026-09-22 this repository held thirteen research lines and eleven of
    them carried unfinished work while new ones were opened beside them, because
    `init` read none of the others before scaffolding - the state the refusal and
    its `--allow-open` hatch exist to break."""

    def concluded(self, repo, slug="alpha"):
        """A line that satisfies every reason `open_lines` can give: concluded, no
        live claim, the report and a review whose findings are labelled. `check`
        still warns about it - no claim is recorded - which is why the assertions
        below are about `open_lines` and about `init`."""
        base = self.line(repo, slug, phase="concluded")
        self.write(os.path.join(base, "to_human", "report.md"),
                   "# Report\n\nheld.\n\nThe evidence does not show the cost.\n")
        self.review(repo, {"dimensions": {name: 3 for name in tr.REVIEW_DIMENSIONS},
                           "findings": [{"severity": "minor", "status": "accepted",
                                         "target": "to_human/report.md",
                                         "quote": "held."}]}, slug=slug)
        return base

    def test_init_refuses_over_an_unfinished_line_and_creates_nothing(self):
        repo = self.repo()
        self.line(repo, "alpha", phase="inner")
        proc = self.cli(repo, "init", "beta", "--ask", "is beta worth it?")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("init refused", proc.stdout)
        self.assertIn("alpha: ", proc.stdout)
        self.assertIn("phase inner", proc.stdout)
        self.assertIn('--allow-open "<reason>"', proc.stdout)
        self.assertEqual(tr.slugs(repo), ["alpha"])

    def test_allow_open_scaffolds_and_records_the_reason(self):
        repo = self.repo()
        self.line(repo, "alpha", phase="inner")
        proc = self.cli(repo, "init", "beta", "--ask", "is beta worth it?", "--allow-open", "because X")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        log = read(os.path.join(tr.line_dir(repo, "beta"), "log.md"))
        self.assertIn("because X", log)
        self.assertEqual(tr.slugs(repo), ["alpha", "beta"])

    def test_an_empty_reason_is_misuse(self):
        repo = self.repo()
        self.line(repo, "alpha", phase="inner")
        proc = self.cli(repo, "init", "beta", "--ask", "is beta worth it?", "--allow-open", "   ")
        self.assertEqual(proc.returncode, 2, (proc.stdout, proc.stderr))
        self.assertEqual(proc.stdout, "")
        self.assertEqual(tr.slugs(repo), ["alpha"])

    def test_a_concluded_line_does_not_block_init(self):
        repo = self.repo()
        self.concluded(repo)
        self.assertEqual(tr.open_lines(repo), [])
        proc = self.cli(repo, "init", "beta", "--ask", "is beta worth it?")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(tr.slugs(repo), ["alpha", "beta"])

    def test_a_superseded_claim_keeps_a_proof_path_that_moved(self):
        """A correction is a new row, so a plan that closes and changes folder -
        or any cited file that is reorganised - must not leave the older row
        refusing for ever: that would make the correction impossible to land, and
        it is how closing a plan broke every line that had cited it. The
        superseded row is reported, the row that supersedes it is checked in
        full."""
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# report\n")
        self.claims(repo,
                    dict(CLAIM, id="c1", proof=".tezgah/plans/open/009-gone.md"),
                    dict(CLAIM, id="c2", supersedes="c1",
                         proof="to_human/report.md"))
        self.assertEqual(self.errors(repo), [])
        self.assertTrue(hit("c1 is superseded, so its proof is the historical",
                            tr.check(repo, "q")["q"]["warnings"]))
        # and the row that supersedes it is still held to its own proof
        self.claims(repo,
                    dict(CLAIM, id="c3", supersedes="c2",
                         proof=".tezgah/plans/open/009-gone.md"))
        self.assertEqual(named(self.errors(repo), "which is not in this line"),
                         ["claim c3 cites .tezgah/plans/open/009-gone.md, "
                          "which is not in this line"])

    def test_a_superseded_claim_is_not_warned_for_its_numbers(self):
        """The same rule as the path above, for the other half of a proof: a
        superseded row's statement may name a figure the corrected row rewrote,
        and warning on it would make that correction impossible to land - the row
        cannot be edited, so the warning would sit under a sentence no reader is
        meant to keep. The row that supersedes it is still held to its own
        numbers."""
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# report 12\n")
        self.claims(repo,
                    dict(CLAIM, id="c1", statement="the yield is 0.99 over 3 runs",
                         proof="to_human/report.md"),
                    dict(CLAIM, id="c2", supersedes="c1",
                         statement="the yield is 12 over 3 runs",
                         proof="to_human/report.md"))
        # c1 is the superseded row, so its unreachable figure is not warned for;
        # c2 is live here and is held to its own numbers (12 is in the report, 3
        # is not).
        first = tr.check(repo, "q")["q"]["warnings"]
        self.assertFalse(any(w.startswith("claim c1 asserts") for w in first), first)
        self.assertTrue(hit("claim c2 asserts", first))
        # and a correction on top of c2 silences c2 in turn
        self.claims(repo, dict(CLAIM, id="c3", supersedes="c2",
                               statement="the yield is 12 over 3 runs",
                               proof="to_human/report.md"))
        after = tr.check(repo, "q")["q"]["warnings"]
        self.assertFalse(any(w.startswith("claim c2 asserts") for w in after), after)

    def test_a_superseded_claim_is_read_through_the_row_that_replaced_it(self):
        # `claims.jsonl` is append-only, so the older row keeps the status it was
        # left in - `c1` stays `hypothesis` for ever - and the relation that says
        # which decision stands is `supersedes`. A row another row supersedes is
        # therefore not a live proposal, and the row that replaced it is the one
        # whose status is read; skipping it is what lets a line close.
        repo = self.repo()
        self.concluded(repo)
        self.claims(repo,
                    dict(CLAIM, id="c1", status="hypothesis"),
                    dict(CLAIM, id="c2", status="untested", supersedes="c1"),
                    slug="alpha")
        self.assertEqual(tr.open_lines(repo), [])
        # the newest row of the chain still decides: a replacement that is itself
        # a live proposal keeps the line open, and its reason is the one reported
        self.claims(repo,
                    dict(CLAIM, id="c1", status="hypothesis"),
                    dict(CLAIM, id="c2", status="testing", supersedes="c1"),
                    slug="alpha")
        reasons = dict(tr.open_lines(repo))["alpha"]
        self.assertTrue(hit("claim c2 is testing", reasons), reasons)
        self.assertFalse(hit("claim c1 is hypothesis", reasons), reasons)

    def test_every_reason_a_line_is_open_for(self):
        repo = self.repo()
        self.line(repo, "alpha", phase="inner")
        self.protocol(repo, "alpha")
        self.claims(repo, dict(CLAIM, status="hypothesis"), slug="alpha")
        self.review(repo, {"dimensions": {},
                           "findings": [{"severity": "minor", "status": "accepted",
                                         "target": "to_human/report.md",
                                         "quote": "held"},
                                        {"severity": "minor",
                                         "target": "to_human/report.md",
                                         "quote": "held"}]}, slug="alpha")
        reasons = dict(tr.open_lines(repo))["alpha"]
        for needle in ("phase inner", "claim c1 is hypothesis",
                       "experiments/h1 has a protocol and no results",
                       "to_human/report.md is missing",
                       "finding 2 carries no status"):
            self.assertTrue(hit(needle, reasons), (needle, reasons))
        self.assertFalse(hit("finding 1", reasons), reasons)
        # a line with no review at all is open for that, and a state.json nothing
        # can parse is open rather than a crash the caller has to catch
        self.line(repo, "gamma", phase="inner")
        self.assertTrue(hit("to_human/review.json is missing",
                            dict(tr.open_lines(repo))["gamma"]))
        self.write(os.path.join(tr.line_dir(repo, "gamma"), "state.json"),
                   "{not json\n")
        self.assertIn("phase unreadable", dict(tr.open_lines(repo))["gamma"])

    def test_the_layer_summary_names_the_open_lines(self):
        repo = self.repo()
        self.line(repo, "alpha", phase="inner")
        self.assertTrue(hit("open: alpha (phase inner", tr.summary(repo)),
                        tr.summary(repo))
        self.assertIn("open: alpha (phase inner", self.cli(repo, "check").stdout)
        self.concluded(repo)
        self.assertEqual(tr.open_note(repo), "")
        self.assertFalse(hit("open: ", tr.summary(repo)), tr.summary(repo))


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

    def test_each_artifact_moves_the_derived_phase_one_rung(self):
        # the derivation the phase rule reads, one artifact at a time: nothing run
        # is `bootstrap`, an experiment with a committed protocol and a results row
        # is `inner`, the results folded into the findings are `outer`, and the two
        # artifacts a concluded line owes are `concluded`
        repo = self.repo()
        base = self.line(repo, phase="bootstrap")
        self.assertEqual(tr.derived_phase(base), "bootstrap")
        self.protocol(repo)
        self.assertEqual(tr.derived_phase(base), "bootstrap",
                         "a protocol with no results is a plan, not a measurement")
        self.results(repo)
        self.assertEqual(tr.derived_phase(base), "inner")
        self.patterns(repo, "the cache cuts p95 [c1]")
        self.assertEqual(tr.derived_phase(base), "outer")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.assertEqual(tr.derived_phase(base), "outer",
                         "a report with no review is not a concluded line")
        self.review(repo, {"dimensions": {}, "findings": []})
        self.assertEqual(tr.derived_phase(base), "concluded")

    def test_a_phase_behind_the_artifacts_warns_and_never_fails(self):
        # the defect class this line's own source named as two authorities: the
        # field is the author's declared intent and the artifacts are the other,
        # and a field behind them says nothing about where the line actually is
        repo = self.repo()
        base = self.line(repo, phase="inner")
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="experiments/h1/results.jsonl (p95 -12%)"))
        self.patterns(repo, "the cache cuts p95 [c1]")
        self.deliver(repo)
        warnings = self.warnings(repo)
        self.assertTrue(hit("state.json phase inner is behind the phase the "
                            "line's artifacts show (concluded)", warnings),
                        warnings)
        # the warn class in both modes: the stored field stays the author's
        # declaration, so the derivation never turns a line the field says is fine
        # into a failing one
        self.assertEqual(self.errors(repo, strict=True), [])
        self.assertTrue(hit("is behind the phase", self.warnings(repo, strict=True)))
        # and a line whose field is the one its artifacts show says nothing at all
        state = json.loads(read(os.path.join(base, "state.json")))
        state["phase"] = "concluded"
        self.write(os.path.join(base, "state.json"), json.dumps(state))
        self.assertFalse(hit("is behind the phase", self.warnings(repo)))
        # the field ahead of its artifacts is the author's call, not a defect the
        # derivation reports: `_check_report` and `_check_review` read the field, so
        # a line it calls concluded is judged as one
        os.remove(os.path.join(base, "to_human", "review.json"))
        self.assertEqual(tr.derived_phase(base), "outer")
        self.assertFalse(hit("is behind the phase", self.warnings(repo)))
        self.assertTrue(hit("review.json is missing", self.errors(repo, strict=True)))


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
        # the claim cites the report, and a line holding a report owes its review:
        # the fixture delivers both and declares the phase they show
        self.line(repo, phase="concluded")
        self.deliver(repo)
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
                   "falsification: p95 holds or rises\n"
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
        ws = os.path.join(repo, ".tezgah")
        self.git(ws, "mv", *self.rel(ws, os.path.join(d, "results-v1.jsonl"),
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
        ws = os.path.join(repo, ".tezgah")
        self.git(ws, "mv", *self.rel(ws, os.path.join(d, "results-v1.jsonl"),
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


class ProtocolContent(Workspace):
    """What a protocol has to answer, not only that the file exists.

    E1's P2 probe is the case this rule answers: a protocol whose whole body was
    `run it` passed every check the layer had, because only its existence and its
    commit order were read."""

    def test_a_protocol_that_answers_neither_question_warns_and_strict_refuses(self):
        repo = self.repo()
        self.line(repo)
        d = self.protocol(repo)
        self.write(os.path.join(d, "protocol.md"), "run it\n")
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("protocol.md states no prediction", warnings), warnings)
        self.assertTrue(hit("protocol.md states no falsification criterion",
                            warnings), warnings)
        strict = self.errors(repo, strict=True)
        self.assertTrue(hit("protocol.md states no prediction", strict), strict)

    def test_a_prose_protocol_that_answers_both_passes(self):
        # the shape the rule must not refuse: a plan written as prose and wrapped
        # over as many lines as the writer liked
        repo = self.repo()
        self.line(repo)
        d = self.protocol(repo)
        self.write(os.path.join(d, "protocol.md"),
                   "# The plan\n\nCaching the lookups is expected to cut p95, and\n"
                   "the prediction is a tenth over seven runs. A p95 that holds\n"
                   "flat would refute it, and so would a p99 that rises.\n")
        self.assertFalse(hit("protocol.md", self.warnings(repo)), self.warnings(repo))

    def test_a_disclaimed_prediction_is_not_an_answer(self):
        # three protocols in this repository are work orders for a read-only
        # agent and say so in the body; reading the word alone would take the
        # disclaimer for an answer, which is the false pass this pins
        repo = self.repo()
        self.line(repo)
        d = self.protocol(repo)
        self.write(os.path.join(d, "protocol.md"),
                   "# The brief\n\nThis file is the brief, and no prediction is\n"
                   "claimed for it.\n\n## What would falsify\n\n- a host where no "
                   "routing arrives at all\n")
        warnings = self.warnings(repo)
        self.assertTrue(hit("protocol.md states no prediction", warnings), warnings)
        self.assertFalse(hit("states no falsification criterion", warnings), warnings)

    def test_only_the_question_that_is_missing_is_named(self):
        repo = self.repo()
        self.line(repo)
        d = self.protocol(repo)
        self.write(os.path.join(d, "protocol.md"),
                   "# Protocol\n\nprediction: p95 drops\n")
        warnings = self.warnings(repo)
        self.assertFalse(hit("states no prediction", warnings), warnings)
        self.assertTrue(hit("protocol.md states no falsification criterion",
                            warnings), warnings)


class Reports(Workspace):
    def test_the_two_reporting_surfaces_are_pinned_apart(self):
        # E6 row 25: summary()'s docstring claimed the session note reads it while
        # the note calls failing(). The drift is what this pins: the docstring must
        # name the surface that really reads it, and the note must still be the
        # one-line-per-broken-line report
        repo = self.repo()
        base = self.line(repo, "beta", question="")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.assertIn("`status`", tr.summary.__doc__)
        self.assertIn("failing()", tr.summary.__doc__)
        self.assertNotIn("session note", tr.summary.__doc__)
        # the per-line row first: the layer's own open-lines line follows it and is
        # what the newer rule added (see Unfinished)
        self.assertEqual(tr.summary(repo)[0], "beta: 1 problem(s)")
        broken = tr.failing(repo, git=True)
        self.assertEqual(len(broken), 1, broken)
        self.assertIn(broken[0][1], self.session_note(repo))

    def test_check_is_keyed_by_slug(self):
        repo = self.repo()
        self.line(repo, "alpha", question="does alpha help?")
        self.line(repo, "beta", question="")
        report = tr.check(repo)
        self.assertEqual(sorted(report), ["alpha", "beta"])
        self.assertEqual(report["alpha"],
                         {"errors": [], "warnings": ["no claims recorded yet"],
                          "notes": []})
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
        self.assertEqual({s for s, _ in rows}, {"q"})
        self.assertTrue(hit(BOTH_TOGETHER, [e for _, e in rows]))
        self.assertEqual(tr.failing(repo), [])

    def test_summary_is_one_line_per_line(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.line(repo, "beta", question="")
        rows = tr.summary(repo)
        self.assertEqual(rows[:2], ["alpha: ok", "beta: 1 problem(s)"])
        self.assertTrue(rows[2].startswith("open: alpha"), rows)


class Cli(Workspace):
    def test_init_scaffolds_and_exits_zero(self):
        repo = self.repo()
        proc = self.cli(repo, "init", "probing", "--ask", "does x help?", "--question", "does x help?")
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

    def test_init_refuses_a_slug_no_other_command_can_see(self):
        """A slug is the directory name `slugs()` lists, which is what `check`,
        `status` and `claim` all go through. `init ..` wrote state.json and
        claims.jsonl into .tezgah itself - the directory the status surfaces
        treat as tezgah's own - and exited 0, and an absolute slug wrote outside
        the repository. Both writers refuse now, and nothing is created."""
        repo = self.repo()
        for slug in ("..", "../escape", "a/b", ".hidden", "/tmp/absolute-line"):
            with self.subTest(slug=slug):
                proc = self.cli(repo, "init", slug)
                self.assertEqual(proc.returncode, 2, (slug, proc.stdout))
                self.assertEqual(proc.stdout, "", slug)

        _id, problems = tr.append_claim(repo, "..", dict(CLAIM))
        self.assertTrue(problems, "append_claim accepted a slug slugs() hides")
        self.assertEqual(tr.slugs(repo), [])
        self.assertFalse(os.path.exists(os.path.join(repo, ".tezgah", "state.json")))
        self.assertFalse(
            os.path.exists(os.path.join(repo, ".tezgah", "research", "state.json")))
        self.assertFalse(os.path.exists(os.path.join(repo, ".tezgah", "claims.jsonl")))

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
        rows = proc.stdout.splitlines()
        self.assertEqual(rows[:2], ["alpha: ok", "beta: 1 problem(s)"])
        self.assertTrue(rows[2].startswith("open: alpha"), rows)


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
                 "kind": "evidence",
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

    def test_a_claim_filed_before_its_run_records_a_row_is_accepted(self):
        """The write path and the checker agree on the evidence-row rule: an
        empty results.jsonl is the class `check` warns about, so `claim` records
        the claim and `check --strict` is what refuses it. A writer stricter than
        the checker would refuse a claim the line is allowed to hold while its run
        is still landing its rows."""
        repo = self.repo()
        base = self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "results.jsonl"), "")
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        proc = self.cli(repo, "claim", "q", payload=self.valid(
            id="C2", kind="evidence", proof="experiments/h1/results.jsonl"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("claim C2 recorded", proc.stdout)
        self.assertEqual(read(os.path.join(base, "claims.jsonl")).count("\n"), 1)
        self.assertTrue(hit("cites experiment h1, whose results.jsonl holds no row",
                            self.warnings(repo)))
        self.assertEqual(self.errors(repo), [])
        self.assertTrue(hit("recorded nothing", self.errors(repo, strict=True)))

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

    def test_an_evidence_claim_naming_only_a_repo_file_is_refused(self):
        # P6 through the command: exit 1, one reason, nothing written
        repo = self.repo()
        path = self.evidence(repo)
        self.write(os.path.join(repo, "src", "unrelated.py"), "x = 1\n")
        proc = self.cli(repo, "claim", "q", payload=self.valid(
            kind="evidence", proof="src/unrelated.py"))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("FAIL q: claim C1 is an evidence claim and cites nothing "
                      "the line produced", proc.stdout)
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

    def test_a_proof_citing_a_path_whose_directory_has_parentheses_resolves(self):
        # measured on Ustam 2026-09-27: a Next.js route group is a real
        # directory name, and a proof naming one was read as naming nothing
        repo = self.repo()
        path = self.evidence(repo)
        base = self.line(repo, "q")
        self.write(os.path.join(base, "experiments", "(v2)", "results.jsonl"),
                   '{"run": 1}\n')
        proof = "experiments/(v2)/results.jsonl (p95 -12% over 7 runs)"
        proc = self.cli(repo, "claim", "q", payload=self.valid(proof=proof))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("claim C1 recorded", proc.stdout)
        self.assertNotEqual(read(path), "")

    def test_an_append_starts_at_the_last_newline_the_file_ended_on(self):
        # a hand edit can leave the file ending mid-line; the boundary the reader
        # and the writer now share is the last newline, so the append starts there
        # and the fragment stops being a row at all. This test asserted the
        # opposite - terminate the tail and keep both rows - until the adoption
        # line's report named the two postures on one file shape (item 4)
        repo = self.repo()
        path = self.evidence(repo)
        self.write(path, json.dumps(self.valid()))
        proc = self.cli(repo, "claim", "q", payload=self.valid(id="C2"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = read(path)
        self.assertTrue(body.endswith("\n"), body)
        self.assertEqual([json.loads(line)["id"] for line in body.splitlines()],
                         ["C2"])
        # the fragment is gone rather than left as a line nothing can read, so the
        # file the reader stops at and the file the writer left are the same one
        self.assertEqual(self.errors(repo), [])

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

    def held_lock(self, repo):
        """A line whose claims.jsonl this process holds exclusively, with what
        the file held when the lock was taken."""
        path = self.evidence(repo)
        before = read(path)
        holder = open(path, "a")
        self.addCleanup(holder.close)
        fcntl.flock(holder, fcntl.LOCK_EX)
        return path, before

    def test_a_held_lock_refuses_in_process(self):
        # the wait bound belongs to the process that appends, so it is patched
        # here and the append path is called directly: this covers the bound
        if fcntl is None:
            self.skipTest("fcntl is unavailable")
        repo = self.repo()
        path, before = self.held_lock(repo)
        saved = tr.LOCK_WAIT
        tr.LOCK_WAIT = 0.05
        try:
            _, problems = tr.append_claim(repo, "q", self.valid())
        finally:
            tr.LOCK_WAIT = saved
        self.assertTrue(problems, problems)
        self.assertIn("claims.jsonl", " ".join(problems), problems)
        self.assertEqual(read(path), before)

    def test_a_held_lock_refuses_the_claim(self):
        # end to end through the CLI, whose own interpreter keeps its default
        # bound: this case costs about one second by design, not by accident
        if fcntl is None:
            self.skipTest("fcntl is unavailable")
        repo = self.repo()
        path, before = self.held_lock(repo)
        proc = self.cli(repo, "claim", "q", payload=self.valid())
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL q: ", proc.stdout)
        self.assertIn("claims.jsonl", proc.stdout)
        self.assertEqual(read(path), before)


class Tracking(Workspace):
    """I1: the tracking requirement, named rather than assumed.

    The project ignores `.tezgah/`, and the commits the order rule reads are made
    in `.tezgah`'s own private repository; a line the project committed before
    the move keeps its proof in the project's history."""

    def ws_log(self, repo, rel):
        return self.git(os.path.join(repo, ".tezgah"), "log", "--all",
                        "--format=%H", "--", rel).split()

    def unmoved(self, repo):
        """A line whose `.tezgah` has no repository yet: the layout before the move."""
        self.line(repo)
        shutil.rmtree(os.path.join(repo, ".tezgah", ".git"))

    def test_init_makes_the_private_repository_and_keeps_the_project_clean(self):
        repo = self.repo()
        self.write(os.path.join(repo, ".gitignore"), "# mine\n/build/")
        self.commit(repo, "the user's ignore", when=BEFORE)
        proc = self.cli(repo, "init", "q", "--ask", "does q hold?")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isdir(os.path.join(repo, ".tezgah", ".git")))
        body = read(os.path.join(repo, ".gitignore"))
        self.assertTrue(body.startswith("# mine\n/build/\n"), body)
        self.assertIn("/.tezgah/\n", body)
        # the project sees one changed line of its own ignore file and nothing
        # of the line, and nothing was staged
        self.assertEqual(self.git(repo, "status", "--porcelain").split(),
                         ["M", ".gitignore"])
        self.assertEqual(self.git(repo, "diff", "--cached", "--name-only").strip(), "")
        self.assertIn("tezgah-research commit q", proc.stdout)

    def test_a_line_in_the_private_repository_is_not_called_unorderable(self):
        # the project ignores `.tezgah/`, and that is not the private repository's
        # business: the pair is committable there, and ordered from there
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.assertFalse(hit("ignored by", self.warnings(repo)), self.warnings(repo))
        self.assertEqual(self.errors(repo), [])
        rel = "research/open/q/experiments/h1/results.jsonl"
        self.assertEqual(len(self.ws_log(repo, rel)), 1)
        self.assertEqual(self.git(repo, "log", "--format=%H", "--", ".tezgah").strip(), "")

    def test_the_private_repository_decides_the_order(self):
        repo = self.repo()
        self.line(repo)
        self.results(repo)
        self.commit(repo, "results first", when=BEFORE)
        self.protocol(repo)
        self.commit(repo, "protocol after", when=AFTER)
        self.assertTrue(hit(NOT_A_PREDICTION, self.errors(repo)), self.errors(repo))

    def test_a_line_the_project_committed_before_the_move_keeps_its_order(self):
        # the move imports the whole line in one private commit; the project's
        # history still holds the two commits that order it, and the import is
        # not read as one commit adding both files
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.git(os.path.join(repo, ".tezgah"), "init", "-q")
        self.commit(repo, "import", when=AFTER)
        self.assertEqual(len(self.ws_log(repo, "research/open/q/experiments/h1/protocol.md")), 1)
        errors = self.errors(repo)
        self.assertFalse(hit(BOTH_TOGETHER, errors), errors)
        self.assertEqual(errors, [])

    def test_a_line_moved_to_done_keeps_its_order(self):
        # 2026-10-03: closing a line moves it from open/ to done/, and the move
        # read as the commit that added protocol, results, criteria and state at
        # once - every moved line failed "plan before run" though its history
        # holds the order
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.assertEqual(tr.move_line(repo, "q", "done")[1], None)
        self.commit(repo, "move to done", when=AFTER)
        self.assertIn(os.path.join("research", "done", "q"), tr.line_dir(repo, "q"))
        self.assertEqual(self.errors(repo), [])

    def test_a_line_the_project_ordered_keeps_its_order_after_the_move_to_done(self):
        # the order lives in the project's history under the line's old name;
        # after the private repository imports it and closing moves it to done/,
        # the project log has to be asked under that old name
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.git(os.path.join(repo, ".tezgah"), "init", "-q")
        self.commit(repo, "import", when=AFTER)
        self.assertEqual(tr.move_line(repo, "q", "done")[1], None)
        self.commit(repo, "move to done", when=AFTER)
        errors = self.errors(repo)
        self.assertFalse(hit(BOTH_TOGETHER, errors), errors)
        self.assertEqual(errors, [])

    def test_a_protocol_renamed_in_from_another_line_does_not_inherit_its_age(self):
        # consult review of plan 032: following every rename let another line's
        # older protocol, moved into this line after its results, read as added
        # before them; only the line's own open/done moves are followed
        repo = self.repo()
        self.line(repo, slug="p")
        self.protocol(repo, slug="p")
        self.commit(repo, "another line's protocol", when=BEFORE)
        self.line(repo)
        self.results(repo)
        self.commit(repo, "results with no protocol", when=AFTER)
        ws = os.path.join(repo, ".tezgah")
        self.git(ws, "mv", *self.rel(ws, os.path.join(self.exp_dir(repo, "p"), "protocol.md"),
                                     os.path.join(self.exp_dir(repo), "protocol.md")))
        self.commit(repo, "protocol moved in after the run", when=AFTER)
        errors = self.errors(repo)
        self.assertTrue(hit("entered the history after results.jsonl", errors)
                        or hit(BOTH_TOGETHER, errors), errors)

    def test_an_edit_after_the_run_is_caught_across_a_case_change(self):
        # consult review round 2: the run's blob sits under the spelling the
        # directory had then (the migration lowercased `D1` to `d1`), so the
        # comparison has to read the historical name, not today's
        repo = self.repo()
        self.line(repo)
        d = self.protocol(repo, h="H1")
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo, h="H1")
        self.commit(repo, "results", when=AFTER)
        ws = os.path.join(repo, ".tezgah")
        exps = os.path.dirname(d)
        self.git(ws, "mv", *self.rel(ws, d, os.path.join(exps, "tmp")))
        self.git(ws, "mv", *self.rel(ws, os.path.join(exps, "tmp"), os.path.join(exps, "h1")))
        self.commit(repo, "lowercase the experiment", when=AFTER)
        self.write(os.path.join(exps, "h1", "protocol.md"),
                   "# Protocol\n\nprediction: whatever the run showed\n")
        self.commit(repo, "protocol rewritten after the run", when=AFTER)
        errors = self.errors(repo)
        self.assertTrue(hit("protocol.md changed after the run", errors), errors)

    def test_a_protocol_edited_after_the_run_is_refused_after_the_move_too(self):
        # following the rename must not lose the edit: the blob the run saw lives
        # under the old path
        repo = self.repo()
        self.line(repo)
        d = self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.write(os.path.join(d, "protocol.md"),
                   "# Protocol\n\nprediction: whatever the run showed\n")
        self.commit(repo, "protocol rewritten after the run", when=AFTER)
        tr.move_line(repo, "q", "done")
        self.commit(repo, "move to done", when=AFTER)
        errors = self.errors(repo)
        self.assertTrue(hit("protocol.md changed after the run", errors), errors)
        self.assertFalse(hit(BOTH_TOGETHER, errors), errors)

    def test_an_untracked_protocol_is_not_a_change_after_the_run(self):
        # `git rm --cached` takes the path out of the index and leaves the blob
        # the run wrote, so it is not a change: the 2026-09-24 commit that
        # untracked `.tezgah/` was read as a protocol edited after the results
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        rel = os.path.relpath(os.path.join(self.exp_dir(repo), "protocol.md"), repo)
        self.git(repo, "rm", "--cached", "-q", "--", rel)
        self.git(repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test",
                 "-c", "user.email=test@example.invalid", "commit", "-q", "-m",
                 "untrack the line", when=AFTER)
        self.assertEqual(self.errors(repo), [])

    def test_a_project_commit_precedes_a_private_one(self):
        # the protocol's add is the project's and the results' is the private
        # repository's: two histories, so git cannot order them and the line warns
        # instead of passing. The declared bridge is the way to prove a
        # cross-history order
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        self.commit(repo, "protocol, before the move", when=BEFORE)
        self.git(os.path.join(repo, ".tezgah"), "init", "-q")
        self.results(repo)
        self.commit(repo, "results, after it", when=AFTER)
        errors, warnings = tr.check_line(repo, "q")
        self.assertEqual(errors, [])
        self.assertTrue(hit("git could not order the protocol against the results",
                            warnings), warnings)

    def test_a_private_protocol_does_not_precede_project_results(self):
        # the same two histories the other way round: unorderable, so a warning
        # and never a pass - the guess that a private commit never precedes a
        # project one was the cross-history bypass the bridge replaced
        repo = self.repo()
        self.unmoved(repo)
        self.results(repo)
        self.commit(repo, "results, before the move", when=BEFORE)
        self.git(os.path.join(repo, ".tezgah"), "init", "-q")
        self.protocol(repo)
        self.commit(repo, "protocol, after it", when=AFTER)
        errors, warnings = tr.check_line(repo, "q")
        self.assertFalse(hit(NOT_A_PREDICTION, errors), errors)
        self.assertTrue(hit("git could not order the protocol against the results",
                            warnings), warnings)

    def test_a_cross_history_pair_is_not_ordered_by_is_ancestor(self):
        # `_holds` used to answer "any project commit precedes any private one",
        # which orders an add in one history against an add in another: that is
        # the bypass the declared bridge replaces, so the pair is undecided
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        self.commit(repo, "protocol, before the move", when=BEFORE)
        project = self.git(repo, "rev-parse", "HEAD").strip()
        self.git(os.path.join(repo, ".tezgah"), "init", "-q")
        self.results(repo)
        self.commit(repo, "results, after it", when=AFTER)
        private = self.git(os.path.join(repo, ".tezgah"), "rev-parse", "HEAD").strip()
        self.assertIsNone(tr.is_ancestor(repo, project, private))
        self.assertIsNone(tr.is_ancestor(repo, private, project))

    def test_a_file_the_private_repository_ignores_warns_with_its_fix(self):
        repo = self.repo()
        self.line(repo)
        self.write(os.path.join(repo, ".tezgah", ".gitignore"), "*.jsonl\n")
        self.protocol(repo)
        self.results(repo)
        warnings = self.warnings(repo)
        self.assertTrue(hit("results.jsonl is ignored by .gitignore:1:*.jsonl", warnings),
                        warnings)
        self.assertTrue(hit("`git -C .tezgah add -f "
                            "research/open/q/experiments/h1/results.jsonl`", warnings),
                        warnings)
        self.assertEqual(self.errors(repo), [])
        self.assertTrue(hit("ignored by", self.errors(repo, strict=True)))
        # the same line checked without git pays nothing for the rule
        self.assertFalse(hit("ignored by", self.warnings(repo, git=False)))

    def test_no_private_repository_names_the_subcommand_that_makes_one(self):
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        warnings = self.warnings(repo)
        self.assertTrue(hit("protocol.md is ignored by .gitignore", warnings), warnings)
        self.assertTrue(hit('`tezgah-research commit q "<message>"`', warnings), warnings)

    def test_a_line_with_no_experiment_has_no_pair_to_order(self):
        # nothing to prove yet, so nothing is claimed either way
        repo = self.repo()
        self.unmoved(repo)
        self.assertFalse(hit("ignored by", self.warnings(repo)))

    def test_commit_orders_the_line_in_the_private_repository(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        first = self.cli(repo, "commit", "q", "protocol h1")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.results(repo)
        second = self.cli(repo, "commit", "q", "results h1")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(len(self.ws_log(repo, "research/open/q")), 2)
        self.assertEqual(self.errors(repo), [])
        # the project's own index is never touched
        self.assertEqual(self.git(repo, "diff", "--cached", "--name-only").strip(), "")
        # nothing left to commit is a failure, not a silent success
        self.assertEqual(self.cli(repo, "commit", "q", "again").returncode, 1)
        self.assertEqual(self.cli(repo, "commit", "nope", "x").returncode, 2)


class LockedEvaluation(Workspace):
    """I2: the evaluation is locked before anything runs, and the environment it
    was measured in is recorded beside it."""

    def state(self, repo, **over):
        path = os.path.join(tr.line_dir(repo, "q"), "state.json")
        state = json.loads(read(path))
        for key, value in over.items():
            if key == "evaluation":
                state["evaluation"] = value
            else:
                state[key] = value
        self.write(path, json.dumps(state))
        return state

    def test_an_empty_evaluation_past_bootstrap_is_refused(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.state(repo, evaluation={"metric": "", "baseline": "",
                                     "locked_at": ""})
        errors = self.errors(repo)
        self.assertTrue(hit("evaluation locks no metric, baseline, locked_at",
                            errors), errors)

    def test_the_same_emptiness_at_bootstrap_warns(self):
        repo = self.repo()
        base = tr.line_dir(repo, "q")
        tr.init(repo, "q", question="does it help?", created="2026-01-01")
        self.assertEqual(self.errors(repo), [])
        self.assertTrue(hit("evaluation locks no metric, baseline, locked_at",
                            self.warnings(repo)))
        self.assertTrue(hit("evaluation locks no metric",
                            self.errors(repo, strict=True)))
        self.assertTrue(os.path.isdir(base))

    def test_an_evaluation_that_is_not_an_object_is_refused(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.state(repo, evaluation="p95 vs the baseline")
        self.assertTrue(hit("evaluation is str, not the object", self.errors(repo)))
        self.state(repo, evaluation=None)
        self.assertTrue(hit("evaluation is absent, not the object",
                            self.errors(repo)))

    def test_an_environment_that_is_not_an_object_is_refused(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        evaluation = {"metric": "p95", "baseline": "the bare build",
                      "locked_at": "2026-01-01", "environment": "a laptop"}
        self.state(repo, evaluation=evaluation)
        self.assertTrue(hit("environment is str, not the object",
                            self.errors(repo)))
        evaluation["environment"] = {"model": "x", "harness": "orx"}
        self.state(repo, evaluation=evaluation)
        self.assertEqual(self.errors(repo), [])

    def test_the_two_gate_fields_are_validated_only_when_present(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        evaluation = {"metric": "p95", "baseline": "the bare build",
                      "locked_at": "2026-01-01",
                      "capability_tolerance": "capability metric within 0.02 of the "
                                              "baseline",
                      "counter_metric": "tokens per task"}
        self.state(repo, evaluation=evaluation)
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit(["capability_tolerance", "counter_metric"],
                             self.errors(repo) + self.warnings(repo)))
        evaluation["counter_metric"] = ""
        self.state(repo, evaluation=evaluation)
        errors = self.errors(repo)
        self.assertTrue(hit("counter_metric", errors), errors)
        evaluation["counter_metric"] = "tokens per task"
        evaluation["capability_tolerance"] = 0.02
        self.state(repo, evaluation=evaluation)
        errors = self.errors(repo)
        self.assertTrue(hit("capability_tolerance", errors), errors)
        self.assertFalse(hit("counter_metric", errors), errors)

    def test_a_state_json_carrying_neither_gate_still_validates(self):
        # The regression case is the tree itself: all fourteen lines under
        # `.tezgah/research/` lock `metric`, `baseline` and `locked_at`, and not one
        # of them carries either new field. Their absence is the ordinary state of a
        # line, so it is neither refused nor warned about - a rule that required the
        # pair would refuse the whole layer.
        repo = self.repo()
        self.line(repo, phase="inner")
        findings = self.errors(repo) + self.warnings(repo)
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit(["capability_tolerance", "counter_metric"], findings),
                         findings)

    def test_a_hypothesis_that_states_nothing_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.state(repo, hypotheses=["the cache helps", {"id": "H2"}, "",
                                     {"id": "H3", "text": "  "}])
        errors = self.errors(repo)
        self.assertTrue(hit("hypothesis 2 states nothing", errors), errors)
        self.assertTrue(hit("hypothesis 4 states nothing", errors), errors)
        self.state(repo, hypotheses="the cache helps")
        self.assertIn("state.json hypotheses is not a list", self.errors(repo))

    def test_a_session_entry_with_a_bad_tag_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.state(repo, sessions=[{"date": "2026-09-20", "tag": "user-typed-it",
                                    "what": "asked for the audit"}])
        errors = self.errors(repo)
        self.assertTrue(hit("sessions[1] tag 'user-typed-it' is not one of",
                            errors), errors)

    def test_a_session_entry_that_is_not_an_object_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.state(repo, sessions=["did the audit", {"tag": "user"}])
        errors = self.errors(repo)
        self.assertTrue(hit("sessions[1] is not an object", errors), errors)
        self.assertTrue(hit("sessions[2] records no date", errors), errors)
        self.assertTrue(hit("sessions[2] records nothing that happened", errors),
                        errors)

    def test_the_grouped_session_shape_is_read_too(self):
        # five lines in this repository keep the date on the entry and the tag on
        # each event; a rule that only read the flat shape would refuse them
        repo = self.repo()
        self.line(repo)
        self.state(repo, sessions=[{"date": "2026-09-20", "events": [
            {"tag": "user", "what": "asked for the audit"},
            "ai-executed: ran the probes",
            {"tag": "guessed", "what": "inferred"},
            "no tag here",
        ]}])
        errors = self.errors(repo)
        self.assertTrue(hit("events[3] tag 'guessed' is not one of", errors), errors)
        self.assertTrue(hit("events[4] does not start with a provenance tag",
                            errors), errors)
        self.assertEqual(len(named(errors, "events[")), 2, errors)


class ClaimKinds(Workspace):
    """I3: what a claim's proof is a proof of, and what each kind has to cite."""

    def base(self, repo):
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        return base

    def test_a_kind_outside_the_enum_is_refused(self):
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, kind="vibes"))
        self.assertTrue(hit("claim c1 kind 'vibes' is not one of", self.errors(repo)))

    def test_a_claim_with_no_kind_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.base(repo)
        claim = dict(CLAIM)
        del claim["kind"]
        self.claims(repo, claim)
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("claim c1 carries no kind", warnings), warnings)
        self.assertTrue(hit("carries no kind", self.errors(repo, strict=True)))

    def test_a_proof_naming_no_artifact_is_refused_for_every_kind(self):
        # the fabricated-evidence failure in its plainest form: "verified by
        # hand" is prose, and no kind makes it evidence
        repo = self.repo()
        self.base(repo)
        for kind in ("evidence", "code", "literature", "derivation"):
            with self.subTest(kind=kind):
                self.claims(repo, dict(CLAIM, kind=kind,
                                       proof="verified by hand, I checked it"))
                errors = self.errors(repo)
                self.assertTrue(hit("cites no artifact", errors), errors)

    def test_a_bare_filename_and_a_command_path_are_artifacts(self):
        # fifteen claims in this repository's own lines cite `findings.md` or
        # `bin/tezgah-status`; neither is path-shaped to the narrow pattern, and
        # both are files the reader can open
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, kind="code",
                               proof="the stop rule in bin/tezgah-research and findings.md"))
        self.assertEqual(self.errors(repo), [])

    def test_an_evidence_claim_bound_to_a_run_with_no_rows_is_reported(self):
        repo = self.repo()
        self.base(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "results.jsonl"), "\n")
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="experiments/h1/results.jsonl (7 runs)"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("cites experiment h1, whose results.jsonl holds no row",
                            warnings), warnings)
        self.assertEqual(self.errors(repo), [])
        strict = self.errors(repo, strict=True)
        self.assertTrue(hit("recorded nothing", strict), strict)

    def test_an_evidence_claim_must_name_something_the_line_produced(self):
        """P6: a claim may cite any file that exists, so `kind: evidence` with a
        proof naming only a repository file used to pass both sides - the line
        never produced the file, and nothing said so. What makes a claim evidence
        is an artifact of the line; a mixed proof (its results row beside the code
        it is about) stays valid, and the rule is the evidence kind's alone."""
        repo = self.repo()
        self.base(repo)
        self.write(os.path.join(repo, "src", "unrelated.py"), "x = 1\n")
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="src/unrelated.py"))
        errors = self.errors(repo)
        self.assertTrue(hit("is an evidence claim and cites nothing the line "
                            "produced: src/unrelated.py", errors), errors)
        self.assertTrue(hit("cites nothing the line produced",
                            self.errors(repo, strict=True)))
        # a code claim is about the repository, so the same proof is its own kind
        self.claims(repo, dict(CLAIM, kind="code", proof="src/unrelated.py"))
        self.assertFalse(hit("cites nothing the line", self.errors(repo)))
        # and the mixed proof - the results row beside the code it is about
        self.protocol(repo)
        self.results(repo)
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="experiments/h1/results.jsonl and "
                                     "src/unrelated.py"))
        self.assertEqual(self.errors(repo), [])

    def test_an_evidence_claim_bound_to_a_missing_run_is_reported(self):
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="experiments/ghost/results.jsonl"))
        self.assertTrue(hit("whose results.jsonl is missing", self.warnings(repo)))

    def test_a_literature_claim_must_cite_a_note_under_literature(self):
        repo = self.repo()
        self.base(repo)
        self.write(os.path.join(repo, "bin", "tezgah-status"), "#!/bin/sh\n")
        self.claims(repo, dict(CLAIM, kind="literature",
                               proof="to_human/report.md"))
        errors = self.errors(repo)
        self.assertTrue(hit("is a literature claim and cites no note under "
                            "literature/", errors), errors)
        self.note(repo, "1707-x.md", "# A note\n")
        self.index(repo, {"note": "1707-x.md", "class": "grey",
                          "quality": "a note, read as a claim",
                          "verified": ["the page itself", "its reference list"]})
        self.claims(repo, dict(CLAIM, kind="literature",
                               proof="literature/1707-x.md; bin/tezgah-status"))
        self.assertEqual(self.errors(repo), [])
        # a note the line does not have is still refused
        self.claims(repo, dict(CLAIM, kind="literature",
                               proof="literature/ghost.md"))
        errors = self.errors(repo)
        self.assertTrue(hit("cites literature/ghost.md, which is not a note under "
                            "literature/", errors), errors)

    def test_the_write_path_accepts_what_the_checker_only_warns_about(self):
        """The evidence-row rule is the one place the two judges could disagree:
        `check` warns about an empty results.jsonl (so a session mid-flight is not
        blocked and `--strict` is the switch that refuses it), so `claim` has to
        record the claim under the same rule. This test caught the writer refusing
        it - the failure the docstring's 'never refuse what the checker accepts'
        names."""
        repo = self.repo()
        base = self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "results.jsonl"), "")
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        claim = dict(CLAIM, kind="evidence", proof="experiments/h1/results.jsonl")
        self.assertEqual(tr.claim_problems(claim, base, repo), [])
        _id, problems = tr.append_claim(repo, "q", claim)
        self.assertEqual(problems, [])
        self.assertTrue(hit("cites experiment h1, whose results.jsonl holds no row",
                            self.warnings(repo)))
        self.assertEqual(self.errors(repo), [])
        self.assertTrue(hit("recorded nothing", self.errors(repo, strict=True)))

    def test_a_derivation_claim_has_to_cite_something_the_line_holds(self):
        repo = self.repo()
        self.base(repo)
        self.write(os.path.join(repo, "bin", "tezgah-status"), "#!/bin/sh\n")
        self.claims(repo, dict(CLAIM, kind="derivation",
                               proof="to_human/report.md"))
        self.assertEqual(self.errors(repo), [])
        self.claims(repo, dict(CLAIM, kind="derivation",
                               proof="bin/tezgah-status, which the line never held"))
        errors = self.errors(repo)
        self.assertTrue(hit("is a derivation and cites bin/tezgah-status, which the "
                            "line itself does not hold", errors), errors)

    def test_an_orx_token_has_to_resolve_to_a_receipt(self):
        # the token is the only link between a claim and the run it came out of,
        # so an id with no log beside it is a reference nobody can follow
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, kind="evidence",
                               proof="orx:9f0c1d2e, 7 runs"))
        errors = self.errors(repo)
        self.assertTrue(hit("cites orx:9f0c1d2e, and no raw/9f0c1d2e.log is under "
                            "this line or the repository", errors), errors)
        raw = os.path.join(self.exp_dir(repo), "raw")
        os.makedirs(raw, exist_ok=True)
        self.write(os.path.join(raw, "9f0c1d2e.log"), "the run's log\n")
        self.assertFalse(hit("no raw/", self.errors(repo)))

    def test_the_write_path_requires_a_kind(self):
        repo = self.repo()
        self.base(repo)
        claim = dict(CLAIM)
        del claim["kind"]
        _id, problems = tr.append_claim(repo, "q", claim)
        self.assertTrue(problems, "a claim with no kind was accepted")
        self.assertTrue(hit("kind None is not one of", problems), problems)

    def test_the_write_path_refuses_a_proof_that_names_no_artifact(self):
        repo = self.repo()
        self.base(repo)
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, kind="code", proof="verified by hand, I checked it"))
        self.assertTrue(problems, "a prose proof was accepted")
        self.assertTrue(hit("cites no artifact", problems), problems)

    def test_the_write_path_refuses_an_evidence_claim_bound_to_no_line_artifact(self):
        # the same rule the checker applies, so `claim` refuses what `check` would
        # refuse rather than recording a row that fails a second later
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(repo, "src", "unrelated.py"), "x = 1\n")
        claim = dict(CLAIM, kind="evidence", proof="src/unrelated.py")
        problems = tr.claim_problems(claim, base, repo)
        self.assertTrue(problems, "the write path accepted a repo-file proof")
        self.assertTrue(hit("is an evidence claim and cites nothing the line "
                            "produced", problems), problems)
        _id, problems = tr.append_claim(repo, "q", claim)
        self.assertTrue(problems, problems)
        self.assertEqual(read(os.path.join(base, "claims.jsonl")), "")

    def test_the_write_path_refuses_an_orx_run_with_no_receipt(self):
        repo = self.repo()
        self.base(repo)
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, kind="evidence", proof="orx:abc123"))
        self.assertTrue(problems, problems)
        self.assertTrue(hit("no raw/abc123.log", problems), problems)


class Supersedes(Workspace):
    """A superseded claim is visible, and only to a claim the line holds.

    C27 of this repository's own audit line went stale when a later fix changed
    its number, and the tool that records claims has no update command - so the
    correction was a new claim (C34), and nothing said the old one was superseded.
    The relation is what says it; the two halves of the rule are the two ways it
    can fail."""

    def base(self, repo):
        base = self.line(repo, phase="inner")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        return base

    def test_a_link_warns_naming_both_ids_and_strict_refuses_it(self):
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, id="C27", proof="to_human/report.md"),
                    dict(CLAIM, id="C34", proof="to_human/report.md",
                         supersedes="C27"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("claim C34 supersedes C27: a reader who opens C27 alone "
                            "reads the statement this line has since replaced",
                            warnings), warnings)
        strict = self.errors(repo, strict=True)
        self.assertTrue(hit("supersedes C27", strict), strict)
        # and the plain run stays green: a recorded relation is not a defect
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(self.warnings(repo, strict=True), [])

    def test_a_list_of_ids_is_read(self):
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, id="C1", proof="to_human/report.md"),
                    dict(CLAIM, id="C2", proof="to_human/report.md"),
                    dict(CLAIM, id="C3", proof="to_human/report.md",
                         supersedes=["C1", "C2"]))
        warnings = self.warnings(repo)
        self.assertTrue(hit("claim C3 supersedes C1:", warnings), warnings)
        self.assertTrue(hit("claim C3 supersedes C2:", warnings), warnings)

    def test_an_id_no_claim_carries_is_refused_by_both_readings(self):
        # the write path and the checker are two readings of one rule; a link to
        # nothing is refused by both, and neither writes one
        repo = self.repo()
        base = self.base(repo)
        self.claims(repo, dict(CLAIM, id="C34", proof="to_human/report.md",
                               supersedes="C27"))
        self.assertTrue(hit("claim C34 supersedes C27, and no claim in this line "
                            "carries that id", self.errors(repo)), self.errors(repo))
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, id="C35", proof="to_human/report.md", supersedes="C27"))
        self.assertTrue(hit("claim C35 supersedes C27, and no claim in this line "
                            "carries that id", problems), problems)
        self.assertEqual(len(read(os.path.join(base, "claims.jsonl")).splitlines()),
                         1)

    def test_a_value_that_is_not_an_id_or_a_list_is_refused(self):
        repo = self.repo()
        base = self.base(repo)
        self.claims(repo, dict(CLAIM, id="C1", proof="to_human/report.md",
                               supersedes=27))
        self.assertTrue(hit("claim C1 supersedes 27 is not a claim id or a list of "
                            "them", self.errors(repo)), self.errors(repo))
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, id="C2", proof="to_human/report.md", supersedes=["C1", 2]))
        self.assertTrue(hit("is not a claim id or a list of them", problems), problems)
        self.assertEqual(len(read(os.path.join(base, "claims.jsonl")).splitlines()),
                         1)

    def test_a_claim_without_the_field_is_untouched(self):
        repo = self.repo()
        self.base(repo)
        self.claims(repo, dict(CLAIM, id="C1", proof="to_human/report.md"))
        self.assertFalse(hit("supersedes", self.warnings(repo)), self.warnings(repo))

    def test_the_write_path_records_a_link_the_line_holds(self):
        repo = self.repo()
        base = self.base(repo)
        self.claims(repo, dict(CLAIM, id="C1", proof="to_human/report.md"))
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, id="C2", proof="to_human/report.md", supersedes="C1"))
        self.assertEqual(problems, [])
        self.assertEqual(len(read(os.path.join(base, "claims.jsonl")).splitlines()),
                         2)
        self.assertTrue(hit("supersedes C1", self.warnings(repo)))


class ResultRows(Workspace):
    """I4: every results row says where it came from."""

    def test_a_row_with_no_source_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo, row={"run": 1, "p95": 0.9})
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("results.jsonl:1 carries no source, so this row cannot "
                            "be traced back to the run that produced it",
                            warnings), warnings)
        strict = self.errors(repo, strict=True)
        self.assertTrue(hit("carries no source", strict), strict)

    def test_a_row_that_claims_a_source_and_gives_none_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo, row={"run": 1, "p95": 0.9, "source": "  "})
        self.assertTrue(hit("results.jsonl:1 carries an empty source",
                            self.errors(repo)))

    def test_a_results_file_that_does_not_parse_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, '{"run": 1, "source": "run.py"}\nnot json at all\n')
        errors = self.errors(repo)
        self.assertTrue(hit("results.jsonl:2 does not parse", errors), errors)

    def test_a_row_that_is_not_an_object_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, "[1, 2, 3]\n")
        self.assertTrue(hit("results.jsonl:1 is a list, not the object a row is",
                            self.errors(repo)))

    def test_a_blank_line_is_not_a_row(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, '{"run": 1, "source": "run.py"}\n\n')
        self.assertEqual(self.errors(repo), [])

    def test_a_row_scope_outside_the_vocabulary_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo, row={"run": 1, "source": "run.py", "scope": "synthetic"})
        errors = self.errors(repo)
        self.assertTrue(hit("results.jsonl:1 scope 'synthetic' is not one of real, "
                            "fixture, derived", errors), errors)

    def test_rows_that_declare_no_scope_are_named_by_count(self):
        """The field cannot be inferred afterwards, so a missing one is reported as
        the debt it is - once per file, with the count, rather than once per row."""
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, '{"run": 1, "source": "run.py"}\n'
                         '{"run": 2, "source": "run.py"}\n'
                         '{"run": 3, "source": "run.py", "scope": "real"}\n')
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("2 of 3 rows declare no scope", warnings), warnings)
        self.assertEqual(len(named(warnings, "declare no scope")), 1, warnings)
        self.assertTrue(hit("2 of 3 rows declare no scope",
                            self.errors(repo, strict=True)))

    def test_a_row_that_declares_a_fixture_input_is_clean(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo, row={"run": 1, "source": "probe.py", "scope": "fixture",
                                "fixture": "a temp HOME and a generated repository "
                                           "of 40 files"})
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit("declare no scope", self.warnings(repo)),
                         self.warnings(repo))
        self.assertFalse(hit("do not say what was generated", self.warnings(repo)),
                         self.warnings(repo))

    def test_a_fixture_row_that_says_nothing_about_its_input_warns_and_strict_refuses(self):
        """`scope: fixture` says the numbers came from a generated input; the field
        beside it says which one, and a row that stops at the class is reported once
        per file with the count, the way an unscoped row is."""
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, '{"run": 1, "source": "probe.py", "scope": "fixture"}\n'
                         '{"run": 2, "source": "probe.py", "scope": "fixture", '
                         '"fixture": "a temp HOME"}\n'
                         '{"run": 3, "source": "run.py", "scope": "real"}\n')
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("1 of 3 rows declare scope fixture and do not say what "
                            "was generated", warnings), warnings)
        self.assertEqual(len(named(warnings, "declare scope fixture")), 1, warnings)
        self.assertTrue(hit("1 of 3 rows declare scope fixture and do not say",
                            self.errors(repo, strict=True)),
                        self.errors(repo, strict=True))

    def test_a_fixture_description_that_is_present_and_names_nothing_is_refused(self):
        """The row answers the question and says nothing: the half a checker can
        decide, so it is a refusal and not the warn class."""
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, '{"run": 1, "source": "probe.py", "scope": "fixture", '
                         '"fixture": "   "}\n'
                         '{"run": 2, "source": "probe.py", "scope": "fixture", '
                         '"fixture": 7}\n')
        errors = self.errors(repo)
        self.assertTrue(hit("results.jsonl:1 carries an empty fixture description",
                            errors), errors)
        self.assertTrue(hit("results.jsonl:2 carries a fixture description that is "
                            "a int, not the text naming what was generated", errors),
                        errors)
        self.assertFalse(hit("do not say what was generated", errors), errors)

    def test_a_real_row_needs_no_fixture_description(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit("declare scope fixture", self.warnings(repo)),
                         self.warnings(repo))

    def test_a_derived_row_needs_no_fixture_description(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo, row={"run": 1, "source": "merge.py", "scope": "derived"})
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit("declare scope fixture", self.warnings(repo)),
                         self.warnings(repo))


class ClaimScopes(Workspace):
    """What a claim's numbers were measured on, and whether they are in its proof."""

    def fixture_line(self, repo, scope="fixture"):
        """A line whose one experiment recorded one row, scoped as asked, with a
        claim in place to rest on it. A fixture row names what was generated, so the
        tests here are about the claims and not about the row rule beside them."""
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# report\n")
        self.protocol(repo)
        row = {"run": 1, "p95": 0.9, "source": "probe.py", "scope": scope}
        if scope == "fixture":
            row["fixture"] = "a probe that builds its own input"
        self.results(repo, row=row)
        return base

    def test_a_claim_may_not_outrun_the_scope_of_its_rows(self):
        """The decidable half: two recorded strings disagree, and the claim would
        present a generated input as the running system."""
        repo = self.repo()
        base = self.fixture_line(repo)
        claim = dict(CLAIM, scope="real", proof="experiments/h1/results.jsonl")
        self.claims(repo, claim)
        errors = self.errors(repo)
        self.assertTrue(hit("declares scope real and every row it rests on records "
                            "fixture", errors), errors)
        self.assertTrue(tr.claim_problems(claim, base, repo),
                        "the write path has to refuse what the checker refuses")
        # and over real rows the same claim is accepted
        self.results(repo, row={"run": 1, "p95": 0.9, "source": "run.py",
                                "scope": "real"})
        self.assertFalse(hit("records fixture", self.errors(repo)))

    def test_a_claim_resting_on_a_fixture_row_must_declare_it(self):
        repo = self.repo()
        self.fixture_line(repo)
        self.claims(repo, dict(CLAIM, proof="experiments/h1/results.jsonl"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("rests on 1 fixture row(s) and declares no scope",
                            warnings), warnings)
        self.assertTrue(hit("declares no scope",
                            self.errors(repo, strict=True)),
                        self.errors(repo, strict=True))
        # declaring it is the whole ask, and then nothing is reported
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl"))
        self.assertFalse(hit("declares no scope", self.warnings(repo)),
                         self.warnings(repo))

    def test_a_claim_scope_outside_the_vocabulary_is_refused(self):
        repo = self.repo()
        base = self.fixture_line(repo)
        claim = dict(CLAIM, scope="synthetic", proof="experiments/h1/results.jsonl")
        self.claims(repo, claim)
        self.assertTrue(hit("claim c1 scope 'synthetic' is not one of", self.errors(repo)))
        self.assertTrue(tr.claim_problems(claim, base, repo))

    def test_a_number_a_claim_asserts_lives_in_the_artifact_it_cites(self):
        repo = self.repo()
        self.fixture_line(repo)
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl",
                               statement="the cache cut p95 to 0.4 and helped 7 of 9 runs"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("asserts 2 number(s)", warnings), warnings)
        self.assertTrue(hit("0.4", warnings), warnings)
        self.assertTrue(hit("asserts 2 number(s)", self.errors(repo, strict=True)),
                        self.errors(repo, strict=True))

    def test_a_metric_name_is_not_a_number_a_claim_asserts(self):
        """`p95` is an identifier: the first pass of E2 counted it and warned about a
        claim whose proof could not contain "95", which is the tokenizer this pins."""
        repo = self.repo()
        self.fixture_line(repo)
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl",
                               statement="the cache cuts p95"))
        self.assertFalse(hit("asserts", self.warnings(repo)), self.warnings(repo))

    def test_a_date_a_claim_names_is_not_a_number_it_asserts(self):
        """`2026-09-19` used to tokenise into three numbers, which is how a line's
        claim was warned about the day it was read on rather than about a
        measurement."""
        repo = self.repo()
        self.fixture_line(repo)
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl",
                               statement="measured on 2026-09-19, p95 was 0.9"))
        self.assertFalse(hit("asserts", self.warnings(repo)), self.warnings(repo))

    def test_a_measurement_beside_a_date_is_still_a_number_it_asserts(self):
        repo = self.repo()
        self.fixture_line(repo)
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl",
                               statement="measured on 2026-09-19, the cache cut p95 "
                                         "to 0.4"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("asserts 1 number(s)", warnings), warnings)
        self.assertTrue(hit("0.4", warnings), warnings)
        self.assertFalse(hit("2026", warnings), warnings)

    def test_a_bare_filename_proof_is_read_for_the_numbers_it_holds(self):
        """The rule reads the artifacts the proof rule resolves, so a proof naming a
        bare `findings.md` is checked against that file: a reader that only took
        directory-qualified paths passed the claim against nothing."""
        repo = self.repo()
        self.fixture_line(repo, scope="real")
        self.patterns(repo, "the cache cuts p95 [c1]")
        self.claims(repo, dict(CLAIM, scope="real", proof="findings.md",
                               statement="the cache cut p95 by 12"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("asserts 1 number(s) that findings.md does not contain: 12",
                            warnings), warnings)

    def test_a_thousands_separator_is_a_rendering_not_a_different_number(self):
        repo = self.repo()
        self.fixture_line(repo)
        self.results(repo, row={"run": 1, "bytes": "20,480", "p95": 1.5,
                                "source": "run.py", "scope": "real"})
        self.claims(repo, dict(CLAIM, scope="real",
                               proof="experiments/h1/results.jsonl",
                               statement="the cache moved 20480 bytes"))
        self.assertFalse(hit("asserts", self.warnings(repo)), self.warnings(repo))
        # a number the artifact does not hold in any rendering is still warned about
        self.claims(repo, dict(CLAIM, scope="real",
                               proof="experiments/h1/results.jsonl",
                               statement="the cache moved 20480 bytes and cut p95 to 0.4"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("asserts 1 number(s)", warnings), warnings)
        self.assertTrue(hit("0.4", warnings), warnings)

    def test_a_comma_separated_list_is_figures_and_not_decimal_numbers(self):
        """`4,2,2,1,1,2` read as decimals gives `4,2`, `2,1` and `1,2`, none of which
        is in an artifact holding the same list with spaces; read as six figures, all
        six are."""
        repo = self.repo()
        base = self.fixture_line(repo, scope="real")
        self.write(os.path.join(base, "to_human", "report.md"),
                   "# report\n\nthe severity column reads 4, 2, 2, 1, 1, 2\n")
        self.claims(repo, dict(CLAIM, scope="real", proof="to_human/report.md",
                               statement="the severity column reads 4,2,2,1,1,2"))
        self.assertFalse(hit("asserts", self.warnings(repo)), self.warnings(repo))
        # one figure the artifact does not hold is still asserted and still missing
        self.claims(repo, dict(CLAIM, scope="real", proof="to_human/report.md",
                               statement="the severity column reads 4,2,2,1,1,2,9"))
        self.assertTrue(hit("asserts 1 number(s)", self.warnings(repo)),
                        self.warnings(repo))

    def test_a_number_past_the_reading_window_is_still_found(self):
        """`_artifact_text` reads a bounded window per file, so a number beyond it is
        streamed for rather than called missing - true of the window, false of the
        artifact."""
        repo = self.repo()
        base = self.fixture_line(repo, scope="real")
        self.write(os.path.join(base, "to_human", "report.md"),
                   "filler\n" * 12000 + "the peak was 424242\n")
        self.claims(repo, dict(CLAIM, scope="real", proof="to_human/report.md",
                               statement="the peak was 424242"))
        self.assertFalse(hit("asserts", self.warnings(repo)), self.warnings(repo))
        self.claims(repo, dict(CLAIM, scope="real", proof="to_human/report.md",
                               statement="the peak was 515151"))
        warnings = self.warnings(repo)
        self.assertTrue(hit("asserts 1 number(s)", warnings), warnings)
        self.assertTrue(hit("515151", warnings), warnings)

    def test_a_claim_over_mixed_rows_that_declares_real_is_warned_about(self):
        """The declaration is a warning to the reader, so under-declaring is the safe
        direction: a claim resting on one fixture row and one real row that says
        `real` hides the half that is not the running system."""
        repo = self.repo()
        self.fixture_line(repo)
        self.protocol(repo, h="h2")
        self.results(repo, h="h2", row={"run": 1, "p95": 0.9, "source": "run.py",
                                        "scope": "real"})
        proof = ("experiments/h1/results.jsonl, experiments/h2/results.jsonl")
        self.claims(repo, dict(CLAIM, scope="real", proof=proof))
        warnings = self.warnings(repo)
        self.assertTrue(hit("claim c1 declares scope real and rests on the fixture "
                            "row(s) of experiments/h1", warnings), warnings)
        self.assertTrue(hit("declares scope real and rests on the fixture row(s)",
                            self.errors(repo, strict=True)),
                        self.errors(repo, strict=True))
        # declaring the fixture half is the whole fix
        self.claims(repo, dict(CLAIM, scope="fixture", proof=proof))
        self.assertFalse(hit("rests on the fixture row(s)", self.warnings(repo)),
                         self.warnings(repo))
        # and rows that are all fixture still refuse the wider claim
        self.claims(repo, dict(CLAIM, scope="real",
                               proof="experiments/h1/results.jsonl"))
        self.assertTrue(hit("declares scope real and every row it rests on records "
                            "fixture", self.errors(repo)))

    def test_status_names_the_claims_that_rest_on_a_fixture(self):
        repo = self.repo()
        self.fixture_line(repo)
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl"))
        lines = [row for row in tr.summary(repo) if not row.startswith("open: ")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(hit("1 fixture-scoped claim(s): c1", lines), lines)
        # a line whose rows and claims are both real says nothing extra
        self.results(repo, row={"run": 1, "p95": 0.9, "source": "run.py",
                                "scope": "real"})
        self.claims(repo, dict(CLAIM, scope="real",
                               proof="experiments/h1/results.jsonl"))
        self.assertTrue(hit("q: ok", tr.summary(repo)), tr.summary(repo))
        self.assertFalse(hit("fixture-scoped", tr.summary(repo)), tr.summary(repo))


class SourceRun(Workspace):
    """I4: `source --run` files the run's log as the experiment's receipt."""

    def cli(self, repo, *args, env=None):
        return support.run([CLI] + list(args), env=env or self.env(), cwd=repo)

    def with_orx(self, repo, logs="the run's log", logs_exit=0):
        stub = self.stub_orx(repo, logs=logs, logs_exit=logs_exit)
        return self.env(extra={"TEZGAH_ORX_BIN": stub})

    def test_it_writes_the_log_and_the_row_and_check_stays_green(self):
        repo = self.repo()
        base = self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e",
                        "--command", "bash run.sh", env=self.with_orx(repo))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        log = os.path.join(self.exp_dir(repo), "raw", "9f0c1d2e.log")
        self.assertEqual(read(log), "the run's log\n")
        row = json.loads(read(os.path.join(self.exp_dir(repo),
                                           "results.jsonl")))
        self.assertEqual(row, {"source": "orx:9f0c1d2e", "log": "raw/9f0c1d2e.log",
                               "command": "bash run.sh"})
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit("carries no source", self.warnings(repo)))
        self.assertTrue(os.path.isdir(base))

    def test_a_fixture_scope_can_name_what_was_generated(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        what = "a temp HOME and a generated repository of 40 files"
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e",
                        "--scope", "fixture", "--fixture", what,
                        env=self.with_orx(repo))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        row = json.loads(read(os.path.join(self.exp_dir(repo),
                                           "results.jsonl")))
        self.assertEqual(row["scope"], "fixture")
        self.assertEqual(row["fixture"], what)
        self.assertNotIn("does not say what was generated", proc.stdout)
        self.assertEqual(self.errors(repo), [])
        self.assertFalse(hit("do not say what was generated", self.warnings(repo)),
                         self.warnings(repo))

    def test_a_fixture_scope_without_the_description_files_the_row_and_names_the_field(self):
        """The tool must not be the thing that makes its own checker warn silently,
        and it must not refuse a row a session may have a reason to file."""
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e",
                        "--scope", "fixture", env=self.with_orx(repo))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("note: the row declares scope fixture and does not say what "
                      "was generated", proc.stdout)
        row = json.loads(read(os.path.join(self.exp_dir(repo),
                                           "results.jsonl")))
        self.assertEqual(row["scope"], "fixture")
        self.assertNotIn("fixture", row)
        self.assertTrue(hit("do not say what was generated", self.warnings(repo)),
                        self.warnings(repo))

    def test_a_fixture_description_that_is_given_and_empty_is_misuse(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e",
                        "--scope", "fixture", "--fixture", "   ",
                        env=self.with_orx(repo))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("--fixture needs the text naming what was generated",
                      proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(os.path.exists(os.path.join(self.exp_dir(repo), "raw")))

    def test_a_second_run_appends_a_second_row(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        for run in ("aaaa", "bbbb"):
            proc = self.cli(repo, "source", "q", "h1", "--run", run,
                            env=self.with_orx(repo))
            self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = [json.loads(line) for line in
                read(os.path.join(self.exp_dir(repo), "results.jsonl")).splitlines()]
        self.assertEqual([r["source"] for r in rows], ["orx:aaaa", "orx:bbbb"])

    def test_without_orx_it_exits_two_and_writes_nothing(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("orx is not installed", proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(os.path.exists(os.path.join(self.exp_dir(repo), "raw")))

    def test_an_experiment_with_no_protocol_is_refused(self):
        # a receipt filed against a run whose plan was never committed reopens the
        # hole the order rule closes
        repo = self.repo()
        self.line(repo)
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e",
                        env=self.with_orx(repo))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL q: experiments/h1 holds no protocol.md", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.exp_dir(repo), "raw")))

    def test_a_run_orx_cannot_read_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        env = self.with_orx(repo, logs="the log of a run that never landed",
                            logs_exit=1)
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e", env=env)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("orx logs 9f0c1d2e failed", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.exp_dir(repo), "raw")))

    def test_an_empty_log_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        proc = self.cli(repo, "source", "q", "h1", "--run", "9f0c1d2e",
                        env=self.with_orx(repo, logs=""))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("returned nothing", proc.stdout)

    def test_misuse_exits_two(self):
        repo = self.repo()
        self.line(repo)
        env = self.with_orx(repo)
        cases = ((("source", "q"), "source <slug>"),
                 (("source", "q", "h1"), "source needs --run"),
                 (("source", "nope", "h1", "--run", "x"), "no such research line"),
                 (("source", "q", "h1", "--run", "x", "--bogus"), "source <slug>"),
                 (("source", "q", "../h1", "--run", "x"), "not an experiment "
                                                           "directory name"))
        for args, message in cases:
            proc = self.cli(repo, *args, env=env)
            self.assertEqual(proc.returncode, 2, (args, proc.stdout, proc.stderr))
            self.assertIn(message, proc.stderr, args)
            self.assertEqual(proc.stdout, "", args)


class LiteratureIndex(Workspace):
    """I5: what the line read, indexed, and labelled by channel."""

    NOTE = ("# A paper\n\n- id: arXiv 1707.02553\n"
            "- url: https://arxiv.org/abs/1707.02553\n")

    def row(self, **over):
        row = {"note": "1707.02553-paper.md", "id": "arXiv 1707.02553",
               "class": "formal", "source": "https://arxiv.org/abs/1707.02553",
               "inclusion": "included: the guidelines the line follows",
               "verified": ["arXiv abs page", "the publisher record"]}
        row.update(over)
        return row

    def test_a_note_the_index_does_not_name_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md", self.NOTE)
        errors = self.errors(repo)
        self.assertTrue(hit("literature/ holds 1 note(s) and no INDEX.jsonl",
                            errors), errors)
        self.index(repo, self.row(note="other.md"))
        errors = self.errors(repo)
        self.assertTrue(hit("literature/1707.02553-paper.md is not in INDEX.jsonl",
                            errors), errors)

    def test_an_index_row_naming_no_note_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.index(repo, self.row(note="ghost.md"))
        errors = self.errors(repo)
        self.assertTrue(hit("literature/INDEX.jsonl:1 names ghost.md, which "
                            "literature/ does not hold", errors), errors)
        self.index(repo, self.row(note=""))
        self.assertTrue(hit("literature/INDEX.jsonl:1 names no note",
                            self.errors(repo)))

    def test_a_note_that_is_indexed_is_clean(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md", self.NOTE)
        self.index(repo, self.row())
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(self.warnings(repo), ["no claims recorded yet"])

    def test_a_class_outside_the_enum_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md", self.NOTE)
        self.index(repo, self.row(**{"class": "industry"}))
        errors = self.errors(repo)
        self.assertTrue(hit("class 'industry' is not one of formal, grey", errors),
                        errors)

    def test_a_grey_source_with_no_quality_note_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md", self.NOTE)
        self.index(repo, self.row(**{"class": "grey"}))
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("1 of 1 rows are a grey source with no quality note",
                            warnings), warnings)
        self.assertTrue(hit("grey source with no quality note",
                            self.errors(repo, strict=True)))
        self.index(repo, self.row(**{"class": "grey", "quality": "vendor page, "
                                                              "read as a claim"}))
        self.assertFalse(hit("quality note", self.warnings(repo)))

    def test_a_source_verified_by_one_record_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md", self.NOTE)
        self.index(repo, self.row(verified=["arXiv abs page"]))
        warnings = self.warnings(repo)
        self.assertTrue(hit("verified by fewer than two sources", warnings),
                        warnings)
        self.assertTrue(hit("fewer than two sources",
                            self.errors(repo, strict=True)))

    def test_a_field_the_row_does_not_carry_is_reported(self):
        # a field nothing can derive is a warning here and is what `migrate`
        # reports; it is not a refusal, because the note may predate the field
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md", self.NOTE)
        self.index(repo, {"note": "1707.02553-paper.md", "class": "formal"})
        warnings = self.warnings(repo)
        self.assertEqual(len(named(warnings, "record no ")), 3, warnings)
        self.assertEqual(self.errors(repo), [])

    def test_an_index_that_does_not_parse_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.write(os.path.join(tr.line_dir(repo, "q"), "literature",
                                "INDEX.jsonl"), "{not json\n")
        self.assertTrue(hit("literature/INDEX.jsonl:1 does not parse",
                            self.errors(repo)))

    def test_a_line_with_no_notes_needs_no_index(self):
        repo = self.repo()
        self.line(repo)
        self.assertEqual(self.errors(repo), [])


class ReviewArtifact(Workspace):
    """I6: the six-dimension review, written down where the next reader can check
    it, with findings that quote what they attack."""

    DIMENSIONS = {"evidence_relevance": 5, "falsifiability": 4,
                  "scope_calibration": 4, "argument_coherence": 4,
                  "exploration_integrity": 5, "methodological_rigour": 4}

    def finding(self, **over):
        finding = {"severity": "major",
                   "target": "to_human/report.md",
                   "quote": "held."}
        finding.update(over)
        return finding

    def test_a_concluded_line_without_a_review_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo, phase="concluded")
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("to_human/review.json is missing: a concluded line "
                            "reports the six-dimension review", warnings), warnings)
        self.assertTrue(hit("review.json is missing",
                            self.errors(repo, strict=True)))
        # the other phases do not need one
        self.line(repo, "booting", phase="bootstrap")
        self.assertFalse(hit("review.json is missing", self.warnings(repo, "booting")))

    def test_a_complete_review_is_clean(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.write(os.path.join(base, "to_human", "report.md"), REPORT)
        self.review(repo, {"dimensions": self.DIMENSIONS,
                           "findings": [self.finding()]})
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(self.warnings(repo), ["no claims recorded yet"])

    def test_a_dimension_that_is_missing_or_out_of_range_is_refused(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n\nheld.\n")
        dimensions = dict(self.DIMENSIONS, methodological_rigour=6)
        del dimensions["falsifiability"]
        self.review(repo, {"dimensions": dimensions, "findings": []})
        errors = self.errors(repo)
        self.assertTrue(hit("dimension falsifiability is None, not a score from 1 "
                            "to 5", errors), errors)
        self.assertTrue(hit("dimension methodological_rigour is 6", errors), errors)

    def test_a_finding_whose_quote_is_not_verbatim_is_refused(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n\nheld.\n")
        self.review(repo, {"dimensions": self.DIMENSIONS,
                           "findings": [self.finding(quote="the cache held")]})
        errors = self.errors(repo)
        self.assertTrue(hit("which to_human/report.md does not contain verbatim",
                            errors), errors)

    def test_a_finding_that_quotes_nothing_or_targets_nothing_is_refused(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.review(repo, {"dimensions": self.DIMENSIONS,
                           "findings": [self.finding(quote=""),
                                        self.finding(target="to_human/ghost.md"),
                                        self.finding(severity="blocker")]})
        errors = self.errors(repo)
        self.assertTrue(hit("finding 1 quotes nothing", errors), errors)
        self.assertTrue(hit("finding 2 targets to_human/ghost.md, which cannot be "
                            "read", errors), errors)
        self.assertTrue(hit("finding 3 severity 'blocker' is not one of", errors),
                        errors)

    def test_a_present_review_is_checked_at_any_phase(self):
        repo = self.repo()
        self.line(repo)
        self.review(repo, {"dimensions": {}, "findings": "none"})
        errors = self.errors(repo)
        self.assertTrue(hit("dimension evidence_relevance is None", errors), errors)
        self.assertTrue(hit("carries no findings list", errors), errors)


class ReportLimits(Workspace):
    """A concluded line's report states what the evidence does not show."""

    def test_a_concluded_line_with_no_report_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo, phase="concluded")
        warnings = self.warnings(repo)
        self.assertTrue(hit("to_human/report.md is missing", warnings), warnings)
        self.assertFalse(hit("states nowhere", warnings), warnings)
        self.assertEqual(self.errors(repo), [])
        strict = self.errors(repo, strict=True)
        self.assertTrue(hit("to_human/report.md is missing", strict), strict)

    def test_a_report_that_names_no_limit_warns(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.write(os.path.join(base, "to_human", "report.md"),
                   "# Report\n\nThe cache held and p95 dropped.\n")
        warnings = self.warnings(repo)
        self.assertTrue(hit("states nowhere what the evidence does not show",
                            warnings), warnings)
        self.assertTrue(hit("states nowhere", self.errors(repo, strict=True)))

    def test_a_limit_passes_as_a_heading_or_as_a_sentence(self):
        # the five reports this repository already concluded with name their
        # limits four different ways, so both shapes have to count
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        for text in ("# Report\n\nThe cache held.\n\n## What this does not show\n\n"
                     "- one host, one workload.\n",
                     "# Report\n\nThe cache held, over one host and one workload:\n"
                     "whether it generalises is unmeasured.\n"):
            with self.subTest(text=text):
                self.write(os.path.join(base, "to_human", "report.md"), text)
                self.assertFalse(hit("states nowhere", self.warnings(repo)),
                                 self.warnings(repo))

    def test_a_line_that_has_not_concluded_owes_no_report(self):
        repo = self.repo()
        self.line(repo)
        self.assertFalse(hit("report.md", self.warnings(repo)), self.warnings(repo))

    def test_a_concluded_report_names_the_claims_resting_on_a_fixture(self):
        """The report is what a reader takes away, and a number measured on a
        generated input reads as a property of the running system once the input is
        out of sight."""
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.protocol(repo)
        self.results(repo, row={"run": 1, "p95": 0.9, "source": "probe.py",
                                "scope": "fixture"})
        self.claims(repo, dict(CLAIM, scope="fixture",
                               proof="experiments/h1/results.jsonl"))
        report = os.path.join(base, "to_human", "report.md")
        self.write(report, "# Report\n\nThe cache held over one workload.\n")
        warnings = self.warnings(repo)
        self.assertTrue(hit("claim(s) resting on a fixture input (c1)", warnings),
                        warnings)
        self.assertTrue(hit("never says so", self.errors(repo, strict=True)))
        self.write(report, "# Report\n\nMeasured on a fixture repository, so the "
                           "numbers are about the code path and not the running "
                           "system.\n")
        self.assertFalse(hit("never says so", self.warnings(repo)), self.warnings(repo))


class PatternsBullets(Workspace):
    """I6: a pattern that names no source is a guess in a finding's clothes."""

    def test_a_bullet_with_no_source_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo)
        self.patterns(repo, "the cache always helps", "and so does the second one")
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("findings.md: 2 of 2 Patterns bullets name no source",
                            warnings), warnings)
        self.assertTrue(hit("name no source", self.errors(repo, strict=True)))

    def test_every_source_shape_a_bullet_may_name_passes(self):
        repo = self.repo()
        # `outer`: the findings' own content is what the derivation reads as the
        # synthesis step, so the fixture declares the phase its artifact shows
        self.line(repo, phase="outer")
        self.note(repo, "1707-x.md", "# A note\n")
        self.patterns(repo, "the cache helps [c1]",
                      "the layer binds to nothing literature/1707-x.md",
                      "the run answers it orx:9f0c1d2e",
                      "one of three is enough [C24]")
        self.assertEqual(self.warnings(repo), ["no claims recorded yet"])

    def test_only_the_patterns_section_is_measured(self):
        # a bullet under `## Lessons` is a note to the next session, not a
        # generalisation a reader carries away
        repo = self.repo()
        base = self.line(repo, phase="outer")
        self.write(os.path.join(base, "findings.md"),
                   "# Findings\n\n## What we know\n\n- unsourced\n\n## Patterns\n\n"
                   "## Lessons\n\n- unsourced too\n\n## Open questions\n")
        self.assertEqual(self.warnings(repo), ["no claims recorded yet"])


class StrictMode(Workspace):
    """`--strict`: the unverifiable class becomes a refusal, and nothing else
    changes."""

    def test_a_clean_line_is_clean_in_both_modes(self):
        repo = self.repo()
        self.clean(repo)
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(self.warnings(repo), [])
        self.assertEqual(self.errors(repo, strict=True), [])
        self.assertEqual(self.warnings(repo, strict=True), [])

    def test_every_unverifiable_class_becomes_an_error(self):
        # one line of each class, and the strict run has to name every one of
        # them
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        # the private repository ignores the results, so no commit can order them
        self.write(os.path.join(repo, ".tezgah", ".gitignore"), "*.jsonl\n")
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        claim = dict(CLAIM)
        del claim["kind"]
        claim["proof"] = "to_human/report.md"
        self.claims(repo, claim)
        self.protocol(repo)
        self.results(repo, row={"run": 1, "p95": 0.9})
        self.note(repo, "03-dora-2025.md", "# DORA\n\n- url: https://dora.dev/x\n")
        self.index(repo, {"note": "03-dora-2025.md", "class": "grey",
                          "id": "x", "source": "https://dora.dev/x",
                          "inclusion": "included", "verified": ["one record"]})
        self.patterns(repo, "an unsourced pattern")
        warnings = self.warnings(repo)
        strict = self.errors(repo, strict=True)
        self.assertEqual(self.errors(repo), [])
        for needle in ("results.jsonl is ignored by .gitignore:1:*.jsonl, so no "
                       "commit can show",
                       "carries no kind",
                       "results.jsonl:1 carries no source",
                       "grey source with no quality note",
                       "verified by fewer than two sources",
                       "Patterns bullets name no source",
                       "review.json is missing",
                       "states nowhere what the evidence does not show"):
            with self.subTest(needle=needle):
                self.assertTrue(hit(needle, strict), strict)
                self.assertTrue(hit(needle, warnings), warnings)
        self.assertTrue(os.path.isdir(base))

    def test_a_decidable_error_is_an_error_in_both_modes(self):
        repo = self.repo()
        self.line(repo, question="")
        for strict in (False, True):
            self.assertIn("state.json records no question",
                          self.errors(repo, strict=strict))

    def test_the_default_run_still_exits_zero_where_only_warnings_stand(self):
        # a claim written before the kind existed: a warning by default, a
        # refusal under --strict, and never a silent pass in either
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        claim = dict(CLAIM, proof="to_human/report.md")
        del claim["kind"]
        self.claims(repo, claim)
        self.cli_ok(repo)
        proc = self.cli(repo, "check", "--strict")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL q: claim c1 carries no kind", proc.stdout)

    def cli_ok(self, repo):
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("research: 1 line(s) ok", proc.stdout)


class Migrate(Workspace):
    """`migrate`: derive what the artifacts already hold, report what they do not."""

    def test_it_derives_the_kind_of_each_claim(self):
        repo = self.repo()
        self.line(repo)
        self.write(os.path.join(tr.line_dir(repo, "q"), "to_human", "report.md"),
                   "# Report\n")
        self.note(repo, "1707-x.md", "# A note\n")
        self.write(os.path.join(repo, "bin", "tezgah-research"), "#!/bin/sh\n")
        rows = [("c1", "experiments/h1/results.jsonl (7 runs)"),
                ("c2", "literature/1707-x.md"),
                ("c3", "bin/tezgah-research"),
                ("c4", "to_human/report.md")]
        self.write(os.path.join(tr.line_dir(repo, "q"), "claims.jsonl"),
                   "".join(json.dumps({"id": cid, "statement": "s", "status":
                                       "supported", "provenance": "ai-executed",
                                       "falsification": "f", "proof": proof}) + "\n"
                           for cid, proof in rows))
        lines, problems = tr.migrate(repo, "q", dry_run=True)
        kinds = dict(line.split(": kind ") for line in lines if ": kind " in line)
        self.assertEqual(kinds, {"claim c1": "evidence", "claim c2": "literature",
                                 "claim c3": "code", "claim c4": "code"})
        self.assertEqual([p for p in problems if "no kind derived" in p], [])
        # the dry run wrote nothing
        self.assertNotIn("kind", read(os.path.join(tr.line_dir(repo, "q"),
                                                   "claims.jsonl")).splitlines()[0])

    def test_it_reports_a_proof_that_names_no_artifact(self):
        repo = self.repo()
        self.line(repo)
        self.claims(repo, dict(CLAIM, kind=None, id="c1",
                               proof="verified by hand, I checked it"))
        path = os.path.join(tr.line_dir(repo, "q"), "claims.jsonl")
        self.write(path, json.dumps({"id": "c1", "statement": "s", "status":
                                     "supported", "provenance": "ai-executed",
                                     "falsification": "f",
                                     "proof": "verified by hand"}) + "\n")
        lines, problems = tr.migrate(repo, "q")
        self.assertEqual(lines, [])
        self.assertTrue(hit("claim c1: no kind derived - its proof names no "
                            "artifact", problems), problems)
        claim = json.loads(read(path))
        self.assertNotIn("kind", claim)

    def test_it_writes_the_index_from_the_notes(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707.02553-paper.md",
                  "# A paper\n\n- id: arXiv 1707.02553\n"
                  "- url: https://arxiv.org/abs/1707.02553\n"
                  "- verified: the abs page + the publisher record\n")
        self.note(repo, "dora.md", "# DORA\n\n- url: https://dora.dev/report/\n")
        lines, problems = tr.migrate(repo, "q")
        rows = [json.loads(line) for line in read(os.path.join(
            tr.line_dir(repo, "q"), "literature", "INDEX.jsonl")).splitlines()]
        self.assertEqual([r["note"] for r in rows],
                         ["1707.02553-paper.md", "dora.md"])
        self.assertEqual(rows[0]["class"], "formal")
        self.assertEqual(rows[0]["id"], "arXiv 1707.02553")
        self.assertEqual(rows[0]["source"], "https://arxiv.org/abs/1707.02553")
        self.assertEqual(rows[0]["verified"],
                         ["the abs page", "the publisher record"])
        self.assertEqual(rows[1]["class"], "grey")
        self.assertNotIn("quality", rows[1])
        self.assertTrue(hit("no quality note derived for a grey source", problems),
                        problems)
        self.assertTrue(hit("no inclusion decision derived", problems), problems)
        self.assertEqual(len(lines), 2, lines)
        self.assertEqual(self.errors(repo), [])

    def test_it_is_idempotent(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "dora.md", "# DORA\n\n- url: https://dora.dev/report/\n")
        self.claims(repo, dict(CLAIM, id="c1"))
        path = os.path.join(tr.line_dir(repo, "q"), "claims.jsonl")
        self.write(path, json.dumps({"id": "c1", "statement": "s", "status":
                                     "supported", "provenance": "ai-executed",
                                     "falsification": "f",
                                     "proof": "to_human/report.md"}) + "\n")
        first, _ = tr.migrate(repo, "q")
        claims_after = read(path)
        index_after = read(os.path.join(tr.line_dir(repo, "q"), "literature",
                                        "INDEX.jsonl"))
        second, problems = tr.migrate(repo, "q")
        self.assertEqual(second, [])
        self.assertEqual(read(path), claims_after)
        self.assertEqual(read(os.path.join(tr.line_dir(repo, "q"), "literature",
                                           "INDEX.jsonl")), index_after)
        self.assertEqual(problems, [])
        self.assertTrue(first)
        self.assertEqual(json.loads(claims_after.splitlines()[0])["kind"], "code")

    def test_a_held_lock_refuses_the_migration(self):
        if fcntl is None:
            self.skipTest("fcntl is unavailable")
        repo = self.repo()
        self.line(repo)
        path = os.path.join(tr.line_dir(repo, "q"), "claims.jsonl")
        self.write(path, json.dumps({"id": "c1", "statement": "s", "status":
                                     "supported", "provenance": "ai-executed",
                                     "falsification": "f",
                                     "proof": "to_human/report.md"}) + "\n")
        before = read(path)
        holder = open(path, "a")
        self.addCleanup(holder.close)
        fcntl.flock(holder, fcntl.LOCK_EX)
        saved = tr.LOCK_WAIT
        tr.LOCK_WAIT = 0.05
        try:
            lines, problems = tr.migrate(repo, "q")
        finally:
            tr.LOCK_WAIT = saved
        self.assertEqual(lines, [])
        self.assertTrue(hit("locked by another writer", problems), problems)
        self.assertEqual(read(path), before)

    def test_a_derived_kind_is_never_one_the_checker_refuses(self):
        # the mixed proof is the case a substring test got wrong on this
        # repository's own lines: a claim citing the note it rests on beside the
        # code it is about
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707-x.md", "# A note\n")
        self.write(os.path.join(repo, "bin", "tezgah-status"), "#!/bin/sh\n")
        self.write(os.path.join(tr.line_dir(repo, "q"), "claims.jsonl"),
                   json.dumps({"id": "c1", "statement": "s", "status": "supported",
                               "provenance": "ai-executed", "falsification": "f",
                               "proof": "literature/1707-x.md; bin/tezgah-status"})
                   + "\n")
        lines, problems = tr.migrate(repo, "q")
        # the claim is the one this test is about; migrate also indexes the note
        self.assertEqual(lines[0], "claim c1: kind literature")
        self.assertIn("literature/INDEX.jsonl: 1707-x.md, class grey", lines)
        # what the bare note does not carry is reported; the kind is not
        self.assertFalse(hit("no kind derived", problems), problems)
        self.assertEqual(self.errors(repo), [])

    def test_a_mixed_proof_keeps_its_evidence_kind_and_stays_valid(self):
        # the back-compat case the new line-local rule must not break: a claim
        # citing its run beside the code it is about derives `evidence` and check
        # accepts it, because the run is a token the line produced
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.write(os.path.join(repo, "bin", "tezgah-status"), "#!/bin/sh\n")
        self.write(os.path.join(tr.line_dir(repo, "q"), "claims.jsonl"),
                   json.dumps({"id": "c1", "statement": "s", "status": "supported",
                               "provenance": "ai-executed", "falsification": "f",
                               "proof": "experiments/h1/results.jsonl and "
                                        "bin/tezgah-status"}) + "\n")
        lines, problems = tr.migrate(repo, "q")
        self.assertEqual(lines, ["claim c1: kind evidence"])
        self.assertFalse(hit("no kind derived", problems), problems)
        self.assertEqual(self.errors(repo), [])
        # and the rule that accepts it here is the one that refuses the proof
        # without its run: an over-strict implementation would fail the case above
        self.claims(repo, {"id": "c1", "statement": "s", "status": "supported",
                           "provenance": "ai-executed", "falsification": "f",
                           "kind": "evidence", "proof": "bin/tezgah-status"})
        self.assertTrue(hit("is an evidence claim and cites nothing the line "
                            "produced: bin/tezgah-status", self.errors(repo)))

    def test_it_derives_a_row_source_from_the_fields_the_row_carries(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        rows = [{"run": 1, "p95": 0.9}, {"id": "N01", "flat": "none"},
                {"raw": "raw/run-1.txt"}, {"log": "raw/9f0c1d2e.log"},
                {"p95": 0.9}]
        before = "".join(json.dumps(r) + "\n" for r in rows)
        self.write(path, before)
        lines, problems = tr.migrate(repo, "q", dry_run=True)
        self.assertEqual(lines, ["experiment h1: results.jsonl:1 source run 1 "
                                 "(from run)",
                                 "experiment h1: results.jsonl:2 source id N01 "
                                 "(from id)",
                                 "experiment h1: results.jsonl:3 source "
                                 "raw/run-1.txt (from raw)",
                                 "experiment h1: results.jsonl:4 source "
                                 "raw/9f0c1d2e.log (from log)"])
        # the row that carries none of the four is reported, never filled with a
        # source nobody recorded
        self.assertTrue(hit("experiment h1: results.jsonl:5: no source derived - "
                            "the row carries none of log, raw, run, id", problems),
                        problems)
        self.assertEqual(read(path), before)

    def test_a_derived_row_source_is_written_and_is_idempotent(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.write(path, json.dumps({"run": 3, "p95": 0.9}) + "\n")
        lines, problems = tr.migrate(repo, "q")
        self.assertEqual(lines, ["experiment h1: results.jsonl:1 source run 3 "
                                 "(from run)"])
        self.assertEqual(problems, [])
        self.assertEqual(json.loads(read(path)),
                         {"run": 3, "p95": 0.9, "source": "run 3"})
        self.assertFalse(hit("carries no source", self.warnings(repo)))
        second, _ = tr.migrate(repo, "q")
        self.assertEqual(second, [])
        self.assertEqual(json.loads(read(path)),
                         {"run": 3, "p95": 0.9, "source": "run 3"})

    def test_a_row_that_already_carries_a_source_is_left_alone(self):
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "analysis.md"), "# Analysis\n")
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        written = {"run": 3, "source": "run.py -> raw/run-3.txt"}
        self.write(path, json.dumps(written) + "\n")
        lines, problems = tr.migrate(repo, "q")
        self.assertEqual(lines, [])
        self.assertEqual(problems, [])
        self.assertEqual(json.loads(read(path)), written)

    def test_a_line_that_does_not_exist_is_reported(self):
        repo = self.repo()
        lines, problems = tr.migrate(repo, "nope")
        self.assertEqual(lines, [])
        self.assertTrue(hit("does not exist", problems), problems)

    def test_misuse_exits_two(self):
        repo = self.repo()
        self.line(repo)
        for args, message in ((("migrate",), "migrate <slug>"),
                              (("migrate", "nope"), "no such research line"),
                              (("migrate", "q", "extra"), "migrate <slug>")):
            proc = self.cli(repo, *args)
            self.assertEqual(proc.returncode, 2, (args, proc.stdout))
            self.assertIn(message, proc.stderr, args)

    def test_the_dry_run_prints_what_the_real_run_derives(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, "dora.md", "# DORA\n\n- url: https://dora.dev/report/\n")
        dry = self.cli(repo, "migrate", "q", "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("(dry run, nothing written)", dry.stdout)
        self.assertIn("class grey", dry.stdout)
        self.assertIn("could not derive: literature/dora.md: no inclusion decision",
                      dry.stdout)
        self.assertFalse(os.path.exists(os.path.join(
            tr.line_dir(repo, "q"), "literature", "INDEX.jsonl")))
        real = self.cli(repo, "migrate", "q")
        self.assertEqual(real.returncode, 0, real.stderr)
        self.assertIn("class grey", real.stdout)
        self.assertTrue(os.path.exists(os.path.join(
            tr.line_dir(repo, "q"), "literature", "INDEX.jsonl")))


class OrxCheck(Workspace):
    """`check --orx`: the run command the registered project holds, against the
    tree it claims to run in."""

    def projects(self, repo, *rows):
        return json.dumps(list(rows))

    def test_a_run_command_naming_a_missing_path_is_reported(self):
        repo = self.repo()
        self.line(repo)
        stub = self.stub_orx(
            repo,
            projects=self.projects(repo, {"id": "p1", "name": "proj",
                                          "path": repo}),
            view="tezgah-harness-research (local)\n  command: bash "
                 "benchmarks/arm-bench/orx-run.sh\n")
        env = self.env(extra={"TEZGAH_ORX_BIN": stub})
        proc = self.cli(repo, "check", "--orx", env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warn orx: orx project proj: the run command names "
                      "benchmarks/arm-bench/orx-run.sh, which this tree does not "
                      "hold", proc.stdout)
        strict = self.cli(repo, "check", "--orx", "--strict", env=env)
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("FAIL orx: orx project proj: the run command names", strict.stdout)

    def test_a_run_command_the_tree_holds_is_silent(self):
        repo = self.repo()
        self.line(repo)
        self.write(os.path.join(repo, "run.sh"), "#!/bin/sh\n")
        stub = self.stub_orx(repo, projects=self.projects(
            repo, {"id": "p1", "name": "proj", "path": repo}),
            view="proj (local)\n  command: bash run.sh\n")
        proc = self.cli(repo, "check", "--orx",
                        env=self.env(extra={"TEZGAH_ORX_BIN": stub}))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("warn orx: orx project", proc.stdout)

    def test_absent_orx_is_a_note_and_never_an_error(self):
        repo = self.repo()
        self.line(repo)
        proc = self.cli(repo, "check", "--orx")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warn orx: orx is not installed", proc.stdout)

    def test_no_project_for_this_repository_is_a_note(self):
        repo = self.repo()
        self.line(repo)
        stub = self.stub_orx(repo, projects=self.projects(
            repo, {"id": "p1", "name": "other", "path": "/somewhere/else"}))
        proc = self.cli(repo, "check", "--orx",
                        env=self.env(extra={"TEZGAH_ORX_BIN": stub}))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warn orx: no orx project is registered against", proc.stdout)

    def test_a_project_whose_view_fails_is_a_note(self):
        repo = self.repo()
        self.line(repo)
        stub = self.stub_orx(repo, projects=self.projects(
            repo, {"id": "p1", "name": "proj", "path": repo}), view_exit=1)
        out = tr.check_orx(repo, stub)
        self.assertEqual(out["errors"], [])
        self.assertTrue(hit("orx project proj could not be read", out["warnings"]),
                        out["warnings"])
        # and the projects call failing is a note too, never an error
        broken = self.stub_orx(repo, projects_exit=1)
        out = tr.check_orx(repo, broken)
        self.assertEqual(out["errors"], [])
        self.assertTrue(hit("orx projects could not be read", out["warnings"]),
                        out["warnings"])
        self.assertTrue(hit("did not answer with JSON",
                            tr.check_orx(repo, self.stub_orx(repo, projects="{"))
                            ["warnings"]))

    def test_orx_is_asked_for_only_when_the_flag_says_so(self):
        repo = self.repo()
        self.line(repo)
        stub = self.stub_orx(repo, projects=self.projects(
            repo, {"id": "p1", "name": "proj", "path": repo}),
            view="proj (local)\n  command: bash gone.sh\n")
        proc = self.cli(repo, "check", env=self.env(extra={"TEZGAH_ORX_BIN": stub}))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("orx", proc.stdout)


class CliEdges(Workspace):
    """The CLI's own surface: what it refuses, prints, and normalizes."""

    def test_status_rejects_extra_arguments(self):
        repo = self.repo()
        self.line(repo)
        proc = self.cli(repo, "status", "extra")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("status takes no arguments", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_check_rejects_a_second_slug(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.line(repo, "beta", question="beta?")
        proc = self.cli(repo, "check", "alpha", "beta")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("check [<slug>]", proc.stderr)

    def test_repo_root_falls_back_outside_a_git_repository(self):
        path = self.make_repo("plain")
        proc = self.cli(path, "init", "q", "--ask", "does it help?", "--question", "does it help?")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(os.path.join(path, ".tezgah", "research", "open", "q"),
                      proc.stdout)
        status = self.cli(path, "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("q: ok", status.stdout)

    def test_init_normalizes_the_slug(self):
        repo = self.repo()
        proc = self.cli(repo, "init", "  My Probe Line  ", "--ask", "does the probe hold?")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isdir(tr.line_dir(repo, "my-probe-line")))
        self.assertEqual(tr.slugs(repo), ["my-probe-line"])

    def test_non_utf8_stdin_is_misuse(self):
        repo = self.repo()
        self.line(repo)
        proc = subprocess.run([sys.executable, CLI, "claim", "q"],
                              input=b'{"id": "C1", "statement": "caf\xe9"}\n',
                              capture_output=True, env=self.env(), cwd=repo,
                              timeout=60)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(b"stdin is not valid UTF-8", proc.stderr)
        self.assertEqual(read(os.path.join(tr.line_dir(repo, "q"),
                                           "claims.jsonl")), "")

    def test_init_prints_the_next_steps_and_the_kill_switch(self):
        repo = self.repo()
        proc = self.cli(repo, "init", "q", "--ask", "does q hold?")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("COMMIT it before the run", proc.stdout)
        self.assertIn("kill switch: research-off", proc.stdout)

    def test_an_unwritable_line_takes_the_refusal_channel(self):
        # the line can go missing or stop being writable between the slug check
        # and the append; that is a problem with the line, not with the call
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        os.remove(os.path.join(base, "claims.jsonl"))
        os.chmod(base, 0o500)
        self.addCleanup(os.chmod, base, 0o700)
        proc = subprocess.run([sys.executable, CLI, "claim", "q"],
                              input=json.dumps(dict(CLAIM, proof="to_human/report.md")),
                              capture_output=True, text=True, env=self.env(),
                              cwd=repo, timeout=60)
        self.assertEqual(proc.returncode, 1, (proc.stdout, proc.stderr))
        self.assertIn("FAIL q: cannot append to claims.jsonl", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(base, "claims.jsonl")))


class AppendEdges(Workspace):
    """`append_claim`'s own edges: the line it needs, and the last byte it reads."""

    def test_init_refuses_an_invalid_slug_by_raising(self):
        # E6 row 1: the CLI refuses a bad slug before tr.init is ever called, so
        # the raise inside the module was unpinned - a caller that skips the CLI
        # has to be refused too, and nothing may be scaffolded
        repo = self.repo()
        for slug in ("..", "../escape", "a/b", ".hidden", "Bad Slug", ""):
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError):
                    tr.init(repo, slug)
        self.assertEqual(tr.slugs(repo), [])
        self.assertFalse(os.path.exists(os.path.join(repo, ".tezgah", "research")))

    def test_a_slug_no_directory_answers_still_raises_nothing(self):
        repo = self.repo()
        _id, problems = tr.append_claim(repo, "..", dict(CLAIM))
        self.assertTrue(problems, problems)
        self.assertTrue(hit("not a research slug", problems), problems)

    def test_a_valid_slug_with_no_line_raises(self):
        repo = self.repo()
        with self.assertRaises(FileNotFoundError):
            tr.append_claim(repo, "ghost", dict(CLAIM))

    def test_an_append_to_a_terminated_file_writes_no_blank_line(self):
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        path = os.path.join(base, "claims.jsonl")
        self.write(path, json.dumps(dict(CLAIM, id="C1",
                                         proof="to_human/report.md")) + "\n")
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, id="C2", proof="to_human/report.md"))
        self.assertEqual(problems, [])
        body = read(path)
        self.assertEqual(len(body.splitlines()), 2, body)
        self.assertNotIn("\n\n", body)
        self.assertEqual([json.loads(line)["id"] for line in body.splitlines()],
                         ["C1", "C2"])

    def test_the_claim_judgement_reads_the_ids_under_the_lock(self):
        # item 3 of the adoption line's report: `claim_problems` ran before the
        # lock and read the ids by path, so another session could land the very id
        # the check had just found absent and this path refused a claim the
        # committed file accepts. The racing row is placed where the order decides
        # it: as the lock is taken
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        path = os.path.join(base, "claims.jsonl")
        self.race_at_the_lock(lambda: self.append_line(
            path, dict(CLAIM, id="C9", proof="to_human/report.md")))
        _id, problems = tr.append_claim(repo, "q", dict(
            CLAIM, id="C10", proof="to_human/report.md", supersedes="C9"))
        self.assertEqual(problems, [])
        self.assertEqual([json.loads(line)["id"] for line in read(path).splitlines()],
                         ["C9", "C10"])

    def test_the_row_writer_refuses_what_the_checker_refuses(self):
        # the third writer the report named: `_append_row` took the lock and wrote
        # whatever it was handed, so a row `_check_rows` refuses could be recorded
        # and then read back as a file its own reader will not load
        repo = self.repo()
        self.line(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        problems = tr._append_row(path, {"source": "", "scope": "real"})
        self.assertTrue(hit("carries an empty source", problems), problems)
        problems = tr._append_row(path, {"source": "orx:r1", "scope": "maybe"})
        self.assertTrue(hit("scope 'maybe' is not one of real, fixture, derived",
                            problems), problems)
        problems = tr._append_row(path, {"source": "orx:r1", "scope": "fixture",
                                         "fixture": " "})
        self.assertTrue(hit("carries an empty fixture description", problems),
                        problems)
        self.assertFalse(os.path.exists(path), "a refused row was written anyway")
        # the row that is written is the row both readings accept
        self.protocol(repo)
        self.results(repo)
        self.assertEqual(tr._append_row(path, {"source": "orx:r2",
                                               "scope": "real"}), [])
        self.assertEqual(self.errors(repo), [], "the checker read the row it was "
                         "written and refused it")
        self.assertEqual([json.loads(line)["source"]
                          for line in read(path).splitlines()],
                         ["run.py run 1", "orx:r2"])


class CommittedBoundary(Workspace):
    """The size a JSONL file has committed to: what a reader stops at and what an
    append starts from, so a fragment a killed writer left behind is neither read
    as a broken record nor appended beside as one."""

    def torn(self, path, first):
        """A whole row the file terminated, then a fragment nothing did."""
        self.write(path, json.dumps(first) + "\n" + '{"statem')

    def test_a_torn_tail_is_invisible_to_both_jsonl_readers(self):
        # item 4 of the adoption line's report: the research reader read to the
        # last byte, so one kill during one append refused the line for good, while
        # the ledger reader skipped the identical damage
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.torn(os.path.join(base, "claims.jsonl"),
                  dict(CLAIM, id="C1", proof="to_human/report.md"))
        self.assertEqual(self.errors(repo), [])
        self.assertEqual(tr._rows(os.path.join(base, "claims.jsonl")), 1)
        self.protocol(repo)
        self.results(repo)
        self.torn(os.path.join(self.exp_dir(repo), "results.jsonl"),
                  {"source": "orx:r1", "scope": "real"})
        self.assertEqual(self.errors(repo), [])

    def test_a_terminated_record_that_does_not_parse_is_still_refused(self):
        # the boundary hides the tail, not the file: a record the file terminated
        # is one its writer committed to, and a broken one is refused
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.write(os.path.join(base, "claims.jsonl"), '{"id": "C1"\n')
        self.assertTrue(hit("claims.jsonl:1 does not parse", self.errors(repo)),
                        self.errors(repo))
        self.protocol(repo)
        self.write(os.path.join(self.exp_dir(repo), "results.jsonl"),
                   '{"source": "orx:r1"\n')
        errors = self.errors(repo)
        self.assertTrue(hit("results.jsonl:1 does not parse", errors), errors)

    def test_an_append_starts_at_the_boundary(self):
        # the writer half: what the reader cannot see must not be appended to as
        # if it were a row
        repo = self.repo()
        self.line(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        self.torn(path, {"source": "orx:r1", "scope": "real"})
        self.assertEqual(tr._append_row(path, {"source": "orx:r2",
                                               "scope": "real"}), [])
        body = read(path)
        self.assertTrue(body.endswith("\n"), body)
        # the terminated row stays where it is and the fragment beside it goes
        self.assertEqual([json.loads(line)["source"]
                          for line in body.splitlines()], ["orx:r1", "orx:r2"])
        # a file that is nothing but a fragment keeps none of it: the boundary is
        # the file's start, and the append is the first thing ever committed there
        self.write(path, '{"source": "orx:r9"')
        self.assertEqual(tr._append_row(path, {"source": "orx:r3",
                                               "scope": "real"}), [])
        self.assertEqual([json.loads(line)["source"]
                          for line in read(path).splitlines()], ["orx:r3"])


    def test_an_index_tail_is_read_at_the_boundary_too(self):
        # the same boundary on the third JSONL file this module reads: the index
        # reader opened it by path and read to the last byte, so the fragment a
        # kill left behind was a row nothing could read
        repo = self.repo()
        self.line(repo)
        self.note(repo, "1707-x.md", "# A note\n")
        path = self.index(repo, {"note": "1707-x.md", "id": "S1", "source": "x",
                                 "inclusion": "used", "class": "formal"})
        self.assertEqual(self.errors(repo), [])
        with open(path, "a") as fh:
            fh.write('{"note": "17')
        self.assertEqual(self.errors(repo), [])
        self.write(path, '{"note": "1707-x.md"\n')
        errors = self.errors(repo)
        self.assertTrue(hit("literature/INDEX.jsonl:1 does not parse", errors),
                        errors)


class UnitEdges(Workspace):
    """The module's own edges, each one E6 recorded as a promise with no test
    behind it: the failing implementation each case catches is named with it."""

    def test_cited_is_total_for_a_proof_that_is_not_a_string_or_a_list(self):
        # E6 row 4: `_cited` promised to be total; a hand-written row carrying a
        # number or a boolean raised on `.findall` before, because `proof` was
        # read as its own iterable
        self.assertEqual(tr._cited(7), [])
        self.assertEqual(tr._cited(True), [])
        self.assertEqual(tr._cited(None), [])
        self.assertEqual(tr._cited(["to_human/report.md"]),
                         ["to_human/report.md"])
        # a mapping is read as its keys, and reading it at all is the promise
        self.assertEqual(tr._cited({"to_human/report.md": "the report"}),
                         ["to_human/report.md"])
        self.assertEqual(tr._cited({"a": "to_human/report.md"}), [])
        self.assertEqual(tr._named(4, (".", )), [])

    def test_resolves_forgives_a_glob_and_a_ref_pair(self):
        # E6 row 3: the two deliberate forgivenesses the docstring promises and
        # only a real path had ever exercised
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.assertTrue(tr._resolves("experiments/*/results.jsonl", (base,)))
        self.assertTrue(tr._resolves("*", (base,)))
        self.assertTrue(tr._resolves("deadbeef:to_human/report.md", (base,)))
        self.assertTrue(tr._resolves("to_human/report.md:deadbeef", (base,)))
        self.assertFalse(tr._resolves("deadbeef:ghost.md", (base,)))
        self.assertFalse(tr._resolves("ghost.md", (base,)))

    def test_without_fcntl_the_append_is_refused_rather_than_taken(self):
        # E6 row 2: both lock tests skip when fcntl is absent, so the refusal the
        # docstring promises was never run. Patched rather than skipped: the
        # branch is the reason this path refuses instead of writing unlocked
        repo = self.repo()
        base = self.line(repo)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        path = os.path.join(base, "claims.jsonl")
        saved = tr.fcntl
        tr.fcntl = None
        try:
            _id, problems = tr.append_claim(repo, "q", dict(
                CLAIM, proof="to_human/report.md"))
        finally:
            tr.fcntl = saved
        self.assertEqual(problems,
                         ["claims.jsonl cannot be locked on this platform"])
        self.assertEqual(read(path), "")

    def test_an_ancestry_git_cannot_answer_warns_instead_of_failing(self):
        # E6 row 5: only `added_commits` was ever made to fail; the None from
        # `merge-base` - a commit git cannot place, or a repository it cannot read
        # - fell into no test, and the check must warn rather than accuse
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.assertIsNone(tr.is_ancestor(repo, "0" * 40, "1" * 40))
        saved = tr.is_ancestor
        tr.is_ancestor = lambda *args, **kw: None
        try:
            errors, warnings = tr.check_line(repo, "q")
        finally:
            tr.is_ancestor = saved
        self.assertEqual(errors, [])
        self.assertTrue(hit("git could not order the protocol against the results",
                            warnings), warnings)

    def test_a_machine_without_git_answers_instead_of_raising(self):
        # E6 row 6: every fixture skips when git is missing, so the error-string
        # path the module promises for a machine without git was never run
        repo = self.repo()
        base = self.line(repo)
        self.protocol(repo)
        self.results(repo)
        saved = os.environ.get("PATH", "")
        os.environ["PATH"] = os.path.join(self.home, "no-bin")
        self.addCleanup(os.environ.__setitem__, "PATH", saved)
        try:
            words, err = tr._git(repo, "status")
            errors, warnings = tr.check_line(repo, "q")
            report = tr.check(repo, "q")
        finally:
            os.environ["PATH"] = saved
        self.assertEqual(words, [])
        self.assertTrue(err, "a missing git was reported as an empty answer")
        self.assertIsNone(tr._ignored(repo, os.path.join(
            base, "experiments", "h1", "results.jsonl")))
        self.assertEqual(errors, [])
        self.assertTrue(hit("git could not be asked about the order", warnings),
                        warnings)
        self.assertEqual(report["q"]["errors"], errors)


class ContextDrop(Workspace):
    """E6 row 10: the budget's drop order, from the research side - the block the
    session gives up is chosen by DROP_ORDER, and a drop nothing reports would be
    a silent redefinition of what the session was armed with."""

    def session_text(self, repo, limit=None):
        """The session-start text, out of a child whose budget is patched there:
        the fixture's roots, HOME and marks are what the hook has to see, and the
        budget has to be patched in the process that reads it."""
        patch = ("tc.CONTEXT_BUDGET['session_start'] = %d\n" % limit
                 if limit is not None else "")
        body = ("import json, tezgah_context as tc\n" + patch
                + "print(json.dumps(tc.context_for('session_start', %r)))\n" % repo)
        proc = subprocess.run([sys.executable, "-c", body], capture_output=True,
                              text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def dropped_keys(self, text):
        return [a or b for a, b in
                re.findall(r"dropped ([a-z_]+) \(\d+ B\)|([a-z_]+) \(\d+ B\)", text)]

    def test_a_drop_happens_in_drop_order(self):
        import tezgah_context as tc  # noqa: E402
        repo = self.repo()
        self.write(os.path.join(repo, ".tezgah", "lessons.md"),
                   "a lesson line long enough that giving it up is measurable\n")
        # both of the two lowest-value blocks are present, so the order between
        # them is what the first drop decides
        self.touch(os.path.join(repo, ".tezgah", "plans", "open", "001-something.md"))
        self.line(repo, "beta", question="")
        self.session_text(repo)  # settle the one-time tier-agent note
        whole = self.session_text(repo)
        self.assertIn("Research: beta has", whole)
        self.assertIn("Open plans in this repo", whole)
        one_over = len(whole.encode()) - 1
        half = len(whole.encode()) // 2
        tight = self.dropped_keys(self.session_text(repo, limit=3000))
        for limit in (one_over, half, 3000):
            with self.subTest(limit=limit):
                keys = self.dropped_keys(self.session_text(repo, limit=limit))
                self.assertTrue(keys, "a drop was not reported at %d B" % limit)
                # the order the blocks went in is the order the file declares: a
                # key absent from this context is skipped, so the dropped keys are
                # that order's subsequence and never a reshuffle of it
                self.assertEqual(keys, [k for k in tc.DROP_ORDER if k in keys], keys)
                # each deeper limit gives up the same keys first, and then more
                self.assertEqual(keys, tight[:len(keys)], (keys, tight))
        # one byte over the whole text, the lowest-value block goes, and only it
        self.assertEqual(self.dropped_keys(self.session_text(repo, limit=one_over)),
                         ["lessons"])
        self.assertIn("Research: beta has", self.session_text(repo, limit=one_over))
        # half the budget reaches the line's own warning, and gives it up after
        # the text another surface already carries
        self.assertGreater(len(tight), 1)
        self.assertIn("research_broken", tight)
        self.assertNotIn("Research: beta has", self.session_text(repo, limit=3000))


class SessionNote(Workspace):
    def test_the_note_is_emitted_on_post_compact_too(self):
        # E6 row 7: the fixture only ever sent session_start, so the branch that
        # adds the note after a compaction was unpinned
        repo = self.repo()
        self.line(repo, "beta", question="")
        for event in ("session_start", "post_compact"):
            with self.subTest(event=event):
                self.assertIn("Research: beta has 1 problem(s), first: "
                              "state.json records no question",
                              self.session_note(repo, event))

    def test_the_note_names_the_command_to_run(self):
        # E6 row 8: the assertions stopped at the first error text, so the hint
        # the note ends with - run the CLI's check - was never checked, and a note
        # that names no command sends the reader to the wrong tool
        repo = self.repo()
        self.line(repo, "beta", question="")
        note = self.session_note(repo)
        self.assertIn("run `", note)
        self.assertIn("tezgah-research check` before reporting a result", note)

    def test_only_the_first_broken_line_is_reported_and_it_is_the_first(self):
        # E6 row 9: no test built two broken lines, so "the first" - and that the
        # first is the first in slug order - was unpinned
        repo = self.repo()
        self.line(repo, "alpha", question="")
        self.line(repo, "beta", question="")
        note = self.session_note(repo)
        broken = tr.failing(repo)
        self.assertEqual([slug for slug, _ in broken], ["alpha", "beta"], broken)
        self.assertIn("Research: alpha has 2 problem(s), first: %s" % broken[0][1],
                      note)
        self.assertNotIn("beta", note)

    def test_a_broken_line_is_reported(self):
        repo = self.repo()
        self.line(repo, "beta", question="")
        self.assertIn("Research: beta has 1 problem(s), first: "
                      "state.json records no question", self.session_note(repo))

    def test_a_clean_line_is_silent(self):
        repo = self.repo()
        self.line(repo, "alpha", question="alpha?")
        self.assertNotIn("problem(s)", self.session_note(repo))

    def test_no_line_is_silent(self):
        repo = self.repo()
        self.assertNotIn("problem(s)", self.session_note(repo))

    def test_an_uncommitted_protocol_is_not_reported(self):
        # the session note pays for structure only: no git history
        repo = self.repo()
        self.line(repo)
        self.protocol(repo)
        self.results(repo)
        self.assertNotIn("problem(s)", self.session_note(repo))

    def test_research_off_suppresses_the_note(self):
        repo = self.repo()
        self.line(repo, "beta", question="")
        self.assertIn("Research: beta has 1 problem(s), first: "
                      "state.json records no question", self.session_note(repo))
        self.touch(os.path.join(self.home, ".config", "tezgah", "research-off"))
        self.assertNotIn("problem(s)", self.session_note(repo))


class Predictions(Workspace):
    """`predictions.jsonl`: one row per proposed change, bound to a commit.

    The artifact is the falsifiable half of a harness-text change - the commit it
    landed in, the number it moves, what would show it did not - and the plan
    that adds it states the rule these cases exercise: the checker's verdict and
    the write path's refusal are two readings of one rule and have to agree,
    because this repository has twice shipped a write path stricter than its
    checker. Every case here hands the same row to both readings, and the file
    the checker reads is written by hand so neither reading is the other's
    fixture.
    """

    def cli(self, repo, *args, payload=None):
        data = None if payload is None else (
            payload if isinstance(payload, str) else json.dumps(payload) + "\n")
        return subprocess.run([sys.executable, CLI] + list(args), input=data,
                              capture_output=True, text=True, env=self.env(),
                              cwd=repo, timeout=60)

    def sha(self, repo, rev="HEAD"):
        return self.git(repo, "rev-parse", rev).strip()

    def row(self, commit, **over):
        pred = {"commit": commit, "claim": "", "metric": "p95",
                "value_before": 120, "value_after": 100,
                "falsifier": "p95 does not drop",
                # the component the row names: a row written under this rule
                # carries the field, so every case that is not about the field
                # carries a real key
                "components": [component_keys()[0]]}
        pred.update(over)
        return pred

    def lines(self, repo, tag=1):
        """(checked, written, commit): the line whose predictions.jsonl the
        checker reads, the line the CLI is handed the same row for, and a commit
        the row may name."""
        checked, written = "checked%d" % tag, "written%d" % tag
        for slug in (checked, written):
            self.line(repo, slug)
        self.commit(repo, "scaffold the lines", when=AFTER)
        return checked, written, self.sha(repo)

    def agree(self, repo, checked, written, row, refused):
        """Hand one row to both readings and assert they watched it alike."""
        self.write(os.path.join(tr.line_dir(repo, checked), "predictions.jsonl"),
                   json.dumps(row) + "\n")
        errors = self.errors(repo, checked)
        proc = self.cli(repo, "predict", written, payload=row)
        why = "checker %r, writer exit %d: %s" % (errors, proc.returncode,
                                                  proc.stdout + proc.stderr)
        self.assertEqual(bool(errors), refused, why)
        self.assertEqual(proc.returncode, 1 if refused else 0, why)
        return errors, proc

    def test_a_prediction_reads_the_claim_ids_under_the_lock(self):
        # the prediction writer is the third site: its `claim` relation is judged
        # against the ids this line holds, and judging that relation before the
        # lock let another session land the claim in between
        repo = self.repo()
        _checked, written, commit = self.lines(repo, 9)
        base = tr.line_dir(repo, written)
        self.write(os.path.join(base, "to_human", "report.md"), "# Report\n")
        self.race_at_the_lock(lambda: self.append_line(
            os.path.join(base, "claims.jsonl"),
            dict(CLAIM, id="C7", proof="to_human/report.md")))
        problems, undecided = tr.append_prediction(repo, written,
                                                   self.row(commit, claim="C7"))
        self.assertEqual(problems, [], undecided)
        self.assertEqual([json.loads(line)["claim"]
                          for line in read(os.path.join(base,
                                                        "predictions.jsonl")
                                           ).splitlines()], ["C7"])

    def test_a_valid_row_is_recorded_and_the_checker_reads_it_back(self):
        repo = self.repo()
        checked, written, commit = self.lines(repo)
        row = self.row(commit)
        errors, proc = self.agree(repo, checked, written, row, False)
        self.assertIn("prediction for commit %s recorded" % commit, proc.stdout)
        path = os.path.join(tr.line_dir(repo, written), "predictions.jsonl")
        self.assertEqual([json.loads(line) for line in read(path).splitlines()],
                         [row])
        # the row the writer appended is one the checker accepts where it stands
        self.assertEqual(self.errors(repo, written), [])

    def test_every_empty_required_field_is_refused_by_both_readings(self):
        cases = ({"metric": ""}, {"metric": "  "}, {"value_before": ""},
                 {"value_before": None}, {"falsifier": ""}, {"commit": ""},
                 {"commit": None}, {"commit": "abc123"})
        for n, over in enumerate(cases, 1):
            with self.subTest(over=over):
                repo = self.repo()
                checked, written, commit = self.lines(repo, n)
                pred = self.row(commit)
                pred.update(over)
                self.agree(repo, checked, written, pred, True)
                self.assertFalse(
                    os.path.exists(os.path.join(tr.line_dir(repo, written),
                                                "predictions.jsonl")),
                    "a refused row was written anyway")
                # the row's own shape is decided without the commit graph, so the
                # cheap path the session note pays for reads it too
                self.assertTrue(self.errors(repo, checked, git=False),
                                "the git-less path read no rule at all")

    def test_a_commit_that_is_not_an_ancestor_is_refused_by_both_readings(self):
        repo = self.repo()
        current = self.git(repo, "symbolic-ref", "--short", "HEAD").strip()
        checked, written, _commit = self.lines(repo)
        self.git(repo, "checkout", "-q", "-b", "side")
        self.write(os.path.join(repo, "side.txt"), "a change elsewhere\n")
        self.commit(repo, "a change on another branch", when=AFTER)
        side = self.sha(repo)
        self.git(repo, "checkout", "-q", current)
        # the fixture is a sha that exists and is not an ancestor, which is the
        # case git can decide; a sha git cannot place is the warn case below
        self.assertIs(tr.is_ancestor(repo, side, "HEAD"), False)
        errors, _proc = self.agree(repo, checked, written, self.row(side), True)
        self.assertTrue(hit("not an ancestor", errors), errors)

    def test_a_frozen_path_needs_a_human_grant(self):
        repo = self.repo()
        for path in ("hooks/tezgah_gate.py", "tests/test_hidden.py",
                     ".tezgah/research/other/experiments/h1/protocol.md"):
            self.write(os.path.join(repo, path), "# frozen\n")
        self.commit(repo, "the change", when=AFTER)
        frozen = self.sha(repo)
        checked, written, _commit = self.lines(repo)
        errors, _proc = self.agree(repo, checked, written, self.row(frozen), True)
        self.assertTrue(hit("granted_by", errors), errors)
        checked, written, _commit = self.lines(repo, 2)
        self.agree(repo, checked, written,
                   self.row(frozen, granted_by="the maintainer"), False)

    def test_the_rule_module_itself_is_frozen(self):
        # the machinery that decides the rule must not be edited by the loop it
        # judges, so a commit touching this module is refused without a grant
        repo = self.repo()
        self.write(os.path.join(repo, "hooks", "tezgah_research.py"),
                   "# the rule\n")
        self.commit(repo, "the change", when=AFTER)
        frozen = self.sha(repo)
        checked, written, _commit = self.lines(repo)
        errors, _proc = self.agree(repo, checked, written, self.row(frozen), True)
        self.assertTrue(hit("granted_by", errors), errors)
        checked, written, _commit = self.lines(repo, 2)
        self.agree(repo, checked, written,
                   self.row(frozen, granted_by="the maintainer"), False)

    def test_a_commit_git_cannot_place_warns_on_both_readings(self):
        # the fail-open the plan asks for: a check that cannot decide warns, it
        # does not invent a refusal
        repo = self.repo()
        checked, written, _commit = self.lines(repo)
        errors, proc = self.agree(repo, checked, written, self.row("0" * 40), False)
        self.assertTrue(hit("unverified", self.warnings(repo, checked)),
                        self.warnings(repo, checked))
        self.assertIn("warn", proc.stdout)

    def test_a_claim_id_the_line_holds_is_the_only_one_that_passes(self):
        repo = self.repo()
        checked, written, commit = self.lines(repo)
        errors, _proc = self.agree(repo, checked, written,
                                   self.row(commit, claim="C9"), True)
        self.assertTrue(hit("C9", errors), errors)
        # the same row with an id the line does hold: the id is checked against
        # the line the row lands in, so both lines carry the claim
        checked, written, commit = self.lines(repo, 2)
        for slug in (checked, written):
            self.write(os.path.join(tr.line_dir(repo, slug), "to_human",
                                    "report.md"), "# Report\n\np95 dropped.\n")
            self.claims(repo, dict(CLAIM, id="C1", proof="to_human/report.md"),
                        slug=slug)
        self.agree(repo, checked, written, self.row(commit, claim="C1"), False)

    def test_a_line_with_no_predictions_file_is_not_a_problem(self):
        # the regression corpus: every line in this repository predates the
        # artifact, and an absent file is not a finding
        repo = self.repo()
        self.line(repo)
        self.assertFalse(os.path.exists(
            os.path.join(tr.line_dir(repo, "q"), "predictions.jsonl")))
        self.assertEqual(self.errors(repo), [])
        proc = self.cli(repo, "check")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_row_without_components_is_refused_by_the_writer_and_warned(self):
        # the one asymmetry the component rule carries, named here so a later edit
        # cannot flip it: a row being written now names the component it changes,
        # and a row written before the rule has none and is the class `check`
        # reports instead - which `--strict` turns into a refusal.
        repo = self.repo()
        checked, written, commit = self.lines(repo)
        legacy = self.row(commit)
        del legacy["components"]
        self.write(os.path.join(tr.line_dir(repo, checked), "predictions.jsonl"),
                   json.dumps(legacy) + "\n")
        self.assertEqual(self.errors(repo, checked), [])
        warnings = self.warnings(repo, checked)
        self.assertTrue(hit("carries no components", warnings), warnings)
        strict = self.errors(repo, checked, strict=True)
        self.assertTrue(hit("carries no components", strict), strict)
        proc = self.cli(repo, "predict", written, payload=legacy)
        why = "writer exit %d: %s" % (proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(proc.returncode, 1, why)
        self.assertTrue(hit("carries no components", [proc.stdout]), proc.stdout)
        self.assertFalse(
            os.path.exists(os.path.join(tr.line_dir(repo, written),
                                        "predictions.jsonl")),
            "a row refused for naming no component was written anyway")

    def test_a_key_the_manifest_does_not_define_is_refused_by_both_readings(self):
        repo = self.repo()
        for n, keys in enumerate((["not-a-component"],
                                  [component_keys()[0], "not-a-component"]), 1):
            with self.subTest(keys=keys):
                checked, written, commit = self.lines(repo, n)
                row = self.row(commit, components=keys)
                errors, _proc = self.agree(repo, checked, written, row, True)
                self.assertTrue(hit("not-a-component", errors), errors)
                self.assertFalse(
                    os.path.exists(os.path.join(tr.line_dir(repo, written),
                                                "predictions.jsonl")),
                    "a row refused for an unknown key was written anyway")

    def test_a_components_field_that_names_no_key_is_refused_by_both_readings(self):
        # the field claims the shape and answers nothing with it: a string, a
        # number and an empty list are the same finding on both paths
        for n, bad in enumerate(([], "exec", 3, {}, ["exec", 1]), 1):
            with self.subTest(components=bad):
                repo = self.repo()
                checked, written, commit = self.lines(repo, n)
                self.agree(repo, checked, written,
                           self.row(commit, components=bad), True)

    def test_misuse_exits_two_with_nothing_on_stdout(self):
        repo = self.repo()
        self.line(repo)
        cases = ((("predict",), self.row("0" * 40)),
                 (("predict", "nope"), self.row("0" * 40)),
                 (("predict", "q", "extra"), self.row("0" * 40)),
                 (("predict", "q"), "{not json"),
                 (("predict", "q"), "[1, 2]"),
                 (("predict", "q"), "   "))
        for args, payload in cases:
            with self.subTest(args=args, payload=payload):
                proc = self.cli(repo, *args, payload=payload)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertEqual(proc.stdout, "")
                self.assertTrue(hit("tezgah-research:", [proc.stderr]), proc.stderr)


class ComponentsReport(Workspace):
    """`tezgah-research components`: the per-component report.

    A report and not a gate: it always exits 0 and prints what it read, so a
    reader can tell an empty manifest from a line with no predictions. A row's
    state is read from the row's own `value_after` and from the line's own claims
    - a `refuted` claim is the line saying the prediction did not hold - and a row
    whose claim the line does not hold says so instead of guessing.
    """

    def pred(self, **over):
        """One prediction row. The report reads the row's fields and the line's
        claims and never git, so a fixture needs no commit."""
        row = {"commit": "0" * 40, "metric": "p95", "value_before": 120,
               "value_after": 100, "falsifier": "p95 does not drop",
               "components": [component_keys()[0]]}
        row.update(over)
        return row

    def line_with(self, repo, *rows, slug="q"):
        base = self.line(repo, slug)
        self.write(os.path.join(base, "predictions.jsonl"),
                   "".join(json.dumps(r) + "\n" for r in rows))
        return base

    def test_the_report_groups_the_rows_by_component_and_counts_them(self):
        repo = self.repo()
        keys = component_keys()
        self.assertGreater(len(keys), 1, "a manifest of one component is not the "
                                         "mapping the plan describes: %r" % keys)
        first, second = keys[0], keys[-1]
        # a row written before the field existed: it names no component, and the
        # round it belongs to has not run either
        legacy = self.pred(value_after="")
        del legacy["components"]
        self.line_with(repo, self.pred(components=[first]),
                       self.pred(components=[first], value_after=""),
                       self.pred(components=[second], value_after=""),
                       legacy)
        proc = self.cli(repo, "components")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        line = proc.stdout
        self.assertIn("components: %d read, 4 prediction row(s) read" % len(keys),
                      line)
        self.assertIn("%s: 2 row(s) - 1 held, 0 falsified, 1 unmeasured" % first,
                      line)
        self.assertIn("%s: 1 row(s) - 0 held, 0 falsified, 1 unmeasured" % second,
                      line)
        self.assertIn("(no components): 1 row(s) - 0 held, 0 falsified, "
                      "1 unmeasured", line)
        self.assertIn("q #1 " + "0" * 8 + " p95: held", line)
        self.assertIn("q #2 " + "0" * 8 + " p95: unmeasured", line)

    def test_a_refuted_claim_is_the_line_saying_the_prediction_did_not_hold(self):
        repo = self.repo()
        self.line_with(repo, self.pred(claim="c1", value_after="0"),
                       self.pred(claim="c9", value_after="0"))
        self.claims(repo, dict(CLAIM, id="c1", status="refuted"))
        proc = self.cli(repo, "components")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        line = proc.stdout
        self.assertIn("q #1 " + "0" * 8 + " p95: falsified", line)
        # the id the line does not hold decides nothing, and the report says why
        # rather than reading the filled `value_after` as a verdict
        self.assertIn("q #2 " + "0" * 8 + " p95: unmeasured", line)
        self.assertIn("claim c9 is not an id this line holds", line)

    def test_the_json_report_carries_the_same_rows_and_counts(self):
        repo = self.repo()
        keys = component_keys()
        first_label = component_labels()[keys[0]]
        self.line_with(repo, self.pred(), self.pred(value_after=""))
        proc = self.cli(repo, "components", "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["read"], len(keys))
        # every component the manifest defines gets a bucket, in the manifest's
        # own order, so a component nothing predicts is visible and not absent
        self.assertEqual([b["key"] for b in report["components"]], keys)
        self.assertEqual([r["state"] for r in report["components"][0]["rows"]],
                         ["held", "unmeasured"])
        self.assertEqual(report["components"][0]["label"], first_label)

    def test_a_key_the_manifest_does_not_define_is_reported_not_refused(self):
        # the report is the other reading of the manifest, and it cannot refuse
        # what the checker already refuses: a hand-written row still prints
        repo = self.repo()
        self.line_with(repo, self.pred(components=["not-a-component"]),
                       self.pred(components="exec"))
        proc = self.cli(repo, "components")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("not-a-component: 1 row(s)", proc.stdout)
        self.assertIn("(no components): 1 row(s)", proc.stdout)

    def test_a_row_that_does_not_parse_is_named_and_the_row_count_skips_it(self):
        repo = self.repo()
        base = self.line_with(repo, self.pred())
        with open(os.path.join(base, "predictions.jsonl"), "a") as fh:
            fh.write("{not json\n")
        proc = self.cli(repo, "components")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("1 prediction row(s) read", proc.stdout)
        self.assertIn("does not parse", proc.stdout)

    def test_misuse_exits_two_with_nothing_on_stdout(self):
        repo = self.repo()
        self.line(repo)
        proc = self.cli(repo, "components", "q")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(hit("tezgah-research:", [proc.stderr]), proc.stderr)


class Standards(Workspace):
    """The design rules a research standard reads past the form of a line:
    variants compared under criteria fixed first, the evaluation locked before the
    first result, results left as the run wrote them, a review by a second reader,
    every ask item answered, sources that are sources."""

    LATER = "2022-02-02T00:00:00+0000"
    CRITERIA = {"question": "which layout", "baseline_variant": "V0",
                "criteria": [{"id": "K1", "name": "p95", "kind": "measured",
                              "direction": "min"},
                             {"id": "K2", "name": "steps", "kind": "measured",
                              "direction": "min"}]}

    def cli(self, repo, *args, payload=None):
        data = None if payload is None else (
            payload if isinstance(payload, str) else json.dumps(payload) + "\n")
        return subprocess.run([sys.executable, CLI] + list(args), input=data,
                              capture_output=True, text=True, env=self.env(),
                              cwd=repo, timeout=60)

    def state(self, repo, slug="q", **fields):
        path = os.path.join(tr.line_dir(repo, slug), "state.json")
        state = json.loads(read(path))
        state.update(fields)
        for key in [k for k, v in fields.items() if v is None]:
            del state[key]
        self.write(path, json.dumps(state))
        return state

    def decision(self, repo, produced=3, slug="q", name="d1", same=False):
        """criteria.json and variants.jsonl for `produced` variants, each a file of
        its own under the line (or one copied file when `same`)."""
        base = tr.line_dir(repo, slug)
        ddir = os.path.join(base, "decisions", name)
        self.write(os.path.join(ddir, "criteria.json"), json.dumps(self.CRITERIA))
        rows = []
        for n in range(produced):
            art = "variants/V%d.md" % n
            self.write(os.path.join(base, art),
                       "# layout\n" if same else "# layout %d\n" % n)
            rows.append({"id": "V%d" % n, "title": "layout %d" % n,
                         "artifact": art, "status": "produced"})
        self.write(os.path.join(ddir, "variants.jsonl"),
                   "".join(json.dumps(r) + "\n" for r in rows))
        return ddir

    def cells(self, ddir, scores):
        """{variant: (K1, K2)} as comparison rows, each sourced from the variant."""
        with open(os.path.join(ddir, "comparison.jsonl"), "a") as fh:
            for vid, values in scores.items():
                for cid, value in zip(("K1", "K2"), values):
                    fh.write(json.dumps({"variant": vid, "criterion": cid,
                                         "value": value,
                                         "source": "variants/%s.md" % vid}) + "\n")

    def decide(self, ddir, chosen="V1", rejected=(("V0", "K1"), ("V2", "K2"))):
        self.write(os.path.join(ddir, "decision.md"),
                   "chosen: %s\n\n%s\nflip: a K1 regression above 5%%\n"
                   % (chosen, "".join("- %s rejected on %s\n" % r for r in rejected)))

    def designed(self, repo, **kw):
        self.line(repo, phase="inner")
        self.state(repo, deliverable={"kind": "design", "path": "docs/x.md"})
        ddir = self.decision(repo, **kw)
        self.commit(repo, "criteria and variants", when=BEFORE)
        return ddir

    # --- P1 variants -----------------------------------------------------------

    def test_a_decided_comparison_of_three_distinct_variants_is_clean(self):
        repo = self.repo()
        ddir = self.designed(repo)
        self.cells(ddir, {"V0": (120, 5), "V1": (90, 4), "V2": (95, 6)})
        self.decide(ddir)
        self.commit(repo, "comparison", when=AFTER)
        errors = self.errors(repo, strict=True)
        self.assertFalse(hit("decisions/", errors), errors)

    def test_fewer_produced_variants_than_the_deliverable_takes_is_refused(self):
        repo = self.repo()
        ddir = self.designed(repo, produced=2)
        self.cells(ddir, {"V0": (120, 5), "V1": (90, 4)})
        self.decide(ddir, rejected=(("V0", "K1"),))
        self.commit(repo, "comparison", when=AFTER)
        self.assertTrue(hit("2 produced variant(s)", self.errors(repo)))
        self.assertEqual(self.cli(repo, "check", "q").returncode, 1)

    def test_a_renamed_copy_is_not_a_variant(self):
        repo = self.repo()
        self.designed(repo, same=True)
        self.assertTrue(hit("are the same file", self.errors(repo)))

    def test_criteria_committed_after_the_first_cell_are_refused(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.state(repo, deliverable={"kind": "design"})
        ddir = self.decision(repo)
        os.remove(os.path.join(ddir, "criteria.json"))
        self.cells(ddir, {"V0": (120, 5), "V1": (90, 4), "V2": (95, 6)})
        self.commit(repo, "cells first", when=BEFORE)
        self.write(os.path.join(ddir, "criteria.json"), json.dumps(self.CRITERIA))
        self.commit(repo, "criteria after", when=AFTER)
        self.assertTrue(hit("criteria.json did not enter the history before "
                            "comparison.jsonl", self.errors(repo)))

    def test_a_missing_cell_is_refused_once_the_decision_is_written(self):
        repo = self.repo()
        ddir = self.designed(repo)
        self.cells(ddir, {"V0": (120, 5), "V1": (90, 4)})
        self.assertFalse(hit("cell(s) of the variants x criteria", self.errors(repo)))
        self.decide(ddir)
        errors = self.errors(repo)
        self.assertTrue(hit("2 cell(s) of the variants x criteria", errors), errors)
        # a cell marked not_checked with its reason fills the matrix
        with open(os.path.join(ddir, "comparison.jsonl"), "a") as fh:
            for cid in ("K1", "K2"):
                fh.write(json.dumps({"variant": "V2", "criterion": cid,
                                     "not_checked": "no rig for V2"}) + "\n")
        self.assertFalse(hit("cell(s) of the variants x criteria", self.errors(repo)))

    def test_a_dominated_choice_is_refused(self):
        repo = self.repo()
        ddir = self.designed(repo)
        self.cells(ddir, {"V0": (120, 5), "V1": (90, 4), "V2": (80, 3)})
        self.decide(ddir)
        self.assertTrue(hit("chosen variant V1 is dominated by V2", self.errors(repo)))

    def test_a_rejection_that_names_no_criterion_is_refused(self):
        repo = self.repo()
        ddir = self.designed(repo)
        self.cells(ddir, {"V0": (120, 5), "V1": (90, 4), "V2": (95, 6)})
        self.write(os.path.join(ddir, "decision.md"),
                   "chosen: V1\n- V0 is older\n- V2 rejected on K2\n")
        errors = self.errors(repo)
        self.assertTrue(hit("rejects V0 on no criterion", errors), errors)
        self.assertTrue(hit("names no `flip:` condition", errors), errors)

    def test_a_design_with_no_decision_warns_and_is_refused_when_delivered(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.state(repo, deliverable={"kind": "design"})
        needle = "decisions/ holds no comparison"
        self.assertTrue(hit(needle, self.warnings(repo)))
        self.assertFalse(hit(needle, self.errors(repo)))
        self.assertTrue(hit(needle, self.errors(repo, strict=True)))
        self.state(repo, direction="conclude")
        self.assertTrue(hit(needle, self.errors(repo)))
        self.assertTrue(hit("has no decision comparing 3 variants",
                            dict(tr.open_lines(repo))["q"]))

    def test_one_variant_needs_its_reason(self):
        self.assertTrue(tr.deliverable_problems({"kind": "plan", "min_variants": 1})[0])
        self.assertEqual(tr.deliverable_problems(
            {"kind": "plan", "min_variants": 1,
             "single_variant_reason": "the ask fixed the design"}), ([], 1))

    def test_the_compare_writer_and_the_checker_agree(self):
        repo = self.repo()
        ddir = self.designed(repo)
        bad = {"variant": "V9", "criterion": "K1", "value": 1, "source": "variants/V0.md"}
        proc = self.cli(repo, "compare", "q", "d1", payload=bad)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(ddir, "comparison.jsonl")))
        self.append_line(os.path.join(ddir, "comparison.jsonl"), bad)
        self.assertTrue(hit("not a produced variant", self.errors(repo)))
        os.remove(os.path.join(ddir, "comparison.jsonl"))
        good = {"variant": "V1", "criterion": "K1", "value": 90,
                "source": "variants/V1.md"}
        proc = self.cli(repo, "compare", "q", "d1", payload=good)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(hit("comparison.jsonl:", self.errors(repo)))

    def test_a_judged_cell_needs_two_raters_under_strict(self):
        repo = self.repo()
        ddir = self.designed(repo)
        crit = dict(self.CRITERIA, criteria=[{"id": "K1", "name": "clarity",
                                              "kind": "judged", "direction": "max"}])
        self.write(os.path.join(ddir, "criteria.json"), json.dumps(crit))
        self.append_line(os.path.join(ddir, "comparison.jsonl"),
                         {"variant": "V0", "criterion": "K1", "value": 3,
                          "source": "variants/V0.md", "rater": "r1"})
        needle = "fewer than two distinct raters"
        self.assertTrue(hit(needle, self.warnings(repo)))
        self.assertTrue(hit(needle, self.errors(repo, strict=True)))
        self.append_line(os.path.join(ddir, "comparison.jsonl"),
                         {"variant": "V0", "criterion": "K1", "value": 4,
                          "source": "variants/V0.md", "rater": "r2"})
        self.assertFalse(hit(needle, self.warnings(repo)))

    def test_a_second_version_of_one_question_supersedes_the_first(self):
        repo = self.repo()
        self.line(repo, "v1", question="which admin layout?", phase="concluded")
        self.state(repo, "v1", closed={"limit": "superseded by v2"})
        proc = self.cli(repo, "init", "v2", "--ask", "which admin layout?",
                        "--question", "which admin layout?")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("--supersedes v1", proc.stdout)
        proc = self.cli(repo, "init", "v2", "--ask", "which admin layout?",
                        "--question", "which admin layout?", "--supersedes", "v1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.state(repo, "v2", direction="conclude")
        needle = "supersedes v1 and no variant carries its deliverable"
        self.assertTrue(hit(needle, self.errors(repo, "v2")))
        ddir = self.decision(repo, slug="v2")
        with open(os.path.join(ddir, "variants.jsonl"), "a") as fh:
            fh.write(json.dumps({"id": "V9", "title": "v1's plan", "line": "v1",
                                 "status": "dropped",
                                 "drop_reason": "kept as the old version"}) + "\n")
        self.assertFalse(hit(needle, self.errors(repo, "v2")))

    # --- P2 evaluation lock ----------------------------------------------------

    def test_an_evaluation_filled_after_the_results_is_refused(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.state(repo, evaluation={"metric": "", "baseline": "", "locked_at": ""})
        self.protocol(repo)
        self.commit(repo, "protocol", when=BEFORE)
        self.results(repo)
        self.commit(repo, "results", when=AFTER)
        self.state(repo, evaluation={"metric": "p95", "baseline": "bare",
                                     "locked_at": "2026-01-01"})
        self.commit(repo, "evaluation", when=self.LATER)
        needle = "the evaluation was not locked before the first results row"
        self.assertTrue(hit(needle, self.errors(repo)))
        # a line opened before the rule existed warns instead
        self.state(repo, rules=None)
        self.assertFalse(hit(needle, self.errors(repo)))
        self.assertTrue(hit(needle, self.warnings(repo)))

    def test_an_evaluation_locked_before_the_results_is_clean(self):
        repo = self.repo()
        self.clean(repo)
        self.assertFalse(hit("was not locked before", self.errors(repo)))

    def test_a_locked_at_commit_the_history_does_not_reach_is_refused(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.commit(repo, "line", when=BEFORE)
        self.state(repo, evaluation={"metric": "p95", "baseline": "bare",
                                     "locked_at": "protocol commit 07235b3"})
        self.assertTrue(hit("locked_at names 07235b3", self.errors(repo)))
        head = self.git(os.path.join(repo, ".tezgah"), "rev-parse", "HEAD").strip()
        self.state(repo, evaluation={"metric": "p95", "baseline": "bare",
                                     "locked_at": "commit %s" % head[:10]})
        self.assertFalse(hit("locked_at names", self.errors(repo)))

    # --- P3 review integrity and phase evasion ---------------------------------

    def test_a_report_owes_a_review_whatever_the_phase_says(self):
        repo = self.repo()
        base = self.line(repo, phase="outer")
        self.write(os.path.join(base, "to_human", "report.md"), REPORT)
        needle = "review.json is missing"
        self.assertTrue(hit(needle, self.warnings(repo)))
        self.assertTrue(hit(needle, self.errors(repo, strict=True)))

    def test_a_review_by_the_producer_is_refused(self):
        repo = self.repo()
        self.line(repo, phase="concluded")
        self.deliver(repo)
        path = os.path.join(tr.line_dir(repo, "q"), "to_human", "review.json")
        review = json.loads(read(path))
        self.review(repo, dict(review, reviewer="session-a"))
        self.assertTrue(hit("reviewer 'session-a' is the producer", self.errors(repo)))
        self.review(repo, dict(review, reviewer=""))
        self.assertTrue(hit("names no reviewer", self.errors(repo)))

    def test_a_review_with_no_finding_warns_and_strict_refuses_it(self):
        repo = self.repo()
        self.line(repo, phase="concluded")
        self.deliver(repo)
        self.review(repo, {"dimensions": {n: 3 for n in tr.REVIEW_DIMENSIONS},
                           "findings": []})
        needle = "records no finding at all"
        self.assertTrue(hit(needle, self.warnings(repo)))
        self.assertTrue(hit(needle, self.errors(repo, strict=True)))

    def test_a_review_cannot_grade_integrity_above_the_order_findings(self):
        repo = self.repo()
        self.line(repo, phase="concluded")
        self.deliver(repo)
        self.protocol(repo)
        self.results(repo)
        self.commit(repo, "protocol and results", when=BEFORE)
        needle = "scores exploration_integrity"
        self.assertFalse(hit(needle, self.errors(repo)))
        self.review(repo, {"dimensions": {n: 5 for n in tr.REVIEW_DIMENSIONS},
                           "findings": [{"severity": "minor", "status": "accepted",
                                         "target": "to_human/report.md",
                                         "quote": "held."}]})
        self.assertTrue(hit(needle, self.errors(repo)))

    # --- P4 results append-only ------------------------------------------------

    def test_a_committed_result_row_rewritten_later_is_refused(self):
        repo = self.repo()
        self.clean(repo)
        path = os.path.join(self.exp_dir(repo), "results.jsonl")
        needle = "results.jsonl was rewritten after the run"
        self.append_line(path, {"run": 2, "p95": 0.8, "scope": "real",
                                "source": "run.py run 2"})
        self.commit(repo, "second run", when=self.LATER)
        self.assertFalse(hit(needle, self.errors(repo)))
        self.write(path, json.dumps({"run": 1, "p95": 0.7, "scope": "real",
                                     "source": "run.py run 1"}) + "\n")
        self.assertTrue(hit(needle, self.errors(repo)), "uncommitted rewrite")
        self.commit(repo, "rewrite", when=self.LATER)
        self.assertTrue(hit(needle, self.errors(repo)), "committed rewrite")

    # --- P5 literature, ask, raters, validity ----------------------------------

    def test_a_nested_source_the_index_does_not_name_is_refused(self):
        repo = self.repo()
        self.line(repo)
        self.note(repo, os.path.join("slices", "scout.json"), "{}\n")
        needle = "literature/ holds 1 note(s) and no INDEX.jsonl"
        self.assertTrue(hit(needle, self.errors(repo)))
        self.index(repo, {"note": "other.md", "class": "grey"})
        self.assertTrue(hit("slices/scout.json is not in INDEX.jsonl",
                            self.errors(repo)))

    def test_every_ask_item_is_delivered_or_says_why_not(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.deliver(repo)
        self.state(repo, deliverable={"kind": "finding",
                                      "ask": ["memory use", "cold start"]})
        errors = self.errors(repo)
        self.assertTrue(hit("ask item(s) A1, A2", errors), errors)
        self.write(os.path.join(base, "to_human", "report.md"),
                   REPORT + "\nMemory use: held.\nA2 not delivered: no cold-start "
                            "rig.\n")
        self.assertFalse(hit("ask item(s)", self.errors(repo)))

    def test_a_claim_on_one_rater_warns_and_two_raters_do_not(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        row = {"run": 1, "score": 3, "scope": "real", "source": "walk 1",
               "rater": "r1"}
        self.results(repo, row=row)
        self.claims(repo, dict(CLAIM, proof="experiments/h1/results.jsonl"))
        needle = "rests only on judged rows from 1 rater"
        self.assertTrue(hit(needle, self.warnings(repo)))
        self.append_line(os.path.join(self.exp_dir(repo), "results.jsonl"),
                         dict(row, rater="r2"))
        self.assertFalse(hit(needle, self.warnings(repo)))

    def test_a_report_naming_no_validity_threat_warns(self):
        repo = self.repo()
        base = self.line(repo, phase="concluded")
        self.deliver(repo)
        self.assertFalse(hit("validity threat", self.warnings(repo)))
        self.write(os.path.join(base, "to_human", "report.md"),
                   "# Report\n\nheld.\n\nThis does not show the cost.\n"
                   "internal validity: one machine.\n")
        warnings = self.warnings(repo)
        self.assertTrue(hit("names no external, construct, conclusion validity",
                            warnings), warnings)

    def test_an_agent_report_cannot_alone_carry_a_literature_claim(self):
        repo = self.repo()
        self.line(repo, phase="inner")
        self.note(repo, "scout.md", "# what the scout read\n")
        self.index(repo, {"note": "scout.md", "class": "agent-report"})
        claim = dict(CLAIM, kind="literature", proof="literature/scout.md")
        self.claims(repo, claim)
        needle = "resting only on agent reports"
        self.assertTrue(hit(needle, self.errors(repo)))
        os.remove(os.path.join(tr.line_dir(repo, "q"), "claims.jsonl"))
        proc = self.cli(repo, "claim", "q", payload=claim)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(needle, proc.stdout)
        # beside the note on the page itself it stands
        self.note(repo, "page.md", "# the page\n")
        self.index(repo, {"note": "scout.md", "class": "agent-report"},
                   {"note": "page.md", "class": "grey", "quality": "vendor doc"})
        self.claims(repo, dict(claim, proof="literature/scout.md; literature/page.md"))
        self.assertFalse(hit(needle, self.errors(repo)))

    # --- the open-line hatch ---------------------------------------------------

    def test_allow_open_is_refused_beside_a_broken_line_until_it_is_closed(self):
        repo = self.repo()
        self.line(repo, "alpha", phase="inner")
        self.protocol(repo, "alpha")
        self.results(repo, "alpha")
        self.commit(repo, "both at once", when=BEFORE)
        proc = self.cli(repo, "init", "beta", "--ask", "is beta worth it?", "--allow-open", "because X")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("alpha:", proc.stdout)
        self.assertEqual(tr.slugs(repo), ["alpha"])
        proc = self.cli(repo, "close", "alpha", "--limit", "order unprovable")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(tr.open_lines(repo), [])
        log = read(os.path.join(tr.line_dir(repo, "alpha"), "log.md"))
        self.assertIn("order unprovable", log)
        self.assertEqual(self.cli(repo, "init", "beta", "--ask", "is beta worth it?").returncode, 0)


class HistoryBridge(Workspace):
    """A repository whose tree was re-rooted in one commit.

    When the whole tree lands in one root commit - this project's 2026-09-23
    force-push - both files of every experiment share that add and the commit
    graph no longer shows which came first. `<repo>/.tezgah/history-bridge.json`
    declares the pre-rewrite anchor; these cases pin what the declaration buys
    and what it never does."""

    TAG = "anchor/pre-rewrite"

    def unmoved(self, repo):
        """A line with no private `.tezgah` repository, opened before the rule set
        that demands a locked evaluation: its commits are the project's, which is
        the shape a re-rooted project is left in, and the evaluation-order rule
        stays the warning class it is for every line that predates it."""
        self.line(repo)
        path = os.path.join(tr.line_dir(repo, "q"), "state.json")
        state = json.loads(read(path))
        state.pop("rules", None)
        self.write(path, json.dumps(state))
        shutil.rmtree(os.path.join(repo, ".tezgah", ".git"))

    def old_history(self, repo, ordered=True):
        """The two-commit order in the project, pinned by the tag: the line was
        committed before the move, so its proof is the project's history."""
        if ordered:
            self.protocol(repo)
            self.commit(repo, "protocol", when=BEFORE)
            self.results(repo)
            self.commit(repo, "results", when=AFTER)
        else:
            self.results(repo)
            self.commit(repo, "results", when=BEFORE)
            self.protocol(repo)
            self.commit(repo, "protocol", when=AFTER)
        anchor = self.git(repo, "rev-parse", "HEAD").strip()
        self.git(repo, "tag", self.TAG, anchor)
        return anchor

    def reroot(self, repo):
        """A new root commit holding the whole tree, so HEAD no longer reaches
        the old history and the tag is the only way back to it."""
        self.git(repo, "checkout", "-q", "--orphan", "reroot")
        self.commit(repo, "initial commit", when=AFTER)
        return self.git(repo, "rev-parse", "HEAD").strip()

    def declare(self, repo, anchor, rewrite, **over):
        bridge = {"rewrite_commit": rewrite[:7], "anchor_tag": self.TAG,
                  "anchor_sha": anchor, "why": "re-rooted on 2026-09-23"}
        bridge.update(over)
        self.write(os.path.join(repo, ".tezgah", "history-bridge.json"),
                   json.dumps(bridge) + "\n")
        return bridge

    def protocol_blob(self, repo, rev):
        rel = os.path.relpath(os.path.join(self.exp_dir(repo), "protocol.md"), repo)
        return self.git(repo, "rev-parse", "%s:%s" % (rev, rel)).strip()

    def test_a_declared_bridge_proves_the_rerooted_order(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        self.assertEqual(self.errors(repo), [])
        report = tr.check(repo, "q")["q"]
        self.assertTrue(hit("order: bridged via %s" % self.TAG, report["notes"]),
                        report["notes"])

    def test_an_orphan_branch_with_no_bridge_is_still_refused(self):
        # no declaration, no proof: one commit adding both files is the refusal
        # it has always been
        repo = self.repo()
        self.unmoved(repo)
        self.old_history(repo)
        self.reroot(repo)
        self.assertTrue(hit(BOTH_TOGETHER, self.errors(repo)), self.errors(repo))

    def test_removing_the_bridge_file_refuses_the_rewrite_commit_again(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        self.assertEqual(self.errors(repo), [])
        os.remove(os.path.join(repo, ".tezgah", "history-bridge.json"))
        self.assertTrue(hit(BOTH_TOGETHER, self.errors(repo)), self.errors(repo))

    def test_an_anchor_that_lost_the_order_is_refused(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo, ordered=False)
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        self.assertTrue(hit("no protocol-before-results", self.errors(repo)),
                        self.errors(repo))

    def test_a_blob_that_moved_across_the_rewrite_is_refused(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        # the re-rooted tree holds a protocol the anchor never ordered: the blob
        # at the rewrite commit differs from the one the anchor proved
        self.write(os.path.join(self.exp_dir(repo), "protocol.md"),
                   "# Protocol\n\nchange: cache the lookups\nprediction: p95 drops\n"
                   "falsification: p95 holds or rises\noutcome: p95 dropped\n")
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        errors = self.errors(repo)
        self.assertTrue(hit("blobs differ", errors), errors)
        self.assertTrue(hit(self.protocol_blob(repo, anchor), errors), errors)

    def test_a_results_file_extended_since_the_anchor_is_still_bridged(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        # A row appended after the anchor was pinned and before the re-root: the
        # run only ever appends, so the anchor's rows are the head of the file the
        # rewrite holds, and a grown file is not a disagreement.
        self.append_line(os.path.join(self.exp_dir(repo), "results.jsonl"),
                         {"run": 2, "p95": 0.8, "scope": "real",
                          "source": "run.py run 2"})
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        self.assertEqual(self.errors(repo), [])
        report = tr.check(repo, "q")["q"]
        self.assertTrue(hit("(results extended since the anchor)", report["notes"]),
                        report["notes"])

    def test_a_protocol_extended_since_the_anchor_is_still_refused(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        # Only the results file is append-only: a protocol that grew after the
        # anchor is still an edited plan, so a prefix is refused there - the pair
        # the bridge tied together is unchanged.
        with open(os.path.join(self.exp_dir(repo), "protocol.md"), "a") as fh:
            fh.write("outcome: p95 dropped\n")
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        errors = self.errors(repo)
        self.assertTrue(hit("protocol.md blobs differ", errors), errors)

    def test_an_experiment_added_by_the_rewrite_warns_where_strict_refuses(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        # A second experiment opened after the anchor was pinned: the re-root is
        # the only commit that ever added its files, so the anchor holds no order
        # for it. The line is younger than the anchor, which is unprovable rather
        # than false, so it warns and `--strict` still refuses it.
        self.protocol(repo, h="h2")
        self.results(repo, h="h2")
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        self.assertEqual(self.errors(repo), [])
        warnings = self.warnings(repo)
        self.assertTrue(hit("this experiment's files first appear in the rewrite",
                            warnings), warnings)
        strict = self.errors(repo, strict=True)
        self.assertTrue(hit("this experiment's files first appear in the rewrite",
                            strict), strict)

    def test_a_bridge_whose_tag_is_missing_is_refused_naming_it(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        self.assertEqual(self.errors(repo), [])
        self.git(repo, "tag", "-d", self.TAG)
        errors = self.errors(repo)
        self.assertTrue(hit(self.TAG, errors), errors)
        self.assertTrue(hit("does not have", errors), errors)

    def test_a_bridge_whose_tag_resolves_elsewhere_is_refused(self):
        repo = self.repo()
        self.unmoved(repo)
        self.old_history(repo)
        rewrite = self.reroot(repo)
        # the tag still points at the old anchor, the declaration names the new
        # root as the sha that tag must equal
        self.declare(repo, rewrite, rewrite)
        errors = self.errors(repo)
        self.assertTrue(hit("resolves to", errors), errors)
        self.assertTrue(hit(self.TAG, errors), errors)

    def test_a_bridge_places_a_prediction_bound_to_a_pre_rewrite_commit(self):
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        row = {"commit": anchor, "metric": "p95", "value_before": 120,
               "falsifier": "p95 does not drop",
               "components": [component_keys()[0]]}
        self.write(os.path.join(tr.line_dir(repo, "q"), "predictions.jsonl"),
                   json.dumps(row) + "\n")
        self.assertFalse(hit("not an ancestor of HEAD", self.errors(repo)),
                         self.errors(repo))

    def test_a_one_commit_add_with_no_bridge_stays_refused(self):
        # the shape Ustam's project commit 3976f19 left: one commit added both
        # files and the repository declares no bridge, so the refusal stands - a
        # bridge is never inferred from a tag that happens to exist
        repo = self.repo()
        self.unmoved(repo)
        self.protocol(repo)
        self.results(repo)
        self.commit(repo, "protocol and results together", when=BEFORE)
        self.assertTrue(hit(BOTH_TOGETHER, self.errors(repo)), self.errors(repo))

    def test_a_commit_under_an_unrelated_tag_stays_unplaced(self):
        # a benchmark pin is not a bridge: only a commit the declared anchor
        # reaches is placed, so a commit reachable from another tag is still
        # refused
        repo = self.repo()
        self.unmoved(repo)
        anchor = self.old_history(repo)
        self.git(repo, "checkout", "-q", "-b", "pin", anchor)
        self.write(os.path.join(repo, "pin.txt"), "pinned\n")
        self.commit(repo, "a benchmark pin", when=AFTER)
        pinned = self.git(repo, "rev-parse", "HEAD").strip()
        self.git(repo, "tag", "benchmark-pin", pinned)
        rewrite = self.reroot(repo)
        self.declare(repo, anchor, rewrite)
        row = {"commit": pinned, "metric": "p95", "value_before": 120,
               "falsifier": "p95 does not drop",
               "components": [component_keys()[0]]}
        self.write(os.path.join(tr.line_dir(repo, "q"), "predictions.jsonl"),
                   json.dumps(row) + "\n")
        errors = self.errors(repo)
        self.assertTrue(hit("not an ancestor of HEAD", errors), errors)


class AskContract(Workspace):
    """The ask contract and the open/done layout (rules 3, 2026-10-01).

    The layer was missing both: a line never recorded the user's words, so
    "answered" had nothing to be judged against, and `close --limit` was an
    unconditional exit (4 of 11 sampled lines concluded with the ask unanswered).
    """

    def setUp(self):
        super().setUp()
        self.repo_path = self.repo()
        tr.init(self.repo_path, "q", question="does it help?", created="2026-01-01",
                ask="does it help?", tier="study")

    def cli(self, *args):
        return super().cli(self.repo_path, *args)

    def write_success(self, rows):
        path = os.path.join(tr.line_dir(self.repo_path, "q"), "state.json")
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        state["success"] = rows
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def errors(self, strict=False):
        return tr.check_line(self.repo_path, "q", git=False, strict=strict)[0]

    def test_init_lands_the_line_under_open(self):
        self.assertTrue(tr.line_dir(self.repo_path, "q").endswith(
            os.path.join("research", "open", "q")))

    def test_init_without_an_ask_is_refused(self):
        proc = self.cli("init", "no-ask")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("--ask", proc.stdout)

    def test_a_quick_question_gets_no_line(self):
        proc = self.cli("init", "quick-one", "--ask", "one number", "--tier", "quick")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("answer it in the reply", proc.stdout)
        self.assertNotIn("quick-one", tr.slugs(self.repo_path))

    def test_a_line_past_bootstrap_without_criteria_is_refused(self):
        path = os.path.join(tr.line_dir(self.repo_path, "q"), "state.json")
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        state["phase"] = "inner"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        self.assertTrue(any("no success criteria" in e for e in self.errors()))

    def test_a_verdict_needs_a_criterion_and_evidence(self):
        self.write_success([{"id": "S1", "criterion": "the table answers it"}])
        self.assertEqual(self.cli("verdict", "q", "S9", "met",
                                  "--evidence", "x").returncode, 1)
        self.assertEqual(self.cli("verdict", "q", "S1", "met").returncode, 1)

    def test_conclude_refuses_until_every_criterion_has_a_verdict(self):
        self.write_success([{"id": "S1", "criterion": "the table answers it"}])
        proc = self.cli("conclude", "q")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no verdict for S1", proc.stdout)

    def test_conclude_moves_the_line_to_done(self):
        self.write_success([{"id": "S1", "criterion": "the table answers it"}])
        self.assertEqual(self.cli("verdict", "q", "S1", "met",
                                  "--evidence", "report.md#S1").returncode, 0)
        proc = self.cli("conclude", "q")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(tr.sealed(self.repo_path, "q"))
        self.assertIn("q", tr.slugs(self.repo_path))

    def test_a_closed_line_over_an_unmet_criterion_needs_an_ack(self):
        self.write_success([{"id": "S1", "criterion": "the table answers it"}])
        self.assertEqual(self.cli("verdict", "q", "S1", "not-met",
                                  "--evidence", "report.md#unmeasured").returncode, 0)
        refused = self.cli("close", "q", "--limit", "stopped")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("--ack", refused.stdout)
        ok = self.cli("close", "q", "--limit", "stopped", "--ack", "user said stop")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertTrue(tr.sealed(self.repo_path, "q"))

    def test_an_unmet_verdict_marks_the_line_unanswered(self):
        self.write_success([{"id": "S1", "criterion": "x", "verdict": "not-met",
                             "evidence": "report.md"}])
        self.assertTrue(tr.unanswered(tr.line_state(self.repo_path, "q")))

    def test_the_resolver_finds_a_flat_legacy_line(self):
        os.makedirs(os.path.join(tr.root(self.repo_path), "legacy"), exist_ok=True)
        with open(os.path.join(tr.root(self.repo_path), "legacy", "state.json"), "w") as fh:
            fh.write('{"question": "old"}')
        self.assertIn("legacy", tr.slugs(self.repo_path))
        self.assertEqual(tr.line_dir(self.repo_path, "legacy"),
                         os.path.join(tr.root(self.repo_path), "legacy"))

    def test_migrate_layout_moves_flat_lines_by_their_state(self):
        os.makedirs(os.path.join(tr.root(self.repo_path), "oldopen"), exist_ok=True)
        os.makedirs(os.path.join(tr.root(self.repo_path), "olddone"), exist_ok=True)
        with open(os.path.join(tr.root(self.repo_path), "oldopen", "state.json"), "w") as fh:
            fh.write('{"question": "x", "phase": "inner"}')
        with open(os.path.join(tr.root(self.repo_path), "olddone", "state.json"), "w") as fh:
            fh.write('{"question": "y", "phase": "concluded"}')
        moved = dict(tr.migrate_layout(self.repo_path))
        self.assertEqual(moved, {"oldopen": "open", "olddone": "done"})
        self.assertEqual(tr.migrate_layout(self.repo_path), [], "idempotent")
        self.assertEqual(tr.slugs(self.repo_path), ["olddone", "oldopen", "q"])


if __name__ == "__main__":
    unittest.main()
