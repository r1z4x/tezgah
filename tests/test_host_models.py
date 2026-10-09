"""docs/models.md: where each host's generated agent artifact carries the model.

The table is `docs/models.md` ("The table", "Which host reads which column");
each host's own documentation says where a custom agent's model may be set, and
the generated artifact must carry the tier's model there - or, where the host
documents that the model comes from somewhere else, must carry none at all:

  Claude Code  `~/.claude/agents/*.md` (written at install), `model:`/`effort:`
      in the frontmatter (code.claude.com/docs/en/sub-agents, model/effort table)
  Cursor       `.cursor/agents/*.md`, always `model: inherit`: cursor-agent
      passes the value through as a raw id, and no id this table names was
      verified against cursor.com/docs/subagents
  Codex        `$CODEX_HOME/agents/*.toml` (written at install), `model` +
      `model_reasoning_effort` (learn.chatgpt.com/docs/agent-configuration/subagents)
  opencode     `.opencode/agents/*.md`, `model:` only from the selector
      `--refresh` wrote (opencode.ai/docs/agents); none resolved, none written
  omp          `~/.omp/agent/agents/*.md` carries no `model:` - the model rides
      `task.agentModelOverrides`, resolved before the agent's own model
      (omp://task-agent-discovery.md, "Model and structured-output precedence")
  dsh          no agent file is generated: no per-agent model surface was found
      (docs/models.md, "dsh | - | none")

Every run is a subprocess with a throwaway HOME (support.TempHome), so the real
~/.claude, ~/.codex, ~/.config and ~/.omp are never read or written; the omp
install runs against a nonexistent TEZGAH_OMP_BIN, so no real `omp config` runs.
"""
import json
import os
import subprocess
import sys
import unittest

import support
from support import TempHome, run_json

CLAUDE = os.path.join(".claude", "agents")
OPENCODE = os.path.join(".opencode", "agents")
CODEX = os.path.join(".codex", "agents")
# where bin/tezgah-setup's install_omp writes omp's user-level agents
OMP_AGENTS = os.path.join(".omp", "agent", "agents")


