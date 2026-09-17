"""skills/ai-research: the vendored library, and the importer that builds it.

Two halves. The committed tree is checked against its own manifest - coverage,
digests, attribution, the drop list, the stage index, the size cap - because a
vendored copy that drifts from its manifest is worse than no copy at all. Then
the importer is driven against a synthetic upstream tree, so every rule it
enforces (markdown only, the drop list, the attribution line, determinism,
`--check`, a dirty or surprising upstream) is proved without the real 98-skill
checkout being present on the machine or in CI.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import support

REPO = support.REPO
HOOKS = support.HOOKS
SKILL = os.path.join(REPO, "skills", "ai-research")
LIBRARY = os.path.join(SKILL, "library.json")
SOURCE = os.path.join(SKILL, "SOURCE")
IMPORTER = os.path.join(REPO, "bin", "tezgah-import-ai-research")
REV = "773a52944ba4747a18bd4ae9ade53fff041adcbc"
GENERATED = {"axolotl", "llama-factory", "unsloth", "deepspeed"}
CAP_BYTES = 5 * 1024 * 1024


def load(name, path):
    """An extension-less script (bin/tezgah-import-ai-research) has no spec from
    its path alone, so the loader is named explicitly."""
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class VendoredTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(read(LIBRARY))
        cls.skills = cls.manifest["skills"]
        cls.index = {f["path"]: f for f in cls.manifest.get("index", [])}

    def test_every_manifest_file_is_present_and_unchanged(self):
        missing, changed = [], []
        for entry in self.skills:
            for f in entry["files"]:
                path = os.path.join(SKILL, f["path"])
                if not os.path.isfile(path):
                    missing.append(f["path"])
                elif digest(path) != f["sha256"]:
                    changed.append(f["path"])
        self.assertEqual((missing, changed), ([], []),
                         "the vendored tree no longer matches library.json - "
                         "re-run bin/tezgah-import-ai-research")

    def test_the_tree_holds_nothing_the_manifest_does_not_name(self):
        listed = {f["path"] for e in self.skills for f in e["files"]} | set(self.index)
        found = set()
        for root, _dirs, names in os.walk(SKILL):
            for name in names:
                rel = os.path.relpath(os.path.join(root, name), SKILL)
                if rel not in ("library.json", "SKILL.md", "SOURCE"):
                    found.add(rel)
        self.assertEqual(sorted(found - listed), [],
                         "an unlisted file sits in the vendored tree")

    def test_the_library_is_complete(self):
        counts = self.manifest["counts"]
        self.assertEqual((counts["categories"], counts["skills"]), (23, 98))
        self.assertEqual(len(self.skills), 98)
        self.assertEqual(len({s["category"] for s in self.skills}), 23)
        for entry in self.skills:
            self.assertTrue(entry["purpose"], entry["upstream_path"])
            self.assertTrue(entry["name"], entry["upstream_path"])
            self.assertTrue(entry["files"], entry["upstream_path"])
            bodies = [f for f in entry["files"] if f["path"].endswith("/SKILL.md")]
            self.assertEqual(len(bodies), 1, entry["upstream_path"])

    def test_the_committed_tree_passes_its_own_check(self):
        """--check is what CI runs; it needs no upstream clone and no manifest
        edit, so a hand-edit of a vendored file cannot land silently."""
        self.assertEqual(load("importer", IMPORTER).cmd_check(SKILL), 0)

    def test_the_index_covers_every_entry_exactly_once(self):
        stages = self.manifest["stages"]
        self.assertEqual(sorted(stages),
                         ["1-frame", "2-data", "3-train", "4-measure",
                          "5-run", "6-write"])
        listed = [p for paths in stages.values() for p in paths]
        self.assertEqual(sorted(listed), sorted(s["upstream_path"] for s in self.skills))
        self.assertEqual(len(listed), len(set(listed)), "an entry appears in two stages")
        for stage in stages:
            path = os.path.join(SKILL, "index", "%s.md" % stage)
            self.assertTrue(os.path.isfile(path), path)
            body = read(path)
            rows = [s for s in self.skills if s["upstream_path"] in stages[stage]]
            self.assertEqual(body.count("\n| `"), len(rows),
                             "%s does not list its entries" % stage)

    def test_every_vendored_file_is_attributed(self):
        """MIT attribution travels with the copy: upstream frontmatter on a body,
        one comment on a reference file, and the revision in both cases."""
        for entry in self.skills:
            for f in entry["files"]:
                body = read(os.path.join(SKILL, f["path"]))
                if f["path"].endswith("/SKILL.md"):
                    self.assertTrue(body.startswith("---\n"), f["path"])
                    frontmatter = body.split("---\n", 2)[1]
                    self.assertIn("license: MIT", frontmatter, f["path"])
                    self.assertIn("author: ", frontmatter, f["path"])
                    self.assertNotIn("vendored from orchestra-research", body,
                                     "a body must stay byte-for-byte upstream")
                else:
                    self.assertTrue(body.startswith("<!-- vendored from "
                                                    "orchestra-research/%s@%s"
                                                    % ("AI-research-SKILLs", REV)),
                                    f["path"])

    def test_the_drop_list_is_the_reviewed_one(self):
        self.assertEqual(self.manifest["drop"]["files"],
                         ["03-fine-tuning/unsloth/references/llms-full.md",
                          "03-fine-tuning/unsloth/references/llms-txt.md",
                          "08-distributed-training/deepspeed/references/tutorials.md"])
        self.assertEqual(self.manifest["drop"]["dirs"],
                         ["20-ml-paper-writing/ml-paper-writing/templates",
                          "20-ml-paper-writing/systems-paper-writing/templates"])
        for dropped in self.manifest["drop"]["files"] + self.manifest["drop"]["dirs"]:
            self.assertFalse(os.path.exists(os.path.join(SKILL, dropped)),
                             "%s was dropped and is in the tree" % dropped)

    def test_the_source_names_the_revision_licence_and_every_drop(self):
        body = read(SOURCE)
        self.assertIn(REV, body)
        self.assertIn("MIT", body)
        self.assertIn("orchestra-research/AI-research-SKILLs", body)
        for dropped in self.manifest["drop"]["files"] + self.manifest["drop"]["dirs"]:
            self.assertIn(dropped, body, "SOURCE does not name what was left out")

    def test_the_tree_stays_inside_its_size_cap(self):
        total = sum(os.path.getsize(os.path.join(root, name))
                    for root, _dirs, names in os.walk(SKILL) for name in names)
        self.assertLess(total, CAP_BYTES,
                        "the vendored tree grew past the cap the plan set (%.1f MB)"
                        % (total / 1024 / 1024))

    def test_the_flags_say_what_the_analysis_found(self):
        """The flags are what keeps a thin or stale body from being read as a
        workflow, so they are pinned to the entries the analysis named."""
        self.assertEqual({s["dir"] for s in self.skills if s["generated"]}, GENERATED)
        stale = {s["upstream_path"] for s in self.skills if s["stale_api"]}
        self.assertEqual(stale, set(self.manifest["stale_api"]))
        self.assertTrue(stale, "no stale-api entry survived the vendoring")
        shipped = {f["path"] for s in self.skills for f in s["files"]}
        for entry in self.skills:
            for link in entry["dangling_links"]:
                self.assertNotIn("%s/%s" % (entry["upstream_path"], link), shipped,
                                 "a link reported dead is actually shipped")
            for orphan in entry["orphan_refs"]:
                self.assertIn(orphan, shipped, orphan)

    def test_the_contributing_authors_keep_their_names(self):
        """MIT attribution is per file, and two entries are not Orchestra
        Research's: a re-vendor that changed this set means the upstream
        authorship moved and NOTICE has to be read again."""
        authors = []
        for entry in self.skills:
            body = read(os.path.join(SKILL, entry["upstream_path"], "SKILL.md"))
            frontmatter = body.split("---\n", 2)[1]
            authors.append([line for line in frontmatter.splitlines()
                            if line.startswith("author: ")][0])
        self.assertEqual(sorted(set(authors)),
                         ["author: A-EVO Lab", "author: Orchestra Research",
                          "author: dailycafi"])
        self.assertEqual(authors.count("author: Orchestra Research"), 96)

    def test_the_entry_point_is_tezgahs_own_and_is_not_vendored(self):
        body = read(os.path.join(SKILL, "SKILL.md"))
        self.assertNotIn("SKILL.md", {f["path"] for s in self.skills for f in s["files"]},
                         "the hand-written entry point ended up in the manifest")
        for stage in self.manifest["stages"]:
            self.assertIn("index/%s.md" % stage, body)
        self.assertIn("research-off", body)


class Importer(unittest.TestCase):
    """The importer against a synthetic upstream: the rules it enforces are
    proved here, so the real checkout is never needed to trust the tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = os.path.join(self.tmp.name, "upstream")
        self.out = os.path.join(self.tmp.name, "ai-research")
        self.mod = load("importer", IMPORTER)
        self.write_fixture()
        if shutil.which("git") is None:
            self.skipTest("git is not installed")
        # the importer refuses a dirty source, so the fixture is a committed repo
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.invalid", "-c", "user.name=t",
                 "commit", "-qm", "fixture")
        self.rev = self.git("rev-parse", "HEAD").stdout.decode().strip()

    def git(self, *args):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        return subprocess.run(("git", "-C", self.source) + args, env=env, check=True,
                              capture_output=True)

    def write(self, rel, text):
        path = os.path.join(self.source, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def skill(self, category, name, body_extra=""):
        rel = "%s/%s" % (category, name) if name else category
        self.write("%s/SKILL.md" % rel,
                   "---\nname: %s\ndescription: Does a thing. Use when testing.\n"
                   "author: Orchestra Research\nlicense: MIT\n---\n\n# %s\n%s\n"
                   % (name or category, name or category, body_extra))
        self.write("%s/references/a-guide.md" % rel, "# A guide\n")
        self.write("%s/references/notes.png" % rel, "binary")
        self.write("%s/.gitkeep" % rel, "")

    def write_fixture(self):
        """23 categories, 98 skills - the shape the importer insists on, using
        the real category names so every entry lands in a stage."""
        os.makedirs(self.source)
        self.skill("0-autoresearch-skill", "", body_extra="references/a-guide.md\n")
        cats = [c for _stage, _title, group in self.mod.STAGES for c in group
                if c != "0-autoresearch-skill"]
        self.assertEqual(len(cats), 22, "the stage map no longer covers 22 categories")
        left = 97
        for n, category in enumerate(cats):
            here = min(13 if n == 0 else 4, left)
            for i in range(here):
                self.skill(category, "skill%d" % i)
            left -= here
        assert left == 0, left

    def import_tree(self, out=None):
        return self.mod.cmd_import(self.source, self.rev, out or self.out)

    def test_the_import_is_markdown_only_and_attributed(self):
        self.import_tree()
        manifest = json.loads(read(os.path.join(self.out, "library.json")))
        self.assertEqual(manifest["counts"]["skills"], 98)
        self.assertEqual(manifest["counts"]["categories"], 23)
        for root, _dirs, names in os.walk(self.out):
            for name in names:
                self.assertFalse(name.endswith(".png") or name == ".gitkeep",
                                 "a non-markdown file was vendored: %s" % name)
        guide = read(os.path.join(self.out, "01-model-architecture/skill0/references/a-guide.md"))
        self.assertTrue(guide.startswith("<!-- vendored from"))
        body = read(os.path.join(self.out, "01-model-architecture/skill0/SKILL.md"))
        self.assertTrue(body.startswith("---\n"), "the body gained a header")
        self.assertIn("orchestra-research/AI-research-SKILLs", read(
            os.path.join(self.out, "SOURCE")))

    def test_the_import_is_deterministic(self):
        self.import_tree()
        before = {rel: digest(os.path.join(self.out, rel))
                  for root, _dirs, names in os.walk(self.out)
                  for rel in [os.path.relpath(os.path.join(root, n), self.out)
                              for n in names]}
        self.import_tree()
        after = {rel: digest(os.path.join(self.out, rel))
                 for root, _dirs, names in os.walk(self.out)
                 for rel in [os.path.relpath(os.path.join(root, n), self.out)
                             for n in names]}
        self.assertEqual(before, after)

    def test_the_index_is_generated_for_every_stage(self):
        """Including the stages this fixture has no entries for: a session that
        opens 2-data must find a file, not a 404."""
        self.import_tree()
        for stage in ("1-frame", "2-data", "3-train", "4-measure", "5-run",
                      "6-write"):
            path = os.path.join(self.out, "index", "%s.md" % stage)
            self.assertTrue(os.path.isfile(path), path)
        listed = [p for paths in json.loads(read(os.path.join(self.out, "library.json"))
                                           )["stages"].values() for p in paths]
        self.assertEqual(len(listed), 98)

    def test_check_fails_on_a_missing_changed_or_extra_file(self):
        self.import_tree()
        self.assertEqual(self.mod.cmd_check(self.out), 0)

        victim = os.path.join(self.out, "01-model-architecture/skill0/references/a-guide.md")
        body = read(victim)
        with open(victim, "a", encoding="utf-8") as fh:
            fh.write("tampered\n")
        self.assertEqual(self.mod.cmd_check(self.out), 1)

        with open(victim, "w", encoding="utf-8") as fh:
            fh.write(body)
        self.assertEqual(self.mod.cmd_check(self.out), 0)

        os.remove(victim)
        self.assertEqual(self.mod.cmd_check(self.out), 1)

        with open(victim, "w", encoding="utf-8") as fh:
            fh.write(body)
        self.write_out("01-model-architecture/skill0/stray.md", "not in the manifest\n")
        self.assertEqual(self.mod.cmd_check(self.out), 1)

    def write_out(self, rel, text):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_an_unexpected_upstream_shape_stops_the_import(self):
        self.mod.EXPECTED_SKILLS = 99
        with self.assertRaises(SystemExit) as caught:
            self.import_tree()
        self.assertIn("expected 23 / 99", str(caught.exception))

    def test_a_category_outside_the_stage_map_stops_the_import(self):
        """An entry no index file lists is an entry no session finds, so a new
        upstream category must be reviewed, not absorbed."""
        self.mod.STAGES = tuple(s for s in self.mod.STAGES
                                if "21-research-ideation" not in s[2])
        with self.assertRaises(SystemExit) as caught:
            self.import_tree()
        self.assertIn("is not in the stage map", str(caught.exception))

    def test_a_dirty_vendored_markdown_file_stops_the_import(self):
        with open(os.path.join(self.source, "01-model-architecture/skill0/references/a-guide.md"),
                  "a", encoding="utf-8") as fh:
            fh.write("uncommitted\n")
        with self.assertRaises(SystemExit) as caught:
            self.import_tree()
        self.assertIn("uncommitted markdown", str(caught.exception))


class Wiring(unittest.TestCase):
    """The library is only useful if every host's research path points at it."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, HOOKS)
        cls.setup = load("tezgah_setup", os.path.join(REPO, "bin", "tezgah-setup"))
        cls.policy = load("tezgah_policy", os.path.join(HOOKS, "tezgah_policy.py"))
        cls.context = load("tezgah_context", os.path.join(HOOKS, "tezgah_context.py"))
        cls.agents = load("tezgah_agents", os.path.join(HOOKS, "tezgah_agents.py"))

    def test_the_installer_ships_it_into_every_host(self):
        self.assertIn("ai-research", self.setup.SKILLS)
        self.assertEqual(self.setup.skill_category("ai-research"), "research & papers")
        self.assertEqual(self.setup.skill_category("research"), "tezgah core")

    def test_the_research_rule_names_the_library_and_renders_to_a_real_path(self):
        self.assertIn("{AI_RESEARCH_DIR}", self.policy.RESEARCH)
        rendered = self.context.render(self.policy.RESEARCH)
        self.assertNotIn("{AI_RESEARCH_DIR}", rendered)
        path = self.context.ai_research_dir()
        self.assertTrue(os.path.isdir(path), path)
        self.assertIn(path, rendered)
        self.assertIn("index/<stage>.md", rendered)

    def test_the_researcher_agent_carries_the_same_path(self):
        body = self.agents._researcher_body("claude")
        self.assertIn(self.context.ai_research_dir(), body)


if __name__ == "__main__":
    unittest.main()
