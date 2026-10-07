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
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from test_setup import SetupBase, setup_module

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402
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
        """<prefix>/<version>/bin/tezgah-setup plus the VERSION file build.sh
        writes at a tree's root; returns (prefix, version dir)."""
        prefix = self.path(name)
        tree = os.path.join(prefix, version)
        os.makedirs(os.path.join(tree, "bin"))
        with open(os.path.join(tree, "bin", "tezgah-setup"), "w") as fh:
            fh.write("# a released installer\n")
        with open(os.path.join(tree, "VERSION"), "w") as fh:
            fh.write(version + "\n")
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

    def test_a_checkout_named_current_beside_a_tree_is_not_a_release(self):
        """A git checkout cloned as `current` next to another tezgah tree:
        taken for a copy, `--uninstall` rmtree'd the checkout and its sibling.
        A copy is a release only with no `.git`, a VERSION, and
        `<prefix>/<VERSION>/bin/tezgah-setup`."""
        prefix, tree = self.release("checkouts")
        checkout = os.path.join(prefix, "current")
        shutil.copytree(tree, checkout)
        os.makedirs(os.path.join(checkout, ".git"))
        self.swap(self.mod, "HERE", checkout)
        self.assertEqual(self.mod.running_prefix(), "")
        # the uninstall's prefix is what main() resolves; the default is kept
        default = self.path("posix-default")
        self.swap(self.mod, "PREFIX_PINNED", False)
        self.swap(self.mod, "INSTALL_PREFIX", default)
        self.swap(tp, "CONFIG", self.path(".config", "tezgah", "config.json"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.main(["tezgah-setup", "--upgrade", "9.9.9", "--dry-run"])
            self.mod.remove_install_tree()
        self.assertEqual(self.mod.INSTALL_PREFIX, default)
        self.assertTrue(os.path.isfile(os.path.join(checkout, "bin", "tezgah-setup")))
        self.assertTrue(os.path.isfile(os.path.join(tree, "bin", "tezgah-setup")))

    def test_a_copy_needs_its_own_version_beside_it(self):
        for case in ("no VERSION", "another version"):
            with self.subTest(case):
                prefix, tree = self.release(case.replace(" ", "-"))
                copy = os.path.join(prefix, "current")
                shutil.copytree(tree, copy)
                if case == "no VERSION":
                    os.remove(os.path.join(copy, "VERSION"))
                else:
                    with open(os.path.join(copy, "VERSION"), "w") as fh:
                        fh.write("9.9.9\n")
                self.swap(self.mod, "HERE", copy)
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


class BrewKeg(Base):
    """A Homebrew install runs from `<brew>/Cellar/tezgah/<version>/libexec`
    and `brew upgrade` deletes that keg by default, so every path an install
    renders names the stable `<brew>/opt/tezgah` link instead. The keg is the
    release tarball (the formula's `libexec.install Dir["*"]`) under a fake
    brew root in the temp HOME; no real Homebrew is touched."""

    HOSTS = "claude,codex,cursor,opencode,dsh,omp"

    @classmethod
    def setUpClass(cls):
        cls.dist = tempfile.mkdtemp(prefix="tezgah-brew-dist.")
        proc = subprocess.run(["sh", os.path.join("packaging", "build.sh"),
                               "--version", "9.9.9", "--out", cls.dist],
                              cwd=REPO, capture_output=True, text=True,
                              env=dict(os.environ, TEZGAH_PYTHON=sys.executable))
        if proc.returncode != 0:
            raise AssertionError(proc.stdout + proc.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dist, ignore_errors=True)

    def keg(self, version):
        """<brew>/Cellar/tezgah/<version>/libexec holding the tarball, and
        <brew>/opt/tezgah pointed at it the way `brew link` does."""
        libexec = self.path("brew", "Cellar", "tezgah", version, "libexec")
        os.makedirs(libexec)
        with tarfile.open(os.path.join(self.dist, "tezgah-9.9.9.tar.gz")) as tar:
            tar.extractall(libexec, **({"filter": "tar"}
                                       if hasattr(tarfile, "tar_filter") else {}))
        opt = self.path("brew", "opt", "tezgah")
        os.makedirs(os.path.dirname(opt), exist_ok=True)
        if os.path.lexists(opt):
            os.unlink(opt)
        os.symlink(os.path.join("..", "Cellar", "tezgah", version), opt)
        return libexec

    def install(self, tree):
        proc = subprocess.run(
            [sys.executable, os.path.join(tree, "bin", "tezgah-setup"), "--install",
             "--no-deps", "--hosts", self.HOSTS],
            capture_output=True, text=True, env=self.env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr)

    def rendered(self):
        """Every link target and every small text file the install wrote
        outside the fake brew root: (path, text) pairs."""
        brew = self.path("brew")
        out = []
        for root, dirs, files in os.walk(self.home):
            dirs[:] = [d for d in dirs if os.path.join(root, d) != brew]
            for name in dirs + files:
                p = os.path.join(root, name)
                if os.path.islink(p):
                    out.append((p, os.readlink(p)))
                elif name in files and os.path.getsize(p) < 1 << 20:
                    with open(p, "rb") as fh:
                        out.append((p, fh.read().decode("utf-8", "replace")))
        return out

    def test_no_versioned_keg_path_survives_and_an_upgrade_with_cleanup_keeps_the_hooks(self):
        self.install(self.keg("9.9.9"))
        opt_tree = self.path("brew", "opt", "tezgah", "libexec")
        texts = self.rendered()
        keg = os.path.join("Cellar", "tezgah", "9.9.9")
        self.assertEqual([p for p, t in texts if keg in t], [])
        # the omp bridge's @HOOK@ and dsh's configPath/pluginRoot name opt/
        joined = "\n".join(t for _, t in texts)
        self.assertIn(os.path.join(opt_tree, "hosts", "omp", "hook.py"), joined)
        self.assertRegex(joined, r"configPath: %s" % re.escape(opt_tree))
        self.assertRegex(joined, r"pluginRoot: %s" % re.escape(opt_tree))
        farm = self.path(".config", "tezgah", "bin")
        self.assertTrue(os.listdir(farm))
        for name in os.listdir(farm):
            self.assertTrue(os.readlink(os.path.join(farm, name)).startswith(opt_tree),
                            name)
        # `brew upgrade`: a new keg, opt/ flipped to it, the old keg cleaned up
        self.keg("9.9.10")
        shutil.rmtree(self.path("brew", "Cellar", "tezgah", "9.9.9"))
        links = [p for p, _ in texts if os.path.islink(p)]
        self.assertTrue(links)
        self.assertEqual([p for p in links if not os.path.exists(p)], [])
        # and the new keg still knows those links as its own
        proc = subprocess.run(
            [sys.executable, os.path.join(opt_tree, "bin", "tezgah-setup"),
             "--uninstall"],
            capture_output=True, text=True, env=self.env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr)
        self.assertEqual([p for p in links if os.path.lexists(p)], [])
        # the uninstall unwires; the keg is Homebrew's to remove
        self.assertTrue(os.path.isfile(self.path("brew", "Cellar", "tezgah", "9.9.10",
                                                 "libexec", "bin", "tezgah-setup")))

    def attest(self, tree, host, session):
        """The detail of the attest row `<tree>/bin/tezgah-context attest`
        writes, the call every host's session start makes."""
        work = self.path("work")
        os.makedirs(work, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, os.path.join(tree, "bin", "tezgah-context"), "attest",
             host, session, work],
            capture_output=True, text=True, env=dict(self.env, TEZGAH_ROOTS=work),
            timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        path = self.path(".cache", "tezgah", "evidence", ti._slug(session) + ".jsonl")
        with open(path) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        return [r["detail"] for r in rows if r["kind"] == "attest"][-1]

    def test_a_session_started_from_the_keg_reports_no_drift_before_or_after_an_upgrade(self):
        """A hook runs from its realpath, the keg, while the install rendered
        opt/: the attest root must read opt/ too, or every brew session starts
        drifted (the omp bridge differs, opencode's plugin link moved)."""
        hosts = self.HOSTS.split(",")
        self.install(self.keg("9.9.9"))
        for host in hosts:
            with self.subTest(host=host, keg="9.9.9"):
                self.assertEqual(self.attest(os.path.realpath(self.keg_tree("9.9.9")),
                                             host, "before-" + host), "ok")
        self.keg("9.9.10")
        shutil.rmtree(self.path("brew", "Cellar", "tezgah", "9.9.9"))
        for host in hosts:
            with self.subTest(host=host, keg="9.9.10"):
                self.assertEqual(self.attest(os.path.realpath(self.keg_tree("9.9.10")),
                                             host, "after-" + host), "ok")

    def keg_tree(self, version):
        return self.path("brew", "Cellar", "tezgah", version, "libexec")

    def test_the_running_tree_is_named_through_opt_only_when_opt_is_this_keg(self):
        libexec = os.path.realpath(self.keg("9.9.9"))
        opt_tree = os.path.join(os.path.realpath(self.path("brew", "opt")),
                                "tezgah", "libexec")
        self.assertEqual(tp.stable_root(libexec), opt_tree)
        # a path inside the keg moves with it
        self.assertEqual(tp.stable_root(os.path.join(libexec, "hosts", "omp", "hook.py")),
                         os.path.join(opt_tree, "hosts", "omp", "hook.py"))
        # opt/ flipped to another keg: this one is not what opt/ names
        other = os.path.realpath(self.keg("9.9.10"))
        self.assertEqual(tp.stable_root(libexec), libexec)
        self.assertEqual(tp.stable_root(other), opt_tree)
        # no opt/ link at all: the keg itself
        os.unlink(self.path("brew", "opt", "tezgah"))
        self.assertEqual(tp.stable_root(other), other)

    def test_a_checkout_still_resolves_to_the_checkout(self):
        real = os.path.realpath(REPO)
        self.assertEqual(tp.stable_root(real), real)
        self.assertEqual(self.mod.HERE, real)
        self.assertEqual(os.path.realpath(tp.PLUGIN_ROOT), real)


if __name__ == "__main__":
    unittest.main()
