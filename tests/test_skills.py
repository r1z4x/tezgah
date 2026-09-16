"""skills/*/SKILL.md: the standards the harness audit found broken.

One test per finding, so an edit that brings back a floating npx tag, an
unrendered placeholder, a bare slash command, a missing kill switch or a
clobbering bootstrap fails here instead of in a session. The nine are the ones
the audit named (F1 and F4-F11); F2/F3 are the router lines the installer owns
and are pinned in tests/test_setup.py.
"""
import glob
import importlib.util
import os
import re
import unittest

import support

SKILLS = os.path.join(support.REPO, "skills")


def flat(text):
    """Prose assertions are on the sentence, not on the line wrapping."""
    return re.sub(r"\s+", " ", text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SkillStandards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
        cls.paths = paths
        cls.texts = {os.path.basename(os.path.dirname(p)): read(p) for p in paths}
        cls.all_text = "\n".join(cls.texts.values())
        cls.notice = read(os.path.join(support.REPO, "NOTICE"))

    def bootstrap_step(self):
        return flat(self.texts["plan-add"].split("2. Bootstrap", 1)[1]
                    .split("3. Next id", 1)[0])

    def test_f1_the_bootstrap_completes_a_partial_tree_and_never_clobbers_it(self):
        # the guard used to test the plans/ dir, so a half-built tree was skipped
        # and an existing README could be overwritten
        step = self.bootstrap_step()
        self.assertIn("mkdir -p plans/open plans/done", step)
        self.assertNotRegex(step, r"if `?\$ROOT/plans`? (is|does not exist)")
        self.assertRegex(step, r"README\.md[^.]*(does not exist|is absent|is missing)")
        self.assertIn("never overwrite", step.lower())

    def test_f4_no_floating_npx_tag_and_the_fallback_names_the_wired_pin(self):
        floating = sorted(set(re.findall(r"[\w@./-]+@latest\b", self.all_text)))
        self.assertEqual(floating, [],
                         "a floating tag fetches whatever the registry serves")
        apps = load("tezgah_apps", os.path.join(support.HOOKS, "tezgah_apps.py"))
        for server in apps.SERVERS:
            pin = [a for a in server["command"] if a.startswith("@")][0]
            self.assertIn(pin, self.texts["analyze-app"],
                          "analyze-app's fallback does not name the wired pin")

    def test_f5_every_documented_kill_switch_is_named_in_the_contract(self):
        policy = load("tezgah_policy", os.path.join(support.HOOKS, "tezgah_policy.py"))
        self.assertIn("**Kill switches:**", policy.CORE)
        block = policy.CORE[policy.CORE.index("**Kill switches:**"):].split("\n\n")[0]
        switches = [s for s in re.findall(r"`([^`]+)`", block)
                    if s != "~/.config/tezgah/"]
        self.assertTrue(switches, "no kill switch names found in policy.CORE")
        missing = [s for s in switches if s not in self.texts["tezgah-contract"]]
        self.assertEqual(missing, [],
                         "tezgah-contract documents %d of %d kill switches"
                         % (len(switches) - len(missing), len(switches)))

    def test_f6_no_unrendered_placeholder_reaches_the_reader(self):
        for placeholder in ("<repo slug>", "<index status>"):
            self.assertNotIn(placeholder, self.all_text)

    def test_f7_the_plan_status_enrichment_flag_lives_only_where_it_is_used(self):
        owners = sorted(n for n, t in self.texts.items()
                        if "For plan-status pass" in t)
        self.assertEqual(owners, ["plan-status"])

    def test_f8_slash_commands_carry_the_prefix_the_plugin_registers(self):
        bare = set()
        for text in self.texts.values():
            bare |= set(re.findall(
                r"(?<![\w:/])/(ponytail|plan-add|plan-status|plan-sync)\b", text))
        self.assertEqual(sorted(bare), [])

    def test_f9_no_convention_points_at_a_marker_absent_from_the_tree(self):
        self.assertNotIn("NOT_IMPLEMENTED", self.all_text)

    def test_f10_notice_records_the_adapted_upstream_and_its_licence(self):
        for needle in ("skills/research", "AI-research-SKILLs", "MIT"):
            self.assertIn(needle, self.notice)

    def test_f11_analyze_app_does_not_claim_only_two_hosts_may_be_unwired(self):
        self.assertNotIn(
            "dsh and Claude are the hosts whose MCP wiring may be absent",
            flat(self.texts["analyze-app"]))

    def test_the_router_trigger_sentences_survive(self):
        # the installer's router prefers these sentences; a reword here silently
        # drops the words that arm the skill
        self.assertIn("Use on ANY coding task", flat(self.texts["ponytail"]))
        self.assertIn("Use when the compact core points here",
                      flat(self.texts["tezgah-contract"]))


if __name__ == "__main__":
    unittest.main()
