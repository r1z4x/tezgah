"""hooks/tezgah_agents.py: per-repo subagent generation, gating and cleanup."""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

import support
from support import TempHome, run_json

# Claude and Codex keep their roles user-level (written at install); only these
# leave a dir in the repo, plus the two an older tezgah wrote there.
CLAUDE = os.path.join(".claude", "agents")
OPENCODE = os.path.join(".opencode", "agents")
CODEX = os.path.join(".codex", "agents")
CURSOR = os.path.join(".cursor", "agents")
# codegraph's own CLI surface. A brief may only name one of these verbs, and
# `codegraph_explore` is the single MCP tool the server exposes by default.
CODEGRAPH_CLI_VERBS = ("query", "node", "callers", "callees", "impact",
                       "affected", "files", "status", "explore", "init", "sync",
                       "serve", "unlock", "uninstall", "upgrade", "version")
sys.path.insert(0, support.HOOKS)
import tezgah_agents  # noqa: E402  (pure renderers, read in-process)


def setup_mcp_tools():
    """The codegraph MCP tools tezgah's server row enables (bin/tezgah-setup)."""
    with open(os.path.join(support.REPO, "bin", "tezgah-setup"), encoding="utf-8") as fh:
        return re.search(r'"CODEGRAPH_MCP_TOOLS": "([^"]+)"', fh.read()).group(1).split(",")


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
        base = {"TEZGAH_CODEGRAPH_BIN": sys.executable, "TEZGAH_ORX_BIN": sys.executable}
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

    def user(self, host, extra=None):
        """{filename: text} the installer writes to `host`'s user agent dir."""
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "user", "host": host},
                             env=self.env(extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def steer(self, host=None):
        """steering() under this HOME, where the user-level dirs live."""
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "steering", "root": self.repo, "host": host},
                             env=self.env())
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
    def test_help_prints_usage_without_generating_agents(self):
        # --help used to be read as PATH, so the run printed nothing at all.
        proc = subprocess.run(
            [sys.executable, os.path.join(support.REPO, "bin", "tezgah-agents"),
             "--help"],
            capture_output=True, text=True, env=self.env(), cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah-agents [PATH]", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.repo, CURSOR)),
                         "the help path generated agents")

    def test_generates_every_active_role_for_every_file_host(self):
        self.assertIn("9 agent(s)", self.sync())
        roles = ["cheap", "docs", "frontier", "researcher", "reviewer", "security",
                 "standard", "tester", "ui"]
        md = ["tezgah-%s.md" % r for r in roles]
        # Cursor and Codex get no orchestrator: their files are subagents the
        # main thread delegates to, and the orchestrator is a primary agent
        self.assertEqual(self.names(CURSOR), md)
        self.assertEqual(self.names(OPENCODE), sorted(md + ["tezgah-orchestrator.md"]))
        self.assertEqual(sorted(self.user("claude")), sorted(md + ["tezgah-orchestrator.md"]))
        self.assertEqual(sorted(self.user("codex")), ["tezgah-%s.toml" % r for r in roles])

    def test_every_specialist_names_its_routed_tier_and_shipped_skills(self):
        # the description is what a host shows when choosing an agent, so it
        # carries the tier the model line is rendered from and the skills the
        # body loads; a skill named there must ship in skills/
        import tezgah_models
        for name, desc, _cap, body, _ro in tezgah_agents.ROLES:
            self.assertIn(name, tezgah_models.AGENT_SLOT, name)
            if name not in tezgah_agents.SPECIALISTS:
                continue
            tier = tezgah_models.AGENT_SLOT[name]
            self.assertIn("Tier: %s" % tier, desc, name)
            self.assertIn("on the %s model tier" % tier, body("claude"), name)
            for skill in tezgah_agents.SPECIALISTS[name][1]:
                self.assertIn(skill, desc, name)
                self.assertIn("`%s`" % skill, body("omp"), name)
                self.assertTrue(skill in tezgah_agents.HOST_SKILLS or os.path.isfile(
                    os.path.join(support.REPO, "skills", skill, "SKILL.md")), skill)
        # the security reviewer is mapped to the host's wstg/attack families
        security = dict((r[0], r[1]) for r in tezgah_agents.ROLES)["tezgah-security"]
        for family in ("wstg-*", "attack-*"):
            self.assertIn(family + " (host-installed)", security)

    def test_a_writing_specialist_gets_every_omp_tool_and_a_read_only_one_does_not(self):
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "omp", "root": self.repo},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ("tezgah-tester", "tezgah-docs", "tezgah-ui", "tezgah-researcher"):
            self.assertNotIn("\ntools:", out[name + ".md"], name)
        self.assertIn("\ntools:\n  - read", out["tezgah-security.md"])
        self.assertIn("disallowedTools", tezgah_agents.render_md(
            "tezgah-security", "d", True, "b"))

    def test_steering_and_the_orchestrator_name_the_specialists(self):
        self.sync()
        line = self.steer()
        orch = self.user("claude")["tezgah-orchestrator.md"]
        for name in tezgah_agents.SPECIALISTS:
            self.assertIn("-> " + name, line)
            self.assertIn(name, orch)

    def test_list_prints_every_role_with_its_tier(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(support.REPO, "bin", "tezgah-agents"),
             "--list"], capture_output=True, text=True, env=self.env(), cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah-security  tier=frontier  read-only", proc.stdout)
        self.assertIn("tezgah-tester  tier=cheap  writes", proc.stdout)
        self.assertIn("Skills: analyze-app", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.repo, CURSOR)))

    def test_the_opencode_entry_carries_the_slots_effort_when_it_has_one(self):
        # opencode documents reasoningEffort in the agent config, and only the
        # slots whose `any` row names an effort get one; the resolved selector
        # comes from the overlay `--refresh` wrote under this HOME
        overlay = os.path.join(self.home, ".config", "tezgah", "models.json")
        os.makedirs(os.path.dirname(overlay), exist_ok=True)
        with open(overlay, "w") as fh:
            json.dump({"opencode": {"standard": "opencode-go/x", "cheap": "opencode-go/y"}}, fh)
        entries = self.opencode_json()["agent"]
        self.assertEqual(entries["tezgah-standard"]["model"], "opencode-go/x")
        self.assertEqual(entries["tezgah-standard"]["reasoningEffort"], "high")
        self.assertEqual(entries["tezgah-cheap"]["model"], "opencode-go/y")
        self.assertNotIn("reasoningEffort", entries["tezgah-cheap"])

    def test_each_agent_carries_its_tier_model_for_the_host_family(self):
        # Claude/Cursor read the Anthropic row, Codex the OpenAI row; the
        # orchestrator is the main thread's own agent and keeps the session model
        claude = self.user("claude")
        cheap = claude["tezgah-cheap.md"]
        # the alias, not the full id: an alias follows the provider and keeps the
        # main session's variant, where a full id breaks on Bedrock or a gateway
        self.assertIn("model: opus\neffort: low", cheap)
        self.assertIn("effort: high", claude["tezgah-reviewer.md"])
        self.assertIn("model: inherit", claude["tezgah-orchestrator.md"])
        codex = self.user("codex")["tezgah-frontier.toml"]
        self.assertIn('model = "gpt-6-astra"', codex)
        self.assertIn('model_reasoning_effort = "high"', codex)
        self.sync()
        # opencode's selector depends on this machine's providers: none resolved,
        # no model line, so the agent inherits instead of naming a missing model
        self.assertNotIn("model:", self.read(OPENCODE, "tezgah-cheap.md"))

    def test_markdown_frontmatter_is_readonly_for_cursor_and_claude(self):
        claude = self.user("claude")
        reviewer = claude["tezgah-reviewer.md"]
        self.assertIn("# tezgah: managed", reviewer)
        # `readonly` stays for the Cursor editor, which reads ~/.claude/agents
        self.assertIn("readonly: true", reviewer)
        self.assertIn("disallowedTools:", reviewer)
        self.assertIn("codegraph_explore", reviewer)
        # a tier worker edits, so it is not marked read-only
        self.assertNotIn("readonly: true", claude["tezgah-cheap.md"])

    def test_every_codegraph_tool_a_brief_names_really_exists(self):
        # The generated reviewer once told the agent to run a tool the ToolSearch
        # select line - built from the same tool list - did not carry. On Claude,
        # where ToolSearch is what makes an MCP tool callable, the role named a
        # call it could not make. Claude's reviewer has no shell, so it names
        # MCP tools only, each one in its select line under both namespaces and
        # enabled by tezgah's server row; Codex's names CLI verbs that exist.
        rev = self.user("claude")["tezgah-reviewer.md"]
        select = rev[rev.index('ToolSearch("select:') + len('ToolSearch("select:'):]
        select = set(select[:select.index('"')].split(","))
        named = set(re.findall(r"`(codegraph_[a-z]+)`", rev)) | {"codegraph_explore"}
        enabled = {"codegraph_" + t for t in setup_mcp_tools()}
        for tool in named:
            for prefix in ("mcp__codegraph__", "mcp__plugin_tezgah_codegraph__"):
                self.assertIn(prefix + tool, select)
            self.assertIn(tool, enabled, "named a tool the server row does not enable")
        self.assertEqual(set(), set(re.findall(r"`codegraph ([a-z]+)", rev)),
                         "a no-shell role was told to run the CLI")
        codex = self.user("codex")["tezgah-reviewer.toml"]
        verbs = set(re.findall(r"`codegraph ([a-z]+)", codex))
        self.assertTrue(verbs, "the codex brief names no codegraph CLI verb")
        self.assertEqual(set(), verbs - set(CODEGRAPH_CLI_VERBS),
                         "named a verb codegraph does not answer")

    def test_a_no_shell_reviewer_gets_the_recipe_it_can_run(self):
        # Claude's `disallowedTools: ... Bash` and opencode's `bash: deny` leave
        # no shell, so `git diff` and the CLI are out of reach: the caller passes
        # the changed files and the role runs the MCP impact tool per symbol. A
        # role with a shell (Codex, omp) runs the diff and `codegraph impact`.
        self.sync()
        texts = {"claude": self.user("claude")["tezgah-reviewer.md"],
                 "opencode": self.read(OPENCODE, "tezgah-reviewer.md"),
                 "cursor": self.read(CURSOR, "tezgah-reviewer.md")}
        for host, text in texts.items():
            body = " ".join(text.split())
            self.assertIn("the caller passes the changed files", body, host)
            self.assertIn("`codegraph_impact` tool per changed symbol", body, host)
            self.assertNotIn("codegraph affected", body, host)
        codex = " ".join(self.user("codex")["tezgah-reviewer.toml"].split())
        self.assertIn("`git diff <target>`", codex)
        self.assertIn("`codegraph impact <symbol>` per changed symbol", codex)
        self.assertIn("codegraph affected --stdin", codex)

    def test_the_plugin_reviewer_is_the_generated_render(self):
        # agents/tezgah-reviewer.md was hand-kept and drifted from the role body
        # the generator writes; it is now rendered from that body
        # (`tezgah-setup --write-plugin-agents`), and the retired explorer's
        # plugin copy is gone with its role.
        out = tezgah_agents.plugin_agents()
        self.assertEqual(sorted(out), ["tezgah-reviewer.md"])
        with open(os.path.join(support.REPO, "agents", "tezgah-reviewer.md"),
                  encoding="utf-8") as fh:
            self.assertEqual(out["tezgah-reviewer.md"], fh.read(),
                             "run `python3 bin/tezgah-setup --write-plugin-agents`")
        self.assertEqual(sorted(os.listdir(os.path.join(support.REPO, "agents"))),
                         ["tezgah-reviewer.md"])

    def test_no_body_names_a_retired_role(self):
        self.sync()
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "omp", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        texts = [self.read(d, n) for d in (CURSOR, OPENCODE) for n in self.names(d)]
        texts += (list(self.user("claude").values()) + list(self.user("codex").values())
                  + list(out.values()))
        for text in texts:
            for retired in tezgah_agents.RETIRED_ROLES:
                self.assertNotIn(retired, text)

    def test_opencode_markdown_uses_native_frontmatter(self):
        self.sync()
        ex = self.read(OPENCODE, "tezgah-reviewer.md")
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
        ex = self.user("codex")["tezgah-reviewer.toml"]
        self.assertIn('name = "tezgah-reviewer"', ex)
        self.assertIn("description = '''", ex)
        self.assertIn("developer_instructions = '''", ex)
        self.assertIn('sandbox_mode = "read-only"', ex)
        self.assertNotIn("ToolSearch(", ex)

    def test_idempotent_second_run_writes_nothing_and_says_nothing(self):
        self.sync()
        before = self.read(CURSOR, "tezgah-reviewer.md")
        # no "N agent(s) current" line: a steady-state session must not be told
        # about tezgah's own files in this repo
        self.assertIsNone(self.sync())
        self.assertEqual(self.read(CURSOR, "tezgah-reviewer.md"), before)

    def test_omps_graph_roles_have_a_tool_that_runs_the_cli_they_name(self):
        # omp's MCP device refuses a subagent's call while the parent holds the
        # index, so the only graph such a role reaches is the CLI - and a tool
        # list of read/grep/glob could not run it
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "omp", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ("tezgah-reviewer.md",):
            text = out[name]
            head, _, body = text.partition("\n---\n")
            self.assertIn("  - bash", head, name)
            self.assertIn("`codegraph callers`", body, name)
            self.assertNotIn("xd://mcp__codegraph_explore", body)

    FLOOR = "An empty or short caller list is not proof that a change is safe"

    def test_every_graph_role_says_an_empty_caller_list_is_not_proof(self):
        # The index records only the edges its parser saw: a dynamic call, a
        # string dispatch or an unindexed script leaves no edge, so "no callers"
        # reads as "safe to change" unless the brief says otherwise - on every
        # host the role is generated for, and in the plugin's own copies.
        self.sync()
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "omp", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for role in ("reviewer",):
            plugin = os.path.join(support.REPO, "agents", "tezgah-%s.md" % role)
            with open(plugin, encoding="utf-8") as fh:
                texts = {"plugin": fh.read()}
            texts.update({
                "claude": self.user("claude")["tezgah-%s.md" % role],
                "opencode": self.read(OPENCODE, "tezgah-%s.md" % role),
                "codex": self.user("codex")["tezgah-%s.toml" % role],
                "omp": out["tezgah-%s.md" % role]})
            for host, text in texts.items():
                self.assertIn(self.FLOOR, " ".join(text.split()),
                              "%s on %s" % (role, host))

    BUDGET = ("One review per plan, over its whole diff in the verification phase; "
              "at most two rounds - only a confirmed critical or major finding opens "
              "round two, a minor or suggestion one is recorded fix-later, and after "
              "round two what is left goes to the user or is recorded fix-later, "
              "never a third round.")

    def test_the_reviewer_names_the_two_round_budget_on_every_host(self):
        # "the review ends when a round ..." had no cap, and any minor finding
        # opened another round: a finished plan was reviewed round after round.
        # The budget keeps no severe finding silent - after round two it goes to
        # the user - and `tezgah-task review` refuses a third round.
        # One rule, on every host and in the plugin's own copy.
        self.sync()
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "omp", "root": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plugin = os.path.join(support.REPO, "agents", "tezgah-reviewer.md")
        with open(plugin, encoding="utf-8") as fh:
            texts = {"plugin": fh.read()}
        texts.update({
            "claude": self.user("claude")["tezgah-reviewer.md"],
            "opencode": self.read(OPENCODE, "tezgah-reviewer.md"),
            "codex": self.user("codex")["tezgah-reviewer.toml"],
            "omp": out["tezgah-reviewer.md"]})
        for host, text in texts.items():
            flat = " ".join(text.split())
            self.assertIn(self.BUDGET, flat, host)
            self.assertNotIn("confirms none", flat, host)

    def test_the_contract_policy_and_plan_sync_say_the_reviewers_budget(self):
        # four hand-kept copies of one rule drift apart one at a time: the agent
        # text looped while the CLI printed two rounds
        import tezgah_policy as policy
        texts = {"policy": policy.EXEC}
        for rel in (("skills", "tezgah-contract", "SKILL.md"),
                    ("skills", "plan-sync", "SKILL.md")):
            with open(os.path.join(support.REPO, *rel), encoding="utf-8") as fh:
                texts[rel[1]] = fh.read()
        for name, text in texts.items():
            flat = " ".join(text.split())
            self.assertIn(self.BUDGET, flat, name)
            self.assertNotIn("confirms none", flat, name)

    def test_a_tier_worker_may_not_widen_or_narrow_its_own_scope(self):
        # A delegate that answered a wider or narrower question than it was
        # handed is read as an answer to the one asked; the brief forbids the
        # redefinition and makes the worker report the mismatch instead.
        claude = self.user("claude")
        for tier in ("cheap", "standard", "frontier"):
            body = " ".join(claude["tezgah-%s.md" % tier].split())
            self.assertIn("Never widen or narrow the brief's scope", body, tier)

    def test_cursor_gets_a_render_its_line_parser_reads(self):
        # cursor-agent splits each frontmatter line at its first ':' (no YAML):
        # a folded `description: >` read as ">", `model: opus` went through as
        # an id its model list lacks, and `effort` is no key there
        self.sync()
        names = self.names(CURSOR)
        self.assertTrue(names)
        for name in names:
            head = self.read(CURSOR, name).split("\n---\n", 1)[0].split("\n")
            fields = dict(line.split(":", 1) for line in head[1:]
                          if line and not line.startswith("#"))
            fields = {k.strip(): v.strip() for k, v in fields.items()}
            self.assertEqual(fields["name"], name[:-len(".md")])
            self.assertNotIn(fields["description"], ("", ">"), name)
            self.assertEqual(fields["model"], "inherit", name)
            for key in ("effort", "tools", "disallowedTools"):
                self.assertNotIn(key, fields, name)
        self.assertIn("readonly: true", self.read(CURSOR, "tezgah-reviewer.md"))
        self.assertIn("readonly: true", self.read(CURSOR, "tezgah-security.md"))
        self.assertNotIn("readonly", self.read(CURSOR, "tezgah-cheap.md"))
        # ToolSearch is Claude's deferred-tool loader, not a Cursor tool
        self.assertNotIn("ToolSearch(", self.read(CURSOR, "tezgah-reviewer.md"))

    def test_the_claude_description_is_one_line(self):
        # the Cursor editor reads ~/.claude/agents with the same kind of line
        # parser; Claude's own parser re-quotes a plain value that YAML rejects
        for name, text in self.user("claude").items():
            line = next(ln for ln in text.split("\n") if ln.startswith("description:"))
            self.assertNotEqual(line.strip(), "description: >", name)
            self.assertGreater(len(line), len("description: ") + 20, name)

    def test_claude_and_codex_get_no_per_repo_file_and_lose_an_older_ones(self):
        # a repo dir written at session start is not watched by Claude and is
        # read at config load by Codex (only in a trusted repo): the roles live
        # user-level now, and a copy an older tezgah left would sit beside them
        stale = "---\n# tezgah: managed by tezgah-agents; do not edit\nname: x\n---\nx\n"
        for d, name in ((CLAUDE, "tezgah-cheap.md"), (CODEX, "tezgah-cheap.toml")):
            os.makedirs(os.path.join(self.repo, d), exist_ok=True)
            with open(os.path.join(self.repo, d, name), "w") as fh:
                fh.write(stale)
            with open(os.path.join(self.repo, d, "tezgah-mine.md"), "w") as fh:
                fh.write("---\nname: tezgah-mine\n---\nmine\n")
        self.assertIn("removed", self.sync())
        self.assertEqual(self.names(CLAUDE), ["tezgah-mine.md"])
        self.assertEqual(self.names(CODEX), ["tezgah-mine.md"])


