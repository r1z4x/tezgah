#!/usr/bin/env python3
"""The impacted-test map cannot silently lose a file or a module.

`tests/impacted.py` decides what runs for a change, so a hole in it is a change
that ships untested. This pins the map's edges rather than its output: every
source file the repo ships maps to a non-empty set or to FULL, the hand-known
edges hold, and the fail-safe answers FULL. It runs no test module.
"""
import os
import unittest

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

    def test_a_docs_change_maps_to_the_docs_modules_only(self):
        self.assertEqual(self.modules("docs/gate.md"), ["docs", "docs_router"])

    def test_a_root_level_page_maps_to_the_docs_modules(self):
        # measured 2026-10-01: `--run RELEASING.md` fell through to the FULL
        # suite because only CHANGELOG.md and MANIFEST were handled at the root
        for page in ("RELEASING.md", "CONTRIBUTING.md", "AGENTS.md", "README.md"):
            mods = self.modules(page)
            self.assertIn("docs", mods or [], page)
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
        self.assertIn("docs", mods)
        self.assertEqual(unmapped, [])
        mods, unmapped = impacted.resolve(["hooks/tezgah_paths.py"], {})
        self.assertEqual(unmapped, ["hooks/tezgah_paths.py"])


if __name__ == "__main__":
    unittest.main()
