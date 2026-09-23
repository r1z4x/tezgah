"""bin/tezgah-doctor: the store report, the reclaim actions and --coverage.

Runs the tool in a throwaway HOME with a real (empty) sqlite database, a
throwaway tezgah root and a stub codegraph, so the machine's own caches, roots,
opencode database and graph index are never read or touched.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCTOR = os.path.join(REPO, "bin", "tezgah-doctor")
# a PATH with git and nothing else: no codegraph, no npx, so a case that wants a
# live index dump must point TEZGAH_CODEGRAPH_BIN at its own stub
BARE_PATH = "/usr/bin:/bin"


def load_module():
    """Import the extensionless doctor script as a module to unit-test it."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("tezgah_doctor_under_test", DOCTOR)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True)


class DoctorBase(unittest.TestCase):
    """The throwaway HOME, root and opencode database every case runs against."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        self.data = os.path.join(self.home, ".local", "share", "opencode")
        os.makedirs(self.data, exist_ok=True)
        self.db = os.path.join(self.data, "opencode.db")
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER)")
        con.execute("CREATE TABLE event (id TEXT)")
        con.commit()
        con.close()
        # the configured root is this empty dir, so a default run can never walk
        # the machine's own ~/Projects
        self.root = os.path.join(self.home, "Projects")
        os.makedirs(self.root, exist_ok=True)
        self.env = {
            "PATH": BARE_PATH,
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_ROOTS": self.root,
        }

    def session(self, sid, age_days):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO session (id, time_updated) VALUES (?, ?)",
                    (sid, int((time.time() - age_days * 86400) * 1000)))
        con.commit()
        con.close()

    def fake_opencode(self):
        log = os.path.join(self.home, "oc-args.log")
        script = os.path.join(self.home, "fake-opencode")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\necho "$@" >> "%s"\n' % log)
        os.chmod(script, 0o755)
        return script, log

    def doctor(self, *args, env=None):
        return subprocess.run([sys.executable, DOCTOR] + list(args),
                              capture_output=True, text=True, env=env or self.env)

    def make_repo(self, name, index_bytes=None, root=None):
        """A repo tezgah would index: a `.git` marker, and `.codegraph/codegraph.db`
        when `index_bytes` is given."""
        repo = os.path.join(root or self.root, name)
        os.makedirs(os.path.join(repo, ".git"), exist_ok=True)
        if index_bytes is not None:
            os.makedirs(os.path.join(repo, ".codegraph"), exist_ok=True)
            with open(os.path.join(repo, ".codegraph", "codegraph.db"), "wb") as fh:
                fh.write(b"x" * index_bytes)
        return repo

    def indexed(self, rep):
        """The report's per-repo rows as {repo: row}."""
        return {row["repo"]: row for row in rep["codegraph_repos"]}


