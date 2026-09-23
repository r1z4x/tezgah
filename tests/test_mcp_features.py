"""MCP feature toggles: one registry, one persisted selection, one reconcile.

Written from `.tezgah/plans/open/012-mcp-feature-toggles.md`'s acceptance list rather
than from `bin/tezgah-setup`, so it can fail on the behaviour the plan promises
instead of agreeing with whatever the code happens to do.

Every test runs the installer in a throwaway HOME with fake host dirs (the same
shape `tests/test_setup.py` uses), so the real ~/.claude, ~/.codex,
~/.config/opencode, ~/.cursor, ~/.dsh and ~/.omp are never touched, and none of
these tests needs the network.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")
ALL = "claude,codex,opencode,cursor,dsh,omp"

sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_apps  # noqa: E402

PLAYWRIGHT = "mcp-playwright"
MOBILE = "mcp-mobile-mcp"
DEVTOOLS = "mcp-chrome-devtools"
# A feature id is not a server name: the id is what config.json stores, the name
# is what a host file carries, and a test that confuses them asserts nothing.
MOBILE_SERVER = "mobile-mcp"
DEVTOOLS_SERVER = "chrome-devtools"
# Each host stores the same row differently: a file, and the key it holds its MCP
# servers under (None for the two shapes that are not a JSON map).
HOST_FILES = {
    "codex": (".codex/config.toml", None),
    "opencode": (".config/opencode/opencode.json", "mcp"),
    "cursor": (".cursor/mcp.json", "mcpServers"),
    "dsh": (".dsh/cordis.patch.yml", None),
    "omp": (".omp/agent/mcp.json", "mcpServers"),
}


def setup_module():
    """`bin/tezgah-setup` as a module, for the constants and pure functions a
    test reads directly (importing it defines paths and functions only)."""
    import importlib.machinery
    import importlib.util
    if "tezgah_setup_mcp_probe" in sys.modules:
        return sys.modules["tezgah_setup_mcp_probe"]
    loader = importlib.machinery.SourceFileLoader("tezgah_setup_mcp_probe", SETUP)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("tezgah_setup_mcp_probe", loader))
    sys.modules["tezgah_setup_mcp_probe"] = module
    loader.exec_module(module)
    return module


class FeaturesBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        for d in (".claude", ".codex", ".cursor", ".dsh", ".config/opencode",
                  ".omp/agent"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_CODEGRAPH_BIN": os.path.join(self.home, "no-such-codegraph"),
            "TEZGAH_ORX_BIN": os.path.join(self.home, "no-such-orx"),
            # never let a test hit the network: --install installs missing deps
            # by default
            "TEZGAH_NO_DEPS": "1",
        }

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def setup(self, *args, stdin="", env=None):
        return subprocess.run([sys.executable, SETUP] + list(args),
                              capture_output=True, text=True,
                              env=env or self.env, input=stdin, timeout=180)

    def read_json(self, path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def read_text(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def write_text(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def config(self):
        return self.read_json(self.path(".config", "tezgah", "config.json"))

    def features_key(self):
        return self.config().get("features")

    def row(self, text, label):
        """The report line carrying this label, "" when the row is absent."""
        return next((line for line in text.splitlines() if label in line), "")

    def row_with(self, text, *needles):
        """The one line carrying every needle, "" when there is none."""
        return next((line for line in text.splitlines()
                     if all(n in line for n in needles)), "")

    def wired(self, host, name=MOBILE_SERVER):
        """True when `host`'s own file carries the row for `name`."""
        rel, holder = HOST_FILES[host]
        if holder:
            return name in (self.read_json(self.path(rel)).get(holder) or {})
        text = self.read_text(self.path(rel))
        return ("[mcp_servers.%s]" % name if host == "codex"
                else "serverName: %s" % name) in text

    def install(self, *args, **kwargs):
        proc = self.setup("--install", "--hosts", ALL, *args, **kwargs)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc


class Defaults(FeaturesBase):
    def test_an_absent_features_key_wires_todays_servers(self):
        """A config.json with no `features` key behaves exactly as today: the
        declared default is per id, never inferred from a missing key."""
        self.write_json(self.path(".config", "tezgah", "config.json"),
                        {"roots": [self.path("Projects")], "hosts": ALL.split(",")})
        self.install()
        self.assertNotIn("chrome-devtools", self.read_text(self.path(".codex", "config.toml")))
        for host in HOST_FILES:
            self.assertTrue(self.wired(host), "%s lost the default server" % host)
        # the install records the selection it resolved, so the next run has one
        self.assertEqual(sorted(self.features_key() or []),
                         sorted(tezgah_apps.defaults()))

    def test_a_disabled_by_default_feature_is_absent_everywhere(self):
        self.install()
        for host in HOST_FILES:
            self.assertFalse(self.wired(host, DEVTOOLS_SERVER),
                             "%s wired a feature that is off by default" % host)


class Selection(FeaturesBase):
    def test_enable_persists_and_a_later_run_reads_it_back(self):
        self.install()
        proc = self.setup("--enable", DEVTOOLS)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(DEVTOOLS, self.features_key())
        # a fresh process reads the file back, not a process global
        report = self.setup("--report", "--hosts", "codex").stdout
        self.assertTrue(self.row(report, "app MCP chrome-devtools").strip()
                        .startswith("ok"),
                        self.row(report, "app MCP chrome-devtools"))
        self.assertIn("[mcp_servers.chrome-devtools]",
                      self.read_text(self.path(".codex", "config.toml")))

    def test_disable_removes_the_row_in_every_host_writer(self):
        self.install()
        proc = self.setup("--disable", MOBILE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for host in HOST_FILES:
            self.assertFalse(self.wired(host), "%s kept the disabled row" % host)
            report = self.setup("--report", "--hosts", host).stdout
            row = self.row(report, "app MCP mobile-mcp")
            self.assertTrue(row.strip().startswith("ok"),
                            "a disabled, unwired server is not a green row: %r" % row)
            self.assertIn("deselected", row)
        self.assertNotIn(MOBILE, self.features_key())

    def test_enable_puts_it_back(self):
        self.install()
        self.setup("--disable", MOBILE)
        proc = self.setup("--enable", MOBILE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for host in HOST_FILES:
            self.assertTrue(self.wired(host), "%s did not get the row back" % host)
        self.assertIn(MOBILE, self.features_key())

    def test_an_unknown_id_exits_one_and_names_the_known_ids(self):
        for flag in ("--enable", "--disable"):
            proc = self.setup(flag, "mcp-nope")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            out = proc.stdout + proc.stderr
            self.assertIn("mcp-nope", out)
            for known in (PLAYWRIGHT, MOBILE, DEVTOOLS):
                self.assertIn(known, out, "%s: unknown-id refusal named no ids" % flag)

    def test_features_lists_every_id_with_its_state_and_exits_zero(self):
        self.install()
        self.setup("--enable", DEVTOOLS)
        proc = self.setup("--features")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for feature in (PLAYWRIGHT, MOBILE, DEVTOOLS):
            line = self.row_with(proc.stdout, feature, "default")
            self.assertTrue(line, "--features listed no row for %s" % feature)
            self.assertIn("selected", line)
        self.assertIn("on", self.row_with(proc.stdout, DEVTOOLS, "default"))

    def test_the_two_non_mcp_features_are_registered_in_the_same_table(self):
        """The mechanism generalises past MCP: plan 011's ai-research payload
        and orx are rows in the same table, listed by the same command."""
        proc = self.setup("--features")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for feature in ("ai-research", "orx"):
            self.assertTrue(self.row_with(proc.stdout, feature, "default"),
                            "--features listed no row for %s" % feature)
        self.assertEqual([r["id"] for r in tezgah_apps.REGISTRY if r["id"] == "orx"],
                         ["orx"])
        # the table is the only place it is described: DEPS' orx row comes from it
        module = setup_module()
        dep = next(d for d in module.DEPS if d["name"] == "orx")
        row = next(r for r in tezgah_apps.REGISTRY if r["id"] == "orx")
        self.assertEqual(dep["cmd"], row["dep"]["cmd"])
        self.assertEqual(dep["needs"], row["dep"]["needs"])


class DevtoolsSugar(FeaturesBase):
    def test_devtools_is_sugar_for_enable_chrome_devtools(self):
        self.install()
        sugar = self.setup("--devtools", "--report", "--hosts", "codex")
        self.assertIn("[mcp_servers.%s]" % DEVTOOLS_SERVER,
                      self.read_text(self.path(".codex", "config.toml")))
        # Both runs have to start from the same state (chrome-devtools off) or
        # the diff is a statement about what the first run left behind rather
        # than about the flag: the second would find the selection already made.
        self.setup("--disable", DEVTOOLS, "--hosts", "codex")
        explicit = self.setup("--enable", DEVTOOLS, "--report", "--hosts", "codex")
        self.assertEqual(sugar.stdout, explicit.stdout)


class Ghosts(FeaturesBase):
    def test_a_disabled_but_wired_row_reads_miss_and_names_the_ghost(self):
        self.install()
        self.setup("--disable", MOBILE)
        # what an older release left behind: the row is back, the selection is not
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.write_text(self.path(".codex", "config.toml"),
                        toml + "\n[mcp_servers.%s]\ncommand = \"npx\"\n"
                        % MOBILE_SERVER)
        report = self.setup("--report", "--hosts", "codex").stdout
        row = self.row(report, "app MCP mobile-mcp")
        self.assertTrue(row.strip().startswith("MISS"), row)
        self.assertIn("ghost", row)
        self.assertIn("mobile-mcp", row)

    def test_a_selected_but_missing_row_reads_miss(self):
        self.install()
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.write_text(self.path(".codex", "config.toml"),
                        toml.replace("[mcp_servers.%s]" % MOBILE_SERVER, "xx"))
        row = self.row(self.setup("--report", "--hosts", "codex").stdout,
                       "app MCP mobile-mcp")
        self.assertTrue(row.strip().startswith("MISS"), row)

    def test_a_reconcile_removes_a_ghost_and_keeps_a_foreign_name(self):
        self.install()
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.write_text(self.path(".codex", "config.toml"),
                        toml + "\n[mcp_servers.mine]\ncommand = \"echo\"\n")
        proc = self.setup("--disable", MOBILE, "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        after = self.read_text(self.path(".codex", "config.toml"))
        self.assertNotIn("[mcp_servers.%s]" % MOBILE_SERVER, after)
        self.assertIn("[mcp_servers.mine]", after,
                      "a server tezgah never owned was removed")

        # the same convergence from the install path, which is what an older
        # release's file meets on the next `--install`
        self.write_text(self.path(".codex", "config.toml"),
                        self.read_text(self.path(".codex", "config.toml"))
                        + "\n[mcp_servers.%s]\ncommand = \"npx\"\n" % MOBILE_SERVER)
        proc = self.setup("--install", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        after = self.read_text(self.path(".codex", "config.toml"))
        self.assertNotIn("[mcp_servers.%s]" % MOBILE_SERVER, after,
                         "an install left the ghost the selection turned off")
        self.assertIn("[mcp_servers.mine]", after)
        self.assertIn("[mcp_servers.playwright]", after)

    def test_uninstall_still_clears_a_row_an_older_release_left(self):
        """app_mcp_names() keeps meaning "every name tezgah may have written", so
        uninstall clears a row for a feature that is off today."""
        self.install()
        toml = self.read_text(self.path(".codex", "config.toml"))
        self.write_text(self.path(".codex", "config.toml"),
                        toml + "\n[mcp_servers.%s]\ncommand = \"npx\"\n"
                        % DEVTOOLS_SERVER)
        proc = self.setup("--uninstall", "--hosts", "codex")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        after = self.read_text(self.path(".codex", "config.toml"))
        self.assertNotIn("chrome-devtools", after)
        self.assertIn("mcp_servers.codegraph", after)


class Idempotence(FeaturesBase):
    def test_a_repeated_disable_writes_nothing(self):
        self.install()
        self.setup("--disable", MOBILE)
        path = self.path(".omp", "agent", "mcp.json")
        before_mtime = os.stat(path).st_mtime_ns
        backups = [p for p in os.listdir(os.path.dirname(path))
                   if p.endswith(".tezgah-bak")]
        time.sleep(0.01)
        proc = self.setup("--disable", MOBILE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(os.stat(path).st_mtime_ns, before_mtime,
                         "a repeated disable rewrote the host file")
        self.assertEqual([p for p in os.listdir(os.path.dirname(path))
                          if p.endswith(".tezgah-bak")], backups)

    # Every generated artifact a disable re-renders: the always-on omp contract
    # and the three files opencode reads. Their writers had no content guard
    # (unlike write_json/set_managed_block), so a repeated --disable rewrote all
    # four and left an identical RULES.md.tezgah-bak behind while the host-JSON
    # case above passed - which is why that case missed this.
    GENERATED = ((".omp", "agent", "RULES.md"),
                 (".config", "tezgah", "opencode-contract.md"),
                 (".config", "tezgah", "opencode-skills.md"),
                 (".config", "tezgah", "opencode-skills.full.md"))

    def backups(self):
        return sorted(os.path.join(d, n)
                      for d, _dirs, names in os.walk(self.home)
                      for n in names if n.endswith(".tezgah-bak"))

    def test_a_repeated_disable_rewrites_none_of_the_generated_files(self):
        self.install()
        self.setup("--disable", MOBILE)
        paths = [self.path(*p) for p in self.GENERATED]
        for path in paths:
            self.assertTrue(os.path.isfile(path), path)
        before = {path: os.stat(path).st_mtime_ns for path in paths}
        backups = self.backups()
        time.sleep(0.01)
        proc = self.setup("--disable", MOBILE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for path in paths:
            self.assertEqual(os.stat(path).st_mtime_ns, before[path],
                             "an unchanged run rewrote %s" % path)
        self.assertEqual(self.backups(), backups,
                         "an unchanged run laid a backup")
        # the symptom the finding names: a backup that is a copy of its own file
        for path in paths:
            bak = path + ".tezgah-bak"
            if os.path.exists(bak):
                self.assertNotEqual(self.read_text(bak), self.read_text(path),
                                    "%s got an identical-bytes backup" % path)

    def test_disable_then_enable_restores_the_same_wiring(self):
        """A disable then an enable restores the same wiring, and the same
        config. Value-equal, not byte-identical: the re-added server is
        re-appended, so JSON key order differs while the object is the same -
        key order is not a property the round trip owns. config.json itself is
        byte-identical, and dsh's row is carried in a managed block."""
        self.install()
        path = self.path(".omp", "agent", "mcp.json")
        before = json.loads(self.read_text(path))
        self.setup("--disable", MOBILE)
        self.setup("--enable", MOBILE)
        self.assertEqual(json.loads(self.read_text(path)), before)
        self.assertEqual(sorted(self.features_key()),
                         sorted(tezgah_apps.defaults()))


class OrxInstall(FeaturesBase):
    """`orx install-skills` is the orx feature's payload, not a step of every
    install. Item 16 makes the registry the only switch, so a deselected orx runs
    no command - while a selected one still does."""

    def stub_orx(self):
        """A TEZGAH_ORX_BIN that records every call, so "ran no command" is
        observed in a file rather than inferred from output."""
        log = self.path("orx-calls.log")
        path = self.path("bin", "orx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.write_text(path, "#!/bin/sh\nprintf '%s\\n' \"$*\" >> "
                         + json.dumps(log) + "\n")
        os.chmod(path, 0o755)
        return path, log

    def calls(self, log):
        return self.read_text(log).splitlines() if os.path.exists(log) else []

    def orx_env(self, orx):
        return dict(self.env, TEZGAH_ORX_BIN=orx)

    def test_an_install_without_orx_runs_no_orx_command(self):
        orx, log = self.stub_orx()
        proc = self.install("--disable", "orx", env=self.orx_env(orx))
        self.assertEqual(self.calls(log), [],
                         "orx ran while its feature was deselected")
        self.assertIn("skipped: orx is not selected", proc.stdout)

    def test_an_install_with_orx_selected_still_runs_it(self):
        orx, log = self.stub_orx()
        self.install(env=self.orx_env(orx))
        self.assertTrue(any("install-skills" in call for call in self.calls(log)),
                        "orx install-skills never ran for a selected feature")


class Markers(FeaturesBase):
    def test_a_disable_writes_no_marker_file(self):
        """The selection is the only persister of the choice: the marker
        vocabulary (~/.config/tezgah/*.off) governs a session, not a host."""
        self.install()
        proc = self.setup("--disable", PLAYWRIGHT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for root in (self.path(".config", "tezgah"), self.path(".claude")):
            offs = [n for n in os.listdir(root) if n.endswith(".off")]
            self.assertEqual(offs, [], "%s got a marker file" % root)


class RestartHint(FeaturesBase):
    def test_a_write_that_changes_a_host_file_prints_the_restart_hint(self):
        self.install()
        proc = self.setup("--disable", MOBILE, "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("restart", proc.stdout.lower())
        self.assertIn("omp", proc.stdout)
        # nothing changed on the second run, so there is nothing to restart for
        again = self.setup("--disable", MOBILE, "--hosts", "omp")
        self.assertNotIn("restart", again.stdout.lower(),
                         "the hint fired without a write")


class Deps(FeaturesBase):
    def test_the_install_time_table_leaves_a_servers_runtime_out(self):
        """A feature that carries a server owns a heavy runtime - the browser
        build Playwright launches on its first tool call - and a plain
        `--install` must not download it. The install-time table therefore holds
        the features with no server, and a feature's row is added by naming it."""
        module = setup_module()
        names = [d["name"] for d in module.DEPS]
        self.assertIn("orx", names)  # the row comes from the registry table
        for fid in tezgah_apps.MCP_IDS:
            self.assertNotIn(fid, names,
                             "a plain --install would pull %s's runtime" % fid)
        self.assertEqual(names, [d["name"] for d in module.dep_rows()])
        rows = [d["name"] for d in module.dep_rows(only=set(tezgah_apps.MCP_IDS))]
        self.assertIn("mcp-playwright", rows, "--enable cannot find the row")
        self.assertEqual(rows.count("orx"), 1,
                         "an --enable considers the base table too, once")

    def test_enable_dry_run_prints_the_command_it_would_run_and_runs_nothing(self):
        """`orx` is unmet by construction here (TEZGAH_ORX_BIN names a path that
        does not exist), so the dependency half has to name the vendor command
        rather than silently wire a payload whose tool is absent."""
        proc = self.setup("--enable", "orx", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("would run", proc.stdout)
        self.assertIn("openresearch.sh", proc.stdout)
        self.assertFalse(os.path.exists(self.path(".local", "bin", "orx")))

    def test_enable_installs_the_dependency_in_the_same_run(self):
        """The probe is missing, so the run has to satisfy it - proven by a fake
        `sh` (the only shell the vendor command names) that creates the payload:
        the probe must read met afterwards without a second command.

        The fake bin dir also carries the install-time rows' tools, because an
        enable considers that table beside its own feature's row: without them
        the run would reach for a real vendor installer on the machine."""
        bin_dir = self.path("fakebin")
        payload = self.path(".local", "bin", "orx")
        self.write_text(os.path.join(bin_dir, "sh"),
                        "#!/bin/sh\nmkdir -p %s\n"
                        "printf '#!/bin/sh\\nexit 0\\n' > %s\n"
                        "chmod 755 %s\n" % (os.path.dirname(payload), payload, payload))
        for stub in ("pnpm", "cursor-agent"):
            self.write_text(os.path.join(bin_dir, stub), "#!/bin/sh\nexit 0\n")
        for name in os.listdir(bin_dir):
            os.chmod(os.path.join(bin_dir, name), 0o755)
        env = dict(self.env, PATH=bin_dir + os.pathsep + self.env["PATH"],
                   TEZGAH_ORX_BIN=payload)
        # the dep step is what this test exercises, so the escape hatch that
        # skips it in every other test comes off
        env.pop("TEZGAH_NO_DEPS")
        proc = self.setup("--enable", "orx", env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.exists(payload), "the dep command did not run")
        self.assertIn("orx installed", proc.stdout)

    def test_enable_names_its_dependency_state(self):
        proc = self.setup("--enable", DEVTOOLS, "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(self.row(proc.stdout, DEVTOOLS) or
                        self.row(proc.stdout, "dependencies:"),
                        "enabling printed no dependency line")

    def test_a_disable_never_uninstalls_anything(self):
        self.install()
        log = self.path(".config", "tezgah", "install.log")
        before = self.read_text(log) if os.path.exists(log) else None
        orx = self.path(".local", "bin", "orx")
        self.write_text(orx, "#!/bin/sh\nexit 0\n")
        os.chmod(orx, 0o755)
        proc = self.setup("--disable", PLAYWRIGHT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("running:", proc.stdout)
        # the install-deps step owns this header; the features table says
        # "would run" as a state, which is not a command being run
        self.assertNotIn("dependencies:", proc.stdout)
        self.assertTrue(os.path.exists(orx), "a disable removed a payload")
        after = self.read_text(log) if os.path.exists(log) else None
        self.assertEqual(after, before, "a disable wrote to the install log")

    def test_an_unmet_dependency_is_named_rather_than_wired_silently(self):
        """--features is where an unmet probe has to be visible, because the
        payload it belongs to cannot run without it. The fixture points
        TEZGAH_ORX_BIN at a path that does not exist, so the orx row is unmet
        without touching the machine's real PATH."""
        proc = self.setup("--features")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        row = self.row_with(proc.stdout, "orx", "unmet")
        self.assertTrue(row, proc.stdout)


class McpJson(FeaturesBase):
    def test_the_committed_mcp_json_is_the_rendered_default_selection(self):
        module = setup_module()
        rendered = module.render_mcp_json(tezgah_apps.defaults())
        with open(os.path.join(REPO, ".mcp.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), json.loads(rendered))
        # The render is Claude's only MCP channel: it carries the graph row and
        # tezgah's own surface beside the selected app servers, because a name
        # left out here is a name Claude never gets.
        self.assertEqual(sorted(json.loads(rendered)["mcpServers"]),
                         ["codegraph", "mobile-mcp", "playwright", "tezgah"])

    def test_write_mcp_json_writes_the_file_and_is_idempotent(self):
        """Through the same function the flag calls. The flag itself writes the
        checkout's file, which a test must not touch: what it adds over this call
        is the default path and nothing else."""
        module = setup_module()
        path = self.path("out", ".mcp.json")
        self.assertEqual(module.write_mcp_json(path, tezgah_apps.defaults()), 0)
        first = self.read_text(path)
        self.assertEqual(module.write_mcp_json(path, tezgah_apps.defaults()), 0)
        self.assertEqual(self.read_text(path), first)
        self.assertEqual(sorted(json.loads(first)["mcpServers"]),
                         ["codegraph", "mobile-mcp", "playwright", "tezgah"])

    def test_sync_carries_the_rendered_file_and_the_copy_stays_current(self):
        copy = self.path(".claude", "plugins", "cache", "tezgah")
        os.makedirs(os.path.join(copy, "hooks"), exist_ok=True)
        shutil.copy2(os.path.join(REPO, "hooks", "tezgah_policy.py"),
                     os.path.join(copy, "hooks", "tezgah_policy.py"))
        proc = self.setup("--sync")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rendered = json.loads(self.read_text(os.path.join(copy, ".mcp.json")))
        self.assertEqual(sorted(rendered["mcpServers"]),
                         ["codegraph", "mobile-mcp", "playwright", "tezgah"])
        row = self.row(self.setup("--report", "--hosts", "claude").stdout,
                       "plugin copy current")
        self.assertTrue(row.strip().startswith("ok"), row)

    def test_a_disabled_feature_leaves_the_copy_named_as_not_matching(self):
        copy = self.path(".claude", "plugins", "cache", "tezgah")
        os.makedirs(os.path.join(copy, "hooks"), exist_ok=True)
        shutil.copy2(os.path.join(REPO, "hooks", "tezgah_policy.py"),
                     os.path.join(copy, "hooks", "tezgah_policy.py"))
        self.setup("--sync")
        self.setup("--disable", MOBILE)
        report = self.setup("--report", "--hosts", "claude").stdout
        row = self.row(report, "MCP server set in %s" % copy)
        self.assertTrue(row.strip().startswith("MISS"), row)
        self.assertIn(MOBILE_SERVER, row)
        self.setup("--sync")
        row = self.row(self.setup("--report", "--hosts", "claude").stdout,
                       "MCP server set in %s" % copy)
        self.assertTrue(row.strip().startswith("ok"), row)


class McpSchemas(FeaturesBase):
    def test_the_band_measures_the_selected_set_only(self):
        self.install()
        env = dict(self.env, PATH=self.path("empty-bin"))
        os.makedirs(self.path("empty-bin"), exist_ok=True)
        both = self.setup("--mcp-schemas", env=env).stdout
        self.assertIn("playwright", both)
        self.assertIn("mobile-mcp", both)
        self.setup("--disable", MOBILE)
        one = self.setup("--mcp-schemas", env=env).stdout
        self.assertIn("playwright", one)
        self.assertNotIn("mobile-mcp", one,
                         "the band reported a server that is not wired")


if __name__ == "__main__":
    unittest.main()
