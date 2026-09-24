"""bin/tezgah-setup: the MCP rows tezgah writes into all six hosts.

The server itself is `bin/tezgah-mcp` and its own protocol is tested in
`tests/test_mcp_server.py`; this file holds the wiring. One argv
(`tezgah_mcp_command()`), written into every host the installer arms, unchanged
by a second install, and removable with `--uninstall` without touching the graph
row or a server of the user's own.

Every test runs in a throwaway HOME. Claude's MCP channel is the plugin COPY's
`.mcp.json` - there is no `install_claude` MCP writer, the copy is what Claude
loads - so those tests build a copy under the fake `~/.claude/plugins/cache`
first, and the row there must name that copy's own `bin/tezgah-mcp`.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO, "bin", "tezgah-setup")
ALL = "claude,codex,opencode,cursor,dsh,omp"
HOSTS = ALL.split(",")
SERVER = "tezgah"
SCRIPT = os.path.join(REPO, "bin", "tezgah-mcp")
COPY_PARTS = (".claude", "plugins", "cache", "tezgah", "tezgah", "1.0")
ROW = "MCP tezgah server wired"
# codegraph's row is written by the same render into Claude's file and by each
# host's own writer into its config, so it is the neighbour an uninstall must
# leave alone.
GRAPH = "codegraph"


def setup_module():
    """bin/tezgah-setup as a module, for the two functions `--write-mcp-json`
    calls. Importing it is side-effect free (its module level is paths and
    definitions)."""
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


def toml_entry(text, name):
    """The `command` and `args` a `[mcp_servers.<name>]` table declares, or None.

    Read here rather than imported from the installer: an assertion that used the
    writer's own reader could agree with the writer about a table that is not
    there."""
    block = re.search(r"(?ms)^\[mcp_servers\.%s\]\s*$(.*?)(?=^\[|\Z)"
                      % re.escape(name), text)
    if not block:
        return None
    command = re.search(r'(?m)^command = "(.*)"$', block.group(1))
    args = re.search(r"(?m)^args = \[(.*)\]$", block.group(1))
    return {"command": command.group(1) if command else None,
            "args": [a.strip('"') for a in args.group(1).split(", ")]
            if args and args.group(1) else []}


def dsh_entry(text, name):
    """The argv one `serverName: <name>` row of the dsh patch block declares."""
    block = re.search(r"(?ms)^\s*serverName: %s\s*$(.*?)(?=^\s*serverName:|\Z)"
                      % re.escape(name), text)
    if not block:
        return None
    command = re.search(r"(?m)^\s*command:\s*(\S+)\s*$", block.group(1))
    args = re.search(r"(?m)^\s*args:\s*\[(.*?)\]\s*$", block.group(1))
    return {"command": command.group(1) if command else None,
            "args": re.findall(r"'([^']*)'", args.group(1)) if args else []}


class WiringBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        for d in (".claude", ".codex", ".cursor", ".dsh", ".config/opencode", ".omp"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LANG": "C.UTF-8",
            # no graph binary, no orx, no dependency installs: this file is about
            # the MCP rows, and the graph row is written by every host either way
            "TEZGAH_CODEGRAPH_BIN": self.path("no-such-codegraph"),
            "TEZGAH_ORX_BIN": self.path("no-such-orx"),
            "TEZGAH_NO_DEPS": "1",
        }
        self.copy = self.path(*COPY_PARTS)

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def setup(self, *args, **extra_env):
        env = dict(self.env, **extra_env)
        return subprocess.run([sys.executable, SETUP] + list(args),
                              capture_output=True, text=True, env=env,
                              input="", timeout=300)

    def read_json(self, path):
        with open(path) as fh:
            return json.load(fh)

    def read_text(self, path):
        with open(path) as fh:
            return fh.read()

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh)

    def make_plugin_copy(self):
        """A fake installed copy: the fingerprint file is what `plugin_copies()`
        recognises, and the install path then fills the copy from this checkout."""
        os.makedirs(os.path.join(self.copy, "hooks"), exist_ok=True)
        open(os.path.join(self.copy, "hooks", "tezgah_policy.py"), "w").close()
        return self.copy

    def config_paths(self):
        """Every file a tezgah MCP row is written into."""
        return {
            "claude": os.path.join(self.copy, ".mcp.json"),
            "codex": self.path(".codex", "config.toml"),
            "opencode": self.path(".config", "opencode", "opencode.json"),
            "cursor": self.path(".cursor", "mcp.json"),
            "dsh": self.path(".dsh", "cordis.patch.yml"),
            "omp": self.path(".omp", "agent", "mcp.json"),
        }

    def entry(self, host):
        """The tezgah row a host's config holds, or None."""
        path = self.config_paths()[host]
        if host == "codex":
            return toml_entry(self.read_text(path), SERVER)
        if host == "dsh":
            return dsh_entry(self.read_text(path), SERVER)
        if host == "opencode":
            return (self.read_json(path).get("mcp") or {}).get(SERVER)
        return (self.read_json(path).get("mcpServers") or {}).get(SERVER)

    def argv_of(self, host, entry):
        """The argv a host's row declares, in the shape that host stores it:
        opencode keeps the whole argv in `command`, the others split it.

        `${HOME}` is expanded back first: the rendered Claude file is tracked and
        read on another machine, so a path under this machine's home is written in
        that form, and what the host actually runs is the expanded value."""
        if host == "opencode":
            argv = list(entry.get("command") or [])
        else:
            argv = [entry.get("command")] + list(entry.get("args") or [])
        return [self.expand(a) for a in argv if isinstance(a, str)]

    def expand(self, value):
        return value.replace("${HOME}", self.home)

    def expected_argv(self, root=REPO):
        """The contract's argv: the interpreter this installer resolves, then the
        absolute path of the tree's `bin/tezgah-mcp`."""
        return [sys.executable, os.path.join(root, "bin", "tezgah-mcp")]

    def user_server_rows(self):
        """Seed one server of the user's own into every host, before an install."""
        with open(self.path(".codex", "config.toml"), "w") as fh:
            fh.write('[mcp_servers.mine]\ncommand = "echo"\nargs = ["kept"]\n')
        self.write_json(self.path(".config", "opencode", "opencode.json"),
                        {"mcp": {"mine": {"type": "local",
                                          "command": ["echo", "kept"]}}})
        self.write_json(self.path(".cursor", "mcp.json"),
                        {"mcpServers": {"mine": {"command": "echo",
                                                 "args": ["kept"]}}})
        self.write_json(self.path(".omp", "agent", "mcp.json"),
                        {"mcpServers": {"mine": {"type": "stdio",
                                                 "command": "echo",
                                                 "args": ["kept"]}}})
        # dsh: tezgah owns the marked block, and a user's rows live outside it
        with open(self.path(".dsh", "cordis.patch.yml"), "w") as fh:
            fh.write("- insert:\n    - id: mine\n      name: 'mine'\n")

    def claude_copy_with_user_rows(self):
        """A plugin copy whose `.mcp.json` carries a server of the user's own, as
        a hand edit or an earlier host would have left it. The install path
        re-renders this file wholesale (that is the renderer's job), so this is
        the state the claude uninstall is asked to clean up."""
        self.make_plugin_copy()
        path = os.path.join(self.copy, ".mcp.json")
        self.write_json(path, {"mcpServers": {
            "mine": {"command": "echo"},
            GRAPH: {"command": "codegraph", "args": ["serve", "--mcp"]},
            SERVER: {"command": "stale"}}})
        return path


