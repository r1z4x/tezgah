"""The update notice beside the logo, the daily check behind it, and
`tezgah update`.

The notice and the check run through the real CLIs (`bin/tezgah-status`,
`hooks/tezgah_update.py check`) in a throwaway HOME, with the releases endpoint
pointed at a `file://` fixture, so no test reaches the network. The channel
dispatch is driven in process with the command runner swapped for a recorder:
what is asserted is the argv each channel would run, never a real brew, npm or
git call.
"""
import json
import os
import re
import subprocess
import sys
import time
import unittest

import support

sys.path.insert(0, support.HOOKS)
import tezgah_context  # noqa: E402
import tezgah_update as tu  # noqa: E402

STATUS = os.path.join(support.REPO, "bin", "tezgah-status")
UPDATE = os.path.join(support.HOOKS, "tezgah_update.py")
SETUP = os.path.join(support.REPO, "bin", "tezgah-setup")
CURRENT = tezgah_context.version()


def bump(version, by=1):
    major, minor, patch = (int(p) for p in version.split("."))
    return "%d.%d.%d" % (major, minor, patch + by)


class Notice(support.TempHome):
    def setUp(self):
        super().setUp()
        self.cache = os.path.join(self.home, ".cache", "tezgah", "update.json")
        os.makedirs(os.path.dirname(self.cache))
        self.release = os.path.join(self.home, "release.json")
        self.serve(bump(CURRENT, 5))

    def serve(self, version):
        with open(self.release, "w", encoding="utf-8") as fh:
            json.dump({"tag_name": "v" + version}, fh)

    def envv(self, **extra):
        env = self.env(extra=dict({"TEZGAH_UPDATE_CHECK": "1",
                                   "TEZGAH_UPDATE_URL": "file://" + self.release},
                                  **extra))
        return env

    def write_cache(self, latest, checked=None):
        with open(self.cache, "w", encoding="utf-8") as fh:
            json.dump({"checked": int(time.time()) if checked is None else checked,
                       "latest": latest}, fh)

    def read_cache(self):
        with open(self.cache, encoding="utf-8") as fh:
            return json.load(fh)

    def status(self, *args, env=None):
        proc = subprocess.run([sys.executable, STATUS, self.home] + list(args),
                              capture_output=True, text=True, timeout=30,
                              env=env or self.envv())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def update_segment(self, env=None):
        segs = json.loads(self.status("--json", env=env))
        return [s for s in segs if s["key"] == "update"]

    def wait_for_latest(self, want):
        for _ in range(100):
            if os.path.exists(self.cache) and self.read_cache().get("latest") == want:
                return True
            time.sleep(0.05)
        return False

    def test_a_newer_cached_release_sits_beside_the_version(self):
        newer = bump(CURRENT)
        self.write_cache(newer)
        line = self.status().splitlines()[0]
        self.assertTrue(line.startswith("tezgah v%s \u2191%s" % (CURRENT, newer)), line)
        seg = self.update_segment()
        self.assertEqual(seg, [{"key": "update", "state": "ready", "glyph": "",
                                "text": "\u2191" + newer, "version": newer,
                                "group": -1}])

    def test_the_notice_survives_every_width_tier_beside_the_logo(self):
        # omp draws the widest tier that fits; the narrow ones drop the version
        # number, never the notice, because it is the logo's own group
        newer = bump(CURRENT)
        self.write_cache(newer)
        out = subprocess.run(
            [sys.executable, "-c",
             "import json, sys, tezgah_context as c\n"
             "print(json.dumps([l for l, _ in c.render_tiers("
             "c.health_segments(sys.argv[1]))]))", self.home],
            capture_output=True, text=True, timeout=30, env=self.envv())
        self.assertEqual(out.returncode, 0, out.stderr)
        for line in json.loads(out.stdout):
            self.assertIn("tezgah", line.split("\u2191")[0])
            self.assertIn("\u2191" + newer, line)

    def test_an_equal_or_older_release_says_nothing(self):
        for latest in (CURRENT, "0.0.1"):
            self.write_cache(latest)
            self.assertEqual(self.update_segment(), [], latest)
            self.assertNotIn("\u2191", self.status())

    def test_an_unreadable_cache_still_draws_the_line(self):
        # garbage is a stale cache: the line draws, then the check replaces it
        with open(self.cache, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertTrue(self.status().startswith("tezgah v%s" % CURRENT))
        self.assertTrue(self.wait_for_latest(bump(CURRENT, 5)))

    def test_a_machine_with_no_cache_dir_yet_still_checks(self):
        # a first run has no ~/.cache/tezgah: the stamp and the answer create it,
        # or the check never starts and the chip never appears
        os.rmdir(os.path.dirname(self.cache))
        self.status()
        self.assertTrue(self.wait_for_latest(bump(CURRENT, 5)))

    def test_a_stale_cache_starts_one_detached_check(self):
        self.write_cache(CURRENT, checked=0)
        line = self.status()
        # the redraw itself answers from what it had: no notice yet
        self.assertNotIn("\u2191", line)
        # the stamp is written before the check runs, so the next redraws start
        # nothing for a day
        self.assertGreater(self.read_cache()["checked"], time.time() - 60)
        self.assertTrue(self.wait_for_latest(bump(CURRENT, 5)))
        self.assertIn("\u2191" + bump(CURRENT, 5), self.status())

    def test_a_fresh_cache_starts_no_check(self):
        self.write_cache(CURRENT)
        before = self.read_cache()
        self.status()
        time.sleep(1)
        self.assertEqual(self.read_cache(), before)

    def test_the_switch_reads_nothing_and_starts_nothing(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "update-check-off"))
        self.write_cache(bump(CURRENT), checked=0)
        before = self.read_cache()
        self.assertNotIn("\u2191", self.status())
        time.sleep(1)
        self.assertEqual(self.read_cache(), before)

    def test_the_check_reads_the_tag_from_a_redirect(self):
        # the production answer: HEAD /releases/latest -> 302 to .../tag/vX.Y.Z,
        # served from a loopback server so the redirect branch itself runs
        import http.server
        import threading
        newer = bump(CURRENT, 7)

        class Releases(http.server.BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(302)
                self.send_header("Location", "https://github.com/r1z4x/tezgah"
                                 "/releases/tag/v" + newer)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Releases)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)  # cleanups run last-in, first-out
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%d/r1z4x/tezgah/releases/latest" % server.server_port
        proc = subprocess.run([sys.executable, UPDATE, "check"], capture_output=True,
                              text=True, timeout=30, env=self.envv(TEZGAH_UPDATE_URL=url))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_cache()["latest"], newer)

    def test_the_check_writes_the_release_it_read(self):
        proc = subprocess.run([sys.executable, UPDATE, "check"], capture_output=True,
                              text=True, timeout=30, env=self.envv())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_cache()["latest"], bump(CURRENT, 5))
        self.assertEqual(os.stat(self.cache).st_mode & 0o777, 0o600)

    def test_an_offline_check_exits_0_and_writes_nothing(self):
        env = self.envv(TEZGAH_UPDATE_URL="file://" + os.path.join(self.home, "nope"))
        proc = subprocess.run([sys.executable, UPDATE, "check"], capture_output=True,
                              text=True, timeout=30, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.cache))

    def test_a_tag_that_is_not_a_version_is_not_written(self):
        with open(self.release, "w", encoding="utf-8") as fh:
            json.dump({"tag_name": "nightly"}, fh)
        subprocess.run([sys.executable, UPDATE, "check"], timeout=30, env=self.envv())
        self.assertFalse(os.path.exists(self.cache))


