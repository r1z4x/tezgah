"""`--install` registers tezgah's Claude plugin through the `claude plugin` CLI.

Written from plan 047's Phase B acceptance list (ADR 013, REPORT.md R03 part 1):
Claude's gate, Stop and ledger hooks ship in the plugin, and the installer wrote
no registry row, so Claude was unarmed on every machine but the maintainer's.
The install now renders `.claude-plugin/{plugin,marketplace}.json` from the
release version into the tree it runs from, adds that tree as a directory
marketplace and installs `tezgah@<marketplace>` - and calls neither when a
`tezgah@*` row already exists, because a second row fires every hook twice.

Every run uses a throwaway HOME, a copy of the tree (the render must not land in
this checkout) and a stub `claude` that records its argv and writes the registry
the way Claude does; the real CLI never runs.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))

# The stub: `plugin marketplace add <dir>` records the directory source under the
# manifest's marketplace name; `plugin install tezgah@<name>` copies the
# marketplace dir into the plugin cache, writes the installed_plugins row and
# enables it - the three files Claude itself writes. FAIL makes every call fail.
STUB = r'''#!%s
import json, os, shutil, sys
home = os.environ["HOME"]
plugins = os.path.join(home, ".claude", "plugins")
os.makedirs(plugins, exist_ok=True)
with open(os.path.join(home, "claude-calls.jsonl"), "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
if os.environ.get("STUB_CLAUDE_FAIL"):
    sys.stderr.write("stub refused\n")
    sys.exit(3)
def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except OSError:
        return {}
def save(path, data):
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
known_path = os.path.join(plugins, "known_marketplaces.json")
args = sys.argv[1:]
if args[:3] == ["plugin", "marketplace", "add"]:
    src = args[3]
    name = load(os.path.join(src, ".claude-plugin", "marketplace.json"))["name"]
    known = load(known_path)
    known[name] = {"source": {"source": "directory", "path": src},
                   "installLocation": src}
    save(known_path, known)
elif args[:2] == ["plugin", "install"]:
    plugin, name = args[2].split("@", 1)
    src = load(known_path)[name]["source"]["path"]
    version = load(os.path.join(src, ".claude-plugin", "plugin.json"))["version"]
    dst = os.path.join(plugins, "cache", name, plugin, version)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    inst_path = os.path.join(plugins, "installed_plugins.json")
    inst = load(inst_path) or {"version": 2, "plugins": {}}
    inst["plugins"][args[2]] = [{"scope": "user", "installPath": dst,
                                 "version": version}]
    save(inst_path, inst)
    settings_path = os.path.join(home, ".claude", "settings.json")
    settings = load(settings_path)
    settings.setdefault("enabledPlugins", {})[args[2]] = True
    save(settings_path, settings)
else:
    sys.exit(2)
''' % sys.executable


def release_tree(dst):
    """A copy of this tree as a release unpacks it: the MANIFEST listing plus
    MANIFEST itself, with no `.git` and no local plugin manifest."""
    with open(os.path.join(REPO, "MANIFEST"), encoding="utf-8") as fh:
        files = [line.strip() for line in fh if line.strip()] + ["MANIFEST"]
    for rel in files:
        src = os.path.join(REPO, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
            shutil.copy2(src, os.path.join(dst, rel))
    return dst


class ClaudeHome(unittest.TestCase):
    """A temp HOME with ~/.claude, a stub claude, and a release-shaped tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = os.path.realpath(self._tmp.name)
        self.home = os.path.join(base, "home")
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "settings.json"), "w") as fh:
            fh.write("{}\n")
        self.tree = release_tree(os.path.join(base, "tree"))
        self.stub = os.path.join(base, "claude")
        with open(self.stub, "w") as fh:
            fh.write(STUB)
        os.chmod(self.stub, 0o755)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_CODEGRAPH_BIN": os.path.join(base, "no-such-codegraph"),
            "TEZGAH_ORX_BIN": os.path.join(base, "no-such-orx"),
            "TEZGAH_OMP_BIN": os.path.join(base, "no-such-omp"),
            "TEZGAH_CLAUDE_BIN": self.stub,
            "TEZGAH_NO_DEPS": "1",
            "TEZGAH_UPDATE_CHECK": "0",
        }

    def setup(self, *args, **extra):
        return subprocess.run(
            [sys.executable, os.path.join(self.tree, "bin", "tezgah-setup")] + list(args),
            capture_output=True, text=True, env=dict(self.env, **extra),
            stdin=subprocess.DEVNULL, timeout=300)

    def calls(self):
        try:
            with open(os.path.join(self.home, "claude-calls.jsonl")) as fh:
                return [json.loads(line) for line in fh]
        except OSError:
            return []

    def registry(self, name):
        try:
            with open(os.path.join(self.home, ".claude", "plugins", name)) as fh:
                return json.load(fh)
        except OSError:
            return {}

    def row(self, out, label):
        return next((ln for ln in out.splitlines() if label in ln), "")


