"""The release tree: the file listing a plugin copy is made from, without git.

`sync()` and `plugin_copy_current()` list the tree through `git ls-files` while
`.git` exists, and through the tracked `MANIFEST` when it does not - an unpacked
release tarball. The manifest is only safe because it cannot drift: one test
holds it to the git listing, and the rest prove the fallback reads it, refuses an
empty one, and recognises a copy with no `.git` anywhere.

`plugin_files()` is the one function both consumers call, so these tests exercise
it through the installer module the way `--sync` does, with `HERE` repointed at a
throwaway tree rather than by re-implementing the filter here.
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")
HAVE_NODE = shutil.which("node")


def setup_module():
    """bin/tezgah-setup as a module - one instance per test run, under a name of
    its own so mutating HERE here cannot reach another module's copy."""
    if "tezgah_setup_packaging" in sys.modules:
        return sys.modules["tezgah_setup_packaging"]
    loader = importlib.machinery.SourceFileLoader("tezgah_setup_packaging", SETUP)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("tezgah_setup_packaging", loader))
    sys.modules["tezgah_setup_packaging"] = module
    loader.exec_module(module)
    return module


class Tree(unittest.TestCase):
    """A throwaway tree with a manifest, and no `.git` above it (the temp dir is
    outside this repository, so `git ls-files` there fails and the fallback is
    the path under test)."""

    def setUp(self):
        self.mod = setup_module()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        # the module is shared: HERE goes back even when a test fails
        self.addCleanup(setattr, self.mod, "HERE", self.mod.HERE)

    def write(self, root, rel, text="x\n"):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def manifest(self, *rels):
        self.write(self.root, self.mod.MANIFEST,
                   "".join(r + "\n" for r in rels))
        self.mod.HERE = self.root

    def read_manifest(self):
        with open(os.path.join(REPO, self.mod.MANIFEST)) as fh:
            return [line.strip() for line in fh if line.strip()]


