"""`tezgah-doctor --stack`: the per-host effective stack and its conflicts.

Every case runs the doctor in a throwaway HOME whose env is built from scratch,
so CODEX_HOME, DSH_HOME and XDG_* from the caller's shell (Orca exports
CODEX_HOME) never point it at the machine's real host dirs.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCTOR = os.path.join(REPO, "bin", "tezgah-doctor")
BLOCK = "<!-- tezgah:start -->\nrule\n<!-- tezgah:end -->\n"


class Stack(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = os.path.realpath(tmp.name)
        self.repo = self.path("Projects", "app")
        os.makedirs(self.repo)
        for d in (".claude", ".codex", ".cursor", ".omp", ".dsh", ".config/opencode"):
            os.makedirs(self.path(d), exist_ok=True)

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def skill(self, base, name, body):
        self.put(os.path.join(base, name, "SKILL.md"),
                 "---\nname: %s\ndescription: x\n---\n%s\n" % (name, body))

    def stack(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.home, "LANG": "C.UTF-8",
               "TEZGAH_UPDATE_CHECK": "0"}
        proc = subprocess.run([sys.executable, DOCTOR, "--stack", "--json",
                               "--repo", self.repo], capture_output=True,
                              text=True, env=env, timeout=60)
        self.assertIn(proc.returncode, (0, 1), proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        kinds = {host: sorted({k for k, _ in s["conflicts"]}) for host, s in data.items()}
        return proc.returncode, data, kinds

    def test_a_clean_home_reports_no_conflict(self):
        omp_skills = self.path(".omp", "agent", "skills")
        self.skill(omp_skills, "solo", "one copy")
        code, data, kinds = self.stack()
        self.assertEqual(code, 0, kinds)
        self.assertTrue(all(not k for k in kinds.values()), kinds)
        self.assertEqual(data["omp"]["skill_dirs"], [[omp_skills, 1]])

    def test_colliding_skills_hooks_rules_and_backups_are_flagged(self):
        agent = self.path(".omp", "agent")
        # omp keeps the first copy of a name: its native dir before ~/.agents
        self.skill(os.path.join(agent, "skills"), "deploy", "omp copy")
        self.skill(self.path(".agents", "skills"), "deploy", "agents copy")
        # a shipped tezgah skill whose bytes are not this tree's
        self.skill(os.path.join(agent, "skills"), "ponytail", "an old copy")
        # Cursor reads ~/.cursor/skills and ~/.codex/skills and lists both
        self.skill(self.path(".cursor", "skills"), "twin", "same")
        self.skill(self.path(".codex", "skills"), "twin", "same")
        # two context files omp loads both carry the tezgah block
        self.put(os.path.join(agent, "RULES.md"), BLOCK)
        self.put(os.path.join(self.repo, "AGENTS.md"), BLOCK)
        # a backup beside the bridge, inside the dir omp's hooks capability lists
        self.put(os.path.join(agent, "hooks", "pre", "tezgah-hook.ts"), "//")
        self.put(os.path.join(agent, "hooks", "pre", "tezgah-hook.ts.tezgah-bak"), "//")
        # one tezgah command registered twice for one Cursor event
        cmd = {"command": "python3 /x/tezgah/hosts/cursor/hook.py"}
        self.put(self.path(".cursor", "hooks.json"),
                 json.dumps({"hooks": {"stop": [cmd, cmd, {"command": "sh ~/.orca/x.sh"}]}}))
        # one MCP name from the project and from the plugin copy, and an orphan copy
        cache = self.path(".claude", "plugins", "cache", "local", "tezgah")
        live, old = os.path.join(cache, "1.0.0"), os.path.join(cache, "0.9.0")
        for d in (live, old):
            self.put(os.path.join(d, ".mcp.json"), json.dumps({"mcpServers": {"tezgah": {}}}))
        self.put(self.path(".claude", "plugins", "installed_plugins.json"),
                 json.dumps({"plugins": {"tezgah@local": [{"installPath": live}]}}))
        self.put(os.path.join(self.repo, ".mcp.json"), json.dumps({"mcpServers": {"tezgah": {}}}))

        code, data, kinds = self.stack()
        self.assertEqual(code, 1)
        self.assertEqual(kinds["omp"], ["backup-in-scan", "rule-twice",
                                        "skill-differs", "skill-stale"], data["omp"])
        differs = [d for k, d in data["omp"]["conflicts"] if k == "skill-differs"]
        self.assertIn("(wins: %s)" % os.path.join(agent, "skills"), differs[0])
        self.assertEqual(kinds["cursor"], ["hook-twice", "skill-dup"], data["cursor"])
        self.assertEqual(kinds["claude"], ["mcp-twice", "orphan-copy"], data["claude"])
        self.assertIn([old], [[d] for k, d in data["claude"]["conflicts"] if k == "orphan-copy"])
        # the hook order is the file's: Orca's entry after tezgah's two
        owners = [row[0] for row in data["cursor"]["hooks"]["stop"]]
        self.assertEqual(owners, ["tezgah", "tezgah", "orca"])


if __name__ == "__main__":
    unittest.main()
