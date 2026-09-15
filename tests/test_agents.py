"""hooks/tezgah_agents.py: per-repo subagent generation, gating and cleanup."""
import os
import subprocess
import sys
import unittest

import support
from support import TempHome, run_json

CLAUDE = os.path.join(".claude", "agents")
OPENCODE = os.path.join(".opencode", "agents")
CODEX = os.path.join(".codex", "agents")


class AgentsBase(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("acme")
        for d in (".claude", ".opencode", ".codex", ".cursor"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        with open(os.path.join(self.repo, "pyproject.toml"), "w") as fh:
            fh.write("")

    def env(self, extra=None, consult=True):
        base = {"TEZGAH_CBM_BIN": sys.executable, "TEZGAH_ORX_BIN": sys.executable}
        if consult:
            key_dir = os.path.join(self.home, ".config", "openrouter")
            os.makedirs(key_dir, exist_ok=True)
            open(os.path.join(key_dir, "key"), "w").close()
        if extra:
            base.update(extra)
        return super().env(extra=base)

    def sync(self, extra=None):
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "sync_root", "root": self.repo},
                             env=self.env(extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def opencode_json(self, extra=None, consult=True):
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "opencode_json", "root": self.repo},
                             env=self.env(extra, consult))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def read(self, directory, name):
        with open(os.path.join(self.repo, directory, name)) as fh:
            return fh.read()

    def exists(self, directory, name):
        return os.path.isfile(os.path.join(self.repo, directory, name))

    def names(self, directory):
        d = os.path.join(self.repo, directory)
        try:
            return sorted(os.listdir(d))
        except OSError:
            return []


class Generation(AgentsBase):
    def test_generates_every_active_role_for_every_file_host(self):
        self.assertIn("4 agent(s)", self.sync())
        for d in (CLAUDE, OPENCODE, CODEX):
            self.assertEqual(
                self.names(d),
                ["tezgah-explorer.md", "tezgah-orchestrator.md",
                 "tezgah-researcher.md", "tezgah-reviewer.md",
                 "tezgah-verifier.md"] if d != CODEX else
                ["tezgah-explorer.toml", "tezgah-researcher.toml",
                 "tezgah-reviewer.toml", "tezgah-verifier.toml"])

    def test_cursor_is_served_by_the_claude_dir(self):
        self.sync()
        self.assertFalse(os.path.isdir(os.path.join(self.repo, ".cursor", "agents")))
        self.assertTrue(self.exists(CLAUDE, "tezgah-explorer.md"))

    def test_markdown_frontmatter_is_readonly_for_cursor_and_claude(self):
        self.sync()
        explorer = self.read(CLAUDE, "tezgah-explorer.md")
        self.assertIn("# tezgah: managed", explorer)
        self.assertIn("readonly: true", explorer)
        self.assertIn("disallowedTools:", explorer)
        self.assertIn("search_graph", explorer)
        # the verifier may run a shell, so it is not marked read-only
        self.assertNotIn("readonly: true", self.read(CLAUDE, "tezgah-verifier.md"))
        # opencode body must not carry the Claude-only ToolSearch step
        self.assertNotIn("ToolSearch(", self.read(OPENCODE, "tezgah-explorer.md"))

    def test_codex_toml_has_required_fields_and_readonly_sandbox(self):
        self.sync()
        ex = self.read(CODEX, "tezgah-explorer.toml")
        self.assertIn('name = "tezgah-explorer"', ex)
        self.assertIn("description = '''", ex)
        self.assertIn("developer_instructions = '''", ex)
        self.assertIn('sandbox_mode = "read-only"', ex)
        self.assertNotIn("ToolSearch(", ex)

    def test_idempotent_second_run_writes_nothing(self):
        self.sync()
        before = self.read(CLAUDE, "tezgah-explorer.md")
        self.assertIn("current", self.sync())
        self.assertEqual(self.read(CLAUDE, "tezgah-explorer.md"), before)


