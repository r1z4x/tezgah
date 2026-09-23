"""bin/tezgah-setup: the versioned install tree, the symlink-less install and
the Windows dependency report.

Item 1 of plan 011 is the prefix: a farm link is tezgah's when it resolves into
the install prefix as well as into the checkout, or a version flip orphans every
link the installer ever wrote. Item 2 is `--upgrade [VERSION]`: one script owns
the version move, and `--dry-run` prints and runs nothing. Item 3 is the install
where `os.symlink` is refused (an unprivileged Windows account), and item 4 is
the Windows dependency report.

Every test runs in a throwaway HOME through tests/test_setup.py's SetupBase, so
the real ~/.claude, ~/.config/tezgah and the codex account home are never
written; the env that base builds is explicit, which is what keeps a host home
from the developer's environment (CODEX_HOME, DSH_HOME) out of the run. No test
needs the network or a Windows host: the fetch step is never reached (--dry-run,
or an injected script) and the Windows branch is entered by `os.name`.

What this slice cannot prove here is a real Windows run: the fallback is
exercised through TEZGAH_NO_SYMLINK on macOS, and the channels the Windows
report names are the vendor channels read from the repository, not an install
that happened on Windows.
"""
import contextlib
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import unittest
from types import SimpleNamespace

from test_setup import SetupBase, setup_module

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_paths as tp  # noqa: E402


def swap(case, obj, name, value):
    """Set an attribute for one test; the previous value goes back after it."""
    case.addCleanup(setattr, obj, name, getattr(obj, name))
    setattr(obj, name, value)


