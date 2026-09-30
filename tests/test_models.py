"""The model table and the tier router (hooks/tezgah_models.py, bin/tezgah-route).

What a consumer sees: which worker a brief is sent to and in what order the rules
decide it, which omp override each mode writes and that the user's own entries
survive it, and what a refresh reports when a model leaves the list or its price
moves. No network: the judge, omp and OpenRouter are stand-ins."""
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_models as tm  # noqa: E402


def judge(choice):
    """A judge stand-in answering one tier choice."""
    def ask(state, questions):
        return {"answers": {"tier": {"choice": choice,
                                     "probabilities": {choice: 0.8}}},
                "usage": {"input_tokens": 650, "output_tokens": 100},
                "latency_ms": 400, "model": "jev-latest"}
    return ask


class Route(unittest.TestCase):
    def test_an_override_beats_the_judge(self):
        # the one class the measured judge under-routed goes to frontier by rule
        out = tm.route("Rename the field everywhere, including stored plans on disk",
                       ask=judge("mechanical"))
        self.assertEqual((out["agent"], out["tier"]), ("tezgah-frontier", "frontier"))
        self.assertIn("override", out["why"])

    def test_the_judge_tier_maps_to_its_worker(self):
        for choice, agent in (("mechanical", "tezgah-cheap"),
                              ("standard", "tezgah-standard"),
                              ("frontier", "tezgah-frontier")):
            self.assertEqual(tm.route("Add a --json flag", ask=judge(choice))["agent"],
                             agent)

    def test_no_judge_falls_back_to_the_phase_table_then_the_middle(self):
        self.assertEqual(tm.route("Bump the version", "mechanical")["agent"],
                         "tezgah-cheap")
        self.assertEqual(tm.route("Compare three designs", "plan")["agent"],
                         "tezgah-frontier")
        self.assertEqual(tm.route("Do the thing")["agent"], "tezgah-standard")

    def test_an_unreadable_judgement_is_no_judgement(self):
        out = tm.route("Add tests", "mechanical", ask=lambda s, q: None)
        self.assertEqual(out["agent"], "tezgah-cheap")
        self.assertIn("no judgement", out["why"])

    def test_author_is_not_an_auth_override(self):
        self.assertNotEqual(tm.route("List the author of each commit", "mechanical")["tier"],
                            "frontier")