class Manifest(Tree):
    def test_the_manifest_matches_the_git_listing(self):
        """The drift pin: adding a file without `--write-manifest` turns this red."""
        out = subprocess.run(
            ["git", "-C", REPO, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True)
        self.assertEqual(self.read_manifest(),
                         sorted(f for f in out.stdout.splitlines()
                                if self.mod.managed(f)))

    def test_write_manifest_regenerates_the_same_file(self):
        before = self.read_manifest()
        self.assertEqual(self.mod.write_manifest(), 0)
        self.assertEqual(self.read_manifest(), before)

    def test_a_tree_without_git_lists_its_files_from_the_manifest(self):
        """The fallback, and the three filters it shares with the git path: a
        plan, a bytecode cache and the manifest itself are never copied."""
        self.manifest("bin/tezgah-setup", "hooks/tezgah_paths.py",
                      ".tezgah/plans/open/001-x.md", "hooks/__pycache__/x.pyc")
        self.assertEqual(self.mod.plugin_files(),
                         ["bin/tezgah-setup", "hooks/tezgah_paths.py"])

    def test_a_tree_with_neither_git_nor_manifest_lists_nothing(self):
        """None, not the empty list: `sync` refuses on None and would empty a
        copy it cannot refill on []."""
        self.mod.HERE = self.root
        self.assertIsNone(self.mod.plugin_files())

    def test_an_empty_manifest_is_not_a_listing(self):
        self.manifest()
        self.assertIsNone(self.mod.plugin_files())

    def test_an_installed_tree_recognises_its_copy(self):
        """The end of the chain: with no `.git`, `plugin_copy_current` still
        answers, which is what makes `--report` readable on a release tree."""
        rels = ("bin/tezgah-setup", "hooks/tezgah_paths.py")
        self.manifest(*rels)
        for rel in rels:
            self.write(self.root, rel)
        with tempfile.TemporaryDirectory() as dst:
            copy = os.path.realpath(dst)
            for rel in rels:
                self.write(copy, rel)
            self.assertTrue(self.mod.plugin_copy_current(copy))
            # a file the copy holds and this tree does not is a ghost, and the
            # listing direction is the one a hash over existing paths cannot see
            self.write(copy, "hooks/removed.py")
            self.assertFalse(self.mod.plugin_copy_current(copy))

    def test_a_listed_file_the_tree_does_not_ship_does_not_stale_the_copy(self):
        """The npm package ships a subset of the MANIFEST (no `bin/*.py` twin
        symlinks, no `.github/`), so a hash over every listed path was None on
        every npm install: the row never passed and each `--install` re-copied
        the plugin (audit M-11b, QA-2). The copy `sync` makes from such a tree
        holds the shipped files only, and that copy is current."""
        shipped = ("bin/tezgah-setup", "hooks/tezgah_paths.py")
        self.manifest(*shipped + ("bin/tezgah-setup.py", ".github/x.yml"))
        for rel in shipped:
            self.write(self.root, rel)
        with tempfile.TemporaryDirectory() as dst:
            copy = os.path.realpath(dst)
            for rel in shipped:
                self.write(copy, rel)
            self.assertTrue(self.mod.plugin_copy_current(copy))
            # a shipped file the copy lacks still reads stale
            os.remove(os.path.join(copy, "hooks/tezgah_paths.py"))
            self.assertFalse(self.mod.plugin_copy_current(copy))

    def test_the_dev_mcp_config_is_not_shipped(self):
        """The checkout's `.mcp.json` names the maintainer's clone
        (`${HOME}/Projects/tezgah/bin/tezgah-mcp`); a copy gets its own render
        from `sync()`, so neither the npm package nor the release listing
        carries it (audit L-12, SEC-12)."""
        with open(os.path.join(REPO, "package.json")) as fh:
            files = json.load(fh)["files"]
        self.assertNotIn(".mcp.json", files)
        self.assertNotIn(".mcp.json", self.read_manifest())

    def test_the_npm_package_ships_what_tezgah_docs_reads(self):
        """`bin/tezgah-docs` reads `docs/index.json` and prints the pages it
        names; a files list without them left every npm install answering
        "nothing matches" (found by an internal research line)."""
        with open(os.path.join(REPO, "package.json")) as fh:
            files = json.load(fh)["files"]
        with open(os.path.join(REPO, "docs", "index.json"), encoding="utf-8") as fh:
            pages = [p["path"] for p in json.load(fh)["pages"]]
        for path in ["docs/index.json"] + pages:
            self.assertTrue(any(path == f or (f.endswith("/") and path.startswith(f))
                                for f in files), path)


@unittest.skipUnless(HAVE_NODE, "node missing")
class NpmShim(unittest.TestCase):
    """bin/tezgah.js, npm's entry point, hands the run to Python and must hand
    the outcome back: a Python killed by a signal reported exit code null, and
    `process.exit(null)` exits 0 (audit L-10, ENV-06)."""

    def test_a_signal_death_is_a_failure(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "fakepy")
            with open(fake, "w") as fh:
                # passes the shim's `-c ''` probe, then dies by SIGKILL
                fh.write('#!/bin/sh\n[ "$1" = "-c" ] && exit 0\nkill -9 $$\n')
            os.chmod(fake, 0o755)
            proc = subprocess.run(
                [HAVE_NODE, os.path.join(REPO, "bin", "tezgah.js"), "--version"],
                env=dict(os.environ, TEZGAH_PYTHON=fake),
                capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 128 + signal.SIGKILL, proc.stderr)

    def test_a_normal_exit_code_passes_through(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "fakepy")
            with open(fake, "w") as fh:
                fh.write('#!/bin/sh\n[ "$1" = "-c" ] && exit 0\nexit 3\n')
            os.chmod(fake, 0o755)
            proc = subprocess.run(
                [HAVE_NODE, os.path.join(REPO, "bin", "tezgah.js")],
                env=dict(os.environ, TEZGAH_PYTHON=fake),
                capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 3, proc.stderr)


class VersionSource(Tree):
    """The artifact's own version claim.

    `version()` is the only reader two surfaces share (the status line's head and
    `bin/tezgah-setup --version`), so the release artifact's `VERSION` file has to
    be one of its sources: without it an unpacked tree answers with the changelog
    head, which agrees on a normal release and is a lie the moment the artifact and
    the changelog are built apart (reproduced: a tarball built as 9.9.9 answered
    the changelog head)."""

    def setUp(self):
        super().setUp()
        sys.path.insert(0, os.path.join(REPO, "hooks"))
        import tezgah_context
        self.ctx = tezgah_context
        self.addCleanup(setattr, self.ctx, "PLUGIN_ROOT", self.ctx.PLUGIN_ROOT)

    def root_with(self, **files):
        for name, text in files.items():
            self.write(self.root, name, text)
        self.ctx.PLUGIN_ROOT = self.root

    def test_the_version_file_answers_without_a_manifest_or_a_changelog(self):
        self.root_with(VERSION="9.9.9\n")
        self.assertEqual(self.ctx.version(), "9.9.9")

    def test_the_version_file_wins_over_the_changelog_head(self):
        self.root_with(VERSION="9.9.9\n",
                       **{"CHANGELOG.md": "# C\n\n## [1.2.3] - 2026-01-01\n"})
        self.assertEqual(self.ctx.version(), "9.9.9")

    def test_the_maintainers_manifest_still_wins_over_both(self):
        self.root_with(VERSION="9.9.9\n",
                       **{".claude-plugin/plugin.json": '{"version": "0.1.0"}'})
        self.assertEqual(self.ctx.version(), "0.1.0")

    def test_an_empty_version_file_falls_through_to_the_changelog(self):
        self.root_with(VERSION="\n",
                       **{"CHANGELOG.md": "# C\n\n## [1.2.3] - 2026-01-01\n"})
        self.assertEqual(self.ctx.version(), "1.2.3")



class PublishedVersion(unittest.TestCase):
    """npm publishes the version package.json names, and release.yml skips a
    version npm already has - so a package.json left behind the changelog made
    two releases reach neither npm nor a matching brew formula."""

    def test_package_json_names_the_newest_release_in_the_changelog(self):
        import json
        import re
        with open(os.path.join(REPO, "package.json"), encoding="utf-8") as fh:
            package = json.load(fh)["version"]
        with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as fh:
            newest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", fh.read(), re.M).group(1)
        self.assertEqual(package, newest)


class ReleaseWaitsForCi(unittest.TestCase):
    """v0.1.2 reached npm and brew while its own CI run went red (release run
    37228979635 beside CI run 37228979769, same commit): publishing runs CI as a
    called workflow and both publish jobs wait for it."""

    @staticmethod
    def workflow(name):
        with open(os.path.join(REPO, ".github", "workflows", name),
                  encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def jobs(text):
        """{job: its block}, for the two-space-indented keys under `jobs:`."""
        import re
        body = text.split("\njobs:\n", 1)[1]
        parts = re.split(r"^  ([A-Za-z0-9_-]+):\n", body, flags=re.M)
        return dict(zip(parts[1::2], parts[2::2]))

    def test_ci_is_callable_and_both_publish_jobs_need_it(self):
        import re
        on = self.workflow("ci.yml").split("\njobs:\n", 1)[0]
        self.assertRegex(on, r"(?m)^  workflow_call:")
        jobs = self.jobs(self.workflow("release.yml"))
        self.assertRegex(jobs.get("ci", ""),
                         r"(?m)^    uses: \./\.github/workflows/ci\.yml\s*$")
        for job in ("npm-publish", "brew-formula"):
            self.assertTrue(re.search(r"(?m)^    needs: \[?ci\]?\s*$",
                                      jobs.get(job, "")), job)

    def test_no_ci_matrix_cancels_its_other_legs(self):
        # the default fail-fast cancelled 3.13 in run 37228979769
        for name, block in self.jobs(self.workflow("ci.yml")).items():
            if "matrix:" in block:
                self.assertIn("fail-fast: false", block, name)

    def test_no_ci_step_reads_the_gitignored_workspace(self):
        # `.tezgah/` is gitignored, so a CI step over it reads nothing and
        # cannot fail: it was presented as a check it never was
        self.assertNotIn("--acceptance --strict", self.workflow("ci.yml"))

    def test_the_weekly_bash5_fuzz_leg_fails_on_any_class(self):
        # plan 054: the fuzzer was only ever run under macOS bash 3.2
        block = self.jobs(self.workflow("neuter.yml")).get("fuzz-shell", "")
        self.assertRegex(block, r"(?m)^    runs-on: ubuntu-")
        self.assertIn('"${BASH_VERSINFO[0]}" -ge 5', block)
        for leg in ("", " --js"):
            self.assertIn("python3 tests/fuzz_shell.py --seed 1 --lines 20000"
                          "%s --strict\n" % leg, block)


class BrewTapWaitsForItsAsset(unittest.TestCase):
    """The tap formula names a release asset by URL, so pushing it before the
    asset is on the release left `brew install` a 404 - for good when the upload
    then failed. The asset goes up and is checked first; the tap is touched only
    after both files are there."""

    def block(self):
        jobs = ReleaseWaitsForCi.jobs(ReleaseWaitsForCi.workflow("release.yml"))
        return jobs.get("brew-formula", "")

    def test_the_asset_is_uploaded_and_verified_before_the_tap_is_cloned(self):
        block = self.block()
        upload = block.find("gh release upload")
        verified = [block.find('grep -qx "tezgah-${VERSION}.tar.gz%s"' % ext)
                    for ext in ("", ".sha256")]
        clone = block.find("git clone")
        for at in [upload] + verified + [clone, block.find("git push")]:
            self.assertNotEqual(at, -1, block)
        self.assertLess(upload, min(verified))
        self.assertLess(max(verified), clone)

    def test_the_formula_tells_a_0_1_2_keg_to_re_arm(self):
        # 0.1.2 armed hooks with Cellar/tezgah/0.1.2 paths; the upgrade's cleanup
        # deletes that keg, and only a re-arm from opt/tezgah rewrites them
        import re
        caveats = re.search(r"def caveats\n(.*?)\n\s*end\n", self.block(), re.S)
        self.assertIsNotNone(caveats, "the formula template has no caveats")
        self.assertIn("tezgah-setup --install", caveats.group(1))
        self.assertIn("tezgah update", caveats.group(1))


if __name__ == "__main__":
    unittest.main()