class PrefixRecognition(SetupBase):
    """A link into the install prefix is tezgah's; the user's own file in the
    same place is not (bin/tezgah-setup is_tezgah_link)."""

    def prefix(self):
        return self.path(".local", "share", "tezgah")

    def version_file(self, name):
        """A file a version tree ships, the shape <prefix>/<version>/bin has."""
        path = os.path.join(self.prefix(), "1.2.3", "bin", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\ntrue\n")
        return path

    def farm(self, name):
        path = self.path(".config", "tezgah", "bin", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def test_a_farm_link_into_the_install_prefix_is_tezgah(self):
        # the link an install from a tarball writes: it resolves through
        # <prefix>/<version>, not through the checkout
        os.symlink(self.version_file("tezgah-status"),
                   self.farm("tezgah-status"))
        proc = self.setup("--uninstall", "--prefix", self.prefix(),
                          "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.lexists(self.farm("tezgah-status")), proc.stdout)

    def test_tezgah_prefix_env_names_the_same_root(self):
        # no --prefix flag: the env is the channel a host adapter reads, so a
        # link written under it has to be recognised there too
        self.env["TEZGAH_PREFIX"] = self.prefix()
        os.symlink(self.version_file("tezgah-status"),
                   self.farm("tezgah-status"))
        proc = self.setup("--uninstall", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.lexists(self.farm("tezgah-status")), proc.stdout)

    def test_a_users_own_file_and_a_foreign_link_are_kept(self):
        own = self.path("my-own-status")
        with open(own, "w") as fh:
            fh.write("#!/bin/sh\necho mine\n")
        os.symlink(own, self.farm("tezgah-status"))
        with open(self.farm("tezgah-pony"), "w") as fh:
            fh.write("mine\n")
        proc = self.setup("--uninstall", "--prefix", self.prefix(),
                          "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.islink(self.farm("tezgah-status")), proc.stdout)
        self.assertTrue(os.path.isfile(self.farm("tezgah-pony")), proc.stdout)
        self.assertIn("kept", proc.stdout)


class Upgrade(SetupBase):
    """--upgrade [VERSION]: one script owns the version move, --dry-run prints
    and runs nothing, and the re-arm runs the tree that was just flipped in."""

    def prefix(self):
        return self.path(".local", "share", "tezgah")

    def configure(self, hosts, roots, prefix=None):
        cfg = {"hosts": hosts, "roots": roots}
        if prefix:
            cfg["prefix"] = prefix
        self.write_json(self.path(".config", "tezgah", "config.json"), cfg)

    def dist(self, version):
        """A release artifact as build.sh writes it, built here so the real
        packaging/upgrade.sh can verify and unpack one with no network:
        TEZGAH_DIST is its own offline channel (see its header).

        The tree is a fixture, not the product: it carries just `bin/tezgah-setup`
        linked back at this checkout, which is what the re-arm step runs."""
        staging = self.path("staging-" + version)
        launcher = os.path.join(staging, "bin", "tezgah-setup")
        os.makedirs(os.path.dirname(launcher), exist_ok=True)
        os.symlink(os.path.join(REPO, "bin", "tezgah-setup"), launcher)
        out = self.path("dist")
        os.makedirs(out, exist_ok=True)
        name = "tezgah-%s.tar.gz" % version
        subprocess.run(["tar", "czf", os.path.join(out, name), "-C", staging, "."],
                       check=True, capture_output=True)
        with open(os.path.join(out, name), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        with open(os.path.join(out, name + ".sha256"), "w") as fh:
            fh.write("%s  %s\n" % (digest, name))
        return out

    def swap(self, obj, name, value):
        swap(self, obj, name, value)

    def test_dry_run_prints_and_changes_nothing_on_disk(self):
        self.configure(["codex"], [self.path("Projects")])
        before = self.tree()
        proc = self.setup("--upgrade", "--dry-run", "--prefix", self.prefix())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.tree(), before)
        self.assertFalse(os.path.exists(self.prefix()),
                         "a dry run created the install prefix")
        self.assertIn("packaging/upgrade.sh", proc.stdout)
        self.assertIn("--prefix %s" % self.prefix(), proc.stdout)
        self.assertIn("re-arm: codex", proc.stdout)
        self.assertIn("nothing fetched", proc.stdout)

    def test_dry_run_takes_a_pinned_version(self):
        self.configure(["codex", "omp"], [self.path("Projects")])
        before = self.tree()
        proc = self.setup("--upgrade", "9.9.9", "--dry-run",
                          "--prefix", self.prefix())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.tree(), before)
        self.assertIn("--version 9.9.9", proc.stdout)
        self.assertIn("re-arm: codex, omp", proc.stdout)

    def run_upgrade(self, version="1.2.3", with_launcher=True):
        """upgrade() with the release script and the process runner swapped out.

        Nothing outside the temp HOME can be written: the two process calls are
        recorded instead of run, and the config the function reads is the temp
        one. Returns (returncode, [[argv, ...]], launcher)."""
        mod = setup_module()
        prefix = self.prefix()
        launcher = os.path.join(prefix, "current", "bin", "tezgah-setup")
        if with_launcher:
            os.makedirs(os.path.dirname(launcher), exist_ok=True)
            with open(launcher, "w") as fh:
                fh.write("# placeholder for the tree the flip puts at `current`\n")
        script = self.path("fake-upgrade.sh")
        with open(script, "w") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        self.configure(["codex", "omp"], [self.path("Projects")])
        calls = []
        self.swap(tp, "CONFIG", self.path(".config", "tezgah", "config.json"))
        self.swap(mod, "UPGRADE", script)
        self.swap(mod, "INSTALL_PREFIX", prefix)
        self.swap(subprocess, "run", lambda argv, *a, **kw: (
            calls.append(list(argv)), SimpleNamespace(returncode=0))[1])
        return mod.upgrade(version, False), calls, launcher

    def test_a_version_flag_refuses_instead_of_printing_and_stopping(self):
        """`--version` is argparse's print-and-exit action, so
        `--upgrade --version V` printed the current version, exited 0 and moved
        nothing - a command that read as done. It has to refuse by name, and the
        documented positional form has to keep working."""
        self.configure(["codex"], [self.path("Projects")])
        before = self.tree()
        for argv in (["--upgrade", "--version", "9.9.9"], ["--upgrade", "--version"]):
            proc = self.setup(*argv)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertEqual(self.tree(), before)
            self.assertIn("--upgrade VERSION", proc.stderr)
            self.assertEqual(proc.stdout.strip(), "", "it printed instead of refusing")
        ok = self.setup("--upgrade", "9.9.9", "--dry-run")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("--version 9.9.9", ok.stdout)

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash")
                         and shutil.which("tar") and shutil.which("curl"),
                         "packaging/upgrade.sh needs a POSIX shell, tar and curl")
    def test_upgrade_uses_the_prefix_the_install_recorded(self):
        """An install made with --prefix records it, so a later upgrade with no
        flag repeated moves that tree: without the record it aimed at
        ~/.local/share/tezgah, where nothing was installed, and exited 1."""
        prefix = self.path("custom-prefix")
        proc = self.setup("--install", "--hosts", "codex", "--prefix", prefix)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            self.read_json(self.path(".config", "tezgah", "config.json"))["prefix"],
            prefix)
        # the real packaging/upgrade.sh, fed a built artifact instead of the
        # network
        self.env["TEZGAH_DIST"] = self.dist("0.0.0-b")
        proc = self.setup("--upgrade", "0.0.0-b")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("verified tezgah-0.0.0-b.tar.gz", proc.stdout)
        self.assertEqual(os.path.realpath(os.path.join(prefix, "current")),
                         os.path.join(prefix, "0.0.0-b"))
        self.assertFalse(os.path.exists(self.path(".local", "share", "tezgah")),
                         "the upgrade aimed at the XDG default")
        # and the re-arm ran the tree the flip put at `current`
        self.assertIn("hooks.json wired", proc.stdout)

    def test_an_explicit_prefix_still_wins_over_the_recorded_one(self):
        recorded = self.path("recorded-prefix")
        self.configure(["codex"], [self.path("Projects")], recorded)
        flag = self.path("flagged-prefix")
        proc = self.setup("--upgrade", "9.9.9", "--dry-run", "--prefix", flag)
        self.assertIn("-> %s" % flag, proc.stdout)
        self.assertNotIn(recorded, proc.stdout)
        from_env = self.path("env-prefix")
        self.env["TEZGAH_PREFIX"] = from_env
        proc = self.setup("--upgrade", "9.9.9", "--dry-run")
        self.assertIn("-> %s" % from_env, proc.stdout)
        self.assertNotIn(recorded, proc.stdout)
        # with nothing explicit, the recorded answer is the one used
        del self.env["TEZGAH_PREFIX"]
        proc = self.setup("--upgrade", "9.9.9", "--dry-run")
        self.assertIn("-> %s" % recorded, proc.stdout)
        self.assertNotIn(self.path(".local", "share", "tezgah"), proc.stdout)

    def test_a_released_tree_names_its_own_prefix(self):
        """`<prefix>/<version>` with `<prefix>/current` pointing at the running
        tree is the released layout, and `packaging/install.sh` starts this
        installer from that tree with no --prefix to pass on - so the tree itself
        is the only thing that can name the prefix a tarball install landed in."""
        mod = setup_module()
        prefix = self.path("released")
        version = os.path.join(prefix, "1.2.3")
        os.makedirs(os.path.join(version, "bin"), exist_ok=True)
        shutil.copy2(os.path.join(REPO, "bin", "tezgah-setup"),
                     os.path.join(version, "bin", "tezgah-setup"))
        os.symlink(version, os.path.join(prefix, "current"))
        swap(self, mod, "HERE", version)
        self.assertEqual(mod.running_prefix(), prefix)
        # a checkout is not a released layout: no `current` points back at it
        swap(self, mod, "HERE", REPO)
        self.assertEqual(mod.running_prefix(), "")

    def test_upgrade_runs_the_script_then_re_arms_the_new_tree(self):
        code, calls, launcher = self.run_upgrade()
        self.assertEqual(code, 0)
        self.assertEqual(calls[0], ["bash", self.path("fake-upgrade.sh"),
                                    "--prefix", self.prefix(),
                                    "--version", "1.2.3"])
        # the second call is the install, and it runs the tree the flip put at
        # `current`: this process started from the old one, whose farm links
        # would point back at it
        argv = calls[1]
        self.assertEqual(argv[1], launcher)
        self.assertIn("--install", argv)
        self.assertIn("--no-deps", argv)
        self.assertEqual(argv[argv.index("--hosts") + 1], "codex,omp")
        self.assertEqual(argv[argv.index("--roots") + 1], self.path("Projects"))
        self.assertEqual(argv[argv.index("--prefix") + 1], self.prefix())

    def test_upgrade_re_arms_from_this_tree_without_a_flipped_one(self):
        code, calls, _ = self.run_upgrade(with_launcher=False)
        self.assertEqual(code, 0)
        self.assertEqual(calls[1][1],
                         os.path.join(REPO, "bin", "tezgah-setup"))

    def test_upgrade_refuses_without_the_release_script(self):
        mod = setup_module()
        calls = []
        self.swap(mod, "INSTALL_PREFIX", self.prefix())
        self.swap(mod, "UPGRADE", self.path("no-such-upgrade.sh"))
        self.swap(subprocess, "run", lambda argv, *a, **kw: calls.append(argv))
        self.assertEqual(mod.upgrade("1.2.3", False), 1)
        self.assertEqual(calls, [], "nothing may run without the release script")


class SymlinklessInstall(SetupBase):
    """os.symlink refused (an unprivileged Windows account): the farm is
    materialised instead, the wiring still runs, and uninstall removes tezgah's
    own entries while leaving the user's."""

    def setUp(self):
        super().setUp()
        self.env["TEZGAH_NO_SYMLINK"] = "1"

    def farm(self, name):
        return self.path(".config", "tezgah", "bin", name)

    def test_install_runs_wired_and_uninstall_removes_it(self):
        proc = self.setup("--install", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.farm("tezgah-codex-hook")
        farm = os.path.dirname(entry)
        self.assertTrue(os.path.isfile(entry) and not os.path.islink(entry),
                        "the farm entry was not materialised: %s" % entry)
        self.assertFalse(any(os.path.islink(os.path.join(farm, n))
                             for n in os.listdir(farm)))
        # the report calls the materialised farm tezgah's, not the user's
        for label in ("hooks.json wired", "skills linked"):
            self.assertTrue(self.row(proc.stdout, label).strip().startswith("ok"),
                            "%s: %s" % (label, proc.stdout))
        # a second run must not read the entries it materialised as a directory
        # in the way, nor leave them stale
        again = self.setup("--install", "--hosts", "codex")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotIn("move it aside first", again.stdout)

        # the entry starts the hook, which is what a plain copy cannot do: a
        # copied farm entry dies on `import tezgah_context`, because its tree
        # root walks up from its own __file__
        cmd = self.read_json(self.path(".codex", "hooks.json"))["hooks"] \
            ["SessionStart"][0]["hooks"][0]["command"]
        run = subprocess.run(
            shlex.split(cmd),
            input=json.dumps({"hook_event_name": "SessionStart",
                              "cwd": self.home, "session_id": "s"}),
            capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("ModuleNotFoundError", run.stderr)

        own = self.farm("tezgah-user-tool")
        with open(own, "w") as fh:
            fh.write("mine\n")
        proc = self.setup("--uninstall", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(entry), proc.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.path(".codex", "skills"), "ponytail")), proc.stdout)
        self.assertTrue(os.path.isfile(own), "uninstall adopted the user's file")


class WindowsDependencyReport(SetupBase):
    """install_deps on Windows names the channel per missing tool and returns
    what is still missing, instead of returning early while the run reads as
    complete."""

    def enter_windows(self):
        """os.name is what the branch reads, so it is what the test sets."""
        mod = setup_module()
        real_deps = mod.DEPS
        # every probe answers "missing": which tools this machine happens to
        # have is not what the row is about
        self.swap(mod, "DEPS", tuple(dict(d, probe=lambda: False)
                                     for d in real_deps))
        old = os.name
        os.name = "nt"
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                still = mod.install_deps()
        finally:
            os.name = old
        return mod, still, out.getvalue()

    def swap(self, obj, name, value):
        swap(self, obj, name, value)

    def line(self, text, name):
        return next((ln for ln in text.splitlines() if " %s missing " % name in ln), "")

    def test_every_missing_tool_is_reported_with_its_channel(self):
        mod, still, text = self.enter_windows()
        self.assertEqual(sorted(still), sorted(d["name"] for d in mod.DEPS))
        self.assertIn("no Windows channel", self.line(text, "orx"))
        self.assertIn("no Windows channel", self.line(text, "cursor-agent"))
        self.assertIn("npm", self.line(text, "pnpm"))
        self.assertIn("npm", self.line(text, "dsh"))
        # the row reports; it does not run an installer, which the POSIX path
        # records in the install log before it does
        self.assertFalse(os.path.exists(
            self.path(".config", "tezgah", "install.log")))

    def test_every_optional_tool_has_a_windows_row(self):
        mod = setup_module()
        self.assertEqual(set(mod.WINDOWS_DEPS),
                         set(d["name"] for d in mod.DEPS))


class Interpreter(SetupBase):
    """Every hook command the installer writes names its interpreter through
    hooks/tezgah_paths.hook_command, so a machine without python3 on PATH still
    starts a hook."""

    def install(self):
        self.write_json(self.path(".claude", "settings.json"), {})
        proc = self.setup("--install", "--hosts", "claude,codex,cursor")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def commands(self):
        codex = self.read_json(self.path(".codex", "hooks.json"))
        cursor = self.read_json(self.path(".cursor", "hooks.json"))
        return [
            codex["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
            cursor["hooks"]["preToolUse"][0]["command"],
            self.read_json(self.path(".cursor", "cli-config.json"))["statusLine"]["command"],
            self.read_json(self.path(".claude", "settings.json"))["statusLine"]["command"],
        ]

    def test_every_written_command_names_the_resolved_interpreter(self):
        self.install()
        for cmd in self.commands():
            argv = shlex.split(cmd)
            # the interpreter this process runs is the resolver's second
            # channel, and the one the installer's own process proves works here
            self.assertEqual(argv[0], sys.executable, cmd)
            self.assertTrue(argv[1].startswith(self.home), cmd)
            self.assertTrue(os.path.exists(argv[1]), cmd)

    def test_the_pinned_interpreter_wins(self):
        # TEZGAH_PYTHON is the channel a user pins when their interpreter is
        # not on PATH, and the written command has to carry it
        pin = self.path("pinned-python")
        self.env["TEZGAH_PYTHON"] = pin
        self.install()
        for cmd in self.commands():
            self.assertTrue(cmd.startswith('"%s"' % pin), cmd)


class PluginCopyVersion(SetupBase):
    """sync() carries the release `VERSION` file into the plugin copy, and
    plugin_copy_current() excludes it from both directions, so a copy made from
    an artifact answers with the same version the tree does instead of falling
    back to the changelog head.

    The tree here is a generated fixture (two files, a listing, no git), not the
    product: these numbers say what the two rules do, not what this checkout
    ships."""

    def fixture(self, with_version=True):
        mod = setup_module()
        tree = self.path("tree")
        listed = ["bin/x", "hooks/tezgah_policy.py"]
        self.write_file(os.path.join(tree, "bin", "x"), "#!/usr/bin/env python3\n")
        self.write_file(os.path.join(tree, "hooks", "tezgah_policy.py"), "# policy\n")
        if with_version:
            self.write_file(os.path.join(tree, "VERSION"), "1.2.3\n")
            listed.append("VERSION")
        self.write_file(os.path.join(tree, "MANIFEST"), "".join(
            f + "\n" for f in listed))
        # the copy Claude runs: recognised by the fingerprint file sync writes
        copy = self.path("fake-home", ".claude", "plugins", "cache", "tezgah", "copy")
        self.write_file(os.path.join(copy, "bin", "x"), "#!/usr/bin/env python3\n")
        self.write_file(os.path.join(copy, "hooks", "tezgah_policy.py"), "# policy\n")
        swap(self, mod, "HERE", tree)
        swap(self, mod, "HOME", self.path("fake-home"))
        return mod, tree, copy

    def write_file(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def test_sync_carries_version_and_the_copy_stays_current(self):
        mod, tree, copy = self.fixture()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(mod.sync(), 0)
        self.assertIn(copy, out.getvalue())
        for rel in ("VERSION", "bin/x", "hooks/tezgah_policy.py"):
            self.assertTrue(os.path.isfile(os.path.join(copy, rel)), rel)
        self.assertEqual(self.read_text(os.path.join(copy, "VERSION")), "1.2.3\n")
        self.assertTrue(mod.plugin_copy_current(copy))
        # and a copy that carries VERSION while the tree does not is not stale
        os.remove(os.path.join(tree, "VERSION"))
        self.assertTrue(mod.plugin_copy_current(copy))


if __name__ == "__main__":
    unittest.main()
