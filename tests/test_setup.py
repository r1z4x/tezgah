"""bin/tezgah-setup: install wiring, idempotency, uninstall, adopt.

Every test runs the installer in a throwaway HOME with fake host dirs, so the
real ~/.claude, ~/.codex, ~/.config/opencode, ~/.cursor and ~/.dsh are never
touched. TEZGAH_CBM_BIN points at nothing so no graph is registered.
"""
import json
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")
ALL = "claude,codex,opencode,cursor,dsh"


class SetupBase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        for d in (".claude", ".codex", ".cursor", ".dsh", ".config/opencode"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_CBM_BIN": os.path.join(self.home, "no-such-cbm"),
        }

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh)

    def read_json(self, path):
        with open(path) as fh:
            return json.load(fh)

    def read_text(self, path):
        with open(path) as fh:
            return fh.read()

    def setup(self, *args):
        return subprocess.run([sys.executable, SETUP] + list(args),
                              capture_output=True, text=True, env=self.env)


class Install(SetupBase):
    def test_installs_every_host_and_backs_up(self):
        self.write_json(self.path(".codex", "hooks.json"), {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "echo keep"}]}]}})
        self.write_json(self.path(".claude", "settings.json"),
                        {"statusLine": {"command": "echo keep"}, "theme": "dark"})
        proc = self.setup("--install", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        # common: config + symlinked CLIs
        cfg = self.read_json(self.path(".config", "tezgah", "config.json"))
        self.assertIn(self.path("Projects"), cfg["roots"])
        self.assertEqual(sorted(cfg["hosts"]), sorted(ALL.split(",")))
        for name in ("consult", "codegen", "tezgah-status", "tezgah-codex-hook",
                     "tezgah-cursor-hook", "tezgah-statusline"):
            self.assertTrue(os.path.islink(self.path(".config", "tezgah", "bin", name)),
                            name)

        # claude: statusline + attribution, existing key kept
        s = self.read_json(self.path(".claude", "settings.json"))
        self.assertIn("statusline.py", s["statusLine"]["command"])
        self.assertEqual(s["attribution"],
                         {"commit": "", "pr": "", "sessionUrl": False})
        self.assertEqual(s["theme"], "dark")
        self.assertTrue(os.path.exists(self.path(".claude", "settings.json.tezgah-bak")))

        # codex: pre-existing entry survives next to tezgah's
        raw = self.read_text(self.path(".codex", "hooks.json"))
        self.assertIn("echo keep", raw)
        self.assertIn("tezgah-codex-hook", raw)

        # dsh: managed patch block with both bridges
        dsh = self.read_text(self.path(".dsh", "cordis.patch.yml"))
        self.assertIn("# tezgah:start", dsh)
        self.assertIn("dsh-hooks-claude-code", dsh)
        self.assertIn("dsh-mcp-client", dsh)
        # both OpenRouter and DeepSeek routes are declared on the pi-ai adapter
        self.assertIn("id: llm-pi-ai", dsh)
        self.assertIn("openrouter", dsh)
        self.assertIn("DEEPSEEK_API_KEY", dsh)
        # a PATH launcher, managed so uninstall removes it
        launcher = self.path(".local", "bin", "dsh")
        self.assertTrue(os.path.islink(launcher), launcher)
        self.assertTrue(os.path.realpath(launcher).startswith(REPO))

        # opencode: contract instruction + TUI plugin + MCP
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertTrue(any("tezgah" in i for i in oc.get("instructions", [])))
        self.assertIn("codebase-memory-mcp", oc.get("mcp", {}))
        tui = self.read_json(self.path(".config", "opencode", "tui.json"))
        self.assertTrue(any("tezgah-tui" in (p if isinstance(p, str) else p[0])
                            for p in tui.get("plugin", [])))

        # cursor: hooks + statusline
        cur = self.read_json(self.path(".cursor", "cli-config.json"))
        self.assertIn("tezgah-statusline", cur["statusLine"]["command"])

    def test_reinstall_is_idempotent(self):
        self.setup("--install", "--hosts", ALL)
        self.setup("--install", "--hosts", ALL)
        dsh = self.read_text(self.path(".dsh", "cordis.patch.yml"))
        self.assertEqual(dsh.count("# tezgah:start"), 1)
        self.assertEqual(dsh.count("id: llm-pi-ai"), 1)
        codex = self.read_text(self.path(".codex", "hooks.json"))
        self.assertEqual(codex.count("tezgah-codex-hook"), 7)
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertEqual(len(oc.get("instructions", [])), 1)


class Uninstall(SetupBase):
    def test_removes_only_tezgah_and_keeps_backups(self):
        self.write_json(self.path(".codex", "hooks.json"), {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "echo keep"}]}]}})
        self.write_json(self.path(".claude", "settings.json"),
                        {"statusLine": {"command": "echo keep"}, "theme": "dark"})
        self.setup("--install", "--hosts", ALL)
        proc = self.setup("--uninstall", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        raw = self.read_text(self.path(".codex", "hooks.json"))
        self.assertIn("echo keep", raw)
        self.assertNotIn("tezgah-codex-hook", raw)
        self.assertNotIn("# tezgah:start",
                         self.read_text(self.path(".dsh", "cordis.patch.yml")))
        self.assertFalse(os.path.exists(self.path(".local", "bin", "dsh")))
        s = self.read_json(self.path(".claude", "settings.json"))
        self.assertNotIn("statusLine", s)
        self.assertNotIn("attribution", s)
        self.assertEqual(s["theme"], "dark")
        self.assertTrue(os.path.exists(self.path(".claude", "settings.json.tezgah-bak")))
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertFalse(oc.get("instructions"))


class Adopt(SetupBase):
    def test_moves_predecessor_wiring_aside(self):
        os.makedirs(self.path(".codex", "projects-harness"), exist_ok=True)
        with open(self.path(".codex", "projects-harness", "f"), "w") as fh:
            fh.write("old")
        self.write_json(self.path(".codex", "hooks.json"), {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "x projects-harness y"}]}]}})
        os.makedirs(self.path(".claude", "hooks"), exist_ok=True)
        with open(self.path(".claude", "hooks", "cbm-session-reminder"), "w") as fh:
            fh.write("old")
        self.write_json(self.path(".claude", "settings.json"), {"hooks": {"PreToolUse": [
            {"hooks": [{"type": "command", "command": "cbm-code-discovery-gate"}]}]},
            "theme": "dark"})
        proc = self.setup("--adopt")
        self.assertEqual(proc.returncode, 0, proc.stderr)

        self.assertFalse(os.path.isdir(self.path(".codex", "projects-harness")))
        self.assertFalse(os.path.exists(self.path(".claude", "hooks", "cbm-session-reminder")))
        adopted = []
        for root, _dirs, files in os.walk(self.path(".config", "tezgah", "adopted")):
            adopted += files
        self.assertIn("cbm-session-reminder", adopted)
        # the empty hooks key is dropped, and the unrelated key survives
        s = self.read_json(self.path(".claude", "settings.json"))
        self.assertNotIn("hooks", s)
        self.assertEqual(s["theme"], "dark")


if __name__ == "__main__":
    unittest.main()
