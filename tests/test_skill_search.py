"""The section search over installed skills: hooks/tezgah_skill_pick's index
plus bin/tezgah-skill, the CLI that exposes it.

The roster a session meets is names only, and the one search that existed (the
judgement's) ranks descriptions of the plugin's 17 skills, so the 280-skill
corpora under omp's custom directories were unreachable by topic and nobody
could name the PART of a skill that answers a question. These cases pin the
three properties that make the fix real on a fixture tree: the hit is a section
with a `skill://<name>:<start>-<end>` address whose line numbers count the file
the way omp's read tool does (frontmatter included, fenced code not headings),
a skill five roots link is one entry, and the CLI prints the address plus the
absolute path a host without skill:// opens.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_skill_pick as sp  # noqa: E402

import support  # noqa: E402

ALPHA = """---
name: alpha
description: Use when authentication tokens are in scope.
---

# Alpha

Intro paragraph, no section yet.

## JWT attacks

Test alg none: strip the signature and send the header
`{"alg":"none"}` unchanged.

```bash
# Generate alg=none token - a comment, not a heading
attack_script jwt_tamper TOKEN --set-header alg=none
```

## The ladder

Reuse a helper before writing one.
"""

BETA = """---
name: beta
description: Use when the database schema must change.
---

# Beta

## Migrations

Add the column, then backfill it.
"""


class FixtureTree(unittest.TestCase):
    """Two skills in one root, one of them symlinked into a second root."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = os.path.realpath(self.tmp.name)
        self.root = os.path.join(base, "skills-a")
        os.makedirs(os.path.join(self.root, "alpha"))
        os.makedirs(os.path.join(self.root, "beta"))
        for name, text in (("alpha", ALPHA), ("beta", BETA)):
            with open(os.path.join(self.root, name, "SKILL.md"), "w") as fh:
                fh.write(text)
        # the shape every host uses for the plugin's skills: another root whose
        # entry is a symlink to the same directory
        self.linked = os.path.join(base, "skills-b")
        os.makedirs(self.linked)
        os.symlink(os.path.join(self.root, "alpha"),
                   os.path.join(self.linked, "alpha"))
        self.roots = [self.root, self.linked]
        self.alpha = os.path.join(self.root, "alpha", "SKILL.md")

    def hits(self, query, k=5):
        return sp.search(query, k=k, roots=self.roots)


class SectionsOfOneFile(FixtureTree):

    def test_line_numbers_count_the_file_the_read_tool_does(self):
        rows = dict((title, (start, end)) for _s, _p, title, start, end
                    in sp.index(self.roots))
        # frontmatter + title + intro sit above "## JWT attacks" at line 10,
        # and the section ends where "## The ladder" starts (line 20 - 1);
        # the last section runs to the end of the file
        with open(self.alpha, encoding="utf-8") as fh:
            last = len(fh.read().splitlines())
        self.assertEqual((10, 19), rows["JWT attacks"], rows)
        self.assertEqual((20, last), rows["The ladder"], rows)

    def test_a_fenced_comment_is_not_a_heading(self):
        titles = [title for _s, _p, title, _st, _e in sp.index(self.roots)]
        self.assertNotIn("Generate alg=none token - a comment, not a heading",
                         titles)


