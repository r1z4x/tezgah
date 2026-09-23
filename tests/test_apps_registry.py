"""hooks/tezgah_apps.py: the feature registry and the selection it answers for.

Written from the acceptance items in .tezgah/plans/open/012 rather than from the module
under test: every row has to be able to answer *wire it* (a server spec), *install
it* (a dependency probe plus the vendor command that satisfies it, or an honest
None) and *report it* (a stable id a config.json can persist). The default
selection has to be exactly the wiring that shipped before the id existed, so a
config.json with no `features` key keeps its hosts as they are.

Runs both ways: `python3 -m unittest discover -s tests` and
`python3 -m unittest tests/test_apps_registry.py`, so it imports no sibling
helper module - the paths below are computed the same way test_setup does.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_apps as ta  # noqa: E402  (the module under test)

# The ids this pass declares, written out rather than derived: an id is what
# config.json stores, so a rename is a migration and this list is where it
# shows up.
MCP_IDS = ("mcp-playwright", "mcp-mobile-mcp", "mcp-chrome-devtools")
PLAIN_IDS = ("ai-research", "orx")
ALL_IDS = MCP_IDS + PLAIN_IDS
# The wiring every release before this pass wrote, and therefore the answer a
# config.json without a `features` key has to keep producing.
WAS_ALWAYS_ON = ["playwright", "mobile-mcp"]


class RegistryShape(unittest.TestCase):
    """Every row can answer the three questions the plan asks of one key."""

    def test_every_row_carries_the_whole_record_under_a_stable_id(self):
        self.assertEqual(tuple(r["id"] for r in ta.REGISTRY), ALL_IDS)
        self.assertEqual(ta.IDS, ALL_IDS)
        for row in ta.REGISTRY:
            for key in ("id", "name", "why", "command", "env", "default", "dep"):
                self.assertIn(key, row, row.get("id"))
            self.assertIsInstance(row["default"], bool, row["id"])
            self.assertTrue(row["why"], row["id"])
        self.assertEqual(len({r["id"] for r in ta.REGISTRY}), len(ta.REGISTRY))

    def test_every_mcp_id_carries_a_server_and_the_plain_ids_carry_none(self):
        self.assertEqual(ta.MCP_IDS, MCP_IDS)
        for row in ta.REGISTRY:
            if row["id"] in MCP_IDS:
                self.assertIsInstance(row["command"], list, row["id"])
                self.assertIsInstance(row["env"], dict, row["id"])
            else:
                # A feature with no host file to write: the writers filter on
                # exactly this, so a stray empty dict here would be rendered as
                # a server named `orx` running nothing.
                self.assertIsNone(row["command"], row["id"])
                self.assertIsNone(row["env"], row["id"])

    def test_no_server_is_described_twice(self):
        names = [r["name"] for r in ta.REGISTRY]
        self.assertEqual(len(set(names)), len(names), names)
        seen = {}
        for row in ta.REGISTRY:
            if not row["command"]:
                continue
            spec = json.dumps(row["command"], sort_keys=True)
            self.assertNotIn(spec, seen, row["id"])
            seen[spec] = row["id"]

    def test_a_dep_record_is_the_installer_shape_with_an_honest_cmd(self):
        for row in ta.REGISTRY:
            dep = row["dep"]
            self.assertIsNotNone(dep, row["id"])
            for key in ("name", "probe", "needs", "cmd", "why"):
                self.assertIn(key, dep, row["id"])
            self.assertTrue(callable(dep["probe"]), row["id"])
            self.assertIsInstance(dep["needs"], tuple, row["id"])
            self.assertTrue(all(isinstance(t, str) and t for t in dep["needs"]),
                            row["id"])
            self.assertTrue(dep["why"], row["id"])
            if dep["cmd"] is None:
                # No vendor installer exists for this one; the row says so
                # instead of naming a command nobody can run unattended.
                continue
            self.assertIsInstance(dep["cmd"], list, row["id"])
            self.assertTrue(all(isinstance(a, str) for a in dep["cmd"]), row["id"])
            self.assertTrue(dep["needs"], "%s: a cmd with nothing to run it" % row["id"])

    def test_no_two_rows_share_a_dep_dict(self):
        # The installer builds its own DEPS rows out of these, so a shared dict
        # would let one consumer's edit appear in another feature's state.
        self.assertEqual(len({id(r["dep"]) for r in ta.REGISTRY}), len(ta.REGISTRY))


class DeclaredDefaults(unittest.TestCase):
    """A config.json with no `features` key behaves exactly as today."""

    def test_the_default_selection_is_the_wiring_that_exists_today(self):
        self.assertEqual(ta.names(), WAS_ALWAYS_ON)
        self.assertEqual([s["name"] for s in ta.servers()], WAS_ALWAYS_ON)
        self.assertEqual(list(ta.defaults()),
                         [i for i in ALL_IDS if i != "mcp-chrome-devtools"])

    def test_an_absent_selection_is_the_declared_default_not_everything(self):
        self.assertEqual(ta.selected_ids(None), ta.defaults())
        self.assertEqual(ta.servers(None), ta.servers(ta.defaults()))

    def test_the_opt_in_sidecar_is_off_until_it_is_named(self):
        self.assertNotIn("chrome-devtools", ta.names())
        self.assertNotIn("mcp-chrome-devtools", ta.selected_ids(None))

    def test_every_name_tezgah_may_have_written_includes_the_opt_in(self):
        # app_mcp_names() keeps this meaning: uninstall has to sweep a file an
        # older release wrote even though the feature is off today.
        self.assertEqual(ta.names(ta.MCP_IDS), WAS_ALWAYS_ON + ["chrome-devtools"])
        self.assertEqual(len(ta.MCP_IDS), 3)

    def test_the_plain_ids_are_in_the_default_selection(self):
        # The mechanism is not MCP-only, and both of these were on before it:
        # the payload ships in the package, orx is installed by --install.
        for ident in PLAIN_IDS:
            self.assertIn(ident, ta.selected_ids(None), ident)


class Selection(unittest.TestCase):
    """What a writer and a report read once a selection exists."""

    def test_the_selection_decides_who_is_wired(self):
        self.assertEqual(ta.names(["mcp-chrome-devtools"]), ["chrome-devtools"])
        self.assertEqual([s["name"] for s in ta.servers(["mcp-playwright"])],
                         ["playwright"])

    def test_nothing_selected_wires_nothing(self):
        self.assertEqual(ta.servers([]), ())
        self.assertEqual(ta.names([]), [])

    def test_rows_come_back_in_registry_order_not_caller_order(self):
        flipped = ["mcp-mobile-mcp", "mcp-playwright"]
        self.assertEqual(ta.names(flipped), WAS_ALWAYS_ON)
        self.assertEqual(ta.names(set(flipped)), WAS_ALWAYS_ON)

    def test_an_unknown_id_is_dropped_rather_than_raising(self):
        # A selection an older release wrote must not break a host writer; the
        # report and --features are where an unknown id is named.
        self.assertEqual(ta.names(["mcp-playwright", "mcp-nope"]), ["playwright"])

    def test_the_dropped_arguments_are_refused(self):
        # A string of ids is iterable, so `names("mcp-playwright")` would match
        # nothing and answer with an empty list - a wiring run that silently
        # removes every server. A bool is the `devtools` argument this signature
        # replaced; it must name the argument the caller has to give instead of
        # failing deeper down.
        for call in (ta.servers, ta.names, ta.selected_ids):
            for bad in ("mcp-playwright", True, False):
                with self.assertRaises(TypeError, msg=call.__name__) as caught:
                    call(bad)
                self.assertIn(type(bad).__name__, str(caught.exception))

    def test_a_callable_never_hands_back_a_serverless_row(self):
        self.assertEqual(ta.servers(ta.IDS), ta.servers(ta.MCP_IDS))
        for srv in ta.servers(ta.IDS):
            self.assertTrue(srv["command"], srv["id"])
            self.assertIsInstance(srv["env"], dict, srv["id"])

    def test_the_answers_are_deterministic_and_frozen(self):
        self.assertIsInstance(ta.servers(), tuple)
        self.assertEqual(ta.names(ta.MCP_IDS), ta.names(ta.MCP_IDS))

    def test_the_rendered_commands_are_pinned(self):
        # The row is the only place a command is written, so the supply-chain
        # pin is checkable here rather than in every host file it lands in.
        for srv in ta.servers(ta.MCP_IDS):
            cmd = srv["command"]
            self.assertEqual(cmd[:2], ["npx", "-y"], srv["name"])
            # The third argument is the package npx fetches and runs with the
            # agent's privileges, so its version is the one that has to be
            # written down.
            self.assertRegex(cmd[2], r"@\d+\.\d+\.\d+", srv["name"])
            self.assertNotIn("@latest", cmd[2], srv["name"])
        self.assertEqual(
            [s for s in ta.servers() if s["name"] == "playwright"][0]["env"],
            {"PLAYWRIGHT_MCP_OUTPUT_DIR": ta.ARTIFACTS})


class Probes(unittest.TestCase):
    """The dependency half of a row: run only when asked, never guessed."""

    def test_a_probe_answers_with_a_path_or_with_none(self):
        for row in ta.REGISTRY:
            got = row["dep"]["probe"]()
            self.assertTrue(got is None or isinstance(got, str), row["id"])

    def test_a_probe_is_a_pure_read_of_the_machine(self):
        for row in ta.REGISTRY:
            self.assertEqual(row["dep"]["probe"](), row["dep"]["probe"](), row["id"])

    def test_a_missing_runtime_reads_as_unmet_instead_of_raising(self):
        with mock.patch.object(ta, "_which", lambda name: None):
            self.assertFalse(ta._probe_playwright())
            self.assertFalse(ta._probe_device_toolchain())
            self.assertFalse(ta._probe_npx())

    def test_the_browser_override_is_read_at_probe_time_and_wins(self):
        # An override pointing at a build is the answer even where the platform
        # cache is empty; the module must not have baked the cache list in.
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "chromium-9999"))
            with mock.patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": d}):
                self.assertEqual(ta._playwright_browsers(),
                                 os.path.join(d, "chromium-9999"))
            self.assertNotEqual(ta._playwright_browsers(),
                                os.path.join(d, "chromium-9999"))

    def test_a_payload_that_is_not_there_reads_as_unmet(self):
        # The probe answers about the plugin that is running, so an empty plugin
        # root has to read as unmet - and it has to ask through the path seam,
        # not through a path copied in here, which is what the patch proves.
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ta, "_tp", lambda attr: (lambda: d)):
                self.assertIsNone(ta._probe_ai_research())
                open(os.path.join(d, "SKILL.md"), "w").close()
                self.assertEqual(ta._probe_ai_research(), d)


class HotPath(unittest.TestCase):
    """This module is imported on the installer's every run; its API is a leaf."""

    def test_importing_it_pulls_no_extra_module(self):
        # `shutil` and `tezgah_paths` are imported inside the probes: at module
        # level they would be paid by every import of a file that is loaded
        # before anything else is decided.
        code = ("import sys; sys.path.insert(0, %r); import tezgah_apps; "
                "print('shutil' in sys.modules or 'tezgah_paths' in sys.modules)"
                % os.path.join(REPO, "hooks"))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, check=True)
        self.assertEqual(out.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