class Rows(WiringBase):
    def test_every_host_carries_the_row_with_the_one_argv(self):
        self.make_plugin_copy()
        proc = self.setup("--install", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for host in HOSTS:
            entry = self.entry(host)
            self.assertIsNotNone(entry, "%s has no tezgah MCP row" % host)
            want = (self.expected_argv(self.copy) if host == "claude"
                    else self.expected_argv())
            self.assertEqual(self.argv_of(host, entry), want, host)
        # opencode is the host whose schema takes the whole argv as a list
        opencode = self.read_json(self.config_paths()["opencode"])["mcp"][SERVER]
        self.assertEqual(opencode["type"], "local")
        self.assertTrue(opencode["enabled"])
        # omp spawns `command` as one executable: a list there is ENOENT
        omp = self.read_json(self.config_paths()["omp"])["mcpServers"][SERVER]
        self.assertEqual(omp["type"], "stdio")
        self.assertIsInstance(omp["command"], str)
        # Claude's file is its only MCP channel, so the graph row rides it too
        claude = self.read_json(self.config_paths()["claude"])["mcpServers"]
        self.assertIn(GRAPH, claude)

    def test_the_interpreter_comes_from_the_paths_resolver(self):
        """The row is `tp.python_cmd()`, not `python3` spelled out: a machine
        whose interpreter is pinned has to see the pin in every host."""
        self.make_plugin_copy()
        pinned = self.path("pinned-python")
        proc = self.setup("--install", "--hosts", ALL, TEZGAH_PYTHON=pinned)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for host in HOSTS:
            self.assertEqual(self.argv_of(host, self.entry(host))[0], pinned, host)

    def test_a_second_install_writes_the_same_bytes_and_one_row(self):
        self.make_plugin_copy()
        self.setup("--install", "--hosts", ALL)
        before = {h: self.read_text(p) for h, p in self.config_paths().items()}
        proc = self.setup("--install", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for host, path in self.config_paths().items():
            self.assertEqual(self.read_text(path), before[host],
                             "%s was rewritten by a second install" % host)
        # the two generated-text hosts are where a duplicate could hide: a JSON
        # object cannot hold the same key twice
        self.assertEqual(before["codex"].count("[mcp_servers.%s]" % SERVER), 1)
        self.assertEqual(before["dsh"].count("serverName: %s" % SERVER), 1)

    def test_uninstall_removes_only_the_tezgah_row(self):
        self.make_plugin_copy()
        self.user_server_rows()
        self.setup("--install", "--hosts", "codex,opencode,cursor,dsh,omp")
        proc = self.setup("--uninstall", "--hosts", "codex,opencode,cursor,dsh,omp")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for host in ("codex", "opencode", "cursor", "dsh", "omp"):
            self.assertIsNone(self.entry(host), "%s kept its tezgah row" % host)
        mine = {
            "codex": ("[mcp_servers.mine]", self.read_text(self.config_paths()["codex"])),
            "opencode": ("mine", json.dumps(self.read_json(self.config_paths()["opencode"]))),
            "cursor": ("mine", json.dumps(self.read_json(self.config_paths()["cursor"]))),
            "omp": ("mine", json.dumps(self.read_json(self.config_paths()["omp"]))),
            "dsh": ("id: mine", self.read_text(self.config_paths()["dsh"])),
        }
        for host, (marker, text) in mine.items():
            self.assertIn(marker, text, "the user's own server is gone from %s" % host)
        # the graph row survives where it is its own entry. omp's uninstaller
        # drops it too and dsh's whole marked block goes with it: both are
        # pre-existing and pinned in test_setup, and neither is this row.
        for host in ("codex", "opencode", "cursor"):
            text = (self.read_text(self.config_paths()[host]) if host == "codex"
                    else json.dumps(self.read_json(self.config_paths()[host])))
            self.assertIn(GRAPH, text, "%s lost the graph row" % host)

    def test_uninstall_removes_the_claude_copy_and_its_rows(self):
        """Claude runs the plugin COPY and reads its `.mcp.json` from there, so
        removing a single row would leave Claude loading tezgah's hooks and
        skills from the same tree. The copy is wholly tezgah-generated (`sync()`
        empties and rewrites it), so a claude uninstall takes the whole tree -
        the one host whose uninstall is a removal, not an edit."""
        path = self.claude_copy_with_user_rows()
        proc = self.setup("--uninstall", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(self.copy), "the plugin copy survived")
        self.assertFalse(os.path.exists(path))

    def test_uninstall_clears_the_plugin_registry_rows(self):
        """installed_plugins.json is what makes Claude keep loading the copy and
        known_marketplaces.json rows sourced from a tezgah tree keep the install
        channel open - both go, and a row of the user's own and a marketplace
        that is not tezgah's stay."""
        self.make_plugin_copy()
        self.write_json(
            self.path(".claude", "plugins", "installed_plugins.json"),
            {"version": 2, "plugins": {
                "tezgah@rizacan-local": [{"scope": "user",
                                          "installPath": self.copy}],
                "mine@rizacan-local": [{"scope": "user",
                                        "installPath": self.path("elsewhere")}],
                "other@official": [{"scope": "user",
                                    "installPath": self.path("cache", "x")}],
            }})
        self.write_json(
            self.path(".claude", "plugins", "known_marketplaces.json"),
            {"rizacan-local": {"source": {"source": "directory",
                                          "path": REPO}},
             "official": {"source": {"source": "github",
                                     "repo": "anthropics/claude-plugins-official"},
                          "installLocation": self.path("marketplaces", "o")}})
        proc = self.setup("--uninstall", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugins = self.read_json(
            self.path(".claude", "plugins", "installed_plugins.json"))["plugins"]
        self.assertNotIn("tezgah@rizacan-local", plugins)
        self.assertIn("mine@rizacan-local", plugins)
        self.assertIn("other@official", plugins)
        markets = self.read_json(
            self.path(".claude", "plugins", "known_marketplaces.json"))
        # the marketplace stays while a plugin of the user's still installs
        # from it, even though its source is a tezgah tree
        self.assertIn("rizacan-local", markets)
        self.assertIn("official", markets)

    def test_uninstall_drops_a_tezgah_sourced_marketplace_with_no_rows_left(self):
        self.make_plugin_copy()
        self.write_json(
            self.path(".claude", "plugins", "installed_plugins.json"),
            {"version": 2, "plugins": {
                "tezgah@rizacan-local": [{"scope": "user",
                                          "installPath": self.copy}]}})
        self.write_json(
            self.path(".claude", "plugins", "known_marketplaces.json"),
            {"rizacan-local": {"source": {"source": "directory",
                                          "path": REPO}},
             "official": {"source": {"source": "github",
                                     "repo": "anthropics/claude-plugins-official"}}})
        proc = self.setup("--uninstall", "--hosts", "claude")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        markets = self.read_json(
            self.path(".claude", "plugins", "known_marketplaces.json"))
        self.assertNotIn("rizacan-local", markets)
        self.assertIn("official", markets)


class Report(WiringBase):
    def sections(self, text):
        """The report's per-host sections, keyed by host name."""
        out, current = {}, None
        for line in text.splitlines():
            if line.endswith(":") and line.strip().rstrip(":").isalpha():
                current = line.strip().rstrip(":")
                out.setdefault(current, [])
            elif current:
                out[current].append(line)
        return out

    def test_the_report_prints_one_wired_row_per_host(self):
        self.make_plugin_copy()
        self.setup("--install", "--hosts", ALL)
        proc = self.setup("--report", "--hosts", ALL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        sections = self.sections(proc.stdout)
        for host in HOSTS:
            rows = [ln for ln in sections.get(host, []) if ROW in ln]
            self.assertEqual(len(rows), 1, "%s: %r" % (host, sections.get(host)))
            self.assertIn("  ok  ", rows[0], rows[0])
        # Claude's server set is checked whole, and it now names both new rows
        set_row = [ln for ln in sections["claude"]
                   if "equals the selection" in ln]
        self.assertTrue(set_row, sections["claude"])
        self.assertIn("  ok  ", set_row[0], set_row[0])
        for name in (GRAPH, SERVER):
            self.assertIn(name, set_row[0])

    def test_a_missing_row_reads_miss_in_the_report(self):
        """The row is a check, not a decoration: a host whose row is gone has to
        report MISS, which is what makes it worth a line."""
        self.make_plugin_copy()
        self.setup("--install", "--hosts", ALL)
        config = self.config_paths()["cursor"]
        broken = self.read_json(config)
        broken["mcpServers"][SERVER]["args"] = ["/somewhere/else/tezgah-mcp"]
        self.write_json(config, broken)
        proc = self.setup("--report", "--hosts", "cursor")
        row = next(ln for ln in proc.stdout.splitlines() if ROW in ln)
        self.assertIn(" MISS ", row, row)


class Render(WiringBase):
    def test_write_mcp_json_renders_the_graph_and_tezgah_rows(self):
        """Through the function `--write-mcp-json` calls. The flag writes the
        checkout's tracked file, which a test must not touch; what it adds over
        this call is the path and nothing else."""
        module = setup_module()
        path = self.path("out", ".mcp.json")
        self.assertEqual(module.write_mcp_json(path), 0)
        servers = self.read_json(path)["mcpServers"]
        self.assertEqual(list(servers)[:2], [GRAPH, SERVER])
        # this render ran in THIS process, whose home is the real one, so the
        # same expansion a host performs is what the check has to apply
        argv = [a.replace("${HOME}", os.path.expanduser("~"))
                for a in [servers[SERVER]["command"]] + servers[SERVER]["args"]]
        self.assertEqual(argv, [sys.executable, SCRIPT])
        self.assertEqual(list(servers[GRAPH]), ["command", "args", "env"])
        first = self.read_text(path)
        self.assertEqual(module.write_mcp_json(path), 0)
        self.assertEqual(self.read_text(path), first)


if __name__ == "__main__":
    unittest.main()
