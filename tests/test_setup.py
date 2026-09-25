"""bin/tezgah-setup: install wiring, idempotency, uninstall, adopt, wizard.

Every test runs the installer in a throwaway HOME with fake host dirs, so the
real ~/.claude, ~/.codex, ~/.config/opencode, ~/.cursor and ~/.dsh are never
touched. TEZGAH_CODEGRAPH_BIN points at nothing so no graph is registered.
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")
ALL = "claude,codex,opencode,cursor,dsh,omp"

sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_apps  # noqa: E402


def setup_module():
    """bin/tezgah-setup as a module, for the constants a test has to read from
    the installer rather than repeat. Importing it is side-effect free (its
    module level is paths and function definitions)."""
    import importlib.machinery
    import importlib.util
    if "tezgah_setup_probe" in sys.modules:
        return sys.modules["tezgah_setup_probe"]
    loader = importlib.machinery.SourceFileLoader("tezgah_setup_probe", SETUP)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("tezgah_setup_probe", loader))
    sys.modules["tezgah_setup_probe"] = module
    loader.exec_module(module)
    return module


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
            "TEZGAH_CODEGRAPH_BIN": os.path.join(self.home, "no-such-codegraph"),
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
                     "tezgah-pony", "tezgah-adhd", "tezgah-docs",
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
        # all three routes are declared on the pi-ai adapter
        self.assertIn("id: llm-pi-ai", dsh)
        self.assertIn("openrouter", dsh)
        self.assertIn("DEEPSEEK_API_KEY", dsh)
        self.assertIn("INCEPTION_API_KEY", dsh)
        # pi-ai's installed catalog ships openrouter and deepseek only, so a
        # route it does not carry has to declare its own protocol, endpoint and
        # models - without them the route resolves to a catalogError and no
        # model can be selected on it
        self.assertIn("api: openai-completions", dsh)
        self.assertIn("baseURL: https://api.inceptionlabs.ai/v1", dsh)
        self.assertIn("maxTokensField: max_completion_tokens", dsh)
        self.assertIn("id: mercury-2.5", dsh)
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
        self.assertIn("codegraph", oc.get("mcp", {}))
        self.assertTrue((oc.get("compaction") or {}).get("prune"))
        self.assertIn("node_modules/**", (oc.get("watcher") or {}).get("ignore", []))
        tui = self.read_json(self.path(".config", "opencode", "tui.json"))
        self.assertTrue(any("tezgah-tui" in (p if isinstance(p, str) else p[0])
                            for p in tui.get("plugin", [])))

        # cursor: hooks + statusline
        cur = self.read_json(self.path(".cursor", "cli-config.json"))
        self.assertIn("tezgah-statusline", cur["statusLine"]["command"])

    def test_opencode_grants_reads_of_tezgahs_own_directories(self):
        """A skill body and tezgah's CLIs sit outside the session's project, and
        opencode auto-rejects an out-of-project read when nobody can answer the
        prompt - measured on a live `opencode run`, which tried to open
        `skills/ai-research/` and was denied. The two directories tezgah installs
        are granted, and an explicit global choice is left alone."""
        self.setup("--install", "--hosts", "opencode")
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        external = oc["permission"]["external_directory"]
        self.assertEqual(
            sorted(external),
            sorted([os.path.join(REPO, "skills", "**"),
                    os.path.join(self.path(".config", "tezgah", "bin"), "**")]))
        self.assertEqual(sorted(external.values()), ["allow", "allow"])
        self.assertEqual(oc["permission"]["skill"], "deny")

        self.write_json(self.path(".config", "opencode", "opencode.json"),
                        {"$schema": "https://opencode.ai/config.json",
                         "permission": {"external_directory": "ask"}})
        self.setup("--install", "--hosts", "opencode")
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertEqual(oc["permission"]["external_directory"], "ask")

    def test_opencode_grants_are_removed_by_uninstall(self):
        self.setup("--install", "--hosts", "opencode")
        self.setup("--uninstall", "--hosts", "opencode")
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertNotIn("external_directory", oc.get("permission") or {})
        self.assertNotIn("permission", oc)

    def test_install_refreshes_a_stale_app_table(self):
        """The TOML writer only appended a missing table, so an existing one kept
        its old argv forever - a changed pin or a new `--caps` never reached an
        install that already had the server."""
        path = self.path(".codex", "config.toml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write('[mcp_servers.playwright]\n'
                     'command = "npx"\n'
                     'args = ["-y", "@playwright/mcp@0.0.1", "--isolated"]\n'
                     'startup_timeout_sec = 9\n')
        proc = self.setup("--install", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        toml = self.read_text(path)
        self.assertIn("--caps=testing,storage,network", toml)
        self.assertNotIn("@playwright/mcp@0.0.1", toml)
        self.assertIn("startup_timeout_sec = 9", toml)  # the user's key survives

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
        self.assertIn("mcp_servers.codegraph", toml)
        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertNotIn("playwright", oc.get("mcp") or {})
        self.assertIn("codegraph", oc.get("mcp") or {})
        cur = self.read_json(self.path(".cursor", "mcp.json"))
        self.assertNotIn("playwright", cur["mcpServers"])
        self.assertIn("codegraph", cur["mcpServers"])

    def test_every_host_row_comes_from_one_codegraph_argv(self):
        """One engine, one name, one surface.

        The row each host carries has to be codegraph's own argv (`serve --mcp`)
        and the two environment values that arm the tools the agent briefs name:
        codegraph exposes `codegraph_explore` alone without CODEGRAPH_MCP_TOOLS,
        and the app rows on this very path write their env, so a host left on the
        bare binary answers fewer questions than the brief expects while
        `--report` still shows a green MCP row."""
        module = setup_module()
        # Both sides are given the same pin: the fixture's default points at a
        # path that does not exist, so the subprocess writes the bare name while
        # an in-process `graph_command()` would resolve whatever this machine has
        # installed - and the assertion flipped the day codegraph landed in
        # ~/.local/bin. A fake binary makes the resolved path the thing asserted,
        # on a machine with or without the engine.
        fake = self.path("fake-codegraph")
        with open(fake, "w") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        os.chmod(fake, 0o755)
        self.env["TEZGAH_CODEGRAPH_BIN"] = fake
        self.setup("--install", "--hosts", ALL)
        had = os.environ.get("TEZGAH_CODEGRAPH_BIN")
        os.environ["TEZGAH_CODEGRAPH_BIN"] = fake
        try:
            argv, env = module.graph_command(), dict(module.GRAPH_ENV)
        finally:
            if had is None:
                os.environ.pop("TEZGAH_CODEGRAPH_BIN", None)
            else:
                os.environ["TEZGAH_CODEGRAPH_BIN"] = had
        self.assertEqual([fake, "serve", "--mcp"], argv)

        codex = self.read_text(self.path(".codex", "config.toml"))
        self.assertIn("[mcp_servers.codegraph]", codex)
        self.assertIn('command = "%s"' % argv[0], codex)
        self.assertIn('args = ["serve", "--mcp"]', codex)
        self.assertEqual(sorted(env),
                         sorted(re.findall(r"(CODEGRAPH_\w+) = ", codex)))

        oc = self.read_json(self.path(".config", "opencode", "opencode.json"))
        self.assertEqual(oc["mcp"]["codegraph"]["command"], argv)
        self.assertEqual(oc["mcp"]["codegraph"]["environment"], env)

        cur = self.read_json(self.path(".cursor", "mcp.json"))["mcpServers"]
        self.assertEqual(cur["codegraph"],
                         {"command": argv[0], "args": argv[1:], "env": env})

        omp = self.read_json(self.path(".omp", "agent", "mcp.json"))["mcpServers"]
        self.assertEqual(omp["codegraph"],
                         {"type": "stdio", "command": argv[0], "args": argv[1:],
                          "env": env})

        # dsh has no codegraph installer of its own: tezgah writes this row by
        # hand, so it is the one row that can silently miss an argument
        dsh = self.read_text(self.path(".dsh", "cordis.patch.yml"))
        self.assertIn("serverName: codegraph", dsh)
        self.assertIn("args: ['serve', '--mcp']", dsh)
        self.assertIn("CODEGRAPH_MCP_TOOLS: '%s'" % env["CODEGRAPH_MCP_TOOLS"], dsh)
        self.assertIn("CODEGRAPH_TELEMETRY: '0'", dsh)

        # the health rows name the same engine the install wrote: with the pin
        # that resolves, the row is green, and with a pin that resolves nothing
        # the same row says MISS - both are the report telling the truth about
        # the binary the row above was written from.
        report = self.setup("--hosts", ALL).stdout
        self.assertTrue(self.row(report, "codegraph on PATH").strip()
                        .startswith("ok"), report)
        self.env["TEZGAH_CODEGRAPH_BIN"] = self.path("no-such-codegraph")
        report = self.setup("--hosts", ALL).stdout
        self.assertTrue(self.row(report, "codegraph on PATH").strip()
                        .startswith("MISS"), report)


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
    """The three dsh LLM routes are reported separately and read the provider key
    files tezgah already uses, so a single-provider setup is not shown broken."""

    def test_routes_are_per_provider_and_read_config_key_files(self):
        os.makedirs(self.path(".config", "openrouter"), exist_ok=True)
        open(self.path(".config", "openrouter", "key"), "w").close()
        proc = self.setup("--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        openrouter = self.row(proc.stdout, "OpenRouter route key resolvable")
        deepseek = self.row(proc.stdout, "DeepSeek route key resolvable")
        inception = self.row(proc.stdout, "Inception route key resolvable")
        self.assertTrue(openrouter, "OpenRouter row missing")
        self.assertTrue(deepseek, "DeepSeek row missing")
        self.assertTrue(inception, "Inception row missing")
        self.assertTrue(openrouter.strip().startswith("ok"))
        self.assertTrue(deepseek.strip().startswith("MISS"))
        self.assertTrue(inception.strip().startswith("MISS"))


class OpencodeKeyRow(SetupBase):
    """opencode's own registry owns the inception provider, so opencode.json
    carries no route block and the key is the whole wiring: the report has to
    say whether one resolves, from the launch env or the store `opencode auth
    login` writes."""

    def test_the_row_follows_the_auth_store(self):
        self.write_json(self.path(".local", "share", "opencode", "auth.json"),
                        {"inception": {"type": "api", "key": "k"}})
        proc = self.setup("--hosts", "opencode")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = self.row(proc.stdout, "Inception provider key resolvable")
        self.assertTrue(row, "row missing")
        self.assertTrue(row.strip().startswith("ok"), row)

    def test_a_missing_key_reads_as_missing(self):
        proc = self.setup("--hosts", "opencode")
        row = self.row(proc.stdout, "Inception provider key resolvable")
        self.assertTrue(row, "row missing")
        self.assertTrue(row.strip().startswith("MISS"), row)


class OmpTypeSafeRow(SetupBase):
    """omp is the host that spends TYPESAFE_API_KEY (judge(), auto thinking,
    unexpected-stop, AI staging), so the report has to say whether one resolves
    - a session whose key is missing silently reads the fallback as the
    feature. What resolves it is the env or omp's own login store; a tezgah
    key file is not a path omp opens.

    The judgement seam's own key is a second row, because its channel set
    differs from omp's in both directions: a key file alone serves the seam
    while omp falls back, and a login-store record alone serves omp while the
    seam has no credential. One row carrying one answer under both questions
    read wrong in whichever of the two shapes the reader was in."""

    OMP = "TypeSafe (Jev) key resolvable"
    SEAM = "judgement seam key resolvable"

    def login_store(self):
        p = self.path(".omp", "agent", "agent.db")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        conn = sqlite3.connect(p)
        conn.execute("create table auth_credentials (provider text)")
        conn.execute("insert into auth_credentials values ('typesafe')")
        conn.commit()
        conn.close()

    def key_file(self, content="k\n"):
        p = self.path(".config", "typesafe", "key")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(content)

    def assertRow(self, text, label, ok):
        row = self.row(text, label)
        self.assertTrue(row, "row missing: %s" % label)
        self.assertTrue(row.strip().startswith("ok" if ok else "MISS"), row)

    def test_the_row_follows_the_login_store(self):
        self.login_store()
        proc = self.setup("--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRow(proc.stdout, self.OMP, True)
        # The mirror divergence: omp is served, the seam is not.
        self.assertRow(proc.stdout, self.SEAM, False)

    def test_a_missing_key_reads_as_missing(self):
        os.makedirs(self.path(".omp", "agent"), exist_ok=True)
        proc = self.setup("--hosts", "omp")
        self.assertRow(proc.stdout, self.OMP, False)
        self.assertRow(proc.stdout, self.SEAM, False)

    def test_the_key_file_alone_reports_the_seam_only(self):
        # The measured divergence: before the second row, this shape printed
        # `MISS key resolvable` while tezgah-triage and tezgah-docs judged.
        self.key_file()
        proc = self.setup("--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRow(proc.stdout, self.OMP, False)
        self.assertRow(proc.stdout, self.SEAM, True)

    def test_the_env_alone_reports_both(self):
        self.env["TYPESAFE_API_KEY"] = "test"
        proc = self.setup("--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRow(proc.stdout, self.OMP, True)
        self.assertRow(proc.stdout, self.SEAM, True)

    def test_a_blank_key_file_is_not_a_credential(self):
        # hooks/tezgah_judge.key() strips the file and returns None when nothing
        # is left, so a whitespace-only file is not a key to either reader.
        self.key_file("  \n")
        proc = self.setup("--hosts", "omp")
        self.assertRow(proc.stdout, self.SEAM, False)


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
        # the router line is the only skill list opencode has, and it is cut at
        # 140 characters: a product trigger that lands past the cut names a skill
        # no product question can reach.
        product = self.line(body, "product-analysis")
        self.assertIn("Use when", product)
        self.assertIn("product analysis", product)
        self.assertIn("feature", product)
        self.assertIn("retention", product)
        frameworks = self.line(body, "pm-frameworks")
        self.assertIn("Use when", frameworks)
        self.assertIn("intended-vs-implemented", frameworks)
        self.assertIn("opportunity solution trees", frameworks)
        # the same 140-character cut applies: the feature-level triggers must land
        # before it, or a feature audit reaches a skill line it cannot match on.
        audit = self.line(body, "feature-audit")
        self.assertIn("Use when", audit)
        self.assertIn("admin panel", audit)
        self.assertIn("CRUD", audit)


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

    PROBE = (
        "import importlib.machinery, importlib.util, json, sys\n"
        "loader = importlib.machinery.SourceFileLoader('setup', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(\n"
        "    importlib.util.spec_from_loader('setup', loader))\n"
        "sys.modules['setup'] = m\n"
        "loader.exec_module(m)\n"
        "print(json.dumps(m.plugin_copy_current(sys.argv[2])))\n"
    )

    def current(self, target):
        """plugin_copy_current for a copy in the throwaway HOME, asked in its own
        process so the temp HOME is the one the module reads."""
        out = subprocess.run([sys.executable, "-c", self.PROBE, SETUP, target],
                             capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def synced_copy(self):
        """A copy made the way --sync makes one, so it matches byte for byte."""
        root = self.path(".claude", "plugins", "cache", "rizacan-local",
                         "tezgah", "0.9.0")
        fingerprint = os.path.join(root, "hooks", "tezgah_policy.py")
        os.makedirs(os.path.dirname(fingerprint), exist_ok=True)
        with open(fingerprint, "w") as fh:
            fh.write("# frozen copy\n")
        proc = self.setup("--sync")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("synced", proc.stdout)
        return root

    def freeze(self, root, rel):
        with open(os.path.join(root, rel), "a") as fh:
            fh.write("# the copy froze before HEAD\n")

    def test_a_copy_that_differs_in_another_hook_is_not_current(self):
        # the regression: the fingerprint alone matched, so --install skipped the
        # refresh while the copy ran the previous gate
        root = self.synced_copy()
        self.assertTrue(self.current(root), "a fresh --sync copy was called stale")
        self.freeze(root, "hooks/tezgah_gate.py")
        self.assertFalse(self.current(root),
                         "a copy differing only in another hook was called current")

    def test_a_copy_that_matches_the_checkout_is_current(self):
        root = self.synced_copy()
        self.assertTrue(self.current(root),
                        "--install would re-copy a copy that already matches")

    def test_install_refreshes_a_copy_whose_other_hook_changed(self):
        root = self.synced_copy()
        self.freeze(root, "hooks/tezgah_gate.py")
        proc = self.setup("--install", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("synced", proc.stdout)
        with open(os.path.join(REPO, "hooks", "tezgah_gate.py")) as fh:
            checkout = fh.read()
        self.assertEqual(
            self.read_text(os.path.join(root, "hooks", "tezgah_gate.py")), checkout)

    def test_a_copy_that_carries_a_file_outside_the_file_set_is_not_current(self):
        """A file the checkout STOPPED shipping is absent from the listed set, so
        it cannot move a hash over that set: the copy stayed "current" while
        serving a skill, or a helper, that no longer exists anywhere. The reverse
        - a listed file the copy does not hold - is caught by the same row."""
        root = self.synced_copy()
        self.assertTrue(self.current(root), "a fresh --sync copy was called stale")

        ghost = os.path.join(root, "skills", "ghost-skill", "SKILL.md")
        os.makedirs(os.path.dirname(ghost), exist_ok=True)
        with open(ghost, "w") as fh:
            fh.write("---\nname: ghost-skill\n---\n")
        self.assertFalse(self.current(root),
                         "a copy still serving a dropped skill was called current")

        os.remove(ghost)
        os.remove(os.path.join(root, "hooks", "tezgah_gate.py"))
        self.assertFalse(self.current(root),
                         "a copy missing a file the checkout ships was current")

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
        self.assertIn("mcp_servers.codegraph",
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

    def test_a_manifest_missing_the_stop_hook_is_not_reported_as_wired(self):
        """The row answers "is this host armed?". Stop is the integrity refusal,
        and the row passed on any single event, so a manifest carrying tezgah's
        command under six of seven events read `ok` with nothing to block a
        false "done"."""
        proc = self.setup("--install", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.row(self.setup("--hosts", "codex").stdout,
                                 "hooks.json wired").strip().startswith("ok"))

        hooks = os.path.join(self.alt, "hooks.json")
        data = self.read_json(hooks)
        del data["hooks"]["Stop"]
        self.write_json(hooks, data)
        row = self.row(self.setup("--hosts", "codex").stdout, "hooks.json wired")
        self.assertTrue(row.strip().startswith("MISS"),
                        "a host wired for every event but Stop was reported as "
                        "wired: %r" % row)


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
    def test_dry_run_uninstall_writes_nothing(self):
        """`--dry-run` is a preview for the uninstall too: the run that the
        acceptance report called a preview once performed a real removal, which
        is the trap this pins shut."""
        self.setup("--install", "--hosts", ALL)
        before = self.tree()
        proc = self.setup("--uninstall", "--dry-run", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("uninstall preview (nothing written)", proc.stdout)
        self.assertEqual(self.tree(), before)
        self.assertFalse(os.path.exists(
            self.path(".config", "tezgah", "pretooluse-off")),
            "a preview must not stand the gate down")

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

    def test_full_uninstall_takes_the_generated_state_and_proves_it(self):
        """A full run (every armed host) ends with nothing tezgah generated on
        disk - the config, the contract hash, the generated opencode contract,
        the caches, the kill switches - and the verify pass says so. The exit
        code is the proof's contract: nonzero when anything tezgah wrote
        survives, so a leftover can never read as a clean uninstall."""
        self.setup("--install", "--hosts", ALL)
        self.assertTrue(os.path.exists(self.path(".config", "tezgah", "config.json")))
        self.assertTrue(os.path.exists(self.path(".config", "tezgah",
                                                 "opencode-contract.md")))
        # the app artifacts dir lives under the cache and the install creates it
        self.assertTrue(os.path.isdir(self.path(".cache", "tezgah")))
        proc = self.setup("--uninstall", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("uninstall complete", proc.stdout)
        self.assertFalse(os.path.exists(self.path(".config", "tezgah",
                                                  "opencode-contract.md")))
        self.assertFalse(os.path.exists(self.path(".config", "tezgah",
                                                  "contract.sha256")))
        self.assertFalse(os.path.exists(self.path(".cache", "tezgah")))
        self.assertFalse(os.path.exists(self.path(".config", "tezgah",
                                                  "pretooluse-off")))

    def test_full_uninstall_keeps_a_users_own_config_dir_entry(self):
        self.setup("--install", "--hosts", "codex")
        mine = self.path(".config", "tezgah", "my-notes.txt")
        with open(mine, "w") as fh:
            fh.write("mine\n")
        proc = self.setup("--uninstall", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(mine), "the user's file was deleted")
        self.assertIn("kept", proc.stdout)

    def test_partial_uninstall_keeps_the_config_for_the_still_armed(self):
        """Uninstalling one of two armed hosts may not take the state: the
        remaining host reads its roots and feature selection from config.json at
        runtime, and the install tree still serves its links."""
        self.setup("--install", "--hosts", "codex,omp")
        proc = self.setup("--uninstall", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("still armed: omp", proc.stdout)
        self.assertTrue(os.path.exists(self.path(".config", "tezgah",
                                                 "config.json")))

    def test_omp_mcp_json_is_removed_when_only_tezgah_keys_remain(self):
        """install_omp writes `$schema` and `mcpServers` into a file it may have
        created; an uninstall that left those two behind left a wired-but-empty
        registration omp would still read."""
        self.setup("--install", "--hosts", "omp")
        mcp = self.path(".omp", "agent", "mcp.json")
        self.assertTrue(os.path.exists(mcp))
        proc = self.setup("--uninstall", "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(mcp), proc.stdout)

    def test_omp_mcp_json_keeps_the_users_own_servers(self):
        self.write_json(self.path(".omp", "agent", "mcp.json"),
                        {"mcpServers": {"mine": {"type": "stdio",
                                                 "command": "echo",
                                                 "args": ["kept"]}}})
        self.setup("--install", "--hosts", "omp")
        proc = self.setup("--uninstall", "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        servers = self.read_json(self.path(".omp", "agent", "mcp.json"))["mcpServers"]
        self.assertIn("mine", servers)
        self.assertNotIn("tezgah", servers)
        self.assertNotIn("codegraph", servers)

    def test_uninstall_unwires_the_cursor_status_line(self):
        """install_cursor writes a `statusLine` into cli-config.json and no
        uninstaller touched it - the one key that kept Cursor drawing the tezgah
        line after a clean uninstall."""
        self.setup("--install", "--hosts", "cursor")
        cc = self.path(".cursor", "cli-config.json")
        self.assertIn("tezgah-statusline", json.dumps(self.read_json(cc)))
        proc = self.setup("--uninstall", "--hosts", "cursor")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("tezgah-statusline", json.dumps(self.read_json(cc)))

    def test_uninstall_sweeps_a_legacy_kill_switch_from_claude(self):
        """The pre-multi-host setup wrote switches to ~/.claude, which the core
        still reads: a switch left behind keeps its rule silent after a
        reinstall, with nothing anywhere saying why."""
        legacy = self.path(".claude", "consult-off")
        with open(legacy, "w") as fh:
            fh.write("")
        proc = self.setup("--uninstall", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(legacy), proc.stdout)


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


class GraphRuleBand(SetupBase):
    """The graph rule is an on-demand paragraph, never part of the always-on
    band.

    `policy.CODEGRAPH_RULE` names one engine and no project id: codegraph indexes
    the repo it runs in and is asked about definitions, callers and blast radius
    in that repo, so there is no project name a static file would have to invent
    (the clause a `%s` project-id slot existed for). What survives that removal
    is the placement - the rule rides the task class that arms it, and the
    session pays its text only then."""

    def test_the_rule_rides_the_task_class_not_the_always_on_band(self):
        """The rule is rendered into policy.CONTRACT, never into CORE.

        The always-on band the installer prints (`core contract (always-on, per
        session)`) is CORE minus the conditional paragraphs, so a rule that
        belongs to the task class must not be in it: the session pays the rule's
        text only on the prompt that arms it, from the skill. This is asserted on
        the rendered text, not on a length, because the band's number moves with
        any CORE edit and a pinned number would report that as this rule
        drifting."""
        import tezgah_policy as policy
        module = setup_module()
        rule = module.CODEGRAPH_RULE % module.CODEGRAPH_STATIC
        self.assertIn(rule, policy.CONTRACT)
        always = module.tezgah_context.always_on_core()
        self.assertNotIn(rule, always)
        # the short CORE paragraph is the same rule's arming stub: it is paid per
        # prompt too, so it belongs to the conditional set and not to the band
        self.assertNotIn("**Code discovery: graph first.**", always)



class Refresh(SetupBase):
    """--refresh re-renders the generated opencode contract in-session when the
    policy or the full-contract skill changed, without a reinstall."""

    def contract_sha(self):
        # from the installer's own list: a helper that repeats the literals
        # asserts the implementation against its own assumption, which is how a
        # source missing from that list stayed invisible
        h = hashlib.sha256()
        for rel in setup_module().CONTRACT_SOURCES:
            with open(os.path.join(REPO, rel), "rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
        return h.hexdigest()

    def test_the_hash_covers_every_source_the_contract_is_rendered_from(self):
        """The rendered opencode contract is `always_on_core()` (policy.CORE
        filtered by CORE_RULES, in hooks/tezgah_context.py) plus the skill, and
        docs/operations.md names all three as sources. With the renderer out of
        the list an edit to it could not move the hash, so --refresh printed
        "contract is current" and every opencode session kept the previous
        always-on text - the one host that cannot see the edit any other way."""
        self.assertEqual(
            sorted(setup_module().CONTRACT_SOURCES),
            ["hooks/tezgah_context.py", "hooks/tezgah_policy.py",
             "skills/tezgah-contract/SKILL.md"])

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
        # the predecessor harness's own filenames, which is what --adopt moves
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

    def marker_agents(self, body):
        os.makedirs(self.path("Projects"), exist_ok=True)
        path = self.path("Projects", "AGENTS.md")
        with open(path, "w") as fh:
            fh.write(body)
        return path

    def test_adopt_strips_the_projects_harness_marker_but_keeps_the_rest(self):
        """The marker block points every session at a POLICY.md inside
        ~/.codex/projects-harness, so after the harness moves the block is a
        dead pointer - stripped, with the file it came from moved aside first
        (adopt moves, never deletes)."""
        path = self.marker_agents(
            "# My notes\n\n"
            "<!-- codex-projects-harness:start -->\n"
            "read /home/x/.codex/projects-harness/POLICY.md\n"
            "<!-- codex-projects-harness:end -->\n\nmore\n")
        proc = self.setup("--adopt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("codex-projects-harness", self.read_text(path))
        self.assertIn("# My notes", self.read_text(path))
        self.assertIn("more", self.read_text(path))
        adopted = []
        for root, _dirs, files in os.walk(self.path(".config", "tezgah", "adopted")):
            adopted += files
        self.assertIn("AGENTS.md", adopted)

    def test_predecessors_and_adopt_handle_a_marker_only_agents_file(self):
        path = self.marker_agents(
            "<!-- codex-projects-harness:start -->\n"
            "read POLICY.md\n"
            "<!-- codex-projects-harness:end -->\n")
        report = self.setup("--report", "--hosts", "codex")
        self.assertIn("projects-harness marker", report.stdout)
        proc = self.setup("--adopt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(path),
                         "a marker-only file must not be left as an empty shell")
        adopted = []
        for root, _dirs, files in os.walk(self.path(".config", "tezgah", "adopted")):
            adopted += files
        self.assertIn("AGENTS.md", adopted)


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
        # a real codegraph binary makes the graph-backed roles active, so the
        # agent set is generated
        self.env["TEZGAH_CODEGRAPH_BIN"] = sys.executable
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
        self.assertIn("codegraph", mcp["mcpServers"])
        # omp spawns `command` as one executable and passes `args`; the argv must
        # round-trip. A list in `command` is spawned comma-joined (ENOENT).
        for srv in tezgah_apps.servers():
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

    def test_install_refreshes_a_stale_entry_and_keeps_the_user_keys(self):
        """The writer used to only add a missing server, so an entry an older
        tezgah wrote kept its argv forever: a bumped pin or a new `--caps` never
        reached an existing install. That is how `--caps=testing,storage,network`
        landed on one host and none of the others."""
        path = self.path(".omp", "agent", "mcp.json")
        self.write_json(path, {"mcpServers": {"playwright": {
            "type": "stdio", "command": "npx",
            "args": ["-y", "@playwright/mcp@0.0.1", "--isolated"],
            "timeout": 1234}}})
        self.install()
        entry = self.read_json(path)["mcpServers"]["playwright"]
        self.assertIn("--caps=testing,storage,network", entry["args"])
        self.assertNotIn("@playwright/mcp@0.0.1", entry["args"])
        self.assertEqual(entry["timeout"], 1234)  # the user's key survives

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
        # the file held nothing but tezgah's keys ($schema, mcpServers), so the
        # uninstall removes it: leaving an empty registration is the shape that
        # reads as wired
        self.assertFalse(os.path.exists(self.path(".omp", "agent", "mcp.json")))
        self.assertFalse(os.path.exists(
            self.path(".omp", "agent", "hooks", "pre", "tezgah-hook.ts")))


class PowershellMatcher(SetupBase):
    """A PowerShell call is a shell call, so every shell rule has to reach it.

    `powershell` is in `BASH_TOOLS` (`hooks/tezgah_integrity.py:113-114`),
    which the secret, shortcut, loop, retry and task-shell rules
    are all keyed on - so refusing one is the design. What decides whether the
    gate sees the call at all is the host's own matcher (Claude's manifest, the
    dsh manifest) or omp's `GATED` list: a name the PostToolUse side carries
    that the PreToolUse side does not is recorded in the ledger and never
    refused, which is the state this class exists to keep out. The spellings
    are the hosts': `PowerShell` on the Claude-family wire and `pwsh` for dsh's
    own tool package (`tests/test_dsh_hooks.py:107-110`)."""

    # Claude's matcher dialect, which the dsh bridge implements: a pattern made
    # only of these characters is a list of exact names, anything else an
    # unanchored regular expression. Mirrors tests/test_dsh_hooks.py.
    LITERAL = re.compile(r"^[A-Za-z0-9_\- ,|]+$")

    def selects(self, matcher, tool):
        if self.LITERAL.match(matcher):
            return tool in matcher.split("|")
        return re.search(matcher, tool) is not None

    def pretool_matchers(self, path):
        with open(os.path.join(REPO, path)) as fh:
            groups = json.load(fh)["hooks"]["PreToolUse"]
        return [g["matcher"] for g in groups if g.get("matcher")]

    def test_the_two_manifests_gate_the_powershell_spellings(self):
        for path in ("hooks/hooks.json", "hosts/dsh/hooks.json"):
            with self.subTest(path=path):
                for tool in ("PowerShell", "pwsh"):
                    self.assertTrue(
                        any(self.selects(m, tool)
                            for m in self.pretool_matchers(path)),
                        "%s: PreToolUse never runs the gate for %s"
                        % (path, tool))

    def test_the_written_omp_hook_gates_the_shell_name(self):
        self.env["TEZGAH_CODEGRAPH_BIN"] = sys.executable  # as OmpHost.install does
        proc = self.setup("--install", "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hook = self.read_text(
            self.path(".omp", "agent", "hooks", "pre", "tezgah-hook.ts"))
        gated = re.search(r"const GATED = \[(.*?)\];", hook, re.S)
        self.assertIsNotNone(gated, "the written omp hook has no GATED list")
        # the list is matched case-insensitively, so the one lowercase entry is
        # what makes a `PowerShell` call on that host reach the gate
        self.assertIn('"powershell"', gated.group(1))


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
        # the count is read from SKILLS, the installer's one definition of a
        # shipped skill: a literal here goes stale on every added skill, which is
        # a failing test about arithmetic rather than about the report.
        skills = len(setup_module().SKILLS)
        for band in ("core contract (always-on, per session)", "per-turn reminder",
                     "skill metadata (%d)" % skills, "subagent metadata (5)",
                     "conditional rules (armed by task class)",
                     "full contract (on demand)", "MCP tool schemas"):
            self.assertIn(band, out)

    def test_budget_numbers_are_ordered_and_nonzero(self):
        proc = self.setup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        skills = len(setup_module().SKILLS)
        core = re.search(r"core contract \(always-on, per session\)\s+~\s*([\d.]+)k tok", proc.stdout)
        skill = re.search(r"skill metadata \((\d+)\)\s+~\s*([\d.]+)k tok", proc.stdout)
        ondemand = re.search(r"full contract \(on demand\)\s+~\s*([\d.]+)k tok", proc.stdout)
        self.assertIsNotNone(core)
        self.assertIsNotNone(skill)
        self.assertIsNotNone(ondemand)
        self.assertEqual(skill.group(1), str(skills),
                         "the report counted a different skill set than SKILLS")
        self.assertGreater(float(core.group(1)), 0)
        self.assertGreater(float(skill.group(2)), 0)
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
        # MCP_IDS, not the defaults: this is every command tezgah may have
        # written, so the pin check covers chrome-devtools too, which is
        # registered but off by default.
        return [s["command"] for s in tezgah_apps.servers(tezgah_apps.MCP_IDS)]

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


def changelog_version():
    """The newest release heading in CHANGELOG.md, read the way the reader reads
    it - the first `## [x.y.z]` in the file."""
    with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as fh:
        return re.search(r"^## \[(\d+\.\d+\.\d+)\]", fh.read(), re.M).group(1)


class PluginVersion(SetupBase):
    """`--version` and the status line's `tezgah vX.Y.Z` prefix are two prints of
    one value, so the reader lives in the core and the installer calls into it.
    A reader left in the installer is a second answer to "which version is
    this", which is the pair the lessons ledger records drifting apart."""

    def version(self):
        proc = subprocess.run([sys.executable, SETUP, "--version"],
                              capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def test_it_prints_the_newest_changelog_release(self):
        self.assertEqual(self.version(), changelog_version())

    def test_the_installer_has_no_reader_of_its_own(self):
        # the installer's answer has to BE the core's, not a second reading of
        # the same manifest and changelog: patching the core's answer is the way
        # to see that it follows, and a reader left in the installer would not
        module = setup_module()
        self.addCleanup(setattr, module.tezgah_context, "version",
                        module.tezgah_context.version)
        module.tezgah_context.version = lambda: "9.9.9"
        self.assertEqual(module.plugin_version(), "9.9.9")
        module.tezgah_context.version = lambda: None
        self.assertEqual(module.plugin_version(), "unknown")
        self.assertEqual(self.version(), changelog_version())

    def test_a_checkout_with_neither_manifest_nor_changelog_answers_unknown(self):
        """The status line degrades to the bare name when the version cannot be
        read; this CLI's whole output *is* the value, so it keeps answering the
        word it always answered rather than printing nothing or a placeholder.

        A child, because the reader's root is a module constant and the CLI
        resolves it while it builds its parser: patching it in this process
        would leave the number every later case reads."""
        empty = self.path("empty")
        os.makedirs(empty, exist_ok=True)
        body = ("import importlib.machinery, importlib.util, sys\n"
                "loader = importlib.machinery.SourceFileLoader('s', sys.argv[1])\n"
                "m = importlib.util.module_from_spec("
                "importlib.util.spec_from_loader('s', loader))\n"
                "sys.modules['s'] = m\n"
                "loader.exec_module(m)\n"
                "assert m.tezgah_context.version() is not None\n"
                "m.tezgah_context.PLUGIN_ROOT = sys.argv[2]\n"
                "assert m.tezgah_context.version() is None\n"
                "m.main(['tezgah-setup', '--version'])\n")
        proc = subprocess.run([sys.executable, "-c", body, SETUP, empty],
                              capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "unknown")


class VersionPrefixIsNotContract(SetupBase):
    """The prefix belongs to the status line, not to the text a session is told:
    a version in the injected contract would be paid for every turn and would
    still be stale in a session that outlived a release."""

    def test_the_always_on_band_is_unchanged(self):
        module = setup_module()
        band = dict(module.context_budget()[0])[
            "core contract (always-on, per session)"]
        # Re-pinned 2026-09-21 with the graph-engine cutover: the code-discovery
        # paragraph names codegraph and its real surface now, which is 8 bytes
        # shorter than the codebase-memory-mcp wording it replaced. Re-pinned
        # 2026-09-22: the CORE ADHD paragraph names rule 10's recap/closer ban,
        # rule 5's mid-work exception and the `i-have-adhd` skill read it had
        # dropped (+272 B). Re-pinned 2026-09-26: the consent paragraph left
        # CORE with the consent gate (-575 B). The band is here to catch an
        # accidental move, so a deliberate one is recorded.
        self.assertEqual(8077, band, "the always-on band moved")
        self.assertNotIn("tezgah v", module.tezgah_context.always_on_core())


if __name__ == "__main__":
    unittest.main()
