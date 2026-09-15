"""hooks/tezgah_agents.py: per-repo subagent generation, gating and cleanup."""
import os
import sys
import unittest

import support
from support import TempHome, run_json

AGENTS = os.path.join("agents")


class AgentsBase(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("acme")
        for d in (".claude", ".opencode"):
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

    def read(self, host, name):
        with open(os.path.join(self.repo, host, AGENTS, name + ".md")) as fh:
            return fh.read()

    def exists(self, host, name):
        return os.path.isfile(os.path.join(self.repo, host, AGENTS, name + ".md"))

    def names(self, host):
        d = os.path.join(self.repo, host, AGENTS)
        try:
            return sorted(f[:-3] for f in os.listdir(d) if f.endswith(".md"))
        except OSError:
            return []


class Generation(AgentsBase):
    def test_generates_every_active_role_for_both_file_hosts(self):
        note = self.sync()
        self.assertIn("4 agent(s)", note)
        for host in (".claude", ".opencode"):
            self.assertEqual(
                self.names(host),
                ["tezgah-explorer", "tezgah-orchestrator", "tezgah-researcher",
                 "tezgah-reviewer", "tezgah-verifier"])

    def test_frontmatter_is_host_specific_and_managed(self):
        self.sync()
        claude = self.read(".claude", "tezgah-explorer")
        self.assertIn("# tezgah: managed", claude)
        self.assertIn("disallowedTools:", claude)
        self.assertIn("search_graph", claude)
        op = self.read(".opencode", "tezgah-explorer")
        self.assertIn("mode: subagent", op)
        self.assertNotIn("disallowedTools", op)
        # the opencode body must not carry the Claude-only ToolSearch step
        self.assertNotIn("ToolSearch(", op)

    def test_opencode_orchestrator_allowlists_only_tezgah_agents(self):
        self.sync()
        orch = self.read(".opencode", "tezgah-orchestrator")
        self.assertIn("mode: primary", orch)
        self.assertIn('"*": deny', orch)
        self.assertIn('"tezgah-*": allow', orch)

    def test_idempotent_second_run_writes_nothing(self):
        self.sync()
        before = self.read(".claude", "tezgah-explorer")
        self.assertIn("current", self.sync())
        self.assertEqual(self.read(".claude", "tezgah-explorer"), before)


class Gating(AgentsBase):
    def test_no_capability_writes_nothing(self):
        env = self.env(extra={"TEZGAH_CBM_BIN": self.pathless(),
                              "TEZGAH_ORX_BIN": self.pathless()}, consult=False)
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "sync_root", "root": self.repo}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)
        self.assertEqual(self.names(".claude"), [])

    def pathless(self):
        return os.path.join(self.home, "nope")

    def test_missing_capability_removes_its_agent(self):
        self.sync()
        self.assertTrue(self.exists(".claude", "tezgah-researcher"))
        note = self.sync(extra={"TEZGAH_ORX_BIN": self.pathless()})
        self.assertNotIn("researcher", " ".join(self.names(".claude")))
        self.assertIn("removed", note)
        # the capability still present keeps its agent
        self.assertTrue(self.exists(".claude", "tezgah-explorer"))

    def test_no_file_host_writes_nothing(self):
        self.sync()
        # a repo whose home has no host dirs (remove them) -> silent no-op
        import shutil
        shutil.rmtree(os.path.join(self.home, ".claude"))
        shutil.rmtree(os.path.join(self.home, ".opencode"))
        repo2 = self.make_repo("other")
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "sync_root", "root": repo2}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)

    def test_agents_off_kill_switch(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "agents-off"))
        self.assertIsNone(self.sync())
        self.assertEqual(self.names(".claude"), [])


class Cleanup(AgentsBase):
    def test_removes_only_managed_files(self):
        self.sync()
        own = os.path.join(self.repo, ".claude", AGENTS, "my-own.md")
        with open(own, "w") as fh:
            fh.write("---\nname: my-own\n---\nx\n")
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "cleanup"},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(out, 0)
        self.assertEqual(self.names(".claude"), ["my-own"])
        self.assertEqual(self.names(".opencode"), [])
        self.assertFalse(os.path.exists(
            os.path.join(self.home, ".config", "tezgah", "agents.state.json")))


class Detection(AgentsBase):
    def test_detects_caps_stack_and_file_hosts(self):
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "detect", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["caps"], {"cbm": True, "orx": True, "consult": True})
        self.assertEqual(out["stack"], ["python"])
        self.assertEqual(out["hosts"], ["claude", "opencode"])

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
        self.assertTrue(self.exists(".claude", "tezgah-explorer"))

    def test_only_session_start_generates(self):
        run_json([support.PROBE_CONTEXT],
                 {"fn": "context_for", "event": "user_prompt", "cwd": self.repo},
                 env=self.env())
        self.assertEqual(self.names(".claude"), [])


if __name__ == "__main__":
    unittest.main()
