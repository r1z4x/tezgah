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

    def test_notice_records_every_vendored_repository_and_what_changed(self):
        # One entry per upstream repository, naming the revision, the licence and
        # every departure: a vendored tree whose NOTICE entry cannot say which
        # bytes changed is a copy nobody can audit.
        for needle in ("skills/design-library",
                       "inclusive-design-skills", "designer-skills",
                       "6e0740f04b2130af60bc57abe3401b91e460e70d",
                       "9a6930cf84a822eb458624bd11c61aac5bbdf224",
                       "touch-target-design", "adaptive-personalisation"):
            self.assertIn(needle, self.notice, needle)

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


class PlanSkillsStayInTheWorkspace(unittest.TestCase):
    """`.tezgah/` is gitignored in the project and is its own repository, so a
    plan skill's git step that ran against the project would either fail on an
    ignored path or put plans into the project's history."""

    def test_every_plan_git_write_runs_in_the_private_repository(self):
        for name in ("plan-add", "plan-status", "plan-sync"):
            text = read(os.path.join(SKILLS, name, "SKILL.md"))
            project = re.findall(r"\bgit (?:add|mv|commit|push|status)\b", text)
            self.assertEqual([], project, name)
            private = re.findall(r'git -C "\$ROOT/\.tezgah"[^`]*? (?:add|commit|status)\b',
                                 text)
            self.assertTrue(private, name)
            # a path handed to that repository is relative to it: `plans/...`
            self.assertNotRegex(flat(text), r'git -C "\$ROOT/\.tezgah" add [^`]*\.tezgah/',
                                name)


LIBRARY = os.path.join(SKILLS, "design-library")
LIBRARY_SOURCE = os.path.join(LIBRARY, "SOURCE")
LIBRARY_ROW = re.compile(
    r"^\|\s*`([A-Za-z0-9/_.-]+/SKILL\.md)`\s*\|\s*`[\w-]+`\s*\|\s*"
    r"`([0-9a-f]{64})`\s*\|", re.M)
# The most a shipped entry point's description may carry: the always-on band is
# the sum of these and the router shows one sentence of each, so a description
# past this is prose nobody reads. The longest today is 961 (`feature-audit`).
DESCRIPTION_CAP = 1200
TRIGGER = re.compile(r"(?:^|[.!?]\s+)(?:Also )?[Uu]se\b")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def library_manifest():
    """{relpath: sha256} from skills/design-library/SOURCE's own table."""
    return dict(LIBRARY_ROW.findall(read(LIBRARY_SOURCE)))


def vendored_skill_files():
    """Every SKILL.md whose frontmatter is upstream's bytes, not tezgah's: the
    bodies under a `skills/<name>/` that ships a SOURCE manifest. Their integrity
    is that library's own hash test, and their frontmatter is not tezgah's to
    rewrite without breaking it."""
    out = set()
    for source in glob.glob(os.path.join(SKILLS, "*", "SOURCE")):
        out |= set(glob.glob(os.path.join(os.path.dirname(source), "**", "SKILL.md"),
                             recursive=True))
    return out