class OpencodeConfig(AgentsBase):
    def test_json_exposes_subagents_and_an_orchestrator(self):
        data = self.opencode_json()
        agent = data["agent"]
        self.assertEqual(agent["tezgah-reviewer"]["mode"], "subagent")
        self.assertEqual(agent["tezgah-reviewer"]["permission"]["edit"], "deny")
        self.assertIn("prompt", agent["tezgah-reviewer"])
        orch = agent["tezgah-orchestrator"]
        self.assertEqual(orch["mode"], "primary")
        self.assertEqual(orch["permission"]["task"]["*"], "deny")
        self.assertEqual(orch["permission"]["task"]["tezgah-*"], "allow")

    def test_json_holds_every_ungated_role_without_capabilities(self):
        data = self.opencode_json(
            extra={"TEZGAH_CODEGRAPH_BIN": self.pathless(),
                   "TEZGAH_ORX_BIN": self.pathless()}, consult=False)
        self.assertEqual(sorted(data["agent"]),
                         ["tezgah-cheap", "tezgah-docs", "tezgah-frontier",
                          "tezgah-orchestrator", "tezgah-researcher",
                          "tezgah-security", "tezgah-standard", "tezgah-tester",
                          "tezgah-ui"])

    def pathless(self):
        return os.path.join(self.home, "nope")