class Registration(ClaudeHome):
    def test_a_fresh_home_renders_the_manifest_and_registers_the_tree(self):
        proc = self.setup("--install", "--hosts", "claude")
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        with open(os.path.join(self.tree, "CHANGELOG.md"), encoding="utf-8") as fh:
            want = re.search(r"(?m)^## \[(\d+\.\d+\.\d+)\]", fh.read()).group(1)
        with open(os.path.join(self.tree, ".claude-plugin", "plugin.json")) as fh:
            plugin = json.load(fh)
        with open(os.path.join(self.tree, ".claude-plugin", "marketplace.json")) as fh:
            market = json.load(fh)
        self.assertEqual(plugin["version"], want)
        self.assertEqual(market["plugins"][0]["version"], want)
        self.assertEqual(market["plugins"][0]["source"], "./")
        # a directory source pinned to the tree, then the plugin from it
        self.assertEqual(self.calls(), [
            ["plugin", "marketplace", "add", self.tree],
            ["plugin", "install", "tezgah@%s" % market["name"]]])
        source = self.registry("known_marketplaces.json")[market["name"]]["source"]
        self.assertEqual(source, {"source": "directory", "path": self.tree})
        # The plugin ships no agent: Claude namespaces a plugin's `agents/*.md`
        # as `tezgah:<name>` beside the generated reviewer and never shadows it,
        # so a shipped copy listed the reviewer twice.
        copy = self.registry("installed_plugins.json")["plugins"][
            "tezgah@%s" % market["name"]][0]["installPath"]
        self.assertFalse(os.path.exists(os.path.join(copy, "agents")), copy)
        # the arming row reads the copy Claude now loads
        self.assertTrue(self.row(out, "plugin copy current").strip().startswith("ok"), out)

    def test_an_existing_tezgah_row_is_not_registered_twice(self):
        plugins = os.path.join(self.home, ".claude", "plugins")
        os.makedirs(plugins)
        with open(os.path.join(plugins, "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {"tezgah@rizacan-local": [
                {"scope": "user", "installPath": "/nowhere", "version": "0.1.0"}]}}, fh)
        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(self.calls(), [], proc.stdout + proc.stderr)
        self.assertIn("Claude plugin registered (tezgah@rizacan-local)", proc.stdout)

    def test_a_refused_registration_fails_the_install(self):
        proc = self.setup("--install", "--hosts", "claude", STUB_CLAUDE_FAIL="1")
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn("claude plugin marketplace add %s exited 3: stub refused"
                      % self.tree, out)
        self.assertIn("plugin copy current", out.split("not armed")[-1], out)

    def test_uninstall_removes_the_rows_the_registration_wrote(self):
        self.assertEqual(self.setup("--install", "--hosts", "claude").returncode, 0)
        self.assertIn("tezgah@tezgah-local",
                      self.registry("installed_plugins.json").get("plugins") or {})
        proc = self.setup("--uninstall", "--hosts", "claude")
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        plugins = self.registry("installed_plugins.json").get("plugins") or {}
        self.assertFalse([k for k in plugins if k.startswith("tezgah@")], out)
        self.assertNotIn("tezgah-local", self.registry("known_marketplaces.json"), out)
        with open(os.path.join(self.home, ".claude", "settings.json")) as fh:
            enabled = json.load(fh).get("enabledPlugins") or {}
        self.assertFalse([k for k in enabled if k.startswith("tezgah@")], out)
        self.assertFalse(os.path.exists(os.path.join(self.tree, ".claude-plugin")), out)

    def test_sync_keeps_a_copys_manifest_when_the_tree_has_none(self):
        self.assertEqual(self.setup("--install", "--hosts", "claude").returncode, 0)
        shutil.rmtree(os.path.join(self.tree, ".claude-plugin"))
        # make the copy stale so --sync rewrites it
        copy = self.registry("installed_plugins.json")["plugins"][
            "tezgah@tezgah-local"][0]["installPath"]
        os.remove(os.path.join(copy, "README.md"))
        proc = self.setup("--sync")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(copy, "README.md")))
        self.assertTrue(os.path.isfile(os.path.join(copy, ".claude-plugin", "plugin.json")))

    def test_a_release_registers_a_source_that_survives_an_upgrade(self):
        """A release prefix deletes old version dirs, so the row names
        `<prefix>/current`, and the next tree carries the manifest again."""
        prefix = os.path.join(os.path.dirname(self.tree), "prefix")
        os.makedirs(prefix)
        old = os.path.join(prefix, "0.1.0")
        shutil.move(self.tree, old)
        os.symlink("0.1.0", os.path.join(prefix, "current"))
        self.tree = old
        self.assertEqual(self.setup("--install", "--hosts", "claude").returncode, 0)
        current = os.path.join(prefix, "current")
        self.assertEqual(self.calls()[0], ["plugin", "marketplace", "add", current])
        # the upgrade: a fresh tree without the untracked pair, `current`
        # flipped to it, and the old version dir gone
        new = os.path.join(prefix, "0.2.0")
        shutil.copytree(old, new, ignore=shutil.ignore_patterns(".claude-plugin"))
        os.remove(current)
        os.symlink("0.2.0", current)
        shutil.rmtree(old)
        self.tree = new
        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        source = self.registry("known_marketplaces.json")["tezgah-local"]["source"]["path"]
        self.assertTrue(os.path.isfile(os.path.join(source, ".claude-plugin",
                                                    "marketplace.json")), source)
        self.assertEqual(len(self.calls()), 2)  # the upgrade registered nothing new

    def read_only_tree(self):
        """The tree a root-owned `sudo npm -g` leaves: no directory writable."""
        dirs = [d for d, _, _ in os.walk(self.tree)]
        for d in dirs:
            os.chmod(d, 0o555)
        self.addCleanup(lambda: [os.chmod(d, 0o755) for d in dirs])

    def test_a_read_only_tree_with_a_registered_plugin_does_not_crash(self):
        plugins = os.path.join(self.home, ".claude", "plugins")
        os.makedirs(plugins)
        with open(os.path.join(plugins, "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {"tezgah@tezgah-local": [
                {"scope": "user", "installPath": "/nowhere", "version": "0.1.0"}]}}, fh)
        self.read_only_tree()
        proc = self.setup("--install", "--hosts", "claude")
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("Claude plugin registered (tezgah@tezgah-local)", out)
        self.assertEqual(self.calls(), [])

    def test_a_read_only_tree_cannot_register_and_says_why(self):
        self.read_only_tree()
        proc = self.setup("--install", "--hosts", "claude")
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("cannot write %s" % os.path.join(self.tree, ".claude-plugin"), out)
        self.assertEqual(self.calls(), [])  # nothing registered without a manifest
        self.assertIn("plugin copy current", out.split("not armed")[-1], out)


class Manifest(unittest.TestCase):
    def test_the_manifest_stays_untracked(self):
        with open(os.path.join(REPO, ".gitignore"), encoding="utf-8") as fh:
            self.assertIn("/.claude-plugin/", fh.read().split())
        with open(os.path.join(REPO, "MANIFEST"), encoding="utf-8") as fh:
            self.assertFalse([ln for ln in fh if ln.startswith(".claude-plugin/")])


if __name__ == "__main__":
    unittest.main()