def frontmatter(text):
    """(name, description, body) of a SKILL.md, or (None, "", text)."""
    block = re.match(r"---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not block:
        return None, "", text
    head = block.group(1)
    name = re.search(r"^name:\s*(.+)$", head, re.M)
    folded = re.search(r"description:\s*[>|]-?\s*\n((?:\s+.*\n?)+)", head)
    if folded:
        desc = " ".join(line.strip() for line in folded.group(1).splitlines())
    else:
        inline = re.search(r"description:\s*(.+)", head)
        desc = inline.group(1).strip().strip("\"'") if inline else ""
    return (name.group(1).strip().strip("\"'") if name else None,
            re.sub(r"\s+", " ", desc).strip(), text[block.end():])


class DesignLibrary(unittest.TestCase):
    """skills/design-library: a nested vendored tree, held to its own manifest.

    The bodies are reached on demand through `INDEX.md` and the router never
    lists them, so nothing else in the suite would notice a body that drifted, a
    file that vanished, or a directory that arrived unvetted."""

    @classmethod
    def setUpClass(cls):
        cls.rows = library_manifest()
        # The library's own entry point sits at the root and is not vendored, so
        # the tree's adopted bodies are the ones under a plugin directory.
        cls.bodies = sorted(p[len(LIBRARY) + 1:] for p in
                            glob.glob(os.path.join(LIBRARY, "**", "SKILL.md"),
                                      recursive=True)
                            if os.sep in p[len(LIBRARY) + 1:])

    def test_the_manifest_lists_every_adopted_body_and_only_bodies(self):
        self.assertTrue(self.rows, "SOURCE records no file/hash pair")
        self.assertEqual(sorted(self.rows), self.bodies,
                         "SOURCE and the tree disagree about which bodies exist")
        for rel in self.rows:
            self.assertEqual(len(rel.split("/")), 4,
                             "%s is not at <plugin>/skills/<name>/SKILL.md" % rel)

    def test_every_listed_body_is_present_and_matches_its_hash(self):
        for rel, want in sorted(self.rows.items()):
            path = os.path.join(LIBRARY, rel)
            self.assertTrue(os.path.isfile(path), "vendored file missing: %s" % rel)
            with open(path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(digest, want,
                             "%s no longer matches the hash SOURCE records" % rel)

    def test_the_tree_holds_no_directory_the_manifest_does_not_list(self):
        listed = {rel.split("/")[0] for rel in self.rows}
        found = {n for n in os.listdir(LIBRARY)
                 if os.path.isdir(os.path.join(LIBRARY, n))}
        self.assertEqual(found, listed,
                         "the tree holds a directory SOURCE does not list")

    def test_every_adopted_body_is_named_for_its_directory(self):
        # A host loads a skill from its directory and skips one whose frontmatter
        # `name` disagrees with it, which is why the adaptive-personalisation copy
        # is adapted; a re-vendor that drops the correction has to fail here.
        for rel in sorted(self.rows):
            name = rel.split("/")[2]
            head = frontmatter(read(os.path.join(LIBRARY, rel)))[0]
            self.assertEqual(head, name, rel)

    def test_the_entry_point_and_its_aids_are_tezgahs_own(self):
        # The same rule skills/pm-frameworks and skills/ai-research state: the
        # entry point, its index, its evals and the manifest are tezgah's files,
        # so no adopted body may be listed at the library root.
        for own in ("SKILL.md", "SOURCE", "INDEX.md", "EVALS.md"):
            self.assertTrue(os.path.isfile(os.path.join(LIBRARY, own)), own)
        self.assertEqual([rel for rel in self.rows if "/" not in rel], [],
                         "SOURCE lists a file at the library root")


class TapTarget(unittest.TestCase):
    """No adopted body may pair 44x44 with WCAG Level AA.

    WCAG 2.2 SC 2.5.8 Target Size (Minimum) is Level AA at 24x24 CSS px and SC
    2.5.5 Target Size (Enhanced) is Level AAA at 44x44; tezgah's own floor is 24
    (`bin/tezgah-design`'s `TAP_TARGET`, citing SC 2.5.8). The corpus this library
    was vendored from shipped the pairing, which is why one body is adapted."""

    SIZE = re.compile(r"44\s*(?:\u00d7|x)\s*44|44\s*px\b")
    LEVEL_AA = re.compile(r"Level AA\b")

    def test_no_adopted_body_pairs_44_with_level_aa(self):
        offenders = []
        for rel in sorted(library_manifest()):
            body = frontmatter(read(os.path.join(LIBRARY, rel)))[2]
            for line in body.splitlines():
                if self.SIZE.search(line) and self.LEVEL_AA.search(line):
                    offenders.append("%s: %s" % (rel, line.strip()))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_adopted_copy_states_24_as_the_aa_floor_and_44_as_aaa(self):
        body = frontmatter(read(os.path.join(
            LIBRARY, "inclusive-interaction/skills/touch-target-design/SKILL.md")))[2]
        self.assertIn("Minimum: 24\u00d724 CSS pixels (WCAG 2.2 SC 2.5.8, Level AA)",
                      body)
        self.assertIn("Enhanced: 44\u00d744 CSS pixels (WCAG 2.2 SC 2.5.5, Level AAA",
                      body)

    def test_the_correction_is_named_in_the_source_table(self):
        source = read(LIBRARY_SOURCE)
        for needle in ("SC 2.5.8", "24x24", "SC 2.5.5", "44x44"):
            self.assertIn(needle, source, needle)


class DesignLibraryEvals(unittest.TestCase):
    """The library's own evals: three trap cases, each with a Must contain and a
    Must not, in the shape the vendored corpus ships. It is the only proposed
    proof in that corpus that a skill changes behaviour."""

    @classmethod
    def setUpClass(cls):
        cls.cases = re.split(r"^## Case ", read(os.path.join(LIBRARY, "EVALS.md")),
                             flags=re.M)[1:]

    def test_three_cases_each_carry_a_must_contain_and_a_must_not(self):
        self.assertEqual(len(self.cases), 3, "the evals no longer hold 3 cases")
        for i, case in enumerate(self.cases, 1):
            self.assertIn("**Must contain**", case, i)
            self.assertIn("**Must not**", case, i)
            contains, rest = case.split("**Must contain**")[1].split("**Must not**")
            self.assertTrue(re.search(r"^- \[ \] \S", contains, re.M),
                            "case %d has no Must contain line" % i)
            must_not = rest.split("**Why this case**")[0]
            self.assertTrue(re.search(r"^- \S", must_not, re.M),
                            "case %d has no Must not line" % i)

    def test_every_case_says_why_it_is_a_trap(self):
        for i, case in enumerate(self.cases, 1):
            self.assertIn("**Why this case**", case, i)


class DesignLibraryIndex(unittest.TestCase):
    """INDEX.md is the routing surface for a nested tree: one line per adopted
    entry, `name - what it makes - path`, inside the router's own budget."""

    LINE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*) - (.+) - "
                      r"([A-Za-z0-9/_.-]+/SKILL\.md)$")

    @classmethod
    def setUpClass(cls):
        cls.text = read(os.path.join(LIBRARY, "INDEX.md"))
        cls.lines = [line for line in cls.text.splitlines()
                     if cls.LINE.match(line)]
        cls.found = [cls.LINE.match(line) for line in cls.lines]

    def test_the_index_covers_every_adopted_entry_exactly_once(self):
        names = [m.group(1) for m in self.found]
        self.assertEqual(len(names), len(set(names)), "an entry is listed twice")
        self.assertEqual(sorted(names), sorted(rel.split("/")[2]
                                               for rel in library_manifest()))

    def test_every_index_line_names_a_file_that_exists(self):
        for m in self.found:
            self.assertTrue(os.path.isfile(os.path.join(LIBRARY, m.group(3))),
                            m.group(3))
            self.assertTrue(m.group(2).strip(), m.group(1))

    def test_every_index_line_stays_inside_the_router_budget(self):
        for line in self.lines:
            self.assertLessEqual(len(line), 140, line)