class SearchRanksSections(FixtureTree):

    def test_a_topic_hits_the_section_that_answers_it(self):
        hits = self.hits("jwt alg none")
        self.assertTrue(hits, "the fixture's JWT section did not score")
        skill, path, title, start, end = hits[0]
        self.assertEqual(("alpha", "JWT attacks"), (skill, title), hits)
        self.assertEqual(self.alpha, path)
        self.assertEqual((10, 19), (start, end))

    def test_the_address_reads_back_as_the_section(self):
        _skill, _path, _title, start, end = self.hits("jwt alg none")[0]
        with open(self.alpha, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual("## JWT attacks", lines[start - 1])
        self.assertEqual("## The ladder", lines[end])

    def test_a_query_no_section_shares_a_term_with_gets_nothing(self):
        self.assertEqual([], self.hits("zzqx vblorb fnord"))

    def test_a_symlinked_copy_is_one_entry_not_two(self):
        names = [skill for skill, _p, _t, _s, _e in sp.index(self.roots)
                 if skill == "alpha"]
        # three sections (the file title counts as one), one copy of each -
        # the symlinked root adds no fourth
        self.assertEqual(3, len(names), names)
        self.assertEqual({os.path.realpath(self.alpha)},
                         {sp.skill_path("alpha", self.roots)})

    def test_the_first_root_wins_a_name_defined_twice(self):
        other = os.path.join(os.path.realpath(self.tmp.name), "skills-c")
        os.makedirs(os.path.join(other, "alpha"), exist_ok=True)
        with open(os.path.join(other, "alpha", "SKILL.md"), "w") as fh:
            fh.write(ALPHA.replace("JWT attacks", "JWT attacks (other copy)"))
        # roots order is the precedence order: the fixture's own, then the new one
        self.assertEqual(os.path.realpath(self.alpha),
                         sp.skill_path("alpha", self.roots + [other]))


class SkillSearchCLI(FixtureTree):

    def run_cli(self, *args):
        # HOME alone is not hermetic: CODEX_HOME/XDG point the root discovery
        # at real host directories (a relocated codex home links the live
        # checkout's skills), and the proxies would reach outside loopback
        env = dict(os.environ, HOME=os.path.realpath(self.tmp.name))
        for key in ("TEZGAH_TYPESAFE_URL", "TYPESAFE_API_KEY",
                    "OPENROUTER_API_KEY", "CODEX_HOME", "DSH_HOME",
                    "XDG_CONFIG_HOME", "http_proxy", "https_proxy",
                    "HTTP_PROXY", "HTTPS_PROXY"):
            env.pop(key, None)
        return subprocess.run(
            [sys.executable, os.path.join(REPO, "bin", "tezgah-skill")]
            + list(args),
            capture_output=True, text=True, env=env,
            cwd=os.path.realpath(self.tmp.name))

    def test_the_cli_prints_address_path_and_heading(self):
        proc = self.run_cli("--root", self.root, "jwt alg none")
        self.assertEqual(0, proc.returncode, proc.stderr)
        uri, path, title = proc.stdout.strip().splitlines()[0].split("\t")
        self.assertEqual("skill://alpha:10-19", uri)
        self.assertEqual(os.path.realpath(self.alpha), path)
        self.assertEqual("JWT attacks", title)

    def test_json_prints_the_machine_shape(self):
        proc = self.run_cli("--json", "--root", self.root, "jwt alg none")
        self.assertEqual(0, proc.returncode, proc.stderr)
        row = json.loads(proc.stdout)[0]
        self.assertEqual({"skill", "uri", "path", "title", "start", "end"},
                         set(row))
        self.assertEqual("skill://alpha:10-19", row["uri"])

    def test_no_hit_is_exit_one_not_a_crash(self):
        proc = self.run_cli("--root", self.root, "zzqx vblorb fnord")
        self.assertEqual(1, proc.returncode, proc.stderr)
        self.assertEqual("", proc.stdout.strip())


class CacheHome(FixtureTree):
    """The fixture tree as the machine's only skill roots, and a private cache
    dir, so the cached path runs without touching the real index."""

    def setUp(self):
        super().setUp()
        self.cache = os.path.join(self.tmp.name, "cache")
        patches = (mock.patch.object(sp, "skill_roots",
                                     lambda extra=(): list(self.roots)),
                   mock.patch.object(sp.tp, "cache_dir", lambda: self.cache))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)


class PostingsIndex(CacheHome):
    """The cached inverted index: same ordering as the plain ranking, rebuilt
    when a skill file's stat moves and only then, and never written for an
    explicit-roots lookup (a fixture lookup must not overwrite the machine's
    own cache with a two-skill index)."""

    QUERIES = ("jwt alg none", "database migration backfill",
               "reuse a helper before writing one", "alpha beta",
               "zzqx vblorb fnord", "authentication tokens")

    def test_the_postings_ranking_agrees_with_tezgah_rank(self):
        import tezgah_rank
        rows = sp._rows(self.roots)
        posts, lengths = sp._postings(rows)
        for query in self.QUERIES:
            self.assertEqual(
                tezgah_rank.rank(query, [sp._toktext(r) for r in rows], 5),
                sp.rank_postings(query, posts, lengths, 5), query)

    def test_the_cache_rebuilds_when_a_skill_file_changes_and_only_then(self):
        with mock.patch.object(sp, "_build", wraps=sp._build) as build:
            first = sp.top_section("database migration backfill")
            sp.top_section("database migration backfill")
            self.assertEqual(1, build.call_count, "a warm lookup rebuilt")
            self.assertEqual("Migrations", first[0][2])
            path = os.path.join(self.root, "beta", "SKILL.md")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("\n## Rollback\n\nRevert a failed schema rollout.\n")
            hit = sp.top_section("rollback schema rollout")
            self.assertEqual(2, build.call_count, "the edit was not noticed")
            self.assertEqual("Rollback", hit[0][2])
        self.assertTrue(os.path.isfile(os.path.join(self.cache,
                                                    sp.INDEX_CACHE)))

    def test_an_explicit_roots_lookup_writes_no_cache(self):
        self.assertTrue(sp.top_section("jwt alg none", roots=self.roots))
        self.assertFalse(os.path.exists(self.cache))