class Tag(unittest.TestCase):
    """The real endpoint answers with a redirect, which no file:// fixture can
    serve, so its one parsing rule is pinned on the strings github.com sends."""

    def test_the_redirect_tail_is_the_tag(self):
        self.assertEqual(tu.tag_from(
            "https://github.com/r1z4x/tezgah/releases/tag/v0.1.2"), "v0.1.2")
        self.assertEqual(tu.tag_from("/r1z4x/tezgah/releases/tag/0.2.0/"), "0.2.0")

    def test_a_redirect_elsewhere_names_no_tag(self):
        # a repository with no release redirects to the releases list
        self.assertIsNone(tu.tag_from("https://github.com/r1z4x/tezgah/releases"))
        self.assertIsNone(tu.tag_from("https://github.com/login", b"<html>"))


class Reset(unittest.TestCase):
    """The 2026-10-04 re-root restarted the numbering at 0.1.x, so an install
    still on the retired 0.2.0-0.32.0 line compares higher than every public
    release; `newer()` has to offer the public one anyway."""

    def test_a_retired_install_is_offered_the_public_release(self):
        for mine in ("0.30.0", "0.29.2", "0.32.0", "0.17.0", "0.2.0", "v0.30.0"):
            self.assertEqual(tu.newer(mine, {"latest": "0.1.2"}), "0.1.2", mine)

    def test_an_older_public_release_is_still_not_offered(self):
        self.assertIsNone(tu.newer("0.1.2", {"latest": "0.1.1"}))
        self.assertIsNone(tu.newer("0.1.2", {"latest": "0.1.2"}))
        self.assertEqual(tu.newer("0.1.1", {"latest": "0.1.2"}), "0.1.2")

    def test_a_retired_latest_is_never_offered_over_the_public_line(self):
        # a cache written before the reset still naming the old line
        self.assertIsNone(tu.newer("0.1.2", {"latest": "0.30.0"}))
        self.assertIsNone(tu.newer("0.29.2", {"latest": "0.30.0"}))

    def test_malformed_versions_offer_nothing_and_never_raise(self):
        for mine, latest in (("0.30", "0.1.2"), ("", "0.1.2"), (None, "0.1.2"),
                             ("0.30.0-rc1", "0.1.2"), ("unknown", "0.1.2"),
                             ("0.30.0", "nightly"), ("0.30.0", None),
                             ("0.30.0", ["0.1.2"]), (30, "0.1.2")):
            self.assertIsNone(tu.newer(mine, {"latest": latest}), (mine, latest))
        self.assertFalse(tu.retired(None))
        self.assertFalse(tu.retired("garbage"))

    def test_the_notice_says_the_line_was_reset(self):
        saved = tu.read_cache, tu.due, tu.disabled
        tu.read_cache = lambda: {"latest": "0.1.2", "checked": 0}
        tu.due, tu.disabled = (lambda data: False), (lambda: False)
        try:
            [seg] = tu.notice_segments("0.30.0")
            self.assertEqual(seg["version"], "0.1.2")
            self.assertIn("reset", seg["text"])
            [seg] = tu.notice_segments("0.1.1")
            self.assertEqual(seg["text"], "\u21910.1.2")
        finally:
            tu.read_cache, tu.due, tu.disabled = saved

    def test_the_shipped_version_stays_outside_the_retired_line(self):
        # 0.1.x installs in the field keep RETIRED forever and never take a
        # release inside it, so the next public line skips past RETIRED[1]
        shipped = tezgah_context.version(manifest=False)
        self.assertIsNotNone(tu.parse(shipped), shipped)
        self.assertFalse(tu.retired(shipped),
                         "%s is inside the retired %s; the 0.1.x line goes "
                         "straight to 0.33.0 or later" % (shipped, tu.RETIRED))


