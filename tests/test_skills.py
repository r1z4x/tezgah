"""skills/*/SKILL.md: the standards the harness audit found broken.

One test per standard, so an edit that brings back a floating npx tag, an
unrendered placeholder, a bare slash command, a missing kill switch or a
clobbering bootstrap fails here instead of in a session. The router lines that
pair with these (a skill's trigger sentence reaching the generated router) are
pinned in tests/test_setup.py.
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


def package_specs(command):
    """The package specs a wired command declares, scoped (`@scope/name@1.2`) or
    not (`name@1.2`): the plain `@`-prefixed read breaks on the second kind."""
    return [p for p in command if "@" in p and not p.startswith("-")]


class SkillStandards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
        cls.paths = paths
        cls.texts = {os.path.basename(os.path.dirname(p)): read(p) for p in paths}
        cls.all_text = "\n".join(cls.texts.values())
        cls.notice = read(os.path.join(support.REPO, "NOTICE"))
        cls.apps = load("tezgah_apps", os.path.join(support.HOOKS, "tezgah_apps.py"))
        cls.policy = load("tezgah_policy", os.path.join(support.HOOKS, "tezgah_policy.py"))

    def test_every_shipped_skill_name_resolves_to_its_skill_file(self):
        # A name in the installer's SKILLS list whose SKILL.md was never written
        # links a dangling path into every host at once and still reported as
        # installed, because the check asked `islink` and a link to nothing is a
        # link. Pin the name list against the files it claims.
        import importlib.machinery
        name = "tezgah_setup_under_test"
        loader = importlib.machinery.SourceFileLoader(
            name, os.path.join(support.REPO, "bin", "tezgah-setup"))
        spec = importlib.util.spec_from_loader(name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        missing = [s for s in mod.SKILLS
                   if not os.path.isfile(os.path.join(SKILLS, s, "SKILL.md"))]
        self.assertEqual(missing, [],
                         "SKILLS names a skill with no SKILL.md: %s" % missing)

    def bootstrap_step(self):
        """The numbered bootstrap step, whatever number it carries."""
        m = re.search(r"\n\d+\.\s*Bootstrap(.*?)(?=\n\d+\.\s|\Z)",
                      self.texts["plan-add"], re.S)
        self.assertIsNotNone(m, "plan-add has no numbered 'Bootstrap' step")
        return flat(m.group(1))

    def test_the_bootstrap_completes_a_partial_tree_and_never_clobbers_it(self):
        # The guard used to test the plans/ DIRECTORY, so a half-built tree was
        # skipped and an existing README could be overwritten. Pin the behaviour,
        # not one phrasing of it.
        step = self.bootstrap_step()
        self.assertIn("mkdir -p plans/open plans/done", step)
        self.assertNotRegex(
            step, r"(?i)(?:if|when|unless)[^.]{0,60}plans[^.]{0,60}"
                  r"(?:exist|director|missing|absent|present)")
        self.assertRegex(step, r"README\.md[^.]*(?:does not exist|is absent|is missing)")
        self.assertIn("never overwrite", step.lower())

    def test_no_floating_npx_tag_and_the_fallback_names_the_wired_pins(self):
        floating = sorted(set(re.findall(r"[\w@./-]+@latest\b", self.all_text)))
        self.assertEqual(floating, [],
                         "a floating tag fetches whatever the registry serves")
        for server in self.apps.SERVERS:
            for spec in package_specs(server["command"]):
                self.assertIn(spec, self.texts["analyze-app"],
                              "analyze-app's fallback does not name the wired pin")

    def test_every_documented_kill_switch_is_named_in_the_contract(self):
        self.assertIn("**Kill switches:**", self.policy.CORE)
        block = self.policy.CORE[
            self.policy.CORE.index("**Kill switches:**"):].split("\n\n")[0]
        switches = [s for s in re.findall(r"`([^`]+)`", block)
                    if s != "~/.config/tezgah/"]
        self.assertTrue(switches, "no kill switch names found in policy.CORE")
        missing = [s for s in switches if s not in self.texts["tezgah-contract"]]
        self.assertEqual(missing, [],
                         "tezgah-contract documents %d of %d kill switches"
                         % (len(switches) - len(missing), len(switches)))

    def test_no_unrendered_placeholder_reaches_the_injected_text(self):
        injected = [v for k, v in vars(self.policy).items()
                    if k.isupper() and isinstance(v, str)]
        self.assertTrue(injected, "no injected text found in tezgah_policy")
        text = "\n".join([self.all_text] + injected)
        for placeholder in ("<repo slug>", "<index status>"):
            self.assertNotIn(placeholder, text)

    def test_the_plan_status_enrichment_flag_lives_only_where_it_is_used(self):
        owners = sorted(n for n, t in self.texts.items()
                        if "For plan-status pass" in t)
        self.assertEqual(owners, ["plan-status"])

    def test_slash_commands_carry_the_prefix_the_plugin_registers(self):
        # `.claude-plugin/plugin.json` registers the plugin as `tezgah`, so a
        # bare `/plan-add` is a command that does not exist - in the skills and
        # in the READMEs a user reads.
        sources = dict(self.texts)
        for path in sorted(glob.glob(os.path.join(support.REPO, "README*.md"))):
            sources[os.path.basename(path)] = read(path)
        bare = {}
        for name, text in sources.items():
            found = set(re.findall(
                r"(?<![\w:/])/(ponytail|plan-add|plan-status|plan-sync)\b", text))
            if found:
                bare[name] = sorted(found)
        self.assertEqual(bare, {})
        self.assertIn("/tezgah:plan-add", self.texts["plan-add"])
        self.assertIn("/tezgah:plan-sync", " ".join(sources.values()))

    def test_no_convention_points_at_a_marker_absent_from_the_tree(self):
        self.assertNotIn("NOT_IMPLEMENTED", self.all_text)

    def test_notice_records_the_adapted_upstream_and_its_licence(self):
        for needle in ("skills/research", "AI-research-SKILLs", "MIT"):
            self.assertIn(needle, self.notice)

    def test_analyze_app_does_not_claim_only_two_hosts_may_be_unwired(self):
        self.assertNotIn(
            "dsh and Claude are the hosts whose MCP wiring may be absent",
            flat(self.texts["analyze-app"]))


if __name__ == "__main__":
    unittest.main()
