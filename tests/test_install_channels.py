"""bin/tezgah-setup on the Windows release channel, proven on a POSIX host.

`packaging/install.ps1` makes `<prefix>/current` a directory junction, or a copy
of the version tree when the junction is refused, and starts the installer from
it. `os.path.islink()` is False for a junction, so the installer never knew
which prefix it ran from; the default prefix ignored LOCALAPPDATA; `--upgrade`
needed `bash`; and the uninstall judged `current` by `islink`.

A junction cannot be made on macOS, so it is a symlink fixture (so realpath
resolves through it, as Windows realpath does through a junction) with
`os.path.islink` answering False for it and the junction probe answering True.
`os.name` is swapped for the Windows default prefix and the PowerShell upgrade.
What only the windows-latest CI leg proves: a real junction, a real copy
fallback, and the install-update-uninstall cycle (.github/workflows/ci.yml).
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

from test_setup import SetupBase, setup_module

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_paths as tp  # noqa: E402

_MISSING = object()


class Base(SetupBase):
    def setUp(self):
        super().setUp()
        self.mod = setup_module()

    def swap(self, obj, name, value):
        """Set (or delete, for _MISSING) an attribute for one test."""
        old = getattr(obj, name, _MISSING)
        self.addCleanup(lambda: setattr(obj, name, old) if old is not _MISSING
                        else delattr(obj, name) if hasattr(obj, name) else None)
        if value is _MISSING:
            if hasattr(obj, name):
                delattr(obj, name)
        else:
            setattr(obj, name, value)

    def release(self, name="released", version="1.2.3"):
        """<prefix>/<version>/bin/tezgah-setup; returns (prefix, version dir)."""
        prefix = self.path(name)
        tree = os.path.join(prefix, version)
        os.makedirs(os.path.join(tree, "bin"))
        with open(os.path.join(tree, "bin", "tezgah-setup"), "w") as fh:
            fh.write("# a released installer\n")
        return prefix, tree

    def junction(self, prefix, tree, with_isjunction):
        """`current` as a junction: a symlink that `islink` does not see.

        `with_isjunction` gives os.path the 3.12+ probe; without it the
        fallback reads `st_reparse_tag` from lstat, which a POSIX lstat lacks,
        so it is faked for `current` alone."""
        current = os.path.join(prefix, "current")
        os.symlink(tree, current)
        real_islink, real_lstat = os.path.islink, os.lstat
        self.swap(os.path, "islink", lambda p: False if p == current else real_islink(p))
        if with_isjunction:
            self.swap(os.path, "isjunction", lambda p: p == current)
        else:
            self.swap(os.path, "isjunction", _MISSING)

            def lstat(p, *a, **kw):
                st = real_lstat(p, *a, **kw)
                if p != current:
                    return st
                # the real fields (realpath reads st_mode) plus the tag a
                # Windows lstat carries: IO_REPARSE_TAG_MOUNT_POINT, a junction
                fields = {k: getattr(st, k) for k in dir(st) if k.startswith("st_")}
                return SimpleNamespace(**dict(fields, st_reparse_tag=0xA0000003))
            self.swap(os, "lstat", lstat)
        return current


class RunningPrefix(Base):
    def test_a_junction_current_names_its_prefix(self):
        for probe in (True, False):
            with self.subTest(isjunction=probe):
                prefix, tree = self.release("junction-%s" % probe)
                self.junction(prefix, tree, probe)
                self.swap(self.mod, "HERE", tree)
                self.assertEqual(self.mod.running_prefix(), prefix)

    def test_a_copy_current_is_the_running_tree_itself(self):
        """The copy case, pinned: install.ps1 runs `$current\\bin\\tezgah-setup`
        from the copy, so HERE is `<prefix>/current` itself (no link to
        resolve), and a sibling version tree is what makes it a release."""
        prefix, tree = self.release()
        shutil.copytree(tree, os.path.join(prefix, "current"))
        self.swap(self.mod, "HERE", os.path.join(prefix, "current"))
        self.assertEqual(self.mod.running_prefix(), prefix)

    def test_a_tree_named_current_with_no_version_beside_it_is_not_a_release(self):
        lone = self.path("work", "current")
        os.makedirs(os.path.join(lone, "bin"))
        self.swap(self.mod, "HERE", lone)
        self.assertEqual(self.mod.running_prefix(), "")
        self.swap(self.mod, "HERE", REPO)
        self.assertEqual(self.mod.running_prefix(), "")


class DefaultPrefix(Base):
    def environ(self, **values):
        """os.environ holding only `values` of the three prefix variables."""
        patch = mock.patch.dict(os.environ, values)
        patch.start()
        self.addCleanup(patch.stop)
        for key in ("TEZGAH_PREFIX", "XDG_DATA_HOME", "LOCALAPPDATA"):
            if key not in values:
                os.environ.pop(key, None)

    def test_windows_defaults_under_localappdata(self):
        local = self.path("AppData", "Local")
        self.environ(LOCALAPPDATA=local)
        self.swap(os, "name", "nt")
        self.assertEqual(self.mod.default_prefix(), os.path.join(local, "tezgah"))

    def test_xdg_still_wins_and_posix_ignores_localappdata(self):
        self.environ(LOCALAPPDATA=self.path("AppData", "Local"),
                     XDG_DATA_HOME=self.path("xdg"))
        self.swap(os, "name", "nt")
        self.assertEqual(self.mod.default_prefix(), self.path("xdg", "tezgah"))
        self.environ(LOCALAPPDATA=self.path("AppData", "Local"))
        self.swap(os, "name", "posix")
        self.assertEqual(self.mod.default_prefix(),
                         os.path.join(self.mod.HOME, ".local", "share", "tezgah"))


class Upgrade(Base):
    def test_no_bash_is_a_refusal_naming_bash_not_a_traceback(self):
        """A real process with an empty PATH: the refusal comes before any
        fetch, so nothing reaches the network either way."""
        empty = self.path("empty-path")
        os.makedirs(empty)
        self.env["PATH"] = empty
        proc = self.setup("--upgrade", "9.9.9", "--prefix", self.path("p"))
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("no `%s` on PATH" % ("powershell" if os.name == "nt" else "bash"),
                      proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_windows_upgrades_through_install_ps1_and_re_arms_once(self):
        mod = self.mod
        prefix = self.path("prefix")
        launcher = os.path.join(prefix, "current", "bin", "tezgah-setup")
        os.makedirs(os.path.dirname(launcher))
        with open(launcher, "w") as fh:
            fh.write("# the flipped tree\n")
        self.write_json(self.path(".config", "tezgah", "config.json"),
                        {"hosts": ["omp"], "roots": []})
        self.swap(tp, "CONFIG", self.path(".config", "tezgah", "config.json"))
        self.swap(mod, "INSTALL_PREFIX", prefix)
        self.swap(os, "name", "nt")
        real_which = shutil.which
        self.swap(shutil, "which", lambda n, *a, **kw: (
            "C:/ps/powershell.exe" if n == "powershell" else real_which(n, *a, **kw)))
        calls = []
        self.swap(subprocess, "run", lambda argv, *a, **kw: (
            "--hook-entries" in argv or calls.append(list(argv)),
            SimpleNamespace(returncode=0, stdout="{}"))[1])
        self.assertEqual(mod.upgrade("1.2.3", False), 0)
        self.assertEqual(calls[0], [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            os.path.join(mod.HERE, "packaging", "install.ps1"),
            "-Prefix", prefix, "-NoInstall", "-Version", "1.2.3"])
        self.assertEqual(calls[1][1:3], [launcher, "--install"])
        self.assertEqual(len(calls), 2)


class RemoveTree(Base):
    def remove(self, prefix):
        self.swap(self.mod, "INSTALL_PREFIX", prefix)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.mod.remove_install_tree()
        return [ln.split("removed ", 1)[1] for ln in out.getvalue().splitlines()
                if "removed " in ln]

    def test_a_junction_current_is_unlinked_as_a_link_and_the_prefix_goes(self):
        """The junction goes first, as the link it is; judged by `islink` it
        was a version tree to rmtree."""
        prefix, tree = self.release()
        current = self.junction(prefix, tree, False)
        self.assertEqual(self.remove(prefix), [current, tree, prefix])
        self.assertFalse(os.path.lexists(prefix))

    def test_a_copy_current_goes_with_the_versions(self):
        prefix, tree = self.release()
        shutil.copytree(tree, os.path.join(prefix, "current"))
        self.remove(prefix)
        self.assertFalse(os.path.lexists(prefix))


class ResolvedPrefix(Base):
    def test_the_running_copy_names_the_prefix_the_uninstall_removes(self):
        """main() resolves INSTALL_PREFIX before any branch, and the uninstall's
        removal and its `install tree gone` claim read it: a copy-style tree
        that named no prefix sent both to the POSIX default, so the claim held
        over a directory that never existed."""
        prefix, tree = self.release()
        copy = os.path.join(prefix, "current")
        shutil.copytree(tree, copy)
        self.swap(self.mod, "HERE", copy)
        self.swap(self.mod, "PREFIX_PINNED", False)
        self.swap(self.mod, "INSTALL_PREFIX", self.path("posix-default"))
        self.swap(tp, "CONFIG", self.path(".config", "tezgah", "config.json"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main(["tezgah-setup", "--upgrade", "9.9.9",
                                            "--dry-run"]), 0)
        self.assertEqual(self.mod.INSTALL_PREFIX, prefix)
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.remove_install_tree()
        self.assertFalse(os.path.lexists(prefix))


if __name__ == "__main__":
    unittest.main()
