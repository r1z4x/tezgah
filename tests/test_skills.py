"""skills/*/SKILL.md: the standards the harness audit found broken.

One test per standard, so an edit that brings back a floating npx tag, an
unrendered placeholder, a bare slash command, a missing kill switch or a
clobbering bootstrap fails here instead of in a session. The router lines that
pair with these (a skill's trigger sentence reaching the generated router) are
pinned in tests/test_setup.py.
"""
import glob
import hashlib
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
        # The guard used to test the .tezgah/plans/ DIRECTORY, so a half-built tree was
        # skipped and an existing README could be overwritten. Pin the behaviour,
        # not one phrasing of it.
        step = self.bootstrap_step()
        self.assertIn("mkdir -p .tezgah/plans/open .tezgah/plans/done", step)
        self.assertNotRegex(
            step, r"(?i)(?:if|when|unless)[^.]{0,60}plans[^.]{0,60}"
                  r"(?:exist|director|missing|absent|present)")
        self.assertRegex(step, r"README\.md[^.]*(?:does not exist|is absent|is missing)")
        self.assertIn("never overwrite", step.lower())

    def test_no_floating_npx_tag_and_the_fallback_names_the_wired_pins(self):
        floating = sorted(set(re.findall(r"[\w@./-]+@latest\b", self.all_text)))
        self.assertEqual(floating, [],
                         "a floating tag fetches whatever the registry serves")
        for server in self.apps.servers():
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
        # A switch the session cannot name is one nobody uses: `judge-off` lived
        # in the module and in three callers for a round and was absent here, so
        # every caller's switch is pinned, not only its mirror in the skill.
        for name in ("judge-off", "triage-off", "docs-judge-off"):
            self.assertIn("`%s`" % name, block)
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

    def test_the_vendored_product_tree_matches_its_manifest(self):
        """A vendored body that drifted from its recorded hash is no longer the
        upstream method, and a directory beside it that SOURCE does not list is
        text nobody vetted. Both are silent without this."""
        root = os.path.join(SKILLS, "pm-frameworks")
        source = read(os.path.join(root, "SOURCE"))
        rows = dict(re.findall(
            r"`([\w-]+/SKILL\.md)`\s*\|\s*`[^`]*`\s*\|\s*`([0-9a-f]{64})`",
            source))
        self.assertTrue(rows, "SOURCE records no file/hash pair")
        for rel, want in rows.items():
            path = os.path.join(root, rel)
            self.assertTrue(os.path.isfile(path), "vendored file missing: %s" % rel)
            with open(path, "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(got, want,
                             "%s no longer matches the hash SOURCE records" % rel)
        listed = {rel.split("/")[0] for rel in rows}
        found = {n for n in os.listdir(root)
                 if os.path.isdir(os.path.join(root, n))}
        self.assertEqual(found, listed,
                         "the tree holds a directory SOURCE does not list")

    def test_analyze_app_does_not_claim_only_two_hosts_may_be_unwired(self):
        self.assertNotIn(
            "dsh and Claude are the hosts whose MCP wiring may be absent",
            flat(self.texts["analyze-app"]))


