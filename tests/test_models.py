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
    def test_the_anthropic_mode_carries_effort_and_the_frontier_row(self):
        out = tm.omp_overrides("anthropic")
        self.assertEqual(out["tezgah-cheap"], "anthropic/claude-opus-5-5:low")
        self.assertEqual(out["tezgah-explorer"], "anthropic/claude-opus-5-5:medium")
        # the frontier agents are written too: a session that started on a
        # weaker model must not drag security-sensitive work down with it
        for agent in ("tezgah-frontier", "tezgah-reviewer", "tezgah-researcher"):
            self.assertEqual(out[agent], "anthropic/claude-opus-5-5:high")

    def test_any_mode_writes_the_frontier_row_through_openrouter(self):
        with mock.patch.object(tm, "openrouter_ready", return_value=True):
            out = tm.omp_overrides("any")
        for agent in ("tezgah-frontier", "tezgah-reviewer", "tezgah-researcher"):
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
        self.assertEqual(
            tm.omp_role_overrides("any"),
            {"modelRoles.plan": "openrouter/anthropic/claude-opus-5.5:high",
             "modelRoles.slow": "openrouter/anthropic/claude-opus-5.5:high"})
        self.assertEqual(tm.omp_role_overrides("off"), {})
        with mock.patch.object(tm, "openrouter_ready", return_value=False):
            self.assertEqual(tm.omp_role_overrides("any"), {})

    def test_any_mode_goes_through_openrouter(self):
        out = tm.omp_overrides("any")
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        state = {}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                                "memory": "zai/glm-5.3-flash:auto"}}
        state = {}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                                "slow": "@plan"}}
        state = {"mode": "off", "omp_written": {
            "modelRoles.plan": "openrouter/anthropic/claude-opus-5.5:high"}}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        state = {}

        def omp(*args):
            return None if args[1] == "modelRoles" else mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "deepseek/deepseek-flash:high"}}
        state = {"mode": "off", "omp_written": {"tezgah-cheap": "openrouter/z-ai/glm-5.3-flash"}}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        state = {}

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "_omp", side_effect=omp), \
                mock.patch.object(tm, "overlay", side_effect=lambda: dict(state)), \
                mock.patch.object(tm, "save_overlay",
                                  side_effect=lambda d: bool(state.update(d)) or True):
            tm.apply_omp(remove=True)
        self.assertEqual(store["task.agentModelOverrides"], {})

    def test_the_zai_mode_names_the_zai_column(self):
        # the provider whose ids omp's own config already uses, so a machine whose
        # funded provider is z.ai routes without a hand-edited override
        out = tm.omp_overrides("zai")
        self.assertEqual(out["tezgah-cheap"], "zai/glm-5.3-flash")
        self.assertEqual(out["tezgah-explorer"], "zai/glm-5.3-flash")
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
                 "modelRoles": {"default": "deepseek/deepseek-flash:high"}}
        state = {"mode": "anthropic"}  # the mode the switch is moving to

        def omp(*args):
            if args[0] == "set":
                store[args[1]] = json.loads(args[2])
            elif args[0] == "reset":
                store[args[1]] = {}
            return mock.Mock(stdout="")

        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        state = {}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        state = {}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
                 "modelRoles": {"default": "deepseek/deepseek-flash:high"}}
        called = []
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
                mock.patch.object(tm, "_omp", side_effect=lambda *a: called.append(a)), \
                mock.patch.object(tm, "openrouter_ready", return_value=False), \
                mock.patch.object(tm, "overlay", return_value={}):
            status = tm.apply_omp()
        self.assertIn("skipped", status)
        self.assertEqual(called, [], "nothing may be written when the tier cannot run")

    def test_bundled_agents_are_routed_and_the_reviewers_inherit(self):
        out = tm.omp_overrides("anthropic")
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
                 "modelRoles": {"default": "anthropic/claude-opus-5-5:high"}}
        state = {}
        with mock.patch.object(tm, "omp_get", side_effect=lambda k: dict(store[k])), \
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
        # a flag before the brief is the same call: the policy text tells an
        # agent to run `tezgah-route --phase code "<brief>"` either way round
        p = self.run_route("--json", "--phase", "code", "Add a flag")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["agent"], "tezgah-standard")

    def test_an_unknown_phase_is_misuse(self):
        self.assertEqual(self.run_route("x", "--phase", "vibes").returncode, 2)


if __name__ == "__main__":
    unittest.main()