class Exclude(AgentsBase):
    """Generated agent dirs are machine-specific, so they are ignored through the
    clone's own `info/exclude`: a session must hand the repo back with nothing
    modified, and `.gitignore` is tracked, so it is never written."""

    def setUp(self):
        super().setUp()
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       capture_output=True)

    def gi(self):
        path = os.path.join(self.repo, ".gitignore")
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            return fh.read()

    def ex(self):
        with open(os.path.join(self.repo, ".git", "info", "exclude")) as fh:
            return fh.read()

    def status(self):
        return subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                              capture_output=True, text=True).stdout

    def test_a_tracked_gitignore_comes_back_untouched(self):
        # the reported defect: a repo unrelated to tezgah was left dirty with
        # ` M .gitignore` after a session start
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n")
        self.sync()
        self.assertEqual(self.gi(), "node_modules/\n")

    def test_generated_files_are_not_untracked_noise(self):
        self.sync()
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))
        status = self.status()
        for noise in (".cursor", ".opencode", ".gitignore"):
            self.assertNotIn(noise, status, status)
        text = self.ex()
        for d in ("/.cursor/agents/", "/.opencode/agents/"):
            self.assertIn(d, text)

    def test_block_is_idempotent(self):
        self.sync()
        once = self.ex()
        self.sync()
        self.assertEqual(self.ex(), once)
        self.assertEqual(once.count("# tezgah: generated agents"), 1)

    def test_block_unions_and_never_drops_a_dir(self):
        # a prior run ignored both; a config that now lists only opencode must
        # not un-ignore the cursor dir
        self.sync()
        self.config({"hosts": ["opencode"]})
        self.sync()
        text = self.ex()
        for d in ("/.cursor/agents/", "/.opencode/agents/"):
            self.assertIn(d, text)

    def test_a_block_that_sits_mid_file_stays_where_it_is(self):
        # rebuilding the file around the block used to move it to the end and
        # dirty the tree with a pure move
        path = os.path.join(self.repo, ".git", "info", "exclude")
        with open(path, "w") as fh:
            fh.write("*.orig\n\n"
                     "# tezgah: generated agents (managed; removed by "
                     "tezgah-setup --uninstall)\n"
                     "/.claude/agents/\n"
                     "# tezgah: end generated agents\n\n"
                     "dist/\n")
        self.sync()
        text = self.ex()
        self.assertLess(text.index("# tezgah: end generated agents"),
                        text.index("dist/"))
        self.assertIn("*.orig", text)
        once = self.ex()
        self.sync()
        self.assertEqual(self.ex(), once)

    def test_cleanup_strips_the_block_but_keeps_every_other_line(self):
        path = os.path.join(self.repo, ".git", "info", "exclude")
        with open(path, "a") as fh:
            fh.write("*.orig\n")
        self.sync()
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "cleanup"},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(out, 0)
        text = self.ex()
        self.assertIn("*.orig", text)
        self.assertNotIn("# tezgah: generated agents", text)

    def test_cleanup_still_clears_a_gitignore_an_older_install_edited(self):
        # installs before this change recorded the repo's .gitignore; --uninstall
        # must still take tezgah's block out of it
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n")
        self.sync()
        state = os.path.join(self.home, ".config", "tezgah", "agents.state.json")
        with open(state) as fh:
            data = json.load(fh)
        for paths in data.values():
            paths.append(os.path.join(self.repo, ".gitignore"))
        with open(state, "w") as fh:
            json.dump(data, fh)
        with open(os.path.join(self.repo, ".gitignore"), "a") as fh:
            fh.write("\n# tezgah: generated agents (managed; removed by "
                     "tezgah-setup --uninstall)\n/.claude/agents/\n"
                     "# tezgah: end generated agents\n")
        run_json([support.PROBE_AGENTS], {"fn": "cleanup"}, env=self.env())
        self.assertEqual(self.gi(), "node_modules/\n")

    def test_no_exclude_outside_a_git_repo(self):
        shutil.rmtree(os.path.join(self.repo, ".git"))
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n")
        self.sync()
        self.assertEqual(self.gi(), "node_modules/\n")
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))

    def test_the_exclude_write_can_be_opted_out(self):
        self.sync(extra={"TEZGAH_NO_EXCLUDE": "1"})
        self.assertNotIn("# tezgah: generated agents", self.ex())
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))

    def test_an_unwritable_exclude_does_not_fail_the_session(self):
        # the module promises every write fails open: the exclude write runs
        # inside sync_root, so an unwritable .git/info used to abort the sync
        # before it reported, and the CLI exited 1 with a traceback
        os.chmod(os.path.join(self.repo, ".git", "info"), 0o555)
        self.addCleanup(os.chmod, os.path.join(self.repo, ".git", "info"), 0o755)
        note = self.sync()
        self.assertIn("written", note)
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))


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
        self.assertEqual(agent["tezgah-reviewer"]["mode"], "subagent")
        self.assertEqual(agent["tezgah-reviewer"]["permission"]["edit"], "deny")
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
    def test_no_capability_writes_only_the_ungated_roles(self):
        # routing needs no capability, so the tier workers, the specialists and
        # the orchestrator that names them are written even with no code graph
        env = self.env(extra={"TEZGAH_CODEGRAPH_BIN": self.pathless(),
                              "TEZGAH_ORX_BIN": self.pathless()}, consult=False)
        out, proc = run_json([support.PROBE_AGENTS],
                             {"fn": "sync_root", "root": self.repo}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, "8 agent(s) written")
        self.assertNotIn("tezgah-reviewer.md", self.names(CURSOR))
        self.assertIn("tezgah-tester.md", self.names(CURSOR))

    def pathless(self):
        return os.path.join(self.home, "nope")

    def test_missing_capability_removes_its_agent(self):
        self.sync()
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))
        note = self.sync(extra={"TEZGAH_CODEGRAPH_BIN": self.pathless()})
        self.assertNotIn("reviewer", " ".join(self.names(CURSOR)))
        self.assertIn("removed", note)
        self.assertTrue(self.exists(CURSOR, "tezgah-cheap.md"))

    def test_agents_off_kill_switch(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "agents-off"))
        self.assertIsNone(self.sync())
        self.assertEqual(self.names(CURSOR), [])

    def test_agents_off_sweeps_what_an_earlier_session_wrote(self):
        # the switch used to return before the sweep, so the files it was meant
        # to turn off stayed for every host to keep loading
        self.sync()
        self.assertTrue(self.names(CURSOR))
        self.touch(os.path.join(self.home, ".config", "tezgah", "agents-off"))
        self.assertIn("removed", self.sync())
        for d in (CURSOR, OPENCODE):
            self.assertEqual(self.names(d), [], d)

    def test_a_retired_roles_managed_file_is_swept(self):
        # tezgah-explorer and -verifier left ROLES; their managed copies from an
        # earlier session must stop being loaded
        self.sync()
        stale = '---\n# tezgah: managed by tezgah-agents; do not edit\nname: x\n---\nx\n'
        for d, ext in ((CURSOR, ".md"), (OPENCODE, ".md")):
            for role in ("explorer", "verifier"):
                with open(os.path.join(self.repo, d, "tezgah-%s%s" % (role, ext)), "w") as fh:
                    fh.write(stale)
        self.assertIn("removed", self.sync())
        for d in (CURSOR, OPENCODE):
            for role in ("explorer", "verifier"):
                self.assertNotIn("tezgah-" + role, " ".join(self.names(d)), d)

    def test_steering_names_no_retired_role_and_honours_no_graph(self):
        self.sync()
        line = self.steer()
        self.assertIn("-> tezgah-reviewer", line)
        self.touch(os.path.join(self.repo, ".no-graph"))
        line = self.steer()
        self.assertNotIn("tezgah-reviewer", line)
        self.assertIn("-> tezgah-cheap", line)

    def test_agents_off_empties_the_user_level_set(self):
        # the installer writes this set and sweeps what it no longer holds, so
        # an empty set is how the switch reaches ~/.claude and $CODEX_HOME
        self.assertTrue(self.user("claude"))
        self.touch(os.path.join(self.home, ".config", "tezgah", "agents-off"))
        self.assertEqual(self.user("claude"), {})
        self.assertEqual(self.user("codex"), {})

    def test_steering_reads_the_dir_each_host_loads(self):
        # Claude and Codex load their user dirs; Cursor only the repo's own
        # `.cursor/agents`; the `.no-graph` rule holds for every host
        for host, home in (("claude", ".claude"), ("codex", ".codex")):
            self.assertIsNone(self.steer(host), host)
            for name, text in self.user(host).items():
                path = os.path.join(self.home, home, "agents", name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as fh:
                    fh.write(text)
            self.assertIn("-> tezgah-reviewer", self.steer(host), host)
        self.assertIsNone(self.steer("cursor"))
        self.sync()
        self.assertIn("-> tezgah-reviewer", self.steer("cursor"))
        self.touch(os.path.join(self.repo, ".no-graph"))
        for host in ("claude", "codex", "cursor"):
            line = self.steer(host)
            self.assertNotIn("tezgah-reviewer", line, host)
            self.assertIn("-> tezgah-cheap", line, host)


class Cleanup(AgentsBase):
    def test_removes_only_managed_files(self):
        self.sync()
        own = os.path.join(self.repo, CURSOR, "my-own.md")
        with open(own, "w") as fh:
            fh.write("---\nname: my-own\n---\nx\n")
        out, proc = run_json([support.PROBE_AGENTS], {"fn": "cleanup"},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(out, 0)
        self.assertEqual(self.names(CURSOR), ["my-own.md"])
        self.assertEqual(self.names(OPENCODE), [])
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
        self.assertEqual(out["caps"], {"graph": True})
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
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))
        self.config({"hosts": ["omp"]})
        self.sync()
        self.assertEqual(self.names(CURSOR), [])
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

    def test_no_graph_marker_disables_the_graph_capability(self):
        self.touch(os.path.join(self.repo, ".no-graph"))
        out, _ = run_json([support.PROBE_AGENTS],
                          {"fn": "detect", "root": self.repo}, env=self.env())
        self.assertFalse(out["caps"]["graph"])


class ContextWiring(AgentsBase):
    """SessionStart must announce and generate the set in the injected context."""

    def test_session_start_injects_a_subagent_note(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": self.repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Subagents (this repo, generated)", out)
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))

    def test_only_session_start_generates(self):
        run_json([support.PROBE_CONTEXT],
                 {"fn": "context_for", "event": "user_prompt", "cwd": self.repo},
                 env=self.env())
        self.assertEqual(self.names(CURSOR), [])

    def test_setup_agents_flag_regenerates(self):
        setup = os.path.join(support.REPO, "bin", "tezgah-setup")
        proc = subprocess.run([sys.executable, setup, "--agents", self.repo],
                              capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("agent(s)", proc.stdout)
        self.assertTrue(self.exists(CURSOR, "tezgah-reviewer.md"))

    def test_the_agents_flag_reports_a_steady_state(self):
        # the command answers a user, so it says "current" instead of the
        # "outside a root, or no capability" line the silent hook path shares
        self.sync()
        setup = os.path.join(support.REPO, "bin", "tezgah-setup")
        proc = subprocess.run([sys.executable, setup, "--agents", self.repo],
                              capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("9 agent(s) current", proc.stdout)


if __name__ == "__main__":
    unittest.main()