class Doctor(DoctorBase):
    """The report and the reclaim actions, no `--coverage`."""

    def test_prune_sessions_selects_only_old_and_calls_cli(self):
        self.session("ses_old", 10)
        self.session("ses_new", 1)
        script, log = self.fake_opencode()
        mod = load_module()
        mod.OPENCODE_DB = self.db
        mod.OPENCODE_BIN = script
        self.assertEqual(mod.select_old_sessions(7), ["ses_old"])
        self.assertEqual(mod.prune_sessions(7), (1, 0))
        with open(log) as fh:
            calls = fh.read()
        self.assertIn("session delete ses_old", calls)
        self.assertNotIn("ses_new", calls)

    def test_prune_sessions_without_the_cli_counts_nothing_failed(self):
        # no opencode binary => nothing is attempted, so no id may be "failed"
        self.session("ses_old", 10)
        mod = load_module()
        mod.OPENCODE_DB = self.db
        mod.OPENCODE_BIN = None
        self.assertEqual(mod.prune_sessions(7), (0, 0))

    def test_clean_reports_vacuum_outcome(self):
        proc = self.doctor("--clean", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertIn("vacuum", rep["cleaned"])

    def test_json_reports_the_index_bytes_per_repo(self):
        indexed = self.make_repo("indexed", index_bytes=500)
        self.make_repo("plain")
        proc = self.doctor("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["codegraph_bytes"], 500)
        self.assertEqual(self.indexed(rep)[indexed]["bytes"], 500)
        self.assertTrue(self.indexed(rep)[indexed]["indexed"])
        self.assertEqual(rep["opencode_sessions"], 0)
        self.assertEqual(rep["opencode_events"], 0)
        # the report is about codegraph's store: no engine it replaced may be
        # named in it, in the JSON or in the text
        self.assertNotIn("cbm", proc.stdout)
        text = self.doctor()
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertNotIn("cbm", text.stdout)

    def test_a_repo_with_no_index_is_reported_as_having_none(self):
        plain = self.make_repo("plain")
        proc = self.doctor("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = self.indexed(json.loads(proc.stdout))[plain]
        self.assertEqual((row["bytes"], row["indexed"]), (0, False))
        text = self.doctor().stdout
        self.assertIn("plain", text)
        self.assertIn("no index", text)

    def test_a_named_repo_replaces_the_configured_roots(self):
        # `--repo` is how a user accounts for a checkout outside every root: the
        # roots' own repos are then not walked at all
        self.make_repo("from-root", index_bytes=100)
        outside = os.path.join(self.home, "elsewhere")
        os.makedirs(outside, exist_ok=True)
        named = self.make_repo("named", index_bytes=42, root=outside)
        proc = self.doctor("--json", "--repo", named)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(list(self.indexed(rep)), [named])
        self.assertEqual(self.indexed(rep)[named]["bytes"], 42)


class Coverage(DoctorBase):
    """The `--coverage` report over one repo: a stub index dump, four tracked
    files, and no codegraph on the machine."""

    INDEX = {"files": [{"path": "app.py"}, {"path": "bin/twin.py"}]}

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.home, "covered")
        os.makedirs(os.path.join(self.repo, "bin"))
        self.write("app.py", "print(1)\n")
        self.write("missing.py", "print(2)\n")
        self.write("bin/twin", "#!/usr/bin/env python3\nprint(3)\n")
        self.write("bin/twin.py", "print(3)\n")
        self.write("bin/tool", "#!/usr/bin/env python3\nprint(4)\n")
        self.write("notes.md", "# notes\n")
        git(self.repo, "init", "-q")
        git(self.repo, "add", ".")
        self.dump = os.path.join(self.home, "dump.json")
        with open(self.dump, "w") as fh:
            json.dump(self.INDEX, fh)

    def write(self, rel, text, mode=0o644):
        path = os.path.join(self.repo, rel)
        with open(path, "w") as fh:
            fh.write(text)
        os.chmod(path, mode)
        return path

    def stub_codegraph(self):
        """A `codegraph` that answers `files -j` with the fixture dump, so the
        live path is exercised without the real binary or npx."""
        script = os.path.join(self.home, "stub-codegraph")
        with open(script, "w") as fh:
            fh.write("#!/bin/sh\ncat <<'JSON'\n%s\nJSON\n" % json.dumps(self.INDEX))
        os.chmod(script, 0o755)
        return script

    def coverage(self, *args, env=None):
        return self.doctor("--coverage", "--repo", self.repo, *args,
                           env=env or self.env)

    def test_coverage_lists_the_missing_supported_file_and_the_script(self):
        env = dict(self.env, TEZGAH_CODEGRAPH_BIN=self.stub_codegraph())
        proc = self.coverage(env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # the counts come first, so an empty report cannot read as full coverage
        self.assertIn("tracked files read: 6 | files the index holds: 2", proc.stdout)
        self.assertIn("uncovered, supported extension (1):", proc.stdout)
        self.assertIn("missing.py (python)", proc.stdout)
        self.assertIn("uncovered, shebang-only script with no `.py` twin (1):",
                      proc.stdout)
        self.assertIn("bin/tool (python3)", proc.stdout)
        # a supported file the index holds, and an extension it has no parser
        # for, are neither of them gaps
        self.assertNotIn("app.py", proc.stdout)
        self.assertNotIn("notes.md", proc.stdout)

    def test_a_script_with_an_indexed_py_twin_counts_as_covered(self):
        env = dict(self.env, TEZGAH_CODEGRAPH_BIN=self.stub_codegraph())
        proc = self.coverage(env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("covered through a `.py` twin (1)", proc.stdout)
        self.assertNotIn("bin/twin (", proc.stdout)

    def test_coverage_reads_a_dump_with_no_codegraph_installed(self):
        proc = self.coverage("--dump", self.dump)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tracked files read: 6 | files the index holds: 2", proc.stdout)
        self.assertIn("missing.py (python)", proc.stdout)

    def test_coverage_is_a_report_when_the_dump_cannot_be_read(self):
        # no dump and no codegraph anywhere: the run still exits 0, and it says
        # what it could not read instead of printing an empty file list
        proc = self.coverage()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("could not read an index dump", proc.stdout)
        self.assertNotIn("tracked files read", proc.stdout)


if __name__ == "__main__":
    unittest.main()
