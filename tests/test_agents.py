"""hooks/tezgah_agents.py: per-repo subagent generation, gating and cleanup."""
import json
import os
import shutil
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
        # the real config roots: opencode keeps its config under ~/.config, and
        # creating it here keeps detection off the machine's own PATH
        for d in (".claude", ".codex", ".cursor", os.path.join(".config", "opencode")):
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

    def test_opencode_markdown_uses_native_frontmatter(self):
        self.sync()
        ex = self.read(OPENCODE, "tezgah-explorer.md")
        self.assertIn("mode: subagent", ex)
        self.assertIn("edit: deny", ex)
        # opencode validates `tools` as an object; a Claude `Agent(...)` string
        # makes the whole config invalid, so it must never appear here.
        self.assertNotIn("tools:", ex)
        self.assertNotIn("Agent(", ex)
        self.assertNotIn("disallowedTools", ex)
        self.assertNotIn("readonly: true", ex)
        self.assertNotIn("ToolSearch(", ex)
        orch = self.read(OPENCODE, "tezgah-orchestrator.md")
        self.assertIn("mode: primary", orch)
        self.assertIn('"tezgah-*": allow', orch)
        self.assertNotIn("tools:", orch)

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

    def test_agent_bodies_use_absolute_cli_paths(self):
        # same bug plan 004 fixed in the contract: a subagent shell is
        # non-interactive, so a bare bin/consult or orx is "not found".
        self.sync()
        verifier = self.read(CLAUDE, "tezgah-verifier.md")
        self.assertNotIn("`bin/consult", verifier)
        self.assertIn(os.path.join(support.REPO, "bin", "consult"), verifier)
        researcher = self.read(CLAUDE, "tezgah-researcher.md")
        self.assertNotIn("`orx`", researcher)
        self.assertIn(sys.executable, researcher)  # TEZGAH_ORX_BIN here


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


class Gitignore(AgentsBase):
    """Generated agent dirs are machine-specific, so they are ignored via one
    managed block that survives a re-run and is stripped on uninstall."""

    def gi(self):
        with open(os.path.join(self.repo, ".gitignore")) as fh:
            return fh.read()

    def test_block_added_and_appended_to_existing_content(self):
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n")
        self.sync()
        text = self.gi()
        self.assertIn("node_modules/", text)
        self.assertIn("/.claude/agents/", text)
        self.assertIn("/.opencode/agents/", text)
        self.assertIn("/.codex/agents/", text)

    def test_block_is_idempotent(self):
        self.sync()
        once = self.gi()
        self.sync()
        self.assertEqual(self.gi(), once)
        self.assertEqual(once.count("# tezgah: generated agents"), 1)

    def test_block_unions_and_never_drops_a_dir(self):
        # a prior install ignored all three; a config that now lists only
        # opencode must not un-ignore the claude/codex dirs
        self.sync()
        self.config({"hosts": ["opencode"]})
        self.sync()
        text = self.gi()
        for d in ("/.claude/agents/", "/.opencode/agents/", "/.codex/agents/"):
            self.assertIn(d, text)

    def test_a_block_that_sits_mid_file_stays_where_it_is(self):
        # this repo's committed .gitignore has the block before other entries;
        # rebuilding the file around it moved it to the end and dirtied the tree
        # on the first session start of a fresh checkout
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n\n"
                     "# tezgah: generated agents (managed; removed by "
                     "tezgah-setup --uninstall)\n"
                     "/.claude/agents/\n"
                     "# tezgah: end generated agents\n\n"
                     "dist/\n")
        self.sync()
        text = self.gi()
        self.assertLess(text.index("# tezgah: end generated agents"),
                        text.index("dist/"))
        once = self.gi()
        self.sync()
        self.assertEqual(self.gi(), once)

    def test_cleanup_strips_block_but_keeps_user_content(self):
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n")
        self.sync()
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "cleanup"},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(out, 0)
        self.assertEqual(self.gi(), "node_modules/\n")

    def test_cleanup_removes_a_gitignore_it_created_alone(self):
        self.sync()
        run_json([support.PROBE_AGENTS], {"fn": "cleanup"}, env=self.env())
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".gitignore")))


