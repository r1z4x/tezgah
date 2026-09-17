"""bin/tezgah-setup: install wiring, idempotency, uninstall, adopt, wizard.

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

sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_apps  # noqa: E402


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

    def setup(self, *args, stdin=""):
        # stdin is always a pipe: a bare run with a terminal on stdin would take
        # the wizard path and then block on the real terminal instead of
        # printing the report this suite asserts on. The timeout turns a hang
        # into a failure, which is what the no-hang tests are about.
        return subprocess.run([sys.executable, SETUP] + list(args),
                              capture_output=True, text=True, env=self.env,
                              input=stdin, timeout=120)

    def tree(self):
        """Every path under the fake HOME, for before/after comparisons."""
        return sorted(os.path.relpath(os.path.join(d, n), self.home)
                      for d, dirs, files in os.walk(self.home)
                      for n in dirs + files)

    def row(self, text, label):
        """The report line carrying this label, "" when the row is absent."""
        return next((line for line in text.splitlines() if label in line), "")


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
        # the bridge skips any event it does not know, so the manifest the patch
        # names has to exist and be the dsh-shaped one, not the Claude manifest
        manifest = re.search(r"configPath: (\S+)", dsh).group(1)
        self.assertTrue(os.path.isfile(manifest), manifest)
        self.assertIn("hosts/dsh/", manifest)
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
        # the exact version is the pin guard's business; here it has to be a pin
        self.assertRegex(dsh, r"'@playwright/mcp@\d+(\.\d+)+'")

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


class SkillTriggerLine(unittest.TestCase):
    """skill_description() feeds the opencode router, which is the only skill
    list that host has. A line built from the description's first sentence is
    what left tezgah-contract and ponytail unroutable, so the rule is pinned
    here on a synthetic SKILL.md, not only on the two shipped ones."""

    PROBE = (
        "import importlib.machinery, importlib.util, json, sys\n"
        "loader = importlib.machinery.SourceFileLoader('setup', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(\n"
        "    importlib.util.spec_from_loader('setup', loader))\n"
        "sys.modules['setup'] = m\n"
        "loader.exec_module(m)\n"
        "print(json.dumps(m.skill_description(sys.argv[2])))\n"
    )

    def line(self, description):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "SKILL.md")
            with open(path, "w") as fh:
                fh.write("---\nname: probe\ndescription: >\n  %s\n---\n\nbody\n"
                         % description)
            out = subprocess.run([sys.executable, "-c", self.PROBE, SETUP, path],
                                 capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_the_trigger_sentence_wins_over_the_opening_one(self):
        self.assertEqual(
            self.line("The full working contract. Load on demand when a session\n"
                      "  needs the deep detail. Use when the compact core points here."),
            "Use when the compact core points here.")

    def test_a_description_without_a_trigger_keeps_its_first_sentence(self):
        self.assertEqual(self.line("Does one small thing. Nothing else."),
                         "Does one small thing.")

    def test_a_long_trigger_sentence_is_still_one_bounded_line(self):
        got = self.line("A preface. Use when " + "x" * 200 + ".")
        self.assertEqual(len(got), 140)
        self.assertTrue(got.endswith("..."))


class SkillRouterTriggers(SetupBase):
    """A router line that drops the skill's trigger words names a skill no
    session will ever match, which is the whole job of the file."""

    def line(self, body, name):
        return next(row for row in body.splitlines() if "`%s`" % name in row)

    def test_core_skill_lines_carry_their_trigger(self):
        self.setup("--install", "--hosts", "opencode")
        body = self.read_text(self.path(".config", "tezgah", "opencode-skills.md"))
        contract = self.line(body, "tezgah-contract")
        pony = self.line(body, "ponytail")
        self.assertIn("Use when", contract)
        self.assertIn("code graph", contract)
        self.assertIn("Use on ANY coding task", pony)
        self.assertIn("refactoring", pony)


class PluginCopy(SetupBase):
    """Claude Code runs tezgah from a COPY under ~/.claude/plugins/cache, never
    from this checkout, so a copy that lags HEAD is the one gap the other claude
    rows cannot see: the report must name it, and --install must refresh it the
    way --sync does."""

    def copy(self):
        root = self.path(".claude", "plugins", "cache", "rizacan-local",
                         "tezgah", "0.9.0")
        self.write_json(os.path.join(root, ".claude-plugin", "plugin.json"),
                        {"name": "tezgah", "version": "0.9.0"})
        fingerprint = os.path.join(root, "hooks", "tezgah_policy.py")
        os.makedirs(os.path.dirname(fingerprint), exist_ok=True)
        with open(fingerprint, "w") as fh:
            fh.write("# the copy froze before HEAD\n")
        return root, fingerprint

    def reported(self):
        proc = self.setup("--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return self.row(proc.stdout, "plugin copy current")

    def test_a_stale_copy_is_reported_and_install_refreshes_it(self):
        _root, fingerprint = self.copy()
        self.assertTrue(self.reported().strip().startswith("MISS"),
                        "a copy that lags the checkout was reported as current")

        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(REPO, "hooks", "tezgah_policy.py")) as fh:
            checkout = fh.read()
        with open(fingerprint) as fh:
            self.assertEqual(fh.read(), checkout)
        self.assertTrue(self.reported().strip().startswith("ok"))

    def test_a_machine_without_a_plugin_copy_is_not_current(self):
        # all([]) is True, so the row used to be green on the one machine where
        # Claude has no tezgah at all - a check that cannot fail. An absent copy
        # is reported, like every sibling claude row.
        self.assertTrue(self.reported().strip().startswith("MISS"),
                        "no plugin copy at all was reported as current")

    def test_install_does_not_invent_a_plugin_copy(self):
        # refreshing is for a copy that exists and lags; there is nothing here
        # to refresh, and guessing a cache path would be a lie
        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.reported().strip().startswith("MISS"))


class CodexHome(SetupBase):
    """codex reads a relocated home from CODEX_HOME (Orca gives each account its
    own); arming ~/.codex while codex reads elsewhere leaves it unarmed."""

    def setUp(self):
        super().setUp()
        self.alt = self.path("orca", "codex")
        self.env["CODEX_HOME"] = self.alt

    def test_install_and_checks_use_the_relocated_home(self):
        proc = self.setup("--install", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hooks = os.path.join(self.alt, "hooks.json")
        self.assertIn("tezgah-codex-hook", self.read_text(hooks))
        self.assertTrue(os.path.islink(os.path.join(self.alt, "skills", "ponytail")))
        self.assertIn("mcp_servers.codebase-memory-mcp",
                      self.read_text(os.path.join(self.alt, "config.toml")))
        self.assertFalse(os.path.exists(self.path(".codex", "hooks.json")))

        # the checks answer about the tree the install wrote, not about ~/.codex,
        # and the row says which home it read
        stdout = self.setup("--hosts", "codex").stdout
        self.assertTrue(self.row(stdout, "hooks.json wired in %s" % self.alt)
                        .strip().startswith("ok"))
        os.remove(hooks)
        self.assertTrue(self.row(self.setup("--hosts", "codex").stdout,
                                 "hooks.json wired").strip().startswith("MISS"))


class CursorMatcher(SetupBase):
    """Cursor runs a preToolUse hook only for the tool types its matcher names,
    so a matcher that omits the write tools leaves the gate's edit branches
    (attribution, integrity) unreachable there. The installed entry and the
    manifest the repo ships have to say the same thing."""

    def test_the_installed_matcher_covers_the_write_tools_and_mirrors_the_manifest(self):
        self.setup("--install", "--hosts", "cursor")
        hooks = self.read_json(self.path(".cursor", "hooks.json"))["hooks"]
        entry = next(e for e in hooks["preToolUse"] if "tezgah" in json.dumps(e))
        matcher = re.compile(entry["matcher"])
        for tool in ("Shell", "Write", "Edit", "MultiEdit", "NotebookEdit"):
            self.assertTrue(matcher.search(tool), "%s not matched" % tool)

        with open(os.path.join(REPO, "hosts", "cursor", "hooks.json")) as fh:
            shipped = json.load(fh)["hooks"]["preToolUse"]
        self.assertEqual(entry["matcher"],
                         next(e for e in shipped if "matcher" in e)["matcher"])


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


class ContractParity(unittest.TestCase):
    """policy.CONTRACT and skills/tezgah-contract/SKILL.md are two hand-kept
    copies of the same rules. The hash in bin/tezgah-setup notices that one of
    them changed; this notices that only one of them changed, which is the
    drift that actually happens."""

    def rules(self, text):
        import re
        return dict.fromkeys(
            re.findall(r"\*\*[^*]{3,60}\.\*\*", text)
            + [h.strip() for h in re.findall(r"(?m)^#{2,3} .+$", text)])

    def test_every_rule_and_heading_in_the_contract_reaches_the_skill(self):
        import tezgah_policy as policy
        path = os.path.join(REPO, "skills", "tezgah-contract", "SKILL.md")
        with open(path, encoding="utf-8") as fh:
            skill = fh.read()
        # the contract is a template; the skill writes the placeholders out
        text = policy.CONTRACT.replace("{ROOT}", "the configured tezgah roots")
        missing = [item for item in self.rules(text) if item not in skill]
        self.assertEqual([], missing,
                         "these rules exist in policy.CONTRACT but not in the "
                         "skill: %s" % missing)



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

    def test_benchmark_readme_quotes_the_live_budget(self):
        # The benchmark README embeds the installer's budget report verbatim.
        # Hand-copying those figures is how that file came to print a core band
        # 1,830 characters smaller than the one the installer produces, so the
        # block is pinned to the instrument rather than to a memory of it.
        # The on-demand row is rendered against the local config path, so its
        # token figure moves by a character or two between machines; its number
        # is normalised out and every char-counted row is compared exactly.
        readme = os.path.join(REPO, "benchmarks", "harness-vs-omp", "README.md")
        with open(readme, encoding="utf-8") as fh:
            block = re.search(r"```\n(context budget \(always-on text.*?)```",
                              fh.read(), re.S)
        self.assertIsNotNone(block, "no budget block in the benchmark README")
        live = subprocess.run(
            [sys.executable, "-c",
             "import contextlib, importlib.machinery, importlib.util, io, sys\n"
             "loader = importlib.machinery.SourceFileLoader('setup', sys.argv[1])\n"
             "m = importlib.util.module_from_spec(\n"
             "    importlib.util.spec_from_loader('setup', loader))\n"
             "sys.modules['setup'] = m\n"
             "loader.exec_module(m)\n"
             "buf = io.StringIO()\n"
             "with contextlib.redirect_stdout(buf):\n"
             "    m.context_budget_report()\n"
             "print(buf.getvalue(), end='')", SETUP],
            capture_output=True, text=True, env=self.env)
        self.assertEqual(live.returncode, 0, live.stderr)

        def normalize(text):
            return re.sub(r"~ *[\d.]+k tok(?=  \(only when the skill is read\))",
                          "~<n>k tok", text)

        self.assertEqual(normalize(block.group(1).strip()),
                         normalize(live.stdout.strip()))

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
        # omp spawns `command` as one executable and passes `args`; the argv must
        # round-trip. A list in `command` is spawned comma-joined (ENOENT).
        for srv in tezgah_apps.servers(False):
            entry = mcp["mcpServers"][srv["name"]]
            self.assertEqual([entry["command"]] + entry["args"],
                             list(srv["command"]), srv["name"])
        agents = os.listdir(self.path(".omp", "agent", "agents"))
        self.assertTrue(any(a.startswith("tezgah-") for a in agents))
        hook = self.read_text(
            self.path(".omp", "agent", "hooks", "pre", "tezgah-hook.ts"))
        self.assertIn(os.path.join("hosts", "omp", "hook.py"), hook)
        self.assertNotIn("@HOOK@", hook)
        for handler in ("session_start", "before_agent_start", "tool_call",
                        "tool_result", "session_stop", "setWidget", "setStatus"):
            self.assertIn(handler, hook)

    def test_install_heals_an_argv_as_list_mcp_entry(self):
        path = self.path(".omp", "agent", "mcp.json")
        self.write_json(path, {"mcpServers": {"mobile-mcp": {
            "type": "stdio",
            "command": ["npx", "-y", "@mobilenext/mobile-mcp@latest"],
            "timeout": 5000}}})
        self.install()
        entry = self.read_json(path)["mcpServers"]["mobile-mcp"]
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["args"][0], "-y")
        self.assertRegex(entry["args"][1], r"^@mobilenext/mobile-mcp@\d+(\.\d+)+$")
        self.assertEqual(entry["timeout"], 5000)  # the user's own key survives

    def test_status_reports_the_omp_wiring(self):
        self.install()
        proc = self.setup("--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RULES.md carries the contract", proc.stdout)
        self.assertIn("app MCP command is one executable", proc.stdout)
        self.assertIn("status line answers", proc.stdout)

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


class ReadmeSnippets(unittest.TestCase):
    """The install snippets are the one language-neutral part of the READMEs.

    Translations are allowed to lag on prose (the English README says so), but a
    command that no longer matches the installer is a real bug in every
    language, so the snippet is pinned here. A hermetic check: no HOME, no
    subprocess.
    """

    LINES = ("bin/tezgah-setup --install --hosts omp",
             "bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh",
             "bin/tezgah-setup --roots ~/work:~/oss --install")

    def test_every_readme_carries_the_current_install_snippet(self):
        import glob
        paths = sorted(glob.glob(os.path.join(REPO, "README*.md")))
        self.assertGreater(len(paths), 1, paths)
        for path in paths:
            with open(path) as fh:
                text = fh.read()
            for line in self.LINES:
                self.assertIn(line, text, os.path.basename(path))


class ContextBudget(SetupBase):
    """The status report must show what tezgah injects before the first turn."""

    def test_report_lists_each_always_on_band(self):
        proc = self.setup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertIn("context budget (always-on text", out)
        for band in ("core contract (always-on, per session)", "per-turn reminder",
                     "skill metadata (10)", "subagent metadata (5)",
                     "conditional rules (armed by task class)",
                     "full contract (on demand)", "MCP tool schemas"):
            self.assertIn(band, out)

    def test_budget_numbers_are_ordered_and_nonzero(self):
        proc = self.setup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        core = re.search(r"core contract \(always-on, per session\)\s+~\s*([\d.]+)k tok", proc.stdout)
        skill = re.search(r"skill metadata \(10\)\s+~\s*([\d.]+)k tok", proc.stdout)
        ondemand = re.search(r"full contract \(on demand\)\s+~\s*([\d.]+)k tok", proc.stdout)
        self.assertIsNotNone(core)
        self.assertIsNotNone(skill)
        self.assertIsNotNone(ondemand)
        self.assertGreater(float(core.group(1)), 0)
        self.assertGreater(float(skill.group(1)), 0)
        # the on-demand whole contract is bigger than the always-on summary
        self.assertGreater(float(ondemand.group(1)), float(core.group(1)))


class McpSchemas(SetupBase):
    """The one context band no static report can see: the tool schemas a host
    injects. It is measured by asking the server, so the handshake is tested
    against a fake one rather than against whatever is installed here."""

    FAKE = (
        "import json, sys\n"
        "tools = [{'name': 'a', 'description': 'x' * 40,"
        " 'inputSchema': {'type': 'object'}},\n"
        "         {'name': 'b', 'description': 'y' * 40,"
        " 'inputSchema': {'type': 'object'}}]\n"
        "for line in sys.stdin:\n"
        "    try:\n"
        "        msg = json.loads(line)\n"
        "    except ValueError:\n"
        "        continue\n"
        "    if msg.get('id') == 1:\n"
        "        print(json.dumps({'jsonrpc': '2.0', 'id': 1,"
        " 'result': {'protocolVersion': '2024-11-05'}}))\n"
        "    elif msg.get('id') == 2:\n"
        "        print(json.dumps({'jsonrpc': '2.0', 'id': 2,"
        " 'result': {'tools': tools}}))\n"
    )

    MEASURE = (
        "import importlib.machinery, importlib.util, json, sys\n"
        "loader = importlib.machinery.SourceFileLoader('setup', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(\n"
        "    importlib.util.spec_from_loader('setup', loader))\n"
        "sys.modules['setup'] = m\n"
        "loader.exec_module(m)\n"
        "print(json.dumps(m.mcp_tool_schemas(sys.argv[2:])))"
    )

    def server(self, source):
        path = os.path.join(self.home, "server.py")
        with open(path, "w") as fh:
            fh.write(source)
        return [sys.executable, path]

    def measure(self, *command):
        out = subprocess.run([sys.executable, "-c", self.MEASURE, SETUP]
                             + list(command),
                             env=self.env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_measures_the_schemas_a_server_declares(self):
        count, size = self.measure(*self.server(self.FAKE))
        self.assertEqual(count, 2)
        self.assertGreater(size, 100)

    def test_a_silent_server_is_unmeasured_not_zero(self):
        count, size = self.measure(*self.server("import sys; sys.stdin.read()\n"))
        self.assertEqual(count, 0)
        self.assertIsNone(size)


class McpAppSpec(unittest.TestCase):
    """The app-analysis MCP commands tezgah writes must pin their version.

    An unpinned npx declaration fetches whatever the registry serves at session
    start and runs it with the agent's privileges; a 2,660-harness study found
    that defect in 9.8% of committed agent configurations (arXiv 2609.07360)."""

    def commands(self):
        sys.path.insert(0, os.path.join(REPO, "hooks"))
        import tezgah_apps
        return [s["command"] for s in tezgah_apps.SERVERS] + [
            tezgah_apps._CHROME_DEVTOOLS]

    def packages(self):
        """(name, tag) for every package spec in the declared commands."""
        out = []
        for command in self.commands():
            for part in command:
                if "@" not in part or part.startswith("-"):
                    continue
                if part.startswith("@"):
                    name, _, tag = part.rpartition("@")
                else:
                    name, _, tag = part.partition("@")
                out.append((name, tag))
        return out

    def test_every_package_runner_declares_a_version(self):
        packages = self.packages()
        self.assertTrue(packages, "no package specs found to check")
        for name, tag in packages:
            self.assertRegex(tag, r"^\d+(\.\d+)*$",
                             "%s declares the floating tag %r" % (name, tag))

    def test_the_playwright_pin_is_visible(self):
        self.assertIn(("@playwright/mcp", "0.0.81"), self.packages())


class Wizard(SetupBase):
    """The interactive install. Answers are fed through a piped stdin, so no
    test needs a terminal, and the wizard must write nothing before its final
    yes - a decline or a closed stdin leaves the machine untouched."""

    def wiz(self, *answers, flags=()):
        """Feed the wizard exactly these answers, one per prompt, through a pipe."""
        return self.setup("--wizard", *flags, stdin="\n".join(answers) + "\n")

    def config(self):
        return self.read_json(self.path(".config", "tezgah", "config.json"))

    def test_answers_drive_the_same_install_path_as_the_flags(self):
        proc = self.wiz("", "", "", "", "")  # every default, then proceed
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the plan:", proc.stdout)
        # what the plan promised is what the shared install path applied; the
        # detected set itself is machine-dependent (omp is on PATH here)
        planned = re.search(r"^\s+ok\s+arm: (.+)$", proc.stdout, re.M).group(1).split(", ")
        self.assertIn("installing for: %s" % ", ".join(planned), proc.stdout)
        cfg = self.config()
        self.assertEqual(cfg["hosts"], planned)
        self.assertIn(self.path("Projects"), cfg["roots"])
        self.assertTrue(os.path.islink(self.path(".config", "tezgah", "bin", "consult")))

    def test_flags_stand_in_as_the_default_answers(self):
        proc = self.wiz("", "", "", "", "", flags=("--hosts", "claude", "--no-deps"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("installing for: claude", proc.stdout)
        self.assertNotIn("installing for: claude,", proc.stdout)
        self.assertEqual(self.config()["hosts"], ["claude"])

    def test_a_bad_answer_is_asked_again_not_installed_half_way(self):
        proc = self.wiz("claude,bogus", "claude", "relative/path", "", "", "", "")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("unknown host; choose from", proc.stdout)
        self.assertIn("use absolute paths", proc.stdout)
        self.assertEqual(self.config()["hosts"], ["claude"])

    def test_declining_the_plan_writes_nothing(self):
        before = self.tree()
        proc = self.wiz("", "", "", "", "n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nothing was installed", proc.stdout)
        self.assertEqual(self.tree(), before)

    def test_a_closed_stdin_aborts_instead_of_hanging(self):
        before = self.tree()
        proc = self.setup("--wizard", stdin="")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("wizard: stdin unusable", proc.stdout)
        self.assertEqual(self.tree(), before)

    def test_adoption_waits_for_the_confirmation(self):
        # --adopt must not retire the predecessor wiring before the plan is
        # confirmed: declining has to leave it exactly where it was
        pred = self.path(".codex", "projects-harness")
        os.makedirs(pred)
        before = self.tree()
        proc = self.wiz("", "", "", "", "", "n", flags=("--adopt",))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("predecessor wiring still present", proc.stdout)
        self.assertIn("nothing was installed", proc.stdout)
        self.assertEqual(self.tree(), before)

    def test_adoption_runs_after_the_confirmation(self):
        pred = self.path(".codex", "projects-harness")
        os.makedirs(pred)
        proc = self.wiz("", "", "", "", "", "", flags=("--adopt",))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(pred))
        self.assertTrue(os.path.isdir(self.path(".config", "tezgah", "adopted")))

    def test_a_root_that_is_a_file_is_re_asked_and_a_missing_one_is_noted(self):
        afile = self.path("not-a-dir")
        with open(afile, "w") as fh:
            fh.write("x")
        missing = self.path("later")
        proc = self.wiz("claude", afile, missing, "", "", "")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("use absolute paths to directories", proc.stdout)
        self.assertIn("does not exist yet", proc.stdout)
        self.assertEqual(self.config()["roots"], [missing])

    def test_a_piped_bare_run_still_reports_and_asks_nothing(self):
        proc = self.setup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah checkout:", proc.stdout)
        self.assertNotIn("the plan:", proc.stdout)
        self.assertNotIn("arm which hosts?", proc.stdout)


class WizardUnits(unittest.TestCase):
    """The wizard's decision logic, loaded in-process: no HOME, no subprocess."""

    PROBE = (
        "import importlib.machinery, importlib.util, json, sys\n"
        "loader = importlib.machinery.SourceFileLoader('setup', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(\n"
        "    importlib.util.spec_from_loader('setup', loader))\n"
        "sys.modules['setup'] = m\n"
        "loader.exec_module(m)\n"
        "print(json.dumps({\n"
        "    'numbers': m.parse_hosts('2,1,2'),\n"
        "    'unknown': m.parse_hosts('claude,bogus'),\n"
        "    'all': m.parse_hosts('all') == m.ALL_HOSTS,\n"
        "    'late': m.unarmed_new_hosts(['claude'], ['claude'], ['claude', 'dsh']),\n"
        "    'chosen_out': m.unarmed_new_hosts(['claude'], ['claude', 'codex'],\n"
        "                                      ['claude', 'codex']),\n"
        "    'none_detected': m._ask_hosts([], lambda _prompt: ''),\n"
        "}))\n"
    )

    def probe(self):
        out = subprocess.run([sys.executable, "-c", self.PROBE, SETUP],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_host_answers_are_names_numbers_or_all(self):
        got = self.probe()
        self.assertEqual(got["numbers"], ["codex", "claude"])
        self.assertIsNone(got["unknown"])
        self.assertTrue(got["all"])

    def test_late_hosts_are_reported_and_an_empty_machine_can_arm_none(self):
        got = self.probe()
        self.assertEqual(got["late"], ["dsh"])
        # a host the user left out on purpose is not reported back at them
        self.assertEqual(got["chosen_out"], [])
        self.assertEqual(got["none_detected"], [])


if __name__ == "__main__":
    unittest.main()
