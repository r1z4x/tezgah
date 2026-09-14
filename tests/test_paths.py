"""hooks/tezgah_paths.py: roots precedence, root_for boundaries, kill switches."""
import os
import unittest

import support
from support import TempHome, run_json


class RootsPrecedence(TempHome):
    def test_env_overrides_config_and_default(self):
        # distinct lengths => deterministic longest-first ordering
        a = os.path.join(self.home, "root-alpha-long")
        b = os.path.join(self.home, "b")
        os.makedirs(a)
        os.makedirs(b)
        self.config({"roots": [os.path.join(self.home, "from-config")]})
        out, proc = run_json([support.PROBE_PATHS, "roots"],
                             env=self.env(roots=[b, a]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, [os.path.realpath(a), os.path.realpath(b)])

    def test_config_used_when_no_env(self):
        cfg_root = os.path.join(self.home, "from-config")
        os.makedirs(cfg_root)
        self.config({"roots": [cfg_root]})
        env = self.env()
        env.pop("TEZGAH_ROOTS", None)
        out, proc = run_json([support.PROBE_PATHS, "roots"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, [os.path.realpath(cfg_root)])

    def test_default_when_nothing_configured(self):
        env = self.env()
        env.pop("TEZGAH_ROOTS", None)
        out, proc = run_json([support.PROBE_PATHS, "roots"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, [os.path.realpath(os.path.join(self.home, "Projects"))])


class RootForBoundaries(TempHome):
    def test_inside_and_exact_return_root(self):
        repo = self.make_repo("proj")
        sub = os.path.join(repo, "pkg", "deep")
        os.makedirs(sub)
        for path in (repo, sub):
            out, proc = run_json([support.PROBE_PATHS, "root_for", path],
                                 env=self.env())
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out, self.roots, "for %s" % path)

    def test_common_prefix_sibling_is_not_inside(self):
        self.make_repo("proj")
        sibling = os.path.join(self.home, "Projects2")
        os.makedirs(sibling)
        out, _ = run_json([support.PROBE_PATHS, "root_for", sibling],
                          env=self.env())
        self.assertIsNone(out)

    def test_outside_is_none(self):
        out, _ = run_json([support.PROBE_PATHS, "root_for", self.home],
                          env=self.env())
        self.assertIsNone(out)


class KillSwitches(TempHome):
    def test_off_by_default(self):
        out, proc = run_json([support.PROBE_PATHS, "off", "reminder-off"],
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(out)

    def test_canonical_config_dir(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "pretooluse-off"))
        out, _ = run_json([support.PROBE_PATHS, "off", "pretooluse-off"],
                          env=self.env())
        self.assertTrue(out)

    def test_legacy_claude_dir(self):
        self.touch(os.path.join(self.home, ".claude", "reminder-off"))
        out, _ = run_json([support.PROBE_PATHS, "off", "reminder-off"],
                          env=self.env())
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()