class OpencodePlugin(AgentsBase):
    """The plugin config hook must arm the agents in the same opencode session.

    Runs the real plugin module in node, so a lost const (e.g. AGENTS_BIN) or a
    broken spawn is caught, not only the Python side.
    """

    def test_config_hook_injects_the_agents(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        self.sync()  # the --json path is what the hook calls; same source
        link = os.path.join(self.home, ".config", "tezgah", "bin", "tezgah-agents")
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(os.path.join(support.REPO, "bin", "tezgah-agents"), link)
        harness = os.path.join(self.home, "h.mjs")
        with open(harness, "w") as fh:
            fh.write(
                'import { Tezgah } from "file://%s"\n'
                'const hooks = await Tezgah({ directory: "%s" })\n'
                'const cfg = {}\n'
                'await hooks.config(cfg)\n'
                'console.log(JSON.stringify(cfg.agent || {}))\n'
                % (os.path.join(support.REPO, "hosts", "opencode", "plugins",
                                "tezgah.js"), self.repo))
        proc = subprocess.run([node, harness], capture_output=True, text=True,
                              env=self.env(), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        agent = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(agent["tezgah-explorer"]["mode"], "subagent")
        self.assertEqual(agent["tezgah-explorer"]["permission"]["edit"], "deny")
        self.assertEqual(agent["tezgah-orchestrator"]["mode"], "primary")
        self.assertEqual(agent["tezgah-orchestrator"]["permission"]["task"]["*"], "deny")

    def test_before_hook_denies_attribution_writes(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        harness = os.path.join(self.home, "attrib.mjs")
        plugin = os.path.join(support.REPO, "hosts", "opencode", "plugins",
                              "tezgah.js")
        with open(harness, "w") as fh:
            fh.write(
                'import { Tezgah } from "file://%s"\n'
                'const hooks = await Tezgah({ directory: "%s" })\n'
                'const run = async (cmd) => {\n'
                '  try {\n'
                '    await hooks["tool.execute.before"](\n'
                '      { tool: "bash", sessionID: "s", args: { command: cmd } },\n'
                '      { args: { command: cmd } })\n'
                '    return "pass"\n'
                '  } catch (e) { return "deny:" + e.message }\n'
                '}\n'
                'console.log(JSON.stringify({\n'
                '  write: await run(\'git commit -m "Co-Authored-By: Claude"\'),\n'
                '  clean: await run(\'git commit -m "fix: typo"\'),\n'
                '}))\n'
                % (plugin, self.repo))
        proc = subprocess.run([node, harness], capture_output=True, text=True,
                              env=self.env(), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(out["write"].startswith("deny:"), out)
        self.assertIn("Attribution", out["write"])
        self.assertEqual(out["clean"], "pass")


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
    def detect(self, env=None, root=None):
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "detect", "root": root or self.repo},
                             env=env or self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_detects_caps_stack_and_file_hosts(self):
        out = self.detect()
        self.assertEqual(out["caps"], {"cbm": True, "orx": True, "consult": True})
        self.assertEqual(out["stack"], ["python"])
        self.assertEqual(sorted(out["hosts"]), ["claude", "codex", "cursor", "opencode"])

    def test_an_explicit_host_list_without_a_file_host_generates_nothing(self):
        # omp keeps its subagents user-level, so a config naming it must not
        # sprout .claude/.cursor agent files in every repo
        self.config({"hosts": ["omp"]})
        self.assertEqual(self.detect()["hosts"], [])

    def test_a_config_without_a_file_host_sweeps_the_previous_files(self):
        # a repo that got agents while another host was configured must not keep
        # them: Claude and Cursor load that dir, so a stale agent is a live one
        self.sync()
        self.assertTrue(self.exists(CLAUDE, "tezgah-explorer.md"))
        self.config({"hosts": ["omp"]})
        self.sync()
        self.assertEqual(self.names(CLAUDE), [])
        self.assertEqual(self.names(CODEX), [])
        self.assertEqual(self.names(OPENCODE), [])

    def test_detection_does_not_read_another_hosts_dir(self):
        # cursor was probed through ~/.claude, so it was "installed" wherever
        # Claude was; only the hosts that are actually here may be selected
        shutil.rmtree(os.path.join(self.home, ".cursor"))
        shutil.rmtree(os.path.join(self.home, ".codex"))
        shutil.rmtree(os.path.join(self.home, ".config", "opencode"))
        # a PATH with nothing on it, so no CLI can stand in for a config dir
        out = self.detect(env=self.env(extra={"PATH": "/nonexistent"}))
        self.assertEqual(out["hosts"], ["claude"])

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