class Frontmatter(unittest.TestCase):
    """The frontmatter of every skill tezgah ships an entry point for: the name
    equals its directory, it is kebab-case, a `Use when` sentence is present, the
    description stays inside the metadata cap, and every backticked
    cross-reference resolves.

    The vendored trees are out of scope by the same rule that keeps them out of
    the router: their frontmatter is upstream's bytes, pinned by that library's
    own hash test (every `skills/<name>/SOURCE`), and rewriting a name there
    would break the manifest that proves the copy is upstream's."""

    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
        cls.roots = sorted(os.path.dirname(source) for source in
                           glob.glob(os.path.join(SKILLS, "*", "SOURCE")))
        cls.exempt = vendored_skill_files()
        cls.names = {d for d in os.listdir(SKILLS)
                     if os.path.isdir(os.path.join(SKILLS, d))}

    def test_the_lint_covers_every_body_and_exempts_only_the_libraries(self):
        # The exemption is the library roots, not a glob: a new body is linted
        # unless it arrives under a tree that ships its own hash manifest.
        self.assertEqual([os.path.basename(root) for root in self.roots],
                         ["ai-research", "design-library", "pm-frameworks"],
                         "the vendored set changed: name it here, or lint it")
        for path in glob.glob(os.path.join(SKILLS, "**", "SKILL.md"), recursive=True):
            covered = (path in self.paths or
                       any(path.startswith(root + os.sep) for root in self.roots))
            self.assertTrue(covered,
                            "%s is neither an entry point nor vendored" % path)

    def test_every_entry_point_declares_a_name_matching_its_directory(self):
        for path in self.paths:
            directory = os.path.basename(os.path.dirname(path))
            name = frontmatter(read(path))[0]
            self.assertEqual(name, directory, path)

    def test_every_name_is_kebab_case(self):
        for path in self.paths:
            name = frontmatter(read(path))[0]
            self.assertRegex(name or "", KEBAB, path)

    def test_every_description_carries_a_use_when_sentence(self):
        for path in self.paths:
            desc = frontmatter(read(path))[1]
            self.assertTrue(desc, "%s carries no description" % path)
            self.assertTrue(TRIGGER.search(desc),
                            "%s has no `Use when` sentence" % path)

    def test_every_description_stays_inside_the_metadata_cap(self):
        for path in self.paths:
            desc = frontmatter(read(path))[1]
            self.assertLessEqual(len(desc), DESCRIPTION_CAP,
                                 "%s: %d chars" % (path, len(desc)))

    def test_every_backticked_cross_reference_resolves(self):
        for path in self.paths:
            text = read(path)
            for ref in re.findall(r"`(skills/[A-Za-z0-9_./-]+)`", text):
                self.assertTrue(os.path.exists(os.path.join(support.REPO, ref)),
                                "%s cites a missing %s" % (path, ref))
            for token in re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)*)`", text):
                if token in self.names:
                    self.assertTrue(
                        os.path.isfile(os.path.join(SKILLS, token, "SKILL.md")),
                        "%s cites the skill `%s`, which has no SKILL.md"
                        % (path, token))
