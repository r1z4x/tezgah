"""bin/tezgah-setup: install wiring, idempotency, uninstall, adopt.

Every test runs the installer in a throwaway HOME with fake host dirs, so the
real ~/.claude, ~/.codex, ~/.config/opencode, ~/.cursor and ~/.dsh are never
touched. TEZGAH_CBM_BIN points at nothing so no graph is registered.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")
ALL = "claude,codex,opencode,cursor,dsh,omp"


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
            # orx off by default so an installed orx on the test machine cannot
            # run its real installer; a test that wants it points at a fake
            "TEZGAH_ORX_BIN": os.path.join(self.home, "no-such-orx"),
            # never let a test hit the network: --install installs missing deps
            # by default, so the suite opts out and the Deps tests exercise it
            "TEZGAH_NO_DEPS": "1",
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
        for name in ("consult", "codegen", "tezgah-status", "tezgah-index",
                     "tezgah-codex-hook", "tezgah-cursor-hook", "tezgah-statusline"):
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
        self.assertTrue((oc.get("compaction") or {}).get("prune"))
        self.assertIn("node_modules/**", (oc.get("watcher") or {}).get("ignore", []))
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
        self.assertEqual(len(oc.get("instructions", [])), 2)

    def test_opencode_skill_router_and_deny(self):
        # a skill in an external dir must be indexed, categorized and by path
        sk = self.path(".claude", "skills", "acme-widget", "SKILL.md")
        os.makedirs(os.path.dirname(sk), exist_ok=True)
        with open(sk, "w") as fh:
            fh.write("---\nname: acme-widget\n"
                     "description: Use when the user needs an acme widget. More.\n"
                     "---\n\nbody\n")
        self.setup("--install", "--hosts", "opencode")

        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertEqual((oc.get("permission") or {}).get("skill"), "deny")
        router = self.path(".config", "tezgah", "opencode-skills.md")
        full = self.path(".config", "tezgah", "opencode-skills.full.md")
        self.assertTrue(os.path.isfile(router))
        self.assertIn(router, oc.get("instructions", []))
        self.assertNotIn(full, oc.get("instructions", []))
        body = self.read_text(router)
        # the always-on router carries the coding buckets and points at the full
        # list; a marketing skill lives only in the full file
        self.assertIn("tezgah core", body)
        self.assertIn("marketing & growth:", body)
        self.assertIn(full, body)
        self.assertNotIn("acme-widget", body)
        self.assertTrue(os.path.isfile(full))
        self.assertIn("acme-widget", self.read_text(full))
        self.assertIn("harness", body)
        self.assertIn("analyze-app", body)


    def test_opencode_context_hygiene_respects_user_choice(self):
        self.write_json(self.path(".config", "opencode", "opencode.json"),
                        {"$schema": "https://opencode.ai/config.json",
                         "compaction": {"prune": False}})
        self.setup("--install", "--hosts", "opencode")
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertIs(oc["compaction"]["prune"], False)
        self.assertIn(".git/**", oc["watcher"]["ignore"])

    def test_apps_mcp_wired_optional_devtools_and_removable(self):
        self.setup("--install", "--hosts", ALL)
        self.assertTrue(os.path.isdir(self.path(".cache", "tezgah", "apps")))
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertIn("playwright", oc["mcp"])
        self.assertIn("mobile-mcp", oc["mcp"])
        cur = self.read_json(self.path(".cursor", "mcp.json"))
        self.assertIn("playwright", cur["mcpServers"])
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.assertIn("[mcp_servers.playwright]", toml)
        self.assertIn("[mcp_servers.mobile-mcp]", toml)
        self.assertNotIn("chrome-devtools", toml)  # opt-in only
        dsh = self.read_text(self.path(".dsh", "cordis.patch.yml"))
        self.assertIn("serverName: playwright", dsh)
        self.assertIn("serverName: mobile-mcp", dsh)
        self.assertIn("'@playwright/mcp@latest'", dsh)

        # re-install is idempotent: no duplicated server tables
        self.setup("--install", "--hosts", ALL)
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.assertEqual(toml.count("[mcp_servers.playwright]"), 1)

        # --devtools adds the optional browser diagnostics server
        self.setup("--install", "--hosts", "codex", "--devtools")
        self.assertIn("[mcp_servers.chrome-devtools]",
                      self.read_text(self.path(".codex", "config.toml")))

        # uninstall removes tezgah's app servers, keeps the code graph
        self.setup("--uninstall", "--hosts", ALL)
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.assertNotIn("[mcp_servers.playwright]", toml)
        self.assertNotIn("[mcp_servers.chrome-devtools]", toml)
        self.assertIn("mcp_servers.codebase-memory-mcp", toml)
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertNotIn("playwright", oc.get("mcp") or {})
        self.assertIn("codebase-memory-mcp", oc.get("mcp") or {})
        cur = self.read_json(self.path(".cursor", "mcp.json"))
        self.assertNotIn("playwright", cur["mcpServers"])
        self.assertIn("codebase-memory-mcp", cur["mcpServers"])


class OpenResearch(SetupBase):
    """--install triggers orx's own skill installer for the hosts it supports."""

    def fake_orx(self):
        log = self.path("orx-args.log")
        script = self.path("fake-orx")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\necho "$@" >> "%s"\n' % log)
        os.chmod(script, 0o755)
        self.env["TEZGAH_ORX_BIN"] = script
        return log

    def test_install_runs_orx_for_supported_hosts_only(self):
        log = self.fake_orx()
        proc = self.setup("--install", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self.read_text(log)
        for agent in ("claude", "codex", "opencode", "cursor"):
            self.assertIn("install-skills --agent " + agent, calls)
        self.assertNotIn("agent dsh", calls)
        self.assertIn("orx has no harness for this host", proc.stdout)

    def test_install_skips_orx_gracefully_when_absent(self):
        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("orx not on PATH - skipped", proc.stdout)


class Deps(SetupBase):
    """--deps installs missing optional tools; --install does it by default."""

    def setUp(self):
        super().setUp()
        self.env.pop("TEZGAH_NO_DEPS", None)  # this class wants deps enabled

    def fakebin(self, *names):
        """A PATH holding only these stubs, so a real tool on the machine (e.g.
        an installed cursor-agent) cannot change the outcome."""
        d = self.path("fakebin")
        os.makedirs(d, exist_ok=True)
        for name in names:
            p = os.path.join(d, name)
            with open(p, "w") as fh:
                fh.write('#!/bin/sh\necho "$@" >> "%s"\n' % self.path("deps.log"))
            os.chmod(p, 0o755)
        self.env["PATH"] = d
        return self.path("deps.log")

    def test_dry_run_lists_the_vendors_installers(self):
        shutil.rmtree(self.path(".dsh"))  # make dsh missing too
        self.fakebin("sh", "bash", "npx", "curl", "npm")
        proc = self.setup("--deps", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("openresearch.sh/install.sh", proc.stdout)
        self.assertIn("cursor.com/install", proc.stdout)
        self.assertIn("@deepseek-ai/dsh", proc.stdout)
        self.assertIn("install -g pnpm", proc.stdout)
        self.assertIn("would run", proc.stdout)
        self.assertFalse(os.path.exists(self.path("deps.log")))
        self.assertFalse(os.path.isdir(self.path(".dsh")))
        self.assertFalse(os.path.exists(self.path(".config", "tezgah", "install.log")))

    def test_installs_missing_tools_with_their_own_commands(self):
        shutil.rmtree(self.path(".dsh"))
        log = self.fakebin("sh", "bash", "npx", "curl", "npm")
        proc = self.setup("--deps")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self.read_text(log)
        self.assertIn("openresearch.sh/install.sh", calls)
        self.assertIn("cursor.com/install", calls)
        self.assertIn("@deepseek-ai/dsh", calls)
        self.assertIn("install -g pnpm", calls)
        self.assertIn("orx:", self.read_text(self.path(".config", "tezgah", "install.log")))

    def test_reports_already_present(self):
        self.env["TEZGAH_ORX_BIN"] = sys.executable  # a real file -> present
        d = self.path("fakebin")
        os.makedirs(d, exist_ok=True)
        for name in ("cursor-agent", "pnpm"):
            p = os.path.join(d, name)
            with open(p, "w") as fh:
                fh.write("#!/bin/sh\n")
            os.chmod(p, 0o755)
        self.env["PATH"] = d
        proc = self.setup("--deps")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("all optional tools present", proc.stdout)

    def test_missing_helper_is_reported_not_attempted(self):
        shutil.rmtree(self.path(".dsh"))
        self.env["PATH"] = self.path("emptybin")  # no curl/sh/bash/npx
        os.makedirs(self.env["PATH"], exist_ok=True)
        proc = self.setup("--deps")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("is not on PATH", proc.stdout)

    def test_install_no_deps_reports_the_skip(self):
        proc = self.setup("--install", "--hosts", "claude", "--no-deps")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("deps skipped", proc.stdout)

    def test_install_runs_deps_by_default(self):
        log = self.fakebin("sh", "bash", "npx", "curl")
        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self.read_text(log)
        self.assertIn("openresearch.sh/install.sh", calls)
        self.assertIn("cursor.com/install", calls)


class DshChecks(SetupBase):
    """The two dsh LLM routes are reported separately and read the provider key
    files tezgah already uses, so a single-provider setup is not shown broken."""

    def row(self, text, label):
        return next((line for line in text.splitlines() if label in line), "")

    def test_routes_are_per_provider_and_read_config_key_files(self):
        os.makedirs(self.path(".config", "openrouter"), exist_ok=True)
        open(self.path(".config", "openrouter", "key"), "w").close()
        proc = self.setup("--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        openrouter = self.row(proc.stdout, "OpenRouter route key resolvable")
        deepseek = self.row(proc.stdout, "DeepSeek route key resolvable")
        self.assertTrue(openrouter, "OpenRouter row missing")
        self.assertTrue(deepseek, "DeepSeek row missing")
        self.assertTrue(openrouter.strip().startswith("ok"))
        self.assertTrue(deepseek.strip().startswith("MISS"))


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

    def test_uninstall_drops_skill_router_and_deny(self):
        self.setup("--install", "--hosts", "opencode")
        self.setup("--uninstall", "--hosts", "opencode")
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertNotIn("permission", oc)
        self.assertNotIn("compaction", oc)
        self.assertNotIn("watcher", oc)
        self.assertFalse(oc.get("instructions"))
        for name in ("opencode-skills.md", "opencode-skills.full.md"):
            self.assertFalse(os.path.exists(self.path(".config", "tezgah", name)), name)


class Refresh(SetupBase):
    """--refresh re-renders the generated opencode contract in-session when the
    policy or the full-contract skill changed, without a reinstall."""

    def contract_sha(self):
        h = hashlib.sha256()
        for rel in ("hooks/tezgah_policy.py", "skills/tezgah-contract/SKILL.md"):
            with open(os.path.join(REPO, rel), "rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
        return h.hexdigest()

    def test_stored_hash_covers_policy_and_skill(self):
        self.setup("--install", "--hosts", "opencode")
        stored = self.read_text(
            self.path(".config", "tezgah", "contract.sha256")).strip()
        self.assertEqual(stored, self.contract_sha())

    def test_refresh_rerenders_a_stale_contract(self):
        self.setup("--install", "--hosts", "opencode")
        sha = self.path(".config", "tezgah", "contract.sha256")
        contract = self.path(".config", "tezgah", "opencode-contract.md")
        with open(sha, "w") as fh:
            fh.write("stale\n")
        os.remove(contract)
        proc = self.setup("--refresh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("refreshed", proc.stdout)
        self.assertTrue(os.path.exists(contract))
        self.assertIn("generated by tezgah-setup", self.read_text(contract))
        self.assertEqual(self.read_text(sha).strip(), self.contract_sha())

    def test_refresh_is_a_noop_when_current(self):
        self.setup("--install", "--hosts", "opencode")
        contract = self.path(".config", "tezgah", "opencode-contract.md")
        before = self.read_text(contract)
        proc = self.setup("--refresh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("current", proc.stdout)
        self.assertEqual(self.read_text(contract), before)


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


class DshStatusline(SetupBase):
    """The dsh web status line: the plugin is linked into the web profile and
    enabled by a managed patch row there, not in the shared home patch."""

    def fake_node(self):
        """A PATH `node` that logs its args and links the plugin for a
        `dsh plugin ... add link:` call, so the wiring is testable without a
        real dsh/pnpm install."""
        d = self.path("fakebin")
        os.makedirs(d, exist_ok=True)
        node = os.path.join(d, "node")
        with open(node, "w") as fh:
            fh.write(
                '#!/bin/sh\n'
                'echo "$@" >> "$HOME/dsh-args.log"\n'
                'dest="$HOME/.dsh/profiles/web/node_modules/tezgah-dsh-statusline"\n'
                'case " $* " in *" remove "*) rm -rf "$dest"; exit 0;; esac\n'
                'for a in "$@"; do case "$a" in link:*) pkg="${a#link:}";; esac; done\n'
                'if [ -n "$pkg" ]; then mkdir -p "$(dirname "$dest")" && ln -sfn "$pkg" "$dest"; fi\n')
        os.chmod(node, 0o755)
        self.env["PATH"] = d + os.pathsep + self.env["PATH"]
        cli = self.path(".dsh", "profiles", "node_modules", "@deepseek-ai",
                        "dsh", "lib", "bin.js")
        os.makedirs(os.path.dirname(cli), exist_ok=True)
        with open(cli, "w"):
            pass
        return self.path("dsh-args.log")

    def test_install_links_and_enables_statusline(self):
        # no web profile yet: the status line is skipped, never half-written
        proc = self.setup("--install", "--hosts", "dsh")
        self.assertIn("web profile not initialized", proc.stdout)
        self.assertFalse(os.path.exists(
            self.path(".dsh", "profiles", "web", "cordis.patch.yml")))

        self.write_json(self.path(".dsh", "profiles", "web", "package.json"),
                        {"name": "dsh-profile-web"})
        log = self.fake_node()
        proc = self.setup("--install", "--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        patch_path = self.path(".dsh", "profiles", "web", "cordis.patch.yml")
        patch = self.read_text(patch_path)
        self.assertEqual(patch.count("# tezgah:start"), 1)
        self.assertIn("tezgah-dsh-statusline", patch)
        # the row lives in the web profile, never the shared home patch
        self.assertNotIn("tezgah-dsh-statusline",
                         self.read_text(self.path(".dsh", "cordis.patch.yml")))
        self.assertIn(
            "plugin --profile web add link:" + os.path.join(
                REPO, "hosts", "dsh", "statusline"),
            self.read_text(log))
        plug = self.path(".dsh", "profiles", "web", "node_modules",
                         "tezgah-dsh-statusline")
        self.assertTrue(os.path.islink(plug))

        self.setup("--install", "--hosts", "dsh")
        self.assertEqual(self.read_text(patch_path).count("# tezgah:start"), 1)

    def test_uninstall_drops_statusline(self):
        self.write_json(self.path(".dsh", "profiles", "web", "package.json"),
                        {"name": "dsh-profile-web"})
        log = self.fake_node()
        self.setup("--install", "--hosts", "dsh")
        proc = self.setup("--uninstall", "--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("plugin --profile web remove tezgah-dsh-statusline",
                      self.read_text(log))
        self.assertFalse(os.path.exists(
            self.path(".dsh", "profiles", "web", "node_modules",
                      "tezgah-dsh-statusline")))
        patch = self.path(".dsh", "profiles", "web", "cordis.patch.yml")
        if os.path.exists(patch):
            text = self.read_text(patch)
            self.assertNotIn("# tezgah:start", text)
            # a dsh patch layer must stay a top-level YAML array
            self.assertIn("[]", text)

    def test_plugin_bundles_are_valid_js(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        for f in ("lib/index.js", "lib/client.js"):
            p = os.path.join(REPO, "hosts", "dsh", "statusline", f)
            proc = subprocess.run([node, "--check", p],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, "%s: %s" % (f, proc.stderr))


class OmpHost(SetupBase):
    """omp is a first-class host: always-on RULES.md, skills, agents, MCP, gate."""

    def install(self):
        # a real cbm binary makes the graph-backed roles active, so the agent
        # set is generated
        self.env["TEZGAH_CBM_BIN"] = sys.executable
        proc = self.setup("--install", "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def test_install_wires_the_omp_agent_dir(self):
        self.install()
        rules = self.read_text(self.path(".omp", "agent", "RULES.md"))
        self.assertIn("tezgah:start", rules)
        self.assertIn("Ponytail", rules)
        # the conditional rules are armed elsewhere, not written always-on
        self.assertNotIn("**Spec before building.**", rules)
        self.assertIn("lessons.md", rules)
        for s in ("harness", "ponytail", "tezgah-contract"):
            self.assertTrue(
                os.path.islink(self.path(".omp", "agent", "skills", s)), s)
        mcp = self.read_json(self.path(".omp", "agent", "mcp.json"))
        self.assertIn("codebase-memory-mcp", mcp["mcpServers"])
        agents = os.listdir(self.path(".omp", "agent", "agents"))
        self.assertTrue(any(a.startswith("tezgah-") for a in agents))
        hook = self.read_text(
            self.path(".omp", "agent", "hooks", "pre", "tezgah-hook.ts"))
        self.assertIn("projects-pretooluse.py", hook)
        self.assertNotIn("@PRETOOLUSE@", hook)

    def test_status_reports_the_omp_wiring(self):
        self.install()
        proc = self.setup("--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RULES.md carries the contract", proc.stdout)
        self.assertIn("gate hook present", proc.stdout)

    def test_uninstall_removes_the_omp_wiring(self):
        self.install()
        proc = self.setup("--uninstall", "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(
            os.path.islink(self.path(".omp", "agent", "skills", "harness")))
        mcp = self.read_json(self.path(".omp", "agent", "mcp.json"))
        self.assertNotIn("codebase-memory-mcp", mcp.get("mcpServers") or {})
        self.assertFalse(os.path.exists(
            self.path(".omp", "agent", "hooks", "pre", "tezgah-hook.ts")))


class ContextBudget(SetupBase):
    """The status report must show what tezgah injects before the first turn."""

    def test_report_lists_each_always_on_band(self):
        proc = self.setup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertIn("context budget (always-on text", out)
        for band in ("core contract (always-on, per session)", "per-turn reminder",
                     "skill metadata (8)", "subagent metadata (5)",
                     "conditional rules (armed by task class)",
                     "full contract (on demand)", "MCP tool schemas"):
            self.assertIn(band, out)

    def test_budget_numbers_are_ordered_and_nonzero(self):
        proc = self.setup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        core = re.search(r"core contract \(always-on, per session\)\s+~\s*([\d.]+)k tok", proc.stdout)
        skill = re.search(r"skill metadata \(8\)\s+~\s*([\d.]+)k tok", proc.stdout)
        ondemand = re.search(r"full contract \(on demand\)\s+~\s*([\d.]+)k tok", proc.stdout)
        self.assertIsNotNone(core)
        self.assertIsNotNone(skill)
        self.assertIsNotNone(ondemand)
        self.assertGreater(float(core.group(1)), 0)
        self.assertGreater(float(skill.group(1)), 0)
        # the on-demand whole contract is bigger than the always-on summary
        self.assertGreater(float(ondemand.group(1)), float(core.group(1)))


if __name__ == "__main__":
    unittest.main()
