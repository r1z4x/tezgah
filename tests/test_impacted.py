#!/usr/bin/env python3
"""The impacted-test map cannot silently lose a file or a module.

`tests/impacted.py` decides what runs for a change, so a hole in it is a change
that ships untested. This pins the map's edges rather than its output: every
source file the repo ships maps to a non-empty set or to FULL, the hand-known
edges hold, and the fail-safe answers FULL. It runs no test module.
"""
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

import impacted

REPO = impacted.REPO


class TheMap(unittest.TestCase):
    def modules(self, path):
        return impacted.modules_for(path, {})

    def test_every_shipped_source_file_maps_to_something(self):
        seen = 0
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", ".tezgah", "__pycache__",
                                    "node_modules", "dist")]
            for name in files:
                path = os.path.relpath(os.path.join(root, name), REPO)
                if not self._is_source(path):
                    continue
                seen += 1
                mods = self.modules(path)
                self.assertTrue(
                    mods is None or mods,  # None is FULL, the fail-safe
                    "%s maps to nothing: a change there would run no test" % path)
        self.assertGreater(seen, 20, "the walk found no source files")

    @staticmethod
    def _is_source(path):
        if path.startswith(("hooks/", "bin/", "hosts/", "skills/")):
            return path.endswith((".py", ".js", ".ts", ".sh", ".json"))
        return path in ("statusline.py",)

    def test_the_hand_known_edges_hold(self):
        mods = self.modules("hooks/tezgah_integrity.py")
        for expected in ("test_integrity.py", "test_gate.py",
                         "test_codex_hook.py", "test_cursor_hook.py",
                         "test_opencode_plugin.py"):
            self.assertIn(expected, mods)

    def test_a_paths_change_is_the_full_suite(self):
        # every module imports tezgah_paths, so a targeted set would lie
        self.assertIsNone(self.modules("hooks/tezgah_paths.py"))

    def test_the_shared_support_layer_is_the_full_suite(self):
        self.assertIsNone(self.modules("tests/support.py"))
        self.assertIsNone(self.modules("tests/_probe_gate.py"))

    def test_a_test_module_maps_to_itself(self):
        self.assertEqual(self.modules("tests/test_gate.py"), ["test_gate.py"])

    def test_a_helper_nothing_imports_is_the_full_suite(self):
        # a helper that changes changes what its importers assert; the import
        # forms and the doubt cases are pinned on a fixture tree below, since
        # naming a real helper here would itself be a mention without an import
        self.assertIsNone(self.modules("tests/no_such_helper.py"))

    def _fixture(self, files):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for name, body in files.items():
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write(body)
        old = impacted.TESTS
        impacted.TESTS = d
        self.addCleanup(setattr, impacted, "TESTS", old)
        return impacted._helper_importers("vec", {})

    def test_every_import_form_counts_and_any_doubt_is_the_full_suite(self):
        # consult review: a substring match missed `from vec import` and
        # `import a, vec`, so a change ran only one of two importers
        self.assertEqual(self._fixture({
            "vec.py": "", "test_a.py": "import vec\n",
            "test_b.py": "from vec import X\n", "test_c.py": "import os, vec\n",
            "test_d.py": "import vectors_other\n"}),
            ["test_a.py", "test_b.py", "test_c.py"])
        # named without an import line: the scan cannot tell, so FULL
        self.assertIsNone(self._fixture({
            "vec.py": "", "test_a.py": "import vec\n",
            "test_b.py": "spec = __import__('vec')\n"}))
        # a transitive importer: another helper imports it, so FULL
        self.assertIsNone(self._fixture({
            "vec.py": "", "other.py": "import vec\n",
            "test_a.py": "import other\n"}))

    def test_a_docs_change_maps_to_the_docs_modules_only(self):
        # real file names: `-p docs` matched no file, so a docs-only run
        # discovered 0 tests and passed (exit 0 on 3.10 and 3.11)
        self.assertEqual(self.modules("docs/gate.md"),
                         ["test_docs.py", "test_docs_router.py", "test_clarity.py"])
        for name in impacted.DOC_TARGETS:
            self.assertTrue(os.path.exists(os.path.join(impacted.TESTS, name)), name)

    def test_a_root_level_page_maps_to_the_docs_modules(self):
        # measured 2026-10-01: `--run RELEASING.md` fell through to the FULL
        # suite because only CHANGELOG.md and MANIFEST were handled at the root
        for page in ("RELEASING.md", "CONTRIBUTING.md", "AGENTS.md", "README.md"):
            mods = self.modules(page)
            self.assertIn("test_docs.py", mods or [], page)
            self.assertNotEqual(mods, None, page)

    def test_an_unknown_path_is_the_full_suite(self):
        self.assertIsNone(self.modules("some/other/file.txt"))

    def test_a_new_hooks_module_falls_back_to_the_full_suite(self):
        # the guard the plan asked for: a hooks module added without a mapping
        # or a test module of its own must not map to an empty set
        self.assertIsNone(self.modules("hooks/tezgah_brand_new_thing.py"))

    def test_the_setup_entry_point_pulls_the_install_modules(self):
        mods = self.modules("bin/tezgah-setup")
        for expected in ("test_setup.py", "test_install_tree.py",
                         "test_mcp_features.py", "test_tezgah_mcp_wiring.py"):
            self.assertIn(expected, mods)

    def test_resolve_unions_the_paths_and_reports_unmapped(self):
        mods, unmapped = impacted.resolve(
            ["hooks/tezgah_integrity.py", "docs/gate.md"], {})
        self.assertIn("test_integrity.py", mods)
        self.assertIn("test_docs.py", mods)
        self.assertEqual(unmapped, [])
        mods, unmapped = impacted.resolve(["hooks/tezgah_paths.py"], {})
        self.assertEqual(unmapped, ["hooks/tezgah_paths.py"])