class Channels(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)

    def tree(self, *parts, git=False):
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.join(path, ".git") if git else path)
        return path

    def test_each_tree_shape_names_its_channel(self):
        keg = self.tree("homebrew", "Cellar", "tezgah", "0.1.1", "libexec")
        pkg = self.tree("lib", "node_modules", "@r1z4x", "tezgah")
        clone = self.tree("src", "tezgah", git=True)
        self.assertEqual(tu.channel(keg), "brew")
        self.assertEqual(tu.channel(pkg), "npm")
        self.assertEqual(tu.channel(clone), "git")
        self.assertEqual(tu.channel(clone, prefix="/p"), "prefix")
        self.assertEqual(tu.channel(self.tree("loose")), "")
        # a keg of another formula is not tezgah's
        self.assertEqual(tu.channel(self.tree("hb", "Cellar", "other", "1", "libexec")), "")

    def test_brew_re_arms_from_the_stable_opt_link(self):
        keg = self.tree("homebrew", "Cellar", "tezgah", "0.1.1", "libexec")
        self.assertEqual(tu.launcher("brew", keg),
                         os.path.join(self.root, "homebrew", "opt", "tezgah",
                                      "libexec", "bin", "tezgah-setup"))
        self.assertEqual(tu.fetch_command("brew", keg),
                         ["brew", "upgrade", "r1z4x/tezgah/tezgah"])

    def test_a_tree_named_through_opt_is_still_brew_and_re_arms_from_opt(self):
        """bin/tezgah-setup names a keg through `opt/tezgah` (its HERE,
        `tezgah_paths.stable_root`), and `tezgah update` reads the channel and
        launcher off that HERE."""
        import tezgah_paths as tp
        keg = self.tree("homebrew", "Cellar", "tezgah", "0.1.1", "libexec")
        os.makedirs(os.path.join(self.root, "homebrew", "opt"))
        os.symlink(os.path.join("..", "Cellar", "tezgah", "0.1.1"),
                   os.path.join(self.root, "homebrew", "opt", "tezgah"))
        here = tp.stable_root(keg)
        opt = os.path.join(self.root, "homebrew", "opt", "tezgah", "libexec")
        self.assertEqual(here, opt)
        self.assertEqual(tu.channel(here), "brew")
        self.assertEqual(tu.launcher("brew", here),
                         os.path.join(opt, "bin", "tezgah-setup"))

    def run_update(self, here, codes=(0, 0), prefix="", dry_run=False,
                   npm_root="", which=lambda name: "/bin/" + name, fail=False,
                   old=None, new=None, tty=False, answer=None):
        """(exit code, the runs, the upgrades, stdout). `old` is the hook
        entries on disk before the fetch, `new` what the new tree's
        `--hook-entries` lists; `answer` is what a terminal user types."""
        import io
        calls, upgrades, asked = [], [], []
        self.printed_before = []
        out = io.StringIO()

        def run(argv, **kwargs):
            if argv[1:] == ["root", "-g"]:
                return subprocess.CompletedProcess(argv, 0, stdout=npm_root + "\n")
            if argv[-1] == "--hook-entries":
                return subprocess.CompletedProcess(
                    argv, 0, stdout=json.dumps(new if new is not None else {}))
            if fail:
                raise FileNotFoundError(argv[0])
            calls.append(argv)
            self.printed_before.append(out.getvalue())
            return subprocess.CompletedProcess(argv, codes[len(calls) - 1])

        def upgrade(version, dry):
            upgrades.append((version, dry))
            return 0

        def ask(prompt):
            asked.append(prompt)
            if answer is None:
                raise AssertionError("asked on a non-terminal: %r" % prompt)
            return answer

        from unittest import mock
        # the recorded install, not this machine's: hosts come from config.json
        with mock.patch.object(tu.tp, "config", lambda: {"hosts": ["codex"]}), \
                mock.patch.object(tu, "installed_entries",
                                  lambda hosts: old if old is not None else {}):
            saved, sys.stdout = sys.stdout, out
            try:
                code = tu.update(here, prefix, upgrade, dry_run, run=run, which=which,
                                 tty=tty, ask=ask)
            finally:
                sys.stdout = saved
        self.asked = asked
        return code, calls, upgrades, out.getvalue()

    # a release that adds one hook entry: Stop was armed, PreToolUse is new
    OLD = {"codex": {"Stop": '[{"hooks": ["stop"]}]'}}
    NEW = {"codex": {"Stop": '[{"hooks": ["stop"]}]',
                     "PreToolUse": '[{"hooks": ["gate"]}]'}}

    def test_an_added_hook_entry_is_printed_before_the_re_arm_runs(self):
        clone = self.tree("src", "tezgah", git=True)
        code, calls, _, out = self.run_update(clone, old=self.OLD, new=self.NEW)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 2)
        change = "codex: re-arming adds the PreToolUse entry"
        self.assertIn(change, out)
        self.assertNotIn(change, self.printed_before[0])   # not before the fetch
        self.assertIn(change, self.printed_before[1])      # before the re-arm
        self.assertEqual(self.asked, [])                   # a pipe never waits

    def test_a_terminal_waits_for_yes_and_a_no_re_arms_nothing(self):
        clone = self.tree("src", "tezgah", git=True)
        code, calls, _, out = self.run_update(clone, old=self.OLD, new=self.NEW,
                                              tty=True, answer="n")
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 1, "only the fetch ran")
        self.assertEqual(len(self.asked), 1)
        self.assertIn("not re-armed", out)
        # what a no leaves is said for the channel: a checkout is pulled in place
        self.assertIn(tu.NOT_REARMED["git"], out)
        code, calls, _, _ = self.run_update(clone, old=self.OLD, new=self.NEW,
                                            tty=True, answer="y")
        self.assertEqual((code, len(calls)), (0, 2))

    def test_unchanged_entries_say_so_and_never_ask(self):
        clone = self.tree("src", "tezgah", git=True)
        code, calls, _, out = self.run_update(clone, old=self.OLD, new=self.OLD,
                                              tty=True)
        self.assertEqual((code, len(calls)), (0, 2))
        self.assertIn("hook entries: unchanged", out)

    def test_a_changed_entry_prints_its_diff(self):
        lines = tu.hook_change({"codex": {"Stop": "a\nb"}},
                               {"codex": {"Stop": "a\nc"}})
        self.assertEqual(lines[0], "  codex: re-arming changes the Stop entry")
        self.assertIn("    -b", lines)
        self.assertIn("    +c", lines)

    def test_two_identical_releases_at_their_own_paths_are_unchanged(self):
        # every release lives at its own versioned path; the omp bridge and the
        # opencode link name it, so a byte compare showed a change between two
        # identical releases and a terminal's Enter (= no) left nothing re-armed
        def entries(root):
            return {"omp": {"bridge": 'spawn("%s/hosts/omp/hook.py")' % root},
                    "opencode": {"plugins": root + "/hosts/opencode/plugins/tezgah.js"},
                    "codex": {"Stop": '[{"command": "\\"python3\\" '
                                      '\\"/h/.config/tezgah/bin/tezgah-codex-hook\\""}]'}}
        old = entries("/opt/homebrew/Cellar/tezgah/0.1.1/libexec")
        new = entries("/opt/homebrew/Cellar/tezgah/0.1.2/libexec")
        self.assertEqual(tu.hook_change(old, new), [])
        clone = self.tree("src", "tezgah", git=True)
        code, calls, _, out = self.run_update(clone, old=old, new=new, tty=True)
        self.assertEqual((code, len(calls)), (0, 2))
        self.assertEqual(self.asked, [])
        self.assertIn("hook entries: unchanged", out)
        # a real change under a moved root still shows
        new["omp"]["bridge"] += "\n// new handler"
        self.assertEqual(tu.hook_change(old, new)[0],
                         "  omp: re-arming changes the bridge entry")

    def test_every_channel_says_what_a_no_leaves(self):
        self.assertEqual(set(tu.NOT_REARMED), {"git", "npm", "brew", "prefix"})

    def test_npm_fetches_then_re_arms_the_global_tree(self):
        root = os.path.join(self.root, "lib", "node_modules")
        pkg = self.tree("lib", "node_modules", "@r1z4x", "tezgah")
        code, calls, _, _ = self.run_update(pkg, npm_root=root)
        self.assertEqual(code, 0)
        self.assertEqual(calls[0], ["/bin/npm", "install", "-g", "@r1z4x/tezgah@latest"])
        self.assertEqual(calls[1][1:4], [os.path.join(pkg, "bin", "tezgah-setup"),
                                         "--install", "--no-deps"])

    def test_npm_running_outside_the_global_root_re_arms_the_global_tree(self):
        # npx or a project-local install: `npm install -g` moves the global
        # package, so that is the tree the hosts are re-armed from
        root = os.path.join(self.root, "global", "node_modules")
        npx = self.tree("npx", "abc", "node_modules", "@r1z4x", "tezgah")
        _, calls, _, _ = self.run_update(npx, npm_root=root)
        self.assertEqual(calls[1][1], os.path.join(root, "@r1z4x", "tezgah", "bin",
                                                   "tezgah-setup"))

    def test_a_failed_fetch_re_arms_nothing(self):
        clone = self.tree("src", "tezgah", git=True)
        code, calls, _, _ = self.run_update(clone, codes=(1,))
        self.assertEqual(code, 1)
        self.assertEqual(calls, [["/bin/git", "-C", clone, "pull", "--ff-only"]])

    def test_a_tool_missing_from_path_is_a_message_not_a_traceback(self):
        pkg = self.tree("lib", "node_modules", "@r1z4x", "tezgah")
        self.assertEqual(self.run_update(pkg, which=lambda name: None)[:2], (127, []))
        clone = self.tree("src", "tezgah", git=True)
        self.assertEqual(self.run_update(clone, fail=True)[:2], (127, []))

    def test_a_dry_run_runs_nothing(self):
        clone = self.tree("src", "tezgah", git=True)
        self.assertEqual(self.run_update(clone, dry_run=True)[:2], (0, []))

    def test_a_release_prefix_goes_through_the_installers_own_upgrade(self):
        clone = self.tree("p", "0.1.1")
        code, calls, upgrades, _ = self.run_update(clone, prefix="/p", dry_run=True)
        self.assertEqual((code, calls, upgrades), (0, [], [("", True)]))

    def test_an_unknown_tree_refuses(self):
        self.assertEqual(self.run_update(self.tree("loose"))[:2], (1, []))


class Command(support.TempHome):
    def test_tezgah_update_dry_run_from_this_checkout(self):
        # the subcommand is reachable through the real installer, and a checkout
        # answers with its git channel without fetching anything
        proc = subprocess.run([sys.executable, SETUP, "update", "--dry-run"],
                              capture_output=True, text=True, timeout=60,
                              env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout, r"update \(git\): \S*git -C %s pull --ff-only"
                         % re.escape(support.REPO))
        self.assertIn("--dry-run: nothing fetched", proc.stdout)


if __name__ == "__main__":
    unittest.main()
