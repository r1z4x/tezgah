#!/usr/bin/env python3
"""The packaging scripts, held to what they promise.

A synthetic tree and its own MANIFEST are handed to the real `packaging/build.sh`
and `packaging/upgrade.sh`; nothing here reaches into either script's internals.
Four promises are checked: the artifact carries exactly the listing (plus the two
generated root files), a rebuild of an untouched tree is byte-identical (and
`--check` names a file that changed), a bad checksum or an unpack that fails
leaves the previous version current, and a good version flips `current` while the
replaced tree stays on disk for a rollback.

`sh` runs the scripts, so the check skips cleanly where there is none.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGING = os.path.join(os.path.dirname(HERE), "packaging")
SH = shutil.which("sh") or shutil.which("bash")
VERSION = "0.0.0-test"
# What the synthetic tree lists, and the file it does not list.
LISTED = ("a.txt", "bin/tezgah-setup", "sub/b.txt")
LEFTOVER = "leftover.txt"


def write(root, rel, data, mode=0o644):
    path = os.path.join(root, rel)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(data)
    os.chmod(path, mode)
    return path


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class Base(unittest.TestCase):
    """A tree with its own MANIFEST, the two scripts, and one unlisted file."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="tezgah-packaging.")
        cls.root = os.path.join(cls.tmp, "tree")
        os.makedirs(os.path.join(cls.root, "packaging"))
        for name in ("build.sh", "install.sh", "upgrade.sh"):
            shutil.copy(os.path.join(PACKAGING, name),
                        os.path.join(cls.root, "packaging", name))
        write(cls.root, "a.txt", "alpha\n")
        write(cls.root, "sub/b.txt", "beta\n")
        # The installer entry point install.sh reaches through <prefix>/current;
        # executable so the artifact has to keep the exec bit.
        write(cls.root, "bin/tezgah-setup", "#!/bin/sh\necho installed \"$@\"\n", 0o755)
        cls.manifest = "".join(name + "\n" for name in LISTED)
        write(cls.root, "MANIFEST", cls.manifest)
        write(cls.root, LEFTOVER, "not in MANIFEST, so not in the artifact\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_script(self, script, *args, env=None):
        full = dict(os.environ)
        # The scripts' documented interpreter override: the test's own python is
        # the one that must read the archive, not whatever PATH happens to hold.
        full["TEZGAH_PYTHON"] = sys.executable
        full.update(env or {})
        return subprocess.run([SH, os.path.join("packaging", script)] + list(args),
                              cwd=self.root, env=full,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True)

    def build(self, out, version=VERSION, *extra):
        return self.run_script("build.sh", "--version", version, "--out", out, *extra)

    def tarball(self, out, version=VERSION):
        return os.path.join(out, "tezgah-%s.tar.gz" % version)

    def names(self, path):
        with tarfile.open(path, "r:gz") as tar:
            return tar.getnames()


@unittest.skipUnless(SH, "sh is not on this host")
class Build(Base):
    def test_artifact_carries_the_listing_and_nothing_else(self):
        out = os.path.join(self.tmp, "build-listing")
        done = self.build(out)
        self.assertEqual(done.returncode, 0, done.stdout)
        tarball = self.tarball(out)
        # Sorted names, the listing verbatim, and the two generated root files.
        self.assertEqual(self.names(tarball),
                         sorted(list(LISTED) + ["MANIFEST", "VERSION"]))
        with tarfile.open(tarball, "r:gz") as tar:
            self.assertEqual(tar.extractfile("VERSION").read(), b"0.0.0-test\n")
            self.assertEqual(tar.extractfile("MANIFEST").read(), self.manifest.encode())
            self.assertEqual(tar.extractfile("a.txt").read(), b"alpha\n")
            # Header normalisation is what makes a rebuild byte-identical, so it
            # is part of the contract and not an implementation detail.
            for info in tar.getmembers():
                self.assertEqual((info.mtime, info.uid, info.gid, info.uname), (0, 0, 0, ""))
            self.assertEqual(tar.getmember("bin/tezgah-setup").mode & 0o111, 0o111)
        # The sidecar records the digest upgrade.sh verifies.
        with open(tarball + ".sha256") as fh:
            self.assertEqual(fh.read().split()[0], digest(tarball))

    def test_list_names_what_it_left_out(self):
        out = os.path.join(self.tmp, "build-list")
        done = self.build(out, VERSION, "--list")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("5 files in the artifact (3 listed, +MANIFEST +VERSION)", done.stdout)
        self.assertIn(LEFTOVER, done.stdout)
        self.assertFalse(os.path.exists(self.tarball(out)), "--list must not build")

    def test_rebuild_is_byte_identical_and_check_names_a_change(self):
        first = os.path.join(self.tmp, "build-first")
        done = self.build(first)
        self.assertEqual(done.returncode, 0, done.stdout)
        before = digest(self.tarball(first))
        self.assertIn(before, done.stdout)

        # An untouched tree: a rebuild into another directory is the same bytes.
        second = os.path.join(self.tmp, "build-second")
        self.assertEqual(self.build(second).returncode, 0)
        self.assertEqual(digest(self.tarball(second)), before)
        # ... even after the checkout's clock moves: mtime is not in the archive.
        os.utime(os.path.join(self.root, "a.txt"), (1, 1))
        third = os.path.join(self.tmp, "build-third")
        self.assertEqual(self.build(third).returncode, 0)
        self.assertEqual(digest(self.tarball(third)), before)

        # --check rebuilds the same tree and agrees with the artifact.
        checked = self.build(first, VERSION, "--check")
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(before, checked.stdout)

        # A changed source file: --check fails and names the file.
        write(self.root, "a.txt", "alpha changed\n")
        try:
            caught = self.build(first, VERSION, "--check")
            self.assertNotEqual(caught.returncode, 0)
            self.assertIn("a.txt", caught.stdout)
        finally:
            write(self.root, "a.txt", "alpha\n")


@unittest.skipUnless(SH and shutil.which("curl") and shutil.which("tar"),
                     "the upgrade check needs sh, curl and tar")
class Upgrade(Base):
    def dist(self, version, mutate=None):
        """A dist directory holding one version's artifact and its sidecar."""
        out = os.path.join(self.tmp, "dist")
        done = self.build(out, version)
        self.assertEqual(done.returncode, 0, done.stdout)
        if mutate:
            mutate(out, "tezgah-%s.tar.gz" % version)
        return out

    def upgrade(self, dist, prefix, version):
        return self.run_script("upgrade.sh", "--version", version, "--prefix", prefix,
                               env={"TEZGAH_DIST": dist})

    def current(self, prefix, version):
        """Is <prefix>/current the given version?

        realpath on both sides: the temp dir itself may sit behind a symlink
        (macOS /var -> /private/var), and the question is which version the link
        names, not how the path is spelled."""
        return (os.path.realpath(os.path.join(prefix, "current"))
                == os.path.realpath(os.path.join(prefix, version)))

    def test_flip_keeps_the_old_current_when_the_new_version_fails(self):
        prefix = os.path.join(self.tmp, "prefix-bad")
        dist = self.dist("0.0.1")
        done = self.upgrade(dist, prefix, "0.0.1")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(self.current(prefix, "0.0.1"))

        # A tarball that passes verification and then fails to unpack: the flip
        # must not have happened, and no half tree may be left beside it.
        garbage = b"not a tarball\n"
        with open(os.path.join(dist, "tezgah-0.0.2.tar.gz"), "wb") as fh:
            fh.write(garbage)
        with open(os.path.join(dist, "tezgah-0.0.2.tar.gz.sha256"), "w") as fh:
            fh.write("%s  tezgah-0.0.2.tar.gz\n" % hashlib.sha256(garbage).hexdigest())
        broke = self.upgrade(dist, prefix, "0.0.2")
        self.assertNotEqual(broke.returncode, 0)
        self.assertIn("cannot unpack", broke.stdout)
        self.assertTrue(self.current(prefix, "0.0.1"))
        self.assertFalse(os.path.exists(os.path.join(prefix, "0.0.2")))
        self.assertEqual([n for n in os.listdir(prefix) if n.startswith(".0.0.2")], [])

        # A checksum that disagrees: caught before anything is unpacked.
        with open(os.path.join(dist, "tezgah-0.0.2.tar.gz.sha256"), "w") as fh:
            fh.write("%s  tezgah-0.0.2.tar.gz\n" % ("0" * 64))
        mismatched = self.upgrade(dist, prefix, "0.0.2")
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("checksum mismatch", mismatched.stdout)
        self.assertTrue(self.current(prefix, "0.0.1"))
        self.assertFalse(os.path.exists(os.path.join(prefix, "0.0.2")))

    def test_good_upgrade_flips_current_and_keeps_the_old_tree(self):
        prefix = os.path.join(self.tmp, "prefix-good")
        first = self.dist("0.1.0")
        self.assertEqual(self.upgrade(first, prefix, "0.1.0").returncode, 0)
        second = self.dist("0.1.1")
        done = self.upgrade(second, prefix, "0.1.1")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(self.current(prefix, "0.1.1"))
        self.assertIn("was %s" % os.path.join(prefix, "0.1.0"), done.stdout)
        # What the rollback needs: the replaced tree is still there, and the
        # installed one is the listing the artifact carried.
        self.assertTrue(os.path.isfile(os.path.join(prefix, "0.1.0", "bin", "tezgah-setup")))
        self.assertTrue(os.path.isfile(os.path.join(prefix, "0.1.1", "MANIFEST")))
        # Re-running the same version is idempotent, not an error.
        again = self.upgrade(second, prefix, "0.1.1")
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertTrue(self.current(prefix, "0.1.1"))

    def test_install_sh_runs_the_installer_from_the_flipped_tree(self):
        """install.sh: upgrade.sh, then the installer the flip made current."""
        prefix = os.path.join(self.tmp, "prefix-install")
        dist = self.dist("0.2.0")
        done = self.run_script("install.sh", "--version", "0.2.0", "--prefix", prefix,
                               env={"TEZGAH_DIST": dist})
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(self.current(prefix, "0.2.0"))
        self.assertIn("installed --install", done.stdout)


if __name__ == "__main__":
    unittest.main()