class ResearchMethod(unittest.TestCase):
    """skills/research/SKILL.md: the method prose a session acts on.

    The standards above police every skill's shape (floating tags, placeholders,
    kill-switch names); nothing read this file, so a dropped review dimension, a
    lost anchor row, a grade mapping that no longer names its thresholds, or a
    claim kind that stopped naming the evidence it needs was invisible. The
    assertions are on the row and the sentence, never on the line wrapping.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = read(os.path.join(SKILLS, "research", "SKILL.md"))
        cls.flat = flat(cls.text)
        cls.plain = re.sub(r"[*`]", "", cls.flat)

    @classmethod
    def tables(cls):
        """Each markdown table as a list of cell rows, in file order."""
        out, block = [], []
        for line in cls.text.splitlines():
            if line.strip().startswith("|"):
                block.append([c.strip() for c in
                              line.strip().strip("|").split("|")])
            elif block:
                out.append(block)
                block = []
        if block:
            out.append(block)
        return out

    def table(self, header):
        """The body rows of the one table whose first header cell is `header`."""
        for block in self.tables():
            if block[0][0] == header:
                return block[2:]          # drop the header and its separator
        self.fail("skills/research/SKILL.md has no `%s` table" % header)

    def test_the_review_keeps_its_six_dimensions_and_their_anchors(self):
        dims = self.table("Dimension")
        self.assertEqual([r[0] for r in dims],
                         ["Evidence relevance", "Falsifiability",
                          "Scope calibration", "Argument coherence",
                          "Exploration integrity", "Methodological rigour"])
        for name, question in dims:
            self.assertTrue(question, "%s asks no question" % name)
        anchors = self.table("Score")
        self.assertEqual([r[0].strip("*") for r in anchors],
                         ["5", "4", "3", "2", "1"])
        for score, meaning in anchors:
            self.assertTrue(meaning, "anchor %s states no meaning" % score)

    def test_the_grade_mapping_names_its_thresholds_and_its_order(self):
        # The mean is the summary, so mean-to-grade is the one thing two sessions
        # compare; a missing threshold or a swapped grade makes the review
        # incomparable and a null result read as an accept.
        for pattern in (r"4\.5[^.]{0,80}accept",
                        r"3\.8[^.]{0,80}weak accept",
                        r"3\.0[^.]{0,80}revise",
                        r"below that[^.]{0,20}any dimension at 1[^.]{0,20}reject"):
            self.assertRegex(self.flat, pattern)

    def test_every_claim_kind_still_names_the_evidence_it_needs(self):
        # The mismatch rule: a claim whose kind and evidence disagree is a
        # finding even when the cited run is real.
        for kind, needs in (("causal", "isolating ablation"),
                            ("generalization", "heterogeneous conditions"),
                            ("improvement", "baseline from the same harness"),
                            ("descriptive", "representative sampling"),
                            ("scoping", "declared bounds")):
            self.assertRegex(self.flat, r"%s[^.]{0,120}%s" % (kind, needs))

    def test_the_provenance_table_keeps_its_four_tags(self):
        tags = [r[0].strip("`") for r in self.table("Tag")]
        self.assertEqual(tags, ["user", "ai-suggested", "ai-executed",
                                "user-revised"])
        self.assertRegex(self.plain,
                         r"Default to ai-suggested when unsure - never tag an "
                         r"inference as user")

    def test_a_citation_is_verified_against_two_sources_or_marked(self):
        # The defect the rule exists for: a plausible-looking reference that does
        # not exist reads exactly like a real one.
        self.assertIn("Never write a citation from memory.", self.flat)
        self.assertRegex(self.flat,
                         r"Verify each one against two of Semantic Scholar, "
                         r"CrossRef \(DOI content negotiation\), arXiv or OpenAlex")
        self.assertIn("[CITATION NEEDED]", self.plain)

    def test_the_evidence_fidelity_rules_survive(self):
        for rule in ("Exact numbers, never rounded.",
                     "A derived view is not the source.",
                     "Every result row carries its source",
                     "Wording cannot outrun the evidence type."):
            self.assertIn(rule, self.plain)

    def test_a_patterns_bullet_names_what_it_generalises_from(self):
        self.assertRegex(self.flat,
                         r"`## Patterns` bullet names what it generalises from - "
                         r"a claim id, a `literature/` note or a run")

    def test_the_ideation_moves_and_the_figure_rules_survive(self):
        # The moves a stuck line is told to reach for, and the figure rules that
        # decide what a report may show.
        self.assertEqual(len(self.table("State")), 4)
        for move in ("Diverge first", "Expose a hidden constraint",
                     "Force distance", "Bisociate", "Kill criteria", "Converge"):
            self.assertIn(move, self.plain)
        self.assertIn("a pie chart is almost never the answer", self.flat)
        self.assertIn("Export PDF for anything with numerical axes", self.flat)
        self.assertIn("colourblind-safe", self.flat)


if __name__ == "__main__":
    unittest.main()


class ContractSkillMatchesTheRule(unittest.TestCase):
    """The contract skill is hand-kept, so it can drift from the rule it ships.

    `skills/tezgah-contract/SKILL.md` is a CONTRACT *source*
    (`bin/tezgah-setup`'s `CONTRACT_SOURCES`), not a generated file: the policy
    constant and the skill are two readings of one rule, which is the shape the
    repository's lessons ledger records as drifting in both directions. This case
    pins the facts a session acts on - where the index is, which verb refreshes
    it, and the mark that turns the rule off - so the next edit to either side has
    to move both.
    """

    def setUp(self):
        with open(os.path.join(SKILLS, "tezgah-contract", "SKILL.md")) as fh:
            self.text = fh.read()
        with open(os.path.join(support.REPO, "hooks", "tezgah_policy.py")) as fh:
            self.policy = fh.read()

    def test_the_skill_carries_the_index_the_sync_and_the_opt_out(self):
        for fact in ("<repo>/.codegraph/codegraph.db", "codegraph sync",
                     ".no-graph"):
            self.assertIn(fact, self.text, fact)
            self.assertIn(fact, self.policy, fact)

    def test_the_skill_explains_the_extension_mapping_and_the_twins(self):
        # `codegraph.json` maps extensions to languages and nothing else, so a
        # `bin/` script with no extension is in the graph only through a `.py`
        # twin beside it. A session that answers a caller question about one of
        # those scripts has to know which path the index actually holds, so the
        # rule states it rather than leaving the twin as a surprise.
        for fact in ("codegraph.json", "`.py` twin", "bin/tezgah-setup.py"):
            self.assertIn(fact, flat(self.text), fact)