class HostModels(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("acme")
        # the config dirs make each file host "installed" for detect_infra;
        # creating them under the temp HOME keeps detection off this machine
        for d in (".claude", ".codex", ".cursor", ".dsh",
                  os.path.join(".config", "opencode")):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        with open(os.path.join(self.repo, "pyproject.toml"), "w") as fh:
            fh.write("")

    def env(self, extra=None, consult=True):
        base = {"TEZGAH_CODEGRAPH_BIN": sys.executable, "TEZGAH_ORX_BIN": sys.executable}
        if consult:
            key_dir = os.path.join(self.home, ".config", "openrouter")
            os.makedirs(key_dir, exist_ok=True)
            open(os.path.join(key_dir, "key"), "w").close()
        if extra:
            base.update(extra)
        return super().env(extra=base)

    def pathless(self):
        return os.path.join(self.home, "no-such-omp")

    def sync(self, extra=None):
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "sync_root", "root": self.repo},
                             env=self.env(extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def frontmatter(self, directory, name, base=None):
        """The text between the two `---` fences, where model/tools lines live;
        `directory` is under the repo, or under `base` when given."""
        with open(os.path.join(base or self.repo, directory, name)) as fh:
            text = fh.read()
        self.assertTrue(text.startswith("---\n"), text[:40])
        return text.split("\n---\n", 1)[0]

    def install(self, *hosts):
        """bin/tezgah-setup --install, the generator of the omp user agents."""
        proc = subprocess.run(
            [sys.executable, os.path.join(support.REPO, "bin", "tezgah-setup"),
             "--install", "--hosts", ",".join(hosts)],
            capture_output=True, text=True, cwd=self.home, input="", timeout=120,
            env=self.env(extra={"TEZGAH_NO_DEPS": "1",
                                "TEZGAH_OMP_BIN": self.pathless()}))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc


class ClaudeCursor(HostModels):
    """The Anthropic column lands as an alias plus `effort:`
    (docs/models.md "Which host reads which column"; code.claude.com/docs/en/sub-agents)."""

    def test_the_cheap_worker_carries_the_tier_alias_and_its_effort(self):
        self.install("claude")
        head = self.frontmatter(CLAUDE, "tezgah-cheap.md", base=self.home)
        # the alias, not a full id, so a Bedrock/Vertex/gateway session keeps
        # its own variant (code.claude.com/docs/en/sub-agents)
        self.assertIn("model: opus", head)
        self.assertIn("effort: low", head)

    def test_the_orchestrator_keeps_the_session_model(self):
        self.install("claude")
        self.assertIn("model: inherit",
                      self.frontmatter(CLAUDE, "tezgah-orchestrator.md", base=self.home))

    def test_cursor_gets_its_own_dir_and_inherits_the_model(self):
        self.sync()
        # cursor-agent passes `model` through as a raw id and has no `effort`
        # key, so its own render pins no tier model (cursor.com/docs/subagents)
        head = self.frontmatter(os.path.join(".cursor", "agents"), "tezgah-cheap.md")
        self.assertIn("model: inherit", head)
        self.assertNotIn("effort", head)
        self.assertFalse(os.path.exists(os.path.join(self.repo, CLAUDE)))


class Codex(HostModels):
    """The OpenAI column lands as `model` + `model_reasoning_effort`
    (docs/models.md; learn.chatgpt.com/docs/agent-configuration/subagents)."""

    def test_the_cheap_worker_carries_its_model_and_effort(self):
        self.install("codex")
        with open(os.path.join(self.home, CODEX, "tezgah-cheap.toml")) as fh:
            text = fh.read()
        self.assertIn('model = "gpt-6.1-sol"', text)
        self.assertIn('model_reasoning_effort = "low"', text)

    def test_the_frontier_worker_carries_the_stronger_row(self):
        self.install("codex")
        with open(os.path.join(self.home, CODEX, "tezgah-frontier.toml")) as fh:
            text = fh.read()
        self.assertIn('model = "gpt-6-astra"', text)
        self.assertIn('model_reasoning_effort = "high"', text)


class Opencode(HostModels):
    """The `any` column lands as a resolved selector, or not at all
    (docs/models.md; opencode.ai/docs/agents)."""

    def overlay(self, mapping):
        path = os.path.join(self.home, ".config", "tezgah", "models.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump({"opencode": mapping}, fh)
        return path

    def test_a_resolved_selector_is_written_as_the_model_line(self):
        self.overlay({"cheap": "synthetic/cheap-selector"})
        self.sync()
        head = self.frontmatter(OPENCODE, "tezgah-cheap.md")
        self.assertIn("model: synthetic/cheap-selector", head)

    def test_with_no_selector_the_agent_inherits(self):
        self.sync()
        self.assertNotIn("model:", self.frontmatter(OPENCODE, "tezgah-cheap.md"))


class Omp(HostModels):
    """omp takes the model from `task.agentModelOverrides`, not from the agent
    file, so the generated file carries none (omp://task-agent-discovery.md,
    "Model and structured-output precedence"; docs/models.md)."""

    def agents(self):
        return os.path.join(self.home, OMP_AGENTS)

    def read(self, name):
        with open(os.path.join(self.agents(), name)) as fh:
            return fh.read()

    def test_the_cheap_worker_file_has_neither_a_model_nor_a_tools_line(self):
        self.install("omp")
        path = os.path.join(self.agents(), "tezgah-cheap.md")
        self.assertTrue(os.path.isfile(path), sorted(os.listdir(self.agents())))
        head = self.read("tezgah-cheap.md").split("\n---\n", 1)[0]
        # no model: the override record is where omp reads it
        self.assertNotIn("\nmodel:", "\n" + head)
        # no tools: a tier worker edits, so it gets every tool the session has
        self.assertNotIn("\ntools:", "\n" + head)

    def test_the_reviewer_keeps_its_tool_list(self):
        self.install("omp")
        head = self.read("tezgah-reviewer.md").split("\n---\n", 1)[0]
        self.assertIn("\ntools:", "\n" + head)
        self.assertIn("  - read", head)

    def test_install_sweeps_the_retired_roles_and_keeps_the_users_files(self):
        # omp's files carry no MARKER, so only names tezgah ever generated are
        # its own: a retired role must stop being loaded after the next install,
        # and a user's own `tezgah-*.md` must survive it
        os.makedirs(self.agents(), exist_ok=True)
        for name in ("tezgah-explorer.md", "tezgah-verifier.md",
                     "my-agent.md", "tezgah-mine.md"):
            with open(os.path.join(self.agents(), name), "w") as fh:
                fh.write("---\nname: x\n---\nx\n")
        self.install("omp")
        names = sorted(os.listdir(self.agents()))
        for gone in ("tezgah-explorer.md", "tezgah-verifier.md"):
            self.assertNotIn(gone, names)
        self.assertIn("my-agent.md", names)
        self.assertIn("tezgah-mine.md", names)
        self.assertIn("tezgah-cheap.md", names)

    def test_agents_off_removes_the_omp_user_agents(self):
        self.install("omp")
        self.assertIn("tezgah-cheap.md", os.listdir(self.agents()))
        switch = os.path.join(self.home, ".config", "tezgah", "agents-off")
        os.makedirs(os.path.dirname(switch), exist_ok=True)
        open(switch, "w").close()
        self.install("omp")
        self.assertEqual([], [n for n in os.listdir(self.agents())
                              if n.startswith("tezgah-")])

    def test_uninstall_keeps_a_users_own_tezgah_named_agent(self):
        # omp's files carry no MARKER, so the uninstall, its verify claim and the
        # report rows own only the names tezgah generated, not the prefix
        self.install("omp")
        mine = os.path.join(self.agents(), "tezgah-mine.md")
        with open(mine, "w") as fh:
            fh.write("---\nname: mine\n---\nx\n")
        proc = subprocess.run(
            [sys.executable, os.path.join(support.REPO, "bin", "tezgah-setup"),
             "--uninstall", "--hosts", "omp"],
            capture_output=True, text=True, cwd=self.home, input="", timeout=120,
            env=self.env(extra={"TEZGAH_NO_DEPS": "1",
                                "TEZGAH_OMP_BIN": self.pathless()}))
        self.assertTrue(os.path.isfile(mine), proc.stdout + proc.stderr)
        self.assertNotIn("tezgah-cheap.md", os.listdir(self.agents()))
        self.assertNotIn("tezgah-mine.md", proc.stdout)

    def test_the_orchestrator_can_delegate(self):
        self.install("omp")
        head = self.read("tezgah-orchestrator.md").split("\n---\n", 1)[0]
        self.assertIn("  - task", head)


class Dsh(HostModels):
    """No model surface is known for dsh, so the generator writes it nothing
    (docs/models.md, "Which host reads which column": `dsh | - | none`)."""

    def test_no_agent_file_is_generated_for_dsh(self):
        self.install("dsh")
        agent_dirs = [os.path.join(root, name)
                      for root, dirs, _f in os.walk(self.home)
                      for name in dirs if name == "agents"]
        self.assertEqual([d for d in agent_dirs
                          if ".dsh" in d or "tezgah" in d], [])
        self.assertFalse(os.path.exists(os.path.join(self.home, ".dsh", "agents")))

    def test_dsh_is_not_a_file_host_so_a_repo_sync_writes_nothing_for_it(self):
        self.config({"hosts": ["dsh"]})
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "detect", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["hosts"], [])
        self.assertIsNone(self.sync())


if __name__ == "__main__":
    unittest.main()
