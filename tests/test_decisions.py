"""bin/tezgah-decisions: the ADR record under `.tezgah/decisions/`.

The gap this closes is a demand with no location: `skills/feature-audit/SKILL.md`
makes a capability change owe an ADR and names "an ADR without a status" as its
falsifier, and the repository had no directory, no status vocabulary and nothing
that read the record back. Every fixture here is a real record under a temp
HOME's own `.tezgah/decisions/`, and the CLI is run in a subprocess the way a
person runs it, so what is asserted is the record that comes out - not what the
writer meant to write.

Each refusal is exercised beside a whole record in the same directory: a checker
that refused everything would satisfy the three refusal cases on their own.
"""
import json
import os
import subprocess
import sys
import unittest

import support
from support import TempHome

CLI = os.path.join(support.REPO, "bin", "tezgah-decisions")


def record_text(ident="001", title="a decision", status="accepted", supersedes="",
                sections=("the constraints", "we record the decision",
                          "it gets easier")):
    """One record file's text, in the shape the CLI's help prints.

    `status=None` omits the key entirely - the shape the checker must refuse for
    the reason the feature-audit skill names; `id=None` omits the frontmatter id,
    which is how a record whose id can only come from its file name is written."""
    lines = ["---"]
    if ident is not None:
        lines.append("id: %s" % ident)
    lines += ["title: %s" % title]
    if status is not None:
        lines.append("status: %s" % status)
    lines += ["date: 2026-09-30", "supersedes: %s" % supersedes, "---"]
    for name, body in zip(("Context", "Decision", "Consequences"), sections):
        lines += ["## %s" % name, body]
    return "\n".join(lines) + "\n"


def entry(records, ident):
    return next(r for r in records["entries"] if r["id"] == ident)


class DecisionRecords(TempHome):
    """A temp HOME whose repository carries a temp `.tezgah/decisions/`."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.directory = os.path.join(self.repo, ".tezgah", "decisions")
        os.makedirs(self.directory)

    def write(self, name, text):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def check(self, *args):
        """The CLI in a subprocess, run from the repository it is about."""
        return subprocess.run([sys.executable, CLI] + list(args),
                              capture_output=True, text=True, env=self.env(),
                              cwd=self.repo, timeout=60)

    def whole(self, name="001-a-decision.md", **kwargs):
        return self.write(name, record_text(**kwargs))


class Check(DecisionRecords):
    def test_a_whole_record_is_read_and_listed(self):
        self.whole(title="Decisions are numbered")
        proc = self.check("check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("1 record(s)", proc.stdout)
        self.assertIn("001", proc.stdout)
        self.assertIn("accepted", proc.stdout)
        self.assertIn("Decisions are numbered", proc.stdout)
        self.assertNotIn("FAIL", proc.stdout)

    def test_a_record_without_a_status_is_refused(self):
        self.whole()
        self.write("002-b.md", record_text(status=None))
        proc = self.check("check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL .tezgah/decisions/002-b.md: no `status:`", proc.stdout)
        # the whole record beside it is still read, not swept up in the refusal
        self.assertIn("2 record(s)", proc.stdout)

    def test_a_status_outside_the_vocabulary_is_refused(self):
        self.whole()
        self.write("002-b.md", record_text(status="maybe"))
        proc = self.check("check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("status 'maybe' is not one of", proc.stdout)
        for status in ("proposed", "accepted", "deprecated", "superseded"):
            self.assertIn(status, proc.stdout)

    def test_a_supersedes_naming_no_record_is_refused(self):
        self.whole()
        self.write("002-b.md", record_text(supersedes="009"))
        proc = self.check("check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL .tezgah/decisions/002-b.md: `supersedes: 009`",
                      proc.stdout)
        self.assertIn("names no record", proc.stdout)

    def test_a_supersedes_naming_a_record_passes(self):
        # the control for the refusal above: the check is existence, so a broken
        # chain is refused and a whole one is not
        self.whole()
        self.write("002-b.md", record_text(supersedes="001"))
        proc = self.check("check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("FAIL", proc.stdout)

    def test_an_id_comes_from_the_file_name_when_the_record_has_none(self):
        self.whole(name="001-a-decision.md", ident=None)
        self.write("002-b.md", record_text(ident=None, supersedes="001"))
        proc = self.check("check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("002", proc.stdout)

    def test_every_record_is_checked_and_not_only_the_first(self):
        self.whole()
        self.write("002-b.md", record_text(status="maybe"))
        proc = self.check("check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(".tezgah/decisions/002-b.md", proc.stdout)

    def test_a_run_that_read_no_record_says_so(self):
        proc = self.check("check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0 record(s)", proc.stdout)
        # the directory absent is the same answer, not a refusal: a repository
        # with no decision to record is not a broken one
        os.rmdir(self.directory)
        proc = self.check("check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0 record(s)", proc.stdout)

    def test_a_file_that_is_not_a_record_is_not_read(self):
        # the layer's own prose sits beside the records (`.tezgah/plans/README.md`
        # is the same shape), and a checker that read it would refuse it for a
        # status it was never meant to carry - the count is what shows a record
        # filed under a name the checker does not read
        self.whole()
        self.write("README.md", "# Decisions\n\nOne file per decision.\n")
        proc = self.check("check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("1 record(s)", proc.stdout)

    def test_the_path_argument_names_the_repository(self):
        self.whole()
        proc = self.check("check", self.repo)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("1 record(s)", proc.stdout)
        # and the repository is read from anywhere, not from where the CLI ran
        elsewhere = os.path.join(self.home, "elsewhere")
        os.makedirs(elsewhere)
        proc = subprocess.run([sys.executable, CLI, "check", self.repo],
                              capture_output=True, text=True, env=self.env(),
                              cwd=elsewhere, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("1 record(s)", proc.stdout)

    def test_json_carries_the_records_and_the_problems(self):
        self.whole()
        self.write("002-b.md", record_text(status=None))
        proc = self.check("check", "--json")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        found = json.loads(proc.stdout)
        self.assertEqual(found["records"], 2)
        self.assertEqual([p.split(":")[0] for p in found["problems"]],
                         [".tezgah/decisions/002-b.md"])
        # a reader gets the prose half too, not only the keys the checker reads
        self.assertEqual(entry(found, "001")["status"], "accepted")
        self.assertEqual(entry(found, "001")["context"], "the constraints")
        self.assertEqual(entry(found, "001")["decision"], "we record the decision")
        self.assertEqual(entry(found, "001")["consequences"], "it gets easier")

    def test_an_unknown_option_is_misuse(self):
        proc = self.check("check", "--verbose")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("--verbose", proc.stderr)

    def test_an_unknown_command_is_misuse(self):
        proc = self.check("list")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("unknown command 'list'", proc.stderr)

    def test_a_directory_that_does_not_exist_is_refused(self):
        proc = self.check("check", os.path.join(self.home, "no-such-repo"))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no such directory", proc.stdout)


if __name__ == "__main__":
    unittest.main()