class OmpOverrides(unittest.TestCase):
    def test_anthropic_mode_carries_effort_and_leaves_frontier_to_the_default(self):
        out = tm.omp_overrides("anthropic")
        self.assertEqual(out["tezgah-cheap"], "anthropic/claude-opus-5-5:low")
        self.assertEqual(out["tezgah-explorer"], "anthropic/claude-opus-5-5:medium")
        for agent in ("tezgah-frontier", "tezgah-reviewer", "tezgah-researcher"):
            self.assertNotIn(agent, out)

    def test_any_mode_goes_through_openrouter(self):
        out = tm.omp_overrides("any")
        self.assertEqual(out["tezgah-cheap"], "openrouter/z-ai/glm-5.3-flash")
        self.assertEqual(out["tezgah-standard"], "openrouter/openai/gpt-6.1-sol:high")

    def test_auto_mode_follows_the_session_default_family(self):
        with mock.patch.object(tm, "overlay", return_value={}):
            self.assertEqual(tm.omp_mode("anthropic/claude-opus-5-5:high"), "anthropic")
            self.assertEqual(tm.omp_mode("zai/glm-5.3"), "any")
        with mock.patch.object(tm, "overlay", return_value={"mode": "any"}):
            self.assertEqual(tm.omp_mode("anthropic/claude-opus-5-5:high"), "any")

    def test_apply_keeps_the_users_entries_and_remove_drops_only_ours(self):
        store = {"task.agentModelOverrides": {"sonic": "@fast", "tezgah-old": "x"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", return_value={}):
            self.assertIn("written (anthropic)", tm.apply_omp())
            written = store["task.agentModelOverrides"]
            self.assertEqual(written["sonic"], "@fast")
            self.assertNotIn("tezgah-old", written)
            self.assertEqual(written["tezgah-cheap"], "anthropic/claude-opus-5-5:low")
            self.assertIn("current", tm.apply_omp())
            tm.apply_omp(remove=True)
            self.assertEqual(store["task.agentModelOverrides"], {"sonic": "@fast"})

    def test_omp_not_answering_is_reported_not_raised(self):
        with mock.patch.object(tm, "omp_get", return_value=None):
            self.assertIsNone(tm.apply_omp())


class Refresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        patcher = mock.patch.object(tm, "OVERLAY", os.path.join(self.tmp, "models.json"))
        patcher.start()
        self.addCleanup(patcher.stop)
        tm.save_overlay({"mode": "any"})

    def listing(self, drop=None, moved=None):
        data = []
        for mid, (inp, out) in tm.SNAPSHOT.items():
            if mid == drop:
                continue
            if mid == moved:
                inp = inp * 2
            data.append({"id": mid, "pricing": {"prompt": str(inp / 1e6),
                                                "completion": str(out / 1e6)}})
        return io.BytesIO(json.dumps({"data": data}).encode())

    def test_flags_a_missing_model_and_a_moved_price_and_keeps_the_mode(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=self.listing(drop="z-ai/glm-5.3-flash",
                                                  moved="openai/gpt-6.1-sol")), \
                mock.patch.object(tm, "resolve_opencode", return_value=None):
            lines, ok = tm.refresh()
        self.assertTrue(ok)
        text = "\n".join(lines)
        self.assertIn("z-ai/glm-5.3-flash is no longer in the OpenRouter list", text)
        self.assertIn("openai/gpt-6.1-sol price moved", text)
        self.assertEqual(tm.overlay()["mode"], "any")
        _lines, stale = tm.check(datetime.date.fromisoformat(tm.READ_ON))
        self.assertTrue(stale, "a flagged refresh must read as stale")

    def test_a_failed_fetch_changes_nothing(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            lines, ok = tm.refresh()
        self.assertFalse(ok)
        self.assertEqual(tm.overlay(), {"mode": "any"})

    def test_the_table_goes_stale_after_its_window(self):
        read = datetime.date.fromisoformat(tm.READ_ON)
        self.assertFalse(tm.check(read)[1])
        self.assertTrue(tm.check(read + datetime.timedelta(days=tm.STALE_DAYS + 1))[1])

    def test_opencode_selectors_match_the_model_under_any_provider(self):
        listed = "opencode-go/glm-5.3-flash\nopencode-go/deepseek-v4.1-flash\nopenai/gpt-6.1-sol\n"
        with mock.patch("shutil.which", return_value="/bin/opencode"), \
                mock.patch("subprocess.run", return_value=mock.Mock(stdout=listed)):
            found = tm.resolve_opencode()
        self.assertEqual(found["cheap"], "opencode-go/glm-5.3-flash")
        self.assertEqual(found["standard"], "openai/gpt-6.1-sol")
        self.assertNotIn("frontier", found)


class Cli(unittest.TestCase):
    def run_route(self, *args):
        home = tempfile.mkdtemp()
        os.makedirs(os.path.join(home, "tezgah"))
        open(os.path.join(home, "tezgah", "judge-off"), "w").close()
        env = dict(os.environ, XDG_CONFIG_HOME=home)
        return subprocess.run([sys.executable, os.path.join(REPO, "bin", "tezgah-route")]
                              + list(args), capture_output=True, text=True, env=env)

    def test_judge_off_routes_by_rule_and_phase(self):
        p = self.run_route("Migrate the ledger rows", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["agent"], "tezgah-frontier")
        p = self.run_route("Bump the version", "--phase", "mechanical")
        self.assertIn("agent: tezgah-cheap", p.stdout)

    def test_an_unknown_phase_is_misuse(self):
        self.assertEqual(self.run_route("x", "--phase", "vibes").returncode, 2)


if __name__ == "__main__":
    unittest.main()