class LocalHint(CacheHome):
    """The default-on, model-free hint: one line naming the top section when
    it carries enough of the prompt's terms, nothing otherwise. The bar is
    coverage, not an absolute BM25 score - scores scale with corpus size, so a
    bar calibrated on the live corpus would misfire on a five-section fixture
    and vice versa; coverage transfers."""

    TOPIC = "test jwt alg none bypass"

    def test_a_topic_prompt_gets_one_section_line(self):
        line = sp.section_hint(self.TOPIC, "s1")
        self.assertTrue(line.startswith("<skill_relevance>\nA local skill "
                                        "search matched"), line)
        self.assertIn("skill://alpha:10-19 (%s)" % self.alpha, line)
        self.assertIn("not an instruction", line)
        self.assertEqual(1, line.count("<skill_relevance>"))

    def test_omp_gets_the_address_without_the_path(self):
        line = sp.section_hint(self.TOPIC, "s1", host="omp")
        self.assertIn("skill://alpha:10-19,", line)
        self.assertNotIn(self.alpha, line)

    def test_a_prompt_the_corpus_does_not_cover_is_silent(self):
        self.assertEqual("", sp.section_hint("fix the typo in the readme", "s1"))
        self.assertEqual("", sp.section_hint("zzqx vblorb", "s1"))
        # one shared word among many the section lacks is below the bar
        self.assertEqual("", sp.section_hint(
            "migrate the jwt column then backfill tokens schema", "s1"))

    def test_a_single_shared_word_is_not_a_topic(self):
        # below the two-term floor: a one-word probe is the CLI's job
        self.assertEqual("", sp.section_hint("jwt", "s1"))

    def test_judge_off_does_not_disarm_the_local_hint(self):
        # no judgement is made here, so the judgement seam's switch is not its
        # switch; `reminder-off` drops it with the rest of the per-turn text
        with mock.patch.object(sp.tp, "OFF_DIRS", (self.tmp.name,)):
            open(os.path.join(self.tmp.name, "judge-off"), "w").close()
            self.assertTrue(sp.section_hint(self.TOPIC, "s1"))

    def test_a_section_is_named_once_per_session(self):
        self.assertTrue(sp.section_hint(self.TOPIC, "s9"))
        self.assertEqual("", sp.section_hint(self.TOPIC, "s9"))
        self.assertEqual("", sp.section_hint("jwt alg none header", "s9"))
        self.assertTrue(sp.section_hint(self.TOPIC, "s10"))


class OmpPromptPath(unittest.TestCase):
    """Through omp's own dispatch (hosts/omp/hook.py), with no judge key and
    no arming file: the local hint alone reaches the user_prompt context, as
    an address omp resolves and without the absolute path."""

    # the plugin's own skills are the only root a throwaway HOME has
    PROMPT = "ponytail intensity levels lite full ultra"

    def test_the_user_prompt_context_carries_the_local_hint(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        repo = os.path.join(home, "Projects", "repo")
        os.makedirs(repo)
        out, proc = support.run_json(
            [support.OMP_HOOK],
            {"event": "user_prompt", "cwd": repo, "prompt": self.PROMPT,
             "session_id": "s-omp"},
            env=support.base_env(home))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        context = out.get("context") or ""
        self.assertRegex(context, r"<skill_relevance>\nA local skill search "
                                  r"matched this request: skill://ponytail:"
                                  r"\d+-\d+, \"Intensity\"")
        self.assertNotIn(os.path.join(REPO, "skills"), context)


if __name__ == "__main__":
    unittest.main()
