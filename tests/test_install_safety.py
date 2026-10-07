"""A host config tezgah cannot parse is refused, never overwritten.

Written from plan 047's Phase A acceptance list (REPORT.md R03 part 3): each of
the seven installer sites that reads a host JSON config and then rewrites it
used to fall back to a default on any parse error, and the write that followed
replaced the user's file. A malformed file (a trailing comma, a `//` comment)
or a top-level value that is not an object must leave the file's bytes alone,
name the file, and make `--install` exit non-zero.

Every run uses a throwaway HOME, so no real host config is read or written.
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")

# (host, path under HOME, malformed text): the seven read-then-rewrite sites,
# alternating the two malformations the plan names.
TRAILING = '{"keep": "mine",}\n'
COMMENT = '// mine\n{"keep": "mine"}\n'
SITES = (
    ("codex", (".codex", "hooks.json"), TRAILING),
    ("opencode", (".config", "opencode", "opencode.json"), COMMENT),
    ("opencode", (".config", "opencode", "tui.json"), TRAILING),
    ("cursor", (".cursor", "hooks.json"), COMMENT),
    ("cursor", (".cursor", "mcp.json"), TRAILING),
    ("cursor", (".cursor", "cli-config.json"), COMMENT),
    ("omp", (".omp", "agent", "mcp.json"), TRAILING),
)


def load_setup():
    name = "tezgah_setup_safety_probe"
    if name in sys.modules:
        return sys.modules[name]
    loader = importlib.machinery.SourceFileLoader(name, SETUP)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader(name, loader))
    sys.modules[name] = module
    loader.exec_module(module)
    return module


class Home(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        for d in (".claude", ".codex", ".cursor", ".dsh", ".config/opencode",
                  ".omp/agent"):
            os.makedirs(self.path(d), exist_ok=True)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_CODEGRAPH_BIN": self.path("no-such-codegraph"),
            "TEZGAH_ORX_BIN": self.path("no-such-orx"),
            "TEZGAH_OMP_BIN": self.path("no-such-omp"),
            "TEZGAH_CLAUDE_BIN": self.path("no-such-claude"),
            "TEZGAH_NO_DEPS": "1",
            "TEZGAH_UPDATE_CHECK": "0",
        }

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(text.encode("utf-8"))

    def bytes(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def setup(self, *args):
        return subprocess.run([sys.executable, SETUP] + list(args),
                              capture_output=True, text=True, env=self.env,
                              input="", timeout=180)

    def backups(self, path):
        """The timestamped backups of `path`: under the throwaway HOME's backup
        dir for a subprocess run, beside the file for an in-process call (the
        module's HOME is the real one, so a temp path is outside it)."""
        d, base = os.path.split(path)
        mirror = os.path.join(self.home, ".config", "tezgah", "backups",
                              os.path.relpath(d, self.home))
        return sorted(os.path.join(where, n) for where in (d, mirror)
                      if os.path.isdir(where) for n in os.listdir(where)
                      if n.startswith(base + ".") and n.endswith(".tezgah-bak")
                      and n != base + ".tezgah-bak")

    def beside(self, path):
        d = os.path.dirname(path)
        return sorted(n for n in os.listdir(d) if n.endswith(".tezgah-bak"))


class Refusal(Home):
    def assert_refused(self, host, rel, text):
        path = self.path(*rel)
        self.put(path, text)
        proc = self.setup("--install", "--hosts", host)
        out = proc.stdout + proc.stderr
        self.assertEqual(self.bytes(path), text.encode("utf-8"),
                         "%s was rewritten\n%s" % (path, out))
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn(path, out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(self.backups(path), [], "a refused file got a backup")

    def test_each_malformed_site_is_refused_and_left_byte_identical(self):
        for host, rel, text in SITES:
            with self.subTest(file="/".join(rel)):
                self.setUp()
                self.assert_refused(host, rel, text)

    def test_a_top_level_array_or_string_is_refused(self):
        for host, rel, text in (("cursor", (".cursor", "mcp.json"), '[1, 2]\n'),
                                ("opencode", (".config", "opencode", "opencode.json"),
                                 '"mine"\n')):
            with self.subTest(file="/".join(rel)):
                self.setUp()
                self.assert_refused(host, rel, text)

    def test_the_refusal_names_the_reason(self):
        path = self.path(".cursor", "hooks.json")
        self.put(path, TRAILING)
        out = self.setup("--install", "--hosts", "cursor").stdout
        line = next((ln for ln in out.splitlines() if path in ln and "MISS" in ln), "")
        self.assertIn("not valid JSON", line, out)
        self.put(path, "[]\n")
        out = self.setup("--install", "--hosts", "cursor").stdout
        line = next((ln for ln in out.splitlines() if path in ln and "MISS" in ln), "")
        self.assertIn("not a JSON object", line, out)


class Backups(Home):
    def test_two_changing_installs_leave_two_timestamped_backups(self):
        path = self.path(".cursor", "cli-config.json")
        mine = '{"user": "original"}'
        self.put(path, mine)
        first = self.setup("--install", "--hosts", "cursor")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        data = json.loads(self.bytes(path))
        data["user"] = "edited"
        self.put(path, json.dumps(data))
        second = self.setup("--install", "--hosts", "cursor")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        baks = self.backups(path)
        self.assertEqual(len(baks), 2, baks)
        self.assertIn(mine.encode("utf-8"), [self.bytes(b) for b in baks])
        self.assertFalse(os.path.exists(path + ".tezgah-bak"),
                         "the untimestamped single backup is still written")
        self.assertEqual(self.beside(path), [],
                         "a host file's backup was laid in the dir the host scans")

    def test_install_moves_old_backups_out_of_host_dirs(self):
        """omp 18.6's hooks capability lists every non-dot file in hooks/pre,
        so a backup an older release laid beside the bridge is one more entry
        omp enumerates: an install moves it under the backup dir, bytes intact."""
        old = {
            self.path(".omp", "agent", "hooks", "pre",
                      "tezgah-hook.ts.20261007T172335952363.tezgah-bak"): "old bridge",
            self.path(".omp", "agent", "agents", "tezgah-explorer.md.tezgah-bak"): "retired",
            self.path(".cursor", "hooks.json.tezgah-bak"): "{}",
        }
        for p, text in old.items():
            self.put(p, text)
        proc = self.setup("--install", "--hosts", "cursor")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for p, text in old.items():
            self.assertFalse(os.path.exists(p), p)
            moved = os.path.join(self.home, ".config", "tezgah", "backups",
                                 os.path.relpath(p, self.home))
            self.assertEqual(self.bytes(moved), text.encode("utf-8"), proc.stdout)

    def test_the_count_never_exceeds_the_cap_and_the_oldest_survives(self):
        mod = load_setup()
        path = self.path("scratch", "conf.json")
        self.put(path, "v0")
        for i in range(1, mod.BACKUP_CAP + 4):
            mod.backup(path)
            self.put(path, "v%d" % i)
            self.assertLessEqual(len(self.backups(path)), mod.BACKUP_CAP)
        contents = [self.bytes(b) for b in self.backups(path)]
        self.assertEqual(len(contents), mod.BACKUP_CAP)
        self.assertIn(b"v0", contents, "the pre-install copy was pruned")
        self.assertIn(("v%d" % (mod.BACKUP_CAP + 2)).encode(), contents,
                      "the newest copy was pruned")

    def test_backups_written_within_one_second_do_not_collide(self):
        mod = load_setup()
        path = self.path("scratch", "fast.json")
        for i in range(3):
            self.put(path, "v%d" % i)
            mod.backup(path)
        self.assertEqual(len(self.backups(path)), 3)

    def test_uninstall_removes_timestamped_backups_of_generated_state(self):
        proc = self.setup("--install", "--hosts", "cursor")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        state = self.path(".config", "tezgah")
        stamped = os.path.join(state, "config.json.20261005T101010123456.tezgah-bak")
        legacy = os.path.join(state, "config.json.tezgah-bak")
        users = os.path.join(state, "notes.txt.20261005T101010123456.tezgah-bak")
        for p in (stamped, legacy, users):
            self.put(p, "{}")
        time.sleep(0.01)
        proc = self.setup("--uninstall")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(stamped), proc.stdout)
        self.assertFalse(os.path.exists(legacy), proc.stdout)
        self.assertTrue(os.path.exists(users), "a user file's backup was deleted")


if __name__ == "__main__":
    unittest.main()
