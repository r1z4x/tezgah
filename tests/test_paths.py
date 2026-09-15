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


class CacheDirFallback(TempHome):
    """cache_dir() must hand back a writable dir even when the global cache is
    denied (the sandboxed-host case, simulated by a file in the dir's place)."""

    def test_global_cache_when_writable(self):
        out, proc = run_json([support.PROBE_PATHS, "cache_dir"], env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, os.path.join(self.home, ".cache", "tezgah"))

    def test_fallback_when_global_cache_is_unwritable(self):
        path = os.path.join(self.home, ".cache", "tezgah")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        fallback = os.path.join(self.home, "fallback")
        env = self.env(extra={"TEZGAH_FALLBACK_CACHE": fallback})
        out, proc = run_json([support.PROBE_PATHS, "cache_dir"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, fallback)


class UserBinFallback(TempHome):
    """A tool installed to a per-user bin dir must read as present even when the
    calling shell's PATH never picked it up (the non-interactive case)."""

    def install(self, rel, name):
        p = os.path.join(self.home, *rel, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(p, 0o755)
        return p

    def empty_path(self):
        d = os.path.join(self.home, "emptybin")
        os.makedirs(d, exist_ok=True)
        return {"PATH": d}

    def test_which_user_finds_cargo_bin_off_path(self):
        want = self.install((".cargo", "bin"), "orx")
        out, proc = run_json([support.PROBE_PATHS, "which_user", "orx"],
                             env=self.env(extra=self.empty_path()))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, want)

    def test_orx_bin_uses_the_fallback(self):
        want = self.install((".local", "bin"), "orx")
        env = self.env(extra=self.empty_path())
        env.pop("TEZGAH_ORX_BIN", None)  # let orx_bin() do the lookup itself
        out, proc = run_json([support.PROBE_PATHS, "orx_bin"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, want)

    def test_missing_tool_is_none(self):
        out, _ = run_json([support.PROBE_PATHS, "which_user", "nope"],
                          env=self.env(extra=self.empty_path()))
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
