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
import tezgah_integrity as ti  # noqa: E402
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
    def overrides(self, mode, funded):
        with mock.patch.object(tm, "funded_families", return_value=list(funded)), \
                mock.patch.object(tm, "openrouter_ready",
                                  return_value="any" in funded):
            return tm.omp_overrides(mode)

    def test_the_anthropic_mode_carries_effort_and_the_frontier_row(self):
        out = self.overrides("anthropic", funded=("anthropic",))
        self.assertEqual(out["tezgah-cheap"], "anthropic/claude-opus-5-5:low")
        self.assertEqual(out["scout"], "anthropic/claude-opus-5-5:medium")
        # the frontier agents are written too: a session that started on a
        # weaker model must not drag security-sensitive work down with it
        for agent in ("tezgah-frontier", "tezgah-reviewer"):
            self.assertEqual(out[agent], "anthropic/claude-opus-5-5:high")
        # the retired roles are no longer generated, so no override names them
        for agent in ("tezgah-explorer", "tezgah-researcher", "tezgah-verifier"):
            self.assertNotIn(agent, out)

    def test_any_mode_writes_the_frontier_row_through_openrouter(self):
        out = self.overrides("any", funded=("any",))
        for agent in ("tezgah-frontier", "tezgah-reviewer"):
            self.assertEqual(out[agent], "openrouter/anthropic/claude-opus-5.5:high")

    def test_the_frontier_row_is_concrete_on_every_family(self):
        # every family names a model; the effort suffix is per family, because a
        # thinking level omp accepts for one provider is not one it accepts for
        # another (the zai column carries none: none was verified there)
        for family, (model, effort) in tm.SLOTS["frontier"].items():
            self.assertTrue(model and model != "inherit", family)
            if family == "zai":
                self.assertIsNone(effort, "no thinking suffix is verified for zai")
            else:
                self.assertEqual(effort, "high", family)

    def test_the_accessors_are_the_table_and_none_for_an_unknown_family(self):
        for family in ("anthropic", "zai", "openai", "any"):
            self.assertEqual(tm.frontier_model(family), tm.SLOTS["frontier"][family])
            self.assertEqual(tm.cheap_model(family), tm.SLOTS["cheap"][family])
            self.assertTrue(tm.frontier_model(family)[0])
            self.assertTrue(tm.cheap_model(family)[0])
        self.assertIsNone(tm.frontier_model("nope"))
        self.assertIsNone(tm.cheap_model("nope"))

    def test_the_plan_and_slow_roles_carry_the_frontier_row(self):
        # plan mode is where a session designs on its own tokens; it runs the
        # table's frontier row, not whatever model the session started on
        self.assertEqual(tm.omp_role_overrides("anthropic"),
                         {"modelRoles.plan": "anthropic/claude-opus-5-5:high",
                          "modelRoles.slow": "anthropic/claude-opus-5-5:high"})
        with mock.patch.object(tm, "openrouter_ready", return_value=True):
            self.assertEqual(
                tm.omp_role_overrides("any"),
                {"modelRoles.plan": "openrouter/anthropic/claude-opus-5.5:high",
                 "modelRoles.slow": "openrouter/anthropic/claude-opus-5.5:high"})
        self.assertEqual(tm.omp_role_overrides("off"), {})
        with mock.patch.object(tm, "openrouter_ready", return_value=False):
            self.assertEqual(tm.omp_role_overrides("any"), {})

    def test_any_mode_goes_through_openrouter(self):
        # the credential is mocked, not read: a machine without a key answered
        # {} and made this case fail on CI while passing on a developer's box
        out = self.overrides("any", funded=("any",))
        self.assertEqual(out["tezgah-cheap"], "openrouter/z-ai/glm-5.3-flash")
        self.assertEqual(out["tezgah-standard"], "openrouter/openai/gpt-6.1-sol:high")

    def test_auto_mode_follows_the_session_default_family(self):
        with mock.patch.object(tm, "overlay", return_value={}):
            self.assertEqual(tm.omp_mode("anthropic/claude-opus-5-5:high"), "anthropic")
            self.assertEqual(tm.omp_mode("zai/glm-5.3"), "zai",
                             "a z.ai default is the column whose ids omp itself uses")
            self.assertEqual(tm.omp_mode("deepseek/deepseek-flash:high"), "any")
            self.assertEqual(tm.omp_mode(None), "any", "no default names no family")
        with mock.patch.object(tm, "overlay", return_value={"mode": "any"}):
            self.assertEqual(tm.omp_mode("anthropic/claude-opus-5-5:high"), "any")

    def test_apply_keeps_every_entry_it_does_not_own_and_removes_its_own(self):
        store = {"task.agentModelOverrides": {"sonic": "@fast", "tezgah-old": "x"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        state = {}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            self.assertIn("written (anthropic)", tm.apply_omp())
            got = store["task.agentModelOverrides"]
            # a bundled agent the user set by hand keeps their value, and an
            # entry tezgah never wrote is untouched
            self.assertEqual(got["sonic"], "@fast")
            self.assertEqual(got["tezgah-old"], "x")
            self.assertEqual(got["tezgah-cheap"], "anthropic/claude-opus-5-5:low")
            # what tezgah wrote is recorded, which is what lets a later mode
            # change or an uninstall tell its own entries apart
            self.assertEqual(state["omp_written"]["tezgah-cheap"],
                             "anthropic/claude-opus-5-5:low")
            self.assertIn("current", tm.apply_omp())
            tm.apply_omp(remove=True)
            self.assertEqual(store["task.agentModelOverrides"],
                             {"sonic": "@fast", "tezgah-old": "x"})

    def test_a_value_the_user_changed_is_never_replaced(self):
        state = {"omp_written": {"tezgah-standard": "anthropic/claude-opus-5-5:medium"}}
        store = {"task.agentModelOverrides": {"tezgah-standard": "openai/gpt-6.1-sol"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", return_value=mock.Mock(stdout="")), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            tm.apply_omp()
        self.assertEqual(store["task.agentModelOverrides"]["tezgah-standard"],
                         "openai/gpt-6.1-sol")

    def test_apply_writes_the_plan_and_slow_roles_and_keeps_every_other_role(self):
        store = {"task.agentModelOverrides": {},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high",
                                "memory": "zai/glm-5.3-flash:auto"},
                 "retry.fallbackChains": {}}
        state = {}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            self.assertIn("written (anthropic)", tm.apply_omp())
            self.assertEqual(store["modelRoles"]["plan"], "anthropic/claude-opus-5-5:high")
            self.assertEqual(store["modelRoles"]["slow"], "anthropic/claude-opus-5-5:high")
            # a role tezgah does not write stays as the user set it
            self.assertEqual(store["modelRoles"]["memory"], "zai/glm-5.3-flash:auto")
            self.assertEqual(state["omp_written"]["modelRoles.plan"],
                             "anthropic/claude-opus-5-5:high")
            # a role the user set by hand is never replaced, and tezgah stops
            # claiming it
            store["modelRoles"]["plan"] = "@slow"
            tm.apply_omp()
        self.assertEqual(store["modelRoles"]["plan"], "@slow")
        self.assertNotIn("modelRoles.plan", state["omp_written"])

    def test_the_off_mode_drops_its_own_roles_and_keeps_the_users(self):
        store = {"task.agentModelOverrides": {},
                 "modelRoles": {"default": "deepseek/deepseek-flash:high",
                                "plan": "openrouter/anthropic/claude-opus-5.5:high",
                                "slow": "@plan"},
                 "retry.fallbackChains": {}}
        state = {"mode": "off", "omp_written": {
            "modelRoles.plan": "openrouter/anthropic/claude-opus-5.5:high"}}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            self.assertIn("removed (off)", tm.apply_omp())
        # ours goes, the user's own role and the default stay
        self.assertEqual(store["modelRoles"],
                         {"default": "deepseek/deepseek-flash:high", "slow": "@plan"})

    def test_a_failed_role_write_records_no_ownership(self):
        store = {"task.agentModelOverrides":
                 {"tezgah-cheap": "anthropic/claude-opus-5-5:low"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        state = {}

        def omp(*args):
            return None if args[1] == "modelRoles" else mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            self.assertIn("NOT written", tm.apply_omp())
        self.assertEqual(state, {}, "a role write that failed must not be recorded")

    def test_the_off_mode_removes_every_entry_and_writes_nothing(self):
        # the way back when the provider the selectors need has no budget:
        # `--mode off` is not `--uninstall`, it only clears the routing
        store = {"task.agentModelOverrides":
                 {"tezgah-cheap": "openrouter/z-ai/glm-5.3-flash", "sonic": "@fast"},
                 "modelRoles": {"default": "deepseek/deepseek-flash:high"},
                 "retry.fallbackChains": {}}
        state = {"mode": "off", "omp_written": {"tezgah-cheap": "openrouter/z-ai/glm-5.3-flash"}}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            self.assertIn("removed (off)", tm.apply_omp())
        self.assertEqual(store["task.agentModelOverrides"], {"sonic": "@fast"})

    def test_remove_drops_an_adopted_entry_that_has_no_record(self):
        # an install from before the ownership record: the entry is ours (it is
        # one of the table's own selectors), so uninstall must take it away
        store = {"task.agentModelOverrides":
                 {"tezgah-cheap": "anthropic/claude-opus-5-5:low"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        state = {}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            tm.apply_omp(remove=True)
        self.assertEqual(store["task.agentModelOverrides"], {})

    def test_the_zai_mode_names_the_zai_column(self):
        # the provider whose ids omp's own config already uses, so a machine whose
        # funded provider is z.ai routes without a hand-edited override
        out = self.overrides("zai", funded=("zai",))
        self.assertEqual(out["tezgah-cheap"], "zai/glm-5.3-flash")
        self.assertEqual(out["scout"], "zai/glm-5.3-flash")
        self.assertEqual(out["tezgah-standard"], "zai/glm-5.3")
        self.assertEqual(out["tezgah-frontier"], "zai/glm-5.3")
        self.assertEqual(tm.omp_role_overrides("zai"),
                         {"modelRoles.plan": "zai/glm-5.3",
                          "modelRoles.slow": "zai/glm-5.3"})

    def test_auto_mode_follows_a_zai_default(self):
        with mock.patch.object(tm, "overlay", return_value={}):
            self.assertEqual(tm.omp_mode("zai/glm-5.3-flash:auto"), "zai")
            self.assertEqual(tm.omp_mode("anthropic/claude-opus-5-5:high"), "anthropic")
            self.assertEqual(tm.omp_mode("deepseek/deepseek-flash:high"), "any")

    def test_the_off_mode_wants_nothing_at_all(self):
        # the status row reads this: an `off` machine must not look like one with
        # a missing override, because no repair could ever clear that row
        self.assertEqual(tm.omp_overrides("off"), {})
        self.assertEqual(tm.omp_role_overrides("off"), {})

    def test_the_any_mode_is_empty_without_a_credential(self):
        # nothing can run through OpenRouter here, so the table emits no selector
        # for that mode at all - which is what the omp status row reads as current
        with mock.patch.object(tm, "openrouter_ready", return_value=False):
            self.assertEqual(tm.omp_overrides("any"), {})

    def test_a_value_the_table_generates_on_another_column_is_adopted(self):
        # measured on this machine: three entries held the zai column's own
        # selector, `_ours_by_shape` only knew anthropic/any, so the next
        # `--mode anthropic` left them at zai
        store = {"task.agentModelOverrides": {"tezgah-cheap": "zai/glm-5.3-flash"},
                 "modelRoles": {"default": "deepseek/deepseek-flash:high"},
                 "retry.fallbackChains": {}}
        state = {"mode": "anthropic"}  # the mode the switch is moving to

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            tm.apply_omp()
        self.assertEqual(store["task.agentModelOverrides"]["tezgah-cheap"],
                         "anthropic/claude-opus-5-5:low")
        self.assertEqual(state["omp_written"]["tezgah-cheap"],
                         "anthropic/claude-opus-5-5:low")

    def test_a_value_identical_to_what_we_want_is_recorded_as_ours(self):
        store = {"task.agentModelOverrides": {"tezgah-cheap": "anthropic/claude-opus-5-5:low"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        state = {}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", return_value=mock.Mock(stdout="")), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            tm.apply_omp()
        self.assertEqual(state["omp_written"]["tezgah-cheap"],
                         "anthropic/claude-opus-5-5:low")

    def test_a_write_from_before_the_record_is_adopted_by_its_shape(self):
        store = {"task.agentModelOverrides":
                 {"tezgah-cheap": "anthropic/claude-opus-5-5:low"},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        state = {}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", return_value=mock.Mock(stdout="")), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            tm.apply_omp()
        self.assertEqual(state["omp_written"]["tezgah-cheap"],
                         "anthropic/claude-opus-5-5:low")

    def test_the_any_mode_writes_nothing_without_an_openrouter_key(self):
        # a default that is neither Anthropic nor z.ai: those two columns need no
        # OpenRouter credential, so the skip only applies to the `any` one
        store = {"task.agentModelOverrides": {},
                 "modelRoles": {"default": "deepseek/deepseek-flash:high"},
                 "retry.fallbackChains": {}}
        called = []
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", side_effect=lambda *a: called.append(a)), \
                mock.patch.object(tm, "openrouter_ready", return_value=False), \
                mock.patch.object(tm, "overlay", return_value={}):
            status = tm.apply_omp()
        self.assertIn("skipped", status)
        self.assertEqual(called, [], "nothing may be written when the tier cannot run")

    def test_the_fallback_order_rotates_per_agent(self):
        # identical chains moved every agent onto the same fallback at once, so a
        # 429 there cascaded instead of falling through (review 2026-10-01)
        out = self.overrides("anthropic", funded=("anthropic", "zai", "any"))
        orders = {a: tuple(out[a].split(",")[1:]) for a in out}
        self.assertGreater(len(set(orders.values())), 1, orders)
        for agent, chain in out.items():
            self.assertTrue(chain.startswith("anthropic/"), agent)
            self.assertEqual(len(set(chain.split(","))), len(chain.split(",")), agent)

    def test_bundled_agents_are_routed_and_the_reviewers_inherit(self):
        out = self.overrides("anthropic", funded=("anthropic",))
        self.assertEqual(out["sonic"], "anthropic/claude-opus-5-5:low")
        self.assertEqual(out["scout"], "anthropic/claude-opus-5-5:medium")
        self.assertEqual(out["task"], "anthropic/claude-opus-5-5:medium")
        for agent in ("reviewer", "security-reviewer"):
            self.assertNotIn(agent, out)

    def test_a_malformed_overlay_cannot_break_a_caller(self):
        path = os.path.join(tempfile.mkdtemp(), "models.json")
        with open(path, "w") as fh:
            fh.write('{"opencode": "x", "flags": "abc", "omp_written": 3, "mode": 7}')
        with mock.patch.object(tm, "OVERLAY", path):
            self.assertEqual(tm.overlay(), {})
            self.assertIsNone(tm.opencode_model("tezgah-cheap"))
            self.assertFalse(tm.check()[1])

    def test_the_override_rule_is_word_bounded(self):
        frontier = ["Migrate the ledger rows to the new table",
                    "Rotate the credential file handling",
                    "Add JWT validation to the endpoint",
                    "Persist sessions in sqlite",
                    "the schema changes with this field",
                    "write the threat model for consult",
                    # the classes an earlier pattern caught and a rewrite missed
                    "Add auth to the login flow",
                    "Add authz checks to the endpoint",
                    "Update the schemas for the new tables",
                    "Write the migrator for postgres",
                    "Read the API-key from the environment",
                    "Rotate the signing key",
                    "Handle user PII in the export"]
        elsewhere = ["Rename migrate_rows to move_rows across bin/",
                     "List the author of each commit",
                     "Add a secretary field to the roster",
                     "make the login form password-less"]
        for brief in frontier:
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "frontier", brief)
        for brief in elsewhere:
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "cheap", brief)

    # The red-team fixture (REPORT.md R08 part 11): 8 high-stakes briefs the
    # pattern matched none of, and 4 controls naming the new terms' near misses.
    HIGH_STAKES = ["Rotate the SSH private key",
                   "Drop the users table",
                   "Fix the bearer token check",
                   "Update the TLS certificate pinning",
                   "Change file permissions and sudoers",
                   "Delete old rows from the production database",
                   "Force-push the rewritten history to main",
                   "Store the user's GitHub PAT"]
    CONTROLS = ["Add a dropdown to the settings page",
                "Count the tokens in each prompt",
                "Fix the pattern matcher in the docs router",
                "Delete the unused import in bin/consult"]
    # Ordinary briefs a loose term over-routed (review of add7e74): pinned here
    # only where the tightened pattern leaves them unmatched.
    NEAR_MISSES = ["Ask Pat to review the copy",
                   "List the pats in the fixture"]

    def test_a_name_or_a_plural_is_not_a_personal_access_token(self):
        for brief in self.NEAR_MISSES:
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "cheap", brief)
        for brief in ("Store the user's GitHub PAT", "Rotate the personal access token"):
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "frontier", brief)

    def test_the_override_routes_every_high_stakes_brief_and_no_control(self):
        for brief in self.HIGH_STAKES:
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "frontier", brief)
        for brief in self.CONTROLS:
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "cheap", brief)

    def test_the_code_verifier_s_four_extra_misses_are_caught_too(self):
        for brief in ("Fix the login token refresh",
                      "Rewrite git history with filter-repo",
                      "Truncate the events table",
                      "Rotate the private key"):
            self.assertEqual(tm.route(brief, "mechanical")["tier"], "frontier", brief)

    def test_a_judged_route_names_who_answered_and_keeps_via(self):
        def ask(state, questions):
            out = judge("standard")(state, questions)
            out.update(model="glm-5.3-flash", provider="openrouter")
            return out
        out = tm.route("Add a --json flag", "code", ask=ask)
        self.assertEqual(out["judge"], "openrouter/glm-5.3-flash")
        detail = tm.route_detail(out, "code")
        fields = tm.route_fields({"kind": "route", "detail": detail})
        self.assertEqual(fields["via"], "jev")
        self.assertEqual(fields["judge"], "openrouter/glm-5.3-flash")

    def test_an_unjudged_route_says_no_judge_answered(self):
        for out in (tm.route("Drop the users table"), tm.route("Bump it", "mechanical")):
            fields = tm.route_fields({"kind": "route", "detail": tm.route_detail(out)})
            self.assertEqual(fields["judge"], "-")

    def test_a_malformed_judgement_never_raises(self):
        broken = [None, {"answers": {"tier": "standard"}},
                  {"answers": {"tier": {"choice": ["standard"]}}},
                  {"answers": {"tier": {"choice": "standard",
                                        "probabilities": {"standard": None}}}}]
        for reply in broken:
            out = tm.route("Add a --json flag", "code", ask=lambda s, q, r=reply: r)
            self.assertEqual(out["agent"], "tezgah-standard")

    def test_the_brief_goes_out_redacted(self):
        seen = {}

        def ask(state, questions):
            seen.update(state)
            return {"answers": {"tier": {"choice": "standard"}}}

        brief = "Fix the retry loop; token=AKIAIOSFODNN7EXAMPLE was in the log"
        tm.route(brief, ask=ask)
        self.assertEqual(seen["task"], ti.redact(brief))
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", seen["task"])

    def test_an_override_is_not_sent_to_the_judge_at_all(self):
        calls = []
        tm.route("Rotate the credential file", ask=lambda s, q: calls.append(s))
        self.assertEqual(calls, [])

    def test_a_failed_write_records_no_ownership(self):
        # ownership is what lets a later run tell tezgah's entries from the
        # user's: a write that never landed must not claim any
        store = {"task.agentModelOverrides": {},
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"},
                 "retry.fallbackChains": {}}
        state = {}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "funded_families",
                                  return_value=["anthropic"]), \
                mock.patch.object(tm, "_omp", return_value=None), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            self.assertIn("NOT written", tm.apply_omp())
        self.assertEqual(state, {}, "a failed write must not record ownership")

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
    def run_route(self, *args, **extra):
        home = tempfile.mkdtemp()
        os.makedirs(os.path.join(home, "tezgah"))
        open(os.path.join(home, "tezgah", "judge-off"), "w").close()
        # this module does not import `support`, so it sandboxes the child
        # itself: no real HOME (the ledger lives under it), and no session but
        # the one a test passes
        env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home)
        env.pop("TEZGAH_SESSION", None)
        env.update(extra)
        return subprocess.run([sys.executable, os.path.join(REPO, "bin", "tezgah-route")]
                              + list(args), capture_output=True, text=True, env=env)

    def test_a_route_run_reaches_neither_the_real_home_nor_the_session(self):
        # 36 rows in the live route ledger came from this class: the child
        # inherited the real HOME and the running session's TEZGAH_SESSION
        with mock.patch.dict(os.environ, {"TEZGAH_SESSION": "r02-probe",
                                          "HOME": "/real-home"}), \
                mock.patch.object(subprocess, "run") as run:
            self.run_route("x")
        env = run.call_args.kwargs["env"]
        self.assertNotIn("TEZGAH_SESSION", env)
        self.assertNotEqual(env["HOME"], "/real-home")
        self.assertTrue(env["HOME"].startswith(env["XDG_CONFIG_HOME"]))

    def test_importing_support_sandboxes_the_process(self):
        # set before any hooks/ import: tezgah_paths fixes HOME and CACHE then
        # A host dir the developer exported (Orca exports CODEX_HOME) is the real
        # config: a test that writes and removes `<CODEX_HOME>/config.toml` deleted
        # the developer's own Codex config on 2026-10-06.
        real = ("TEZGAH_SESSION", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
                "CODEX_HOME", "DSH_HOME", "TEZGAH_OPENCODE_DATA")
        code = ("import os, support; print(os.environ['HOME']); "
                "print(sorted(n for n in %r if n in os.environ))" % (real,))
        env = dict(os.environ, HOME="/real-home", **{n: "/real-home/" + n for n in real})
        p = subprocess.run([sys.executable, "-c", code], cwd=os.path.join(REPO, "tests"),
                           env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        home, left = p.stdout.splitlines()
        self.assertNotEqual(home, "/real-home")
        self.assertEqual(left, "[]")

    def test_judge_off_routes_by_rule_and_phase(self):
        p = self.run_route("Migrate the ledger rows", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["agent"], "tezgah-frontier")
        p = self.run_route("Bump the version", "--phase", "mechanical")
        self.assertIn("agent: tezgah-cheap", p.stdout)
        # a flag before the brief is the same call: the policy text tells an
        # agent to run `tezgah-route --phase code "<brief>"` either way round
        p = self.run_route("--json", "--phase", "code", "Add a flag")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["agent"], "tezgah-standard")

    def test_an_unknown_phase_is_misuse(self):
        self.assertEqual(self.run_route("x", "--phase", "vibes").returncode, 2)

    def test_every_route_writes_one_route_row_the_outcome_fold_reads(self):
        # the unjudged path too: an override or a static pick is a route the
        # V2-as-default question has to count, not only the judged ones
        home = tempfile.mkdtemp()
        p = self.run_route("Migrate the ledger rows", "--phase", "code", HOME=home,
                           TEZGAH_SESSION="s1", CLAUDECODE="1", OMPCODE="")
        self.assertEqual(p.returncode, 0, p.stderr)
        ledger = os.path.join(home, ".cache", "tezgah", "evidence",
                              ti._slug("s1") + ".jsonl")
        rows = [r for r in ti.events_path(ledger) if r.get("kind") == "route"]
        self.assertEqual(len(rows), 1, ti.events_path(ledger))
        self.assertEqual(tm.route_fields(rows[0]),
                         {"tier": "frontier", "agent": "tezgah-frontier", "via": "rule",
                          "static": "standard", "model": "claude-opus-5-5:high",
                          "override": "-", "judge": "-"})

    def test_report_joins_a_route_to_its_child_session_s_first_check(self):
        home = tempfile.mkdtemp()
        self.run_route("Bump the version", "--phase", "mechanical", HOME=home,
                       TEZGAH_SESSION="s2", CLAUDECODE="1", OMPCODE="")
        evidence = os.path.join(home, ".cache", "tezgah", "evidence")
        with open(os.path.join(evidence, ti._slug("child") + ".jsonl"), "w") as fh:
            for row in ({"kind": "spawned", "ts": 2 ** 40, "parent": "s2"},
                        {"kind": "verify_ok", "ts": 2 ** 40, "exit": 0, "out_bytes": 3,
                         "detail": "pytest"}):
                fh.write(json.dumps(row) + "\n")
        p = self.run_route("--report", HOME=home)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("phase cheap routes=1 pass=1 fail=0 ran=0 none=0 unjoined=0",
                      p.stdout)


class RouteReport(unittest.TestCase):
    """The fold the V2-as-default call reads: each route joined to the first
    check of the worker it routed - the child session whose `spawned` row names
    the route's session as its parent. The join must be provable: by the
    worker's agent type, or by order only when nothing can be swapped."""

    OK = {"kind": "verify_ok", "exit": 0, "out_bytes": 5, "detail": "pytest"}
    FAIL = {"kind": "verify_fail", "exit": 1, "detail": "pytest"}
    EMPTY = {"kind": "verify_ok", "exit": 0, "out_bytes": 0, "detail": "pytest"}

    @staticmethod
    def route(tier, via, static=None, ts=10):
        return {"kind": "route", "ts": ts,
                "detail": "tezgah-route tier=%s agent=tezgah-%s via=%s%s "
                "model=m override=-" % (tier, tier, via,
                                        " static=" + static if static else "")}

    @staticmethod
    def child(parent, ts, *rows, agent=None):
        row = {"kind": "spawned", "ts": ts, "parent": parent}
        if agent:
            row["agent"] = agent
        return [row] + list(rows)

    @staticmethod
    def spawn(name, agent):
        """The parent's own record of one task it spawned (omp's task call)."""
        return {"kind": "spawn", "ts": 50, "child": name, "agent": agent}

    @staticmethod
    def counts(**got):
        return dict({"routes": 1, "pass": 0, "fail": 0, "ran": 0, "none": 0,
                     "unjoined": 0}, **got)

    def test_spawns_in_one_second_join_by_the_worker_s_agent_type(self):
        # opencode: the child's own row carries its agent type. The batch
        # spawns share a second, so order could not tell them apart.
        parent = [self.route("cheap", "jev", "standard", ts=10),
                  self.route("frontier", "rule", ts=11),
                  self.route("standard", "phase", "standard", ts=12), self.OK]
        ledgers = {ti._slug("p"): parent,
                   "c3": self.child("p", 40, self.EMPTY, agent="tezgah-standard"),
                   "c1": self.child("p", 40, self.FAIL, self.OK, agent="tezgah-cheap"),
                   "c2": self.child("p", 40, {"kind": "edit"}, self.OK,
                                    agent="tezgah-frontier")}
        groups, below = tm.route_report(ledgers)
        self.assertEqual(groups[("jev", "cheap")], self.counts(fail=1))
        self.assertEqual(groups[("rule", "frontier")], self.counts(**{"pass": 1}))
        # an exit-0-but-empty check is not a pass
        self.assertEqual(groups[("phase", "standard")], self.counts(ran=1))
        # Jev under the static row with a failed first check: the under-route
        # V1b's table would not have made
        self.assertEqual(below, self.counts(fail=1))

    def test_omp_children_take_their_type_from_the_parent_s_spawn_rows(self):
        # omp names a child by its task name; the parent's task call says which
        # agent that name runs. Spawned in the reverse of route order.
        parent = [self.route("frontier", "jev", ts=100), self.route("cheap", "jev", ts=101),
                  self.spawn("Fix", "tezgah-cheap"), self.spawn("Design", "tezgah-frontier"),
                  self.spawn("Look", "scout")]
        ledgers = {ti._slug("p"): parent,
                   "a": self.child("p", 102, self.OK, agent="Fix"),
                   "b": self.child("p", 103, self.FAIL, agent="Design"),
                   "s": self.child("p", 104, self.OK, agent="Look")}  # unrouted scout
        groups = tm.route_report(ledgers)[0]
        self.assertEqual(groups[("jev", "frontier")], self.counts(fail=1))
        self.assertEqual(groups[("jev", "cheap")], self.counts(**{"pass": 1}))

    def test_a_worker_s_orphan_pass_reads_as_ran_through_the_ledger_reader(self):
        # plan 051: `tezgah-route --report` reads each ledger with
        # `events_path`, which pairs a pass with the gate's `began` row. A pass
        # with none, in a ledger that has began rows, is not the worker's pass.
        began = {"kind": "began", "id": "c", "check": 1, "detail": "pytest"}
        other = {"kind": "began", "id": "x", "check": 1, "detail": "ruff check ."}
        ok = dict(self.OK, id="c")
        rows = {"a": self.child("p", 102, began, ok, agent="Fix"),
                "b": self.child("p", 103, other, ok, agent="Design")}
        parent = [self.route("frontier", "jev", ts=100), self.route("cheap", "jev", ts=101),
                  self.spawn("Fix", "tezgah-cheap"), self.spawn("Design", "tezgah-frontier")]
        with tempfile.TemporaryDirectory() as d:
            ledgers = {ti._slug("p"): parent}
            for stem, child in rows.items():
                path = os.path.join(d, stem + ".jsonl")
                with open(path, "w") as fh:
                    fh.writelines(json.dumps(r) + "\n" for r in child)
                ledgers[stem] = ti.events_path(path)
            groups = tm.route_report(ledgers)[0]
        self.assertEqual(groups[("jev", "cheap")], self.counts(**{"pass": 1}))
        self.assertEqual(groups[("jev", "frontier")], self.counts(ran=1))

    def test_order_joins_only_when_nothing_could_be_swapped(self):
        # no agent identity on either child: order is the only evidence
        p = ti._slug("p")
        cases = {
            # the reviewer's tie: two spawns in one second after two routes
            "tie": {p: [self.route("frontier", "jev", ts=100),
                        self.route("cheap", "jev", ts=101)],
                    "a": self.child("p", 102, self.FAIL),
                    "b": self.child("p", 102, self.OK)},
            # distinct seconds, but the first spawn came after the second route
            "overlap": {p: [self.route("frontier", "jev", ts=100),
                            self.route("cheap", "jev", ts=101)],
                        "a": self.child("p", 102, self.FAIL),
                        "b": self.child("p", 103, self.OK)},
        }
        for name, ledgers in cases.items():
            with self.subTest(name):
                groups = tm.route_report(ledgers)[0]
                self.assertEqual(groups[("jev", "frontier")], self.counts(unjoined=1))
                self.assertEqual(groups[("jev", "cheap")], self.counts(unjoined=1))
        # route, spawn, route, spawn: each worker can only be its own route's
        ledgers = {p: [self.route("frontier", "jev", ts=100),
                       self.route("cheap", "jev", ts=102)],
                   "a": self.child("p", 101, self.FAIL),
                   "b": self.child("p", 103, self.OK)}
        groups = tm.route_report(ledgers)[0]
        self.assertEqual(groups[("jev", "frontier")], self.counts(fail=1))
        self.assertEqual(groups[("jev", "cheap")], self.counts(**{"pass": 1}))

    def test_a_nested_orchestrator_s_spawn_rows_type_its_children(self):
        # omp: an unrouted orchestrator shares main's TEZGAH_SESSION, so its route
        # row lands in main's ledger and its worker names main as parent, while
        # the `spawn` row that types that worker is in the orchestrator's ledger
        m = ti._slug("main")
        for tier, name in (("frontier", "Design"), ("cheap", "Patch")):
            with self.subTest(tier):
                ledgers = {m: [self.route("cheap", "jev", ts=100),
                               self.spawn("Fix", "tezgah-cheap"), self.spawn("Orch", "task"),
                               self.route(tier, "jev", ts=110)],
                           "fix": self.child("main", 101, self.OK, agent="Fix"),
                           "orch": self.child("main", 101, self.spawn(name, "tezgah-" + tier),
                                              agent="Orch"),
                           "kid": self.child("main", 111, self.FAIL, agent=name)}
                groups = tm.route_report(ledgers)[0]
                cheap = groups[("jev", "cheap")]
                worker = groups[("jev", tier)]
                if tier == "cheap":
                    self.assertEqual(cheap, dict(self.counts(**{"pass": 1, "fail": 1}),
                                                 routes=2))
                else:
                    self.assertEqual(cheap, self.counts(**{"pass": 1}))
                    self.assertEqual(worker, self.counts(fail=1))

    def test_another_session_s_task_names_never_type_this_one_s_children(self):
        # session A, unrelated and earlier, spawned a cheap worker named Review
        a = {ti._slug("sessA"): [self.route("cheap", "jev", ts=10),
                                 self.spawn("Review", "tezgah-cheap")],
             "a-review": self.child("sessA", 11, self.OK, agent="Review")}
        b = ti._slug("sessB")
        cases = {
            # mis-join: B's unrouted Review would join B's cheap route
            "mis-join": ({b: [self.route("cheap", "jev", ts=100),
                              self.spawn("Review", "task")],
                          "b-review": self.child("sessB", 101, self.FAIL, agent="Review")},
                         self.counts(**{"pass": 1, "unjoined": 1}, routes=2)),
            # lost join: A's Review untyped B's, so B's real cheap worker was lost
            "lost join": ({b: [self.route("cheap", "jev", ts=100),
                               self.spawn("Fix", "tezgah-cheap"), self.spawn("Review", "task")],
                           "b-fix": self.child("sessB", 101, self.OK, agent="Fix"),
                           "b-review": self.child("sessB", 102, self.FAIL, agent="Review")},
                          self.counts(**{"pass": 2}, routes=2)),
        }
        for name, (ledgers, want) in cases.items():
            with self.subTest(name):
                self.assertEqual(tm.route_report(dict(a, **ledgers))[0][("jev", "cheap")],
                                 want)

    def test_two_parents_interleaved_each_join_their_own_children(self):
        ledgers = {ti._slug("p"): [self.route("cheap", "jev", ts=10),
                                   self.route("frontier", "jev", ts=12)],
                   ti._slug("q"): [self.route("standard", "jev", ts=11)],
                   "p1": self.child("p", 11, self.FAIL),
                   "q1": self.child("q", 12, self.EMPTY),
                   "p2": self.child("p", 13, self.OK)}
        groups = tm.route_report(ledgers)[0]
        self.assertEqual(groups[("jev", "cheap")], self.counts(fail=1))
        self.assertEqual(groups[("jev", "frontier")], self.counts(**{"pass": 1}))
        self.assertEqual(groups[("jev", "standard")], self.counts(ran=1))

    def test_a_worker_with_no_check_is_none(self):
        ledgers = {ti._slug("p"): [self.route("cheap", "jev")],
                   "c": self.child("p", 20, {"kind": "edit"})}
        self.assertEqual(tm.route_report(ledgers)[0][("jev", "cheap")],
                         self.counts(none=1))

    def test_counts_that_do_not_line_up_are_unjoined_never_guessed(self):
        p = ti._slug("p")
        cases = {
            # a host with no parent signal (Claude Code, Codex, ...): no child
            "no child": {p: [self.route("cheap", "jev"), self.OK]},
            # an unrouted spawn beside the routed one
            "extra child": {p: [self.route("cheap", "jev")],
                            "a": self.child("p", 20, self.OK),
                            "b": self.child("p", 21, self.FAIL)},
            # a child spawned before its route cannot be that route's worker
            "child first": {p: [self.route("cheap", "jev", ts=30)],
                            "a": self.child("p", 20, self.OK)},
            # another session's child
            "other parent": {p: [self.route("cheap", "jev")],
                             "a": self.child("q", 20, self.OK)},
            # the routed worker never spawned; a typed scout did
            "unrouted scout": {p: [self.route("cheap", "jev"), self.spawn("Look", "scout")],
                               "s": self.child("p", 20, self.OK, agent="Look")},
            # two workers of one type in one second
            "same type tie": {p: [self.route("cheap", "jev", ts=10),
                                  self.route("cheap", "jev", ts=11)],
                              "a": self.child("p", 12, self.OK, agent="tezgah-cheap"),
                              "b": self.child("p", 12, self.FAIL, agent="tezgah-cheap")},
        }
        for name, ledgers in cases.items():
            with self.subTest(name):
                got = tm.route_report(ledgers)[0][("jev", "cheap")]
                self.assertEqual(got["unjoined"], got["routes"], got)

    def test_a_row_another_writer_left_is_not_a_route(self):
        groups, below = tm.route_report({"p": [{"kind": "route", "detail": "garbage"},
                                               {"kind": "judge",
                                                "detail": "tezgah-route x"}]})
        self.assertEqual((groups, below["routes"]), ({}, 0))

    def test_on_omp_the_model_is_the_held_entry_and_a_user_entry_is_an_override(self):
        chain = ["anthropic/claude-opus-5-5:low", "openrouter/z-ai/glm-5.3-flash"]
        cases = (({"tezgah-cheap": chain}, {"tezgah-cheap": chain}, (chain[0], None)),
                 ({"tezgah-cheap": "zai/glm-5.3"}, {"tezgah-cheap": chain},
                  ("zai/glm-5.3", "user")),
                 ({}, {}, (None, "mode")))
        for held, written, want in cases:
            with mock.patch.dict(os.environ, {"OMPCODE": "1"}), \
                    mock.patch.object(tm, "omp_get", return_value=held), \
                    mock.patch.object(tm, "overlay", return_value={"omp_written": written}):
                self.assertEqual(tm.worker_model("tezgah-cheap"), want)


if __name__ == "__main__":
    unittest.main()