class OpencodeConfig(AgentsBase):
    def test_json_exposes_subagents_and_an_orchestrator(self):
        data = self.opencode_json()
        agent = data["agent"]
        self.assertEqual(agent["tezgah-explorer"]["mode"], "subagent")
        self.assertEqual(agent["tezgah-explorer"]["permission"]["edit"], "deny")
        self.assertIn("prompt", agent["tezgah-reviewer"])
        orch = agent["tezgah-orchestrator"]
        self.assertEqual(orch["mode"], "primary")
        self.assertEqual(orch["permission"]["task"]["*"], "deny")
        self.assertEqual(orch["permission"]["task"]["tezgah-*"], "allow")

    def test_json_empty_without_capabilities(self):
        data = self.opencode_json(
            extra={"TEZGAH_CBM_BIN": self.pathless(),
                   "TEZGAH_ORX_BIN": self.pathless()}, consult=False)
        self.assertEqual(data, {})

    def pathless(self):
        return os.path.join(self.home, "nope")


class Gating(AgentsBase):
    def test_no_capability_writes_nothing(self):
        env = self.env(extra={"TEZGAH_CBM_BIN": self.pathless(),
                              "TEZGAH_ORX_BIN": self.pathless()}, consult=False)
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "sync_root", "root": self.repo}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)
        self.assertEqual(self.names(CLAUDE), [])

    def pathless(self):
        return os.path.join(self.home, "nope")

    def test_missing_capability_removes_its_agent(self):
        self.sync()
        self.assertTrue(self.exists(CLAUDE, "tezgah-researcher.md"))
        note = self.sync(extra={"TEZGAH_ORX_BIN": self.pathless()})
        self.assertNotIn("researcher", " ".join(self.names(CLAUDE)))
        self.assertIn("removed", note)
        self.assertTrue(self.exists(CLAUDE, "tezgah-explorer.md"))

    def test_agents_off_kill_switch(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "agents-off"))
        self.assertIsNone(self.sync())
        self.assertEqual(self.names(CLAUDE), [])


class Cleanup(AgentsBase):
    def test_removes_only_managed_files(self):
        self.sync()
        own = os.path.join(self.repo, CLAUDE, "my-own.md")
        with open(own, "w") as fh:
            fh.write("---\nname: my-own\n---\nx\n")
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "cleanup"},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(out, 0)
        self.assertEqual(self.names(CLAUDE), ["my-own.md"])
        self.assertEqual(self.names(OPENCODE), [])
        self.assertEqual(self.names(CODEX), [])
        self.assertFalse(os.path.exists(
            os.path.join(self.home, ".config", "tezgah", "agents.state.json")))


class Detection(AgentsBase):
    def test_detects_caps_stack_and_file_hosts(self):
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "detect", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["caps"], {"cbm": True, "orx": True, "consult": True})
        self.assertEqual(out["stack"], ["python"])
        self.assertEqual(sorted(out["hosts"]), ["claude", "codex", "cursor", "opencode"])

    def test_no_cbm_marker_disables_the_graph_capability(self):
        self.touch(os.path.join(self.repo, ".no-cbm"))
        out, _ = run_json([support.PROBE_AGENTS],
                          {"fn": "detect", "root": self.repo}, env=self.env())
        self.assertFalse(out["caps"]["cbm"])


class ContextWiring(AgentsBase):
    """SessionStart must announce and generate the set in the injected context."""

    def test_session_start_injects_a_subagent_note(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Subagents (this repo, generated)", out)
        self.assertTrue(self.exists(CLAUDE, "tezgah-explorer.md"))

    def test_only_session_start_generates(self):
        run_json([support.PROBE_CONTEXT],
                 {"fn": "context_for", "event": "user_prompt", "cwd": self.repo},
                 env=self.env())
        self.assertEqual(self.names(CLAUDE), [])

    def test_setup_agents_flag_regenerates(self):
        setup = os.path.join(support.REPO, "bin", "tezgah-setup")
        proc = subprocess.run([sys.executable, setup, "--agents", self.repo],
                              capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("agent(s)", proc.stdout)
        self.assertTrue(self.exists(CLAUDE, "tezgah-explorer.md"))


if __name__ == "__main__":
    unittest.main()