class NothingRanIsNotAPass(unittest.TestCase):
    """A run that executes no test exits 5 (unittest's own "no tests ran"), never
    0: the integrity ledger records an exit-0 check as `verify_ok`."""

    def main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = impacted.main(argv)
        return rc, out.getvalue()

    def test_zero_modules_exits_5(self):
        d = tempfile.mkdtemp()  # a tests/ tree with no module at all
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.object(impacted, "TESTS", d):
            rc, out = self.main(["--run", "docs/gate.md"])
        self.assertEqual(rc, 5, out)
        self.assertIn("nothing to run", out)

    def test_an_empty_ref_diff_exits_5(self):
        # it used to re-enter `--run` with no path: argparse exit 2
        with mock.patch.object(impacted, "changed_paths", return_value=[]):
            rc, out = self.main(["--ref", "main"])
        self.assertEqual(rc, 5, out)

    def test_all_with_no_module_exits_5(self):
        with mock.patch.object(impacted, "test_modules", return_value=[]):
            rc, out = self.main(["--all"])
        self.assertEqual(rc, 5, out)

    def test_an_unknown_ref_is_an_error_not_an_empty_diff(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = impacted.main(["--ref", "no-such-ref-r02"])
        self.assertEqual(rc, 2, err.getvalue())
        self.assertIn("no-such-ref-r02", err.getvalue())

    def test_a_failed_module_prints_its_log_section(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, "test_boom.py"), "w", encoding="utf-8") as fh:
            fh.write("import unittest\n\nclass T(unittest.TestCase):\n"
                     "    def test_x(self):\n        self.fail('boom-marker')\n")
        with mock.patch.object(impacted, "TESTS", d):
            rc, out = self.main(["--run", os.path.join(d, "test_boom.py")])
        self.assertEqual(rc, 1, out)
        self.assertIn("===== test_boom.py", out)
        self.assertIn("boom-marker", out)


if __name__ == "__main__":
    unittest.main()
