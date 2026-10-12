"""hooks/tezgah_task.py and bin/tezgah-task: the active task record.

A task is the plan file itself, so every fixture here is a real plan file under
a temp HOME's own repository, and the CLI is exercised in a subprocess the way a
person runs it. Nothing below asserts what the writer meant to write: the
assertions read the record back through the parser the gate uses, which is the
thing an agent's write is refused by.
"""
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import support
from support import TempHome, run_json

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_task as tt  # noqa: E402

CLI = os.path.join(support.REPO, "bin", "tezgah-task")
RENDER = os.path.join(support.REPO, "skills", "plan-add", "render_table.py")

# The three shapes an acceptance item can have, as the plan format now asks for
# them: a command, no command at all, and a declared unverifiable.
COMMAND_ITEM = ("- [ ] The counts it read are printed. "
                "Proof: `bin/tezgah-docs --citations`.\n")
MISSING_ITEM = ("- [ ] The reader lives in the module that already owns the plan\n"
                "      record (`hooks/tezgah_task.py`), so there is one reader.\n")
UNVERIFIABLE_ITEM = ("- [ ] The fixture cannot exist here: `unverifiable` - the\n"
                     "      corpus has no such file.\n")
BARE_MARKER_ITEM = "- [ ] `unverifiable`\n"
# The word named in prose, not declared: the shape the real corpus actually has
# (a real plan's Acceptance section), which must not hide an item.
MENTION_ITEM = ("- [ ] Read the format: it asks for either the command or the word\n"
                "      `unverifiable` followed by why.\n")


def acceptance_plan(*items):
    """One plan file whose Acceptance section holds exactly these items."""
    return ("---\nid: 001\ntitle: a plan\nstatus: open\n---\n## Goal\nthe goal\n"
            "## Acceptance\n" + "".join(items) + "## Next\nthe first action\n")


def line_of(text, needle):
    """The 1-based number of the line `needle` sits on - the expected `plan:line`
    of an item, derived from the fixture and not from the reader."""
    return next(number for number, line in enumerate(text.split("\n"), 1)
                if needle in line)

# git's own config must not reach a fixture repository
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}


def read(path):
    with open(path) as fh:
        return fh.read()


def plan_text(ident=None, phase=None, allowed=None, title="a plan", body="the goal",
              spike=None, spike_box="one focused session", spike_recorded=None,
              checkpoint=None):
    """One plan file: the keys a real one carries, plus whichever of the optional
    ones the test is about. The four spike keys go together, so one `spike=`
    writes the block and `spike_recorded=` is what the answer fills in."""
    front = ["id: %s" % ident] if ident else []
    front += ["title: %s" % title, "status: open",
              "created: 2026-01-01", "updated: 2026-01-01"]
    if phase is not None:
        front.append("phase: %s" % phase)
    if allowed is not None:
        front.append("allowed_paths:")
        front += ["  - %s" % glob for glob in allowed]
    if spike is not None:
        front += ["spike: %s" % spike, "spike_box: %s" % spike_box,
                  "spike_recorded: %s" % (spike_recorded or ""),
                  "spike_throwaway: true"]
    if checkpoint is not None:
        front.append("checkpoint: %s" % checkpoint)
    return "---\n%s\n---\n## Goal\n%s\n" % ("\n".join(front), body)


class Record(unittest.TestCase):
    """The parser and the readers, in process: base is a configured root and the
    repository is its first path component below it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = os.path.realpath(self._tmp.name)
        self.repo = os.path.join(self.base, "repo")
        self.open = os.path.join(self.repo, ".tezgah", "plans", "open")
        os.makedirs(self.open)
        # the provenance answer is cached under cache_dir(): an in-process test
        # must never write the machine's own cache
        import tezgah_paths as tp
        cache = os.path.join(self.base, "cache")
        os.makedirs(cache)
        self._cache = tp.CACHE
        tp.CACHE = cache
        self.addCleanup(setattr, tp, "CACHE", self._cache)

    def plan(self, name, text):
        path = os.path.join(self.open, name)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    # ------------------------------------------------------------ frontmatter

    def test_frontmatter_reads_key_value_lines(self):
        text = "---\nid: 001\ntitle: a: b\n\n# note\n---\nbody: not frontmatter\n"
        self.assertEqual(tt.frontmatter(text), {"id": "001", "title": "a: b"})

    def test_frontmatter_is_empty_without_both_markers(self):
        self.assertEqual(tt.frontmatter("## Goal\nid: 001\n"), {})
        self.assertEqual(tt.frontmatter("---\nid: 001\n## Goal\n"), {})

    def test_frontmatter_ignores_a_line_with_no_key(self):
        self.assertEqual(tt.frontmatter("---\nid: 001\njust words\n- item\n---\n"),
                         {"id": "001"})

    # --------------------------------------------------------- allowed_paths

    def test_allowed_paths_reads_the_list_form_only(self):
        listed = "---\nphase: implementation\nallowed_paths:\n  - hooks/**\n  - tests/**\n---\n"
        self.assertEqual(tt.allowed_paths(listed), ["hooks/**", "tests/**"])
        self.assertEqual(tt.allowed_paths(plan_text("001")), [])
        self.assertEqual(tt.allowed_paths("---\nallowed_paths: hooks/**\n---\n"), [])

    def test_allowed_paths_stops_at_the_next_key_and_the_closing_marker(self):
        text = ("---\nallowed_paths:\n  - hooks/**\nphase: implementation\n---\n"
                "- a body bullet\n")
        self.assertEqual(tt.allowed_paths(text), ["hooks/**"])

    # ---------------------------------------------------------------- active

    def test_active_picks_the_first_valid_phase_and_skips_an_invalid_one(self):
        first = self.plan("001-first.md", plan_text("001", phase="implement"))
        self.plan("002-second.md", plan_text("002", phase="verification",
                                             allowed=["tests/**"]))
        task = tt.active(self.repo, self.base)
        self.assertEqual(task["id"], "002")
        self.assertEqual(task["title"], "a plan")
        self.assertEqual(task["phase"], "verification")
        self.assertEqual(task["allowed_paths"], ["tests/**"])
        self.assertEqual(task["path"], os.path.join(self.open, "002-second.md"))
        self.assertNotIn(first, task["path"])

    def test_active_takes_the_id_from_the_filename_when_the_frontmatter_has_none(self):
        self.plan("003-third.md", plan_text(phase="discovery"))
        self.assertEqual(tt.active(self.repo, self.base)["id"], "003")

    def test_active_is_none_without_a_phase_or_without_a_plan_directory(self):
        self.plan("001-first.md", plan_text("001", allowed=["hooks/**"]))
        self.assertIsNone(tt.active(self.repo, self.base))
        self.plan("001-first.md", plan_text("001", phase=""))
        self.assertIsNone(tt.active(self.repo, self.base))
        self.assertIsNone(tt.active(os.path.join(self.base, "no-repo"), self.base))

    def test_a_plan_the_repository_tracks_rules_nothing(self):
        # Audit L-16 (review UNRESOLVED): a cloned repository that ships
        # `.tezgah/plans/open/x.md` with a phase and an allowlist used to become
        # the active task, and the gate then locked writes to its allowlist.
        self.plan("001-hostile.md", plan_text("001", phase="implementation",
                                              allowed=["nothing/**"]))
        env = dict(os.environ, **GIT_ENV)
        subprocess.run(["git", "init", "-q", self.repo], check=True, env=env)
        self.assertEqual(tt.active(self.repo, self.base)["id"], "001")  # untracked
        subprocess.run(["git", "-C", self.repo, "add", "-f", ".tezgah"], check=True,
                       env=env)
        self.assertIsNone(tt.active(self.repo, self.base))

    def git_repo(self):
        env = dict(os.environ, **GIT_ENV)
        subprocess.run(["git", "init", "-q", self.repo], check=True, env=env)
        return env

    def test_a_workspace_that_cannot_be_told_keeps_the_users_plan_in_force(self):
        # Review R2: the injection side reads every can't-tell as
        # "repository-provided", and the task rule borrowed that reading, so the
        # user's own guard went off in silence. Only a tracked `.tezgah` does it.
        self.plan("001-mine.md", plan_text("001", phase="implementation",
                                           allowed=["hooks/**"]))
        self.git_repo()
        with open(os.path.join(self.repo, ".git", "index"), "wb") as fh:
            fh.write(b"not an index")  # unreadable: can't tell
        self.assertEqual(tt.active(self.repo, self.base)["id"], "001")

    def test_a_symlinked_workspace_of_the_users_own_keeps_the_plan_in_force(self):
        real = os.path.join(self.base, "elsewhere")
        os.rename(os.path.join(self.repo, ".tezgah"), real)
        os.symlink(real, os.path.join(self.repo, ".tezgah"))
        self.open = os.path.join(real, "plans", "open")
        self.plan("001-mine.md", plan_text("001", phase="implementation"))
        self.git_repo()
        self.assertEqual(tt.active(self.repo, self.base)["id"], "001")

    def test_an_unchanged_index_is_not_parsed_again(self):
        import tezgah_paths as tp
        self.plan("001-mine.md", plan_text("001", phase="implementation"))
        env = self.git_repo()
        self.touch_tracked(env, "f")
        calls = []
        real = tp._index_tracks_workspace
        tp._index_tracks_workspace = lambda root: calls.append(root) or real(root)
        self.addCleanup(setattr, tp, "_index_tracks_workspace", real)
        for _ in range(3):
            self.assertEqual(tt.active(self.repo, self.base)["id"], "001")
        self.assertEqual(len(calls), 1)
        # a changed index is read again, and the new answer wins
        subprocess.run(["git", "-C", self.repo, "add", "-f", ".tezgah"], check=True,
                       env=env)
        self.assertIsNone(tt.active(self.repo, self.base))
        self.assertEqual(len(calls), 2)

    def touch_tracked(self, env, name):
        open(os.path.join(self.repo, name), "w").close()
        subprocess.run(["git", "-C", self.repo, "add", name], check=True, env=env)

    # ----------------------------------------------------------------- match

    def test_match_crosses_separators_for_double_star_only(self):
        self.assertTrue(tt.match("hooks/a.py", "hooks/*"))
        self.assertTrue(tt.match("hooks/deep/a.py", "hooks/**"))
        self.assertFalse(tt.match("hooks/deep/a.py", "hooks/*"))
        self.assertFalse(tt.match("hooks/a.py", "tests/**"))
        self.assertTrue(tt.match("src/deep/a.py", "**/deep/**"))
        self.assertTrue(tt.match("deep/a.py", "**/deep/**"))
        self.assertTrue(tt.match("any/where.py", "**"))

    def test_match_treats_every_other_character_literally(self):
        self.assertTrue(tt.match("a+b.py", "a+b.py"))
        self.assertFalse(tt.match("aXb.py", "a.b.py"))
        self.assertFalse(tt.match("a/b.py", "a?b.py"))

    # -------------------------------------------------------------- relative

    def test_relative_answers_inside_the_root_and_none_outside_it(self):
        self.assertEqual(tt.relative("hooks/a.py", self.repo, self.base), "hooks/a.py")
        self.assertEqual(tt.relative(os.path.join(self.repo, "hooks", "a.py"),
                                     self.repo, self.base), "hooks/a.py")
        self.assertEqual(tt.relative(os.path.join(self.repo, "hooks", "..", "b.py"),
                                     self.repo, self.base), "b.py")
        self.assertIsNone(tt.relative(os.path.join(self.base, "elsewhere.py"),
                                      self.repo, self.base))
        self.assertIsNone(tt.relative("../elsewhere.py", self.repo, self.base))
        self.assertIsNone(tt.relative(self.repo, self.repo, self.base))

    def test_relative_expands_a_home_tilde(self):
        # a host may spell the path `~/...`; read as relative to cwd it named a
        # file that does not exist and refused an in-scope write
        home = os.path.dirname(self.repo)
        tilde = "~/" + os.path.basename(self.repo) + "/hooks/a.py"
        with unittest.mock.patch.dict(os.environ, {"HOME": home}):
            self.assertEqual(tt.relative(tilde, self.repo, self.base), "hooks/a.py")

    def test_relative_resolves_a_symlink_out_of_the_root(self):
        outside = os.path.join(self.base, "outside.py")
        open(outside, "w").close()
        link = os.path.join(self.repo, "link.py")
        os.symlink(outside, link)
        self.assertIsNone(tt.relative(link, self.repo, self.base))

    def linked_worktree(self, main, name, branch=None):
        """A linked worktree of `main` the way git writes one: `<wt>/.git` is a
        `gitdir:` pointer into `<main>/.git/worktrees/<name>`, which holds
        `commondir` and, given a `branch`, the `HEAD` that checks it out."""
        admin = os.path.join(main, ".git", "worktrees", name)
        os.makedirs(admin)
        top = os.path.join(self.base, name)
        os.makedirs(os.path.join(top, "hooks"))
        files = [(os.path.join(admin, "commondir"), "../..\n"),
                 (os.path.join(top, ".git"), "gitdir: %s\n" % admin),
                 (os.path.join(admin, "gitdir"), os.path.join(top, ".git") + "\n")]
        if branch:
            files.append((os.path.join(admin, "HEAD"), "ref: refs/heads/%s\n" % branch))
        for path, text in files:
            with open(path, "w") as fh:
                fh.write(text)
        return top

    def test_a_plan_worktree_is_held_to_its_own_plan_by_branch(self):
        # two plans run at once, each in a worktree on its plan/NNN branch: each
        # worktree has its own, the main checkout none (the CLI's `held` reading
        # still names the first, the plan its `phase` moves)
        os.makedirs(os.path.join(self.repo, ".git"))
        self.plan("001-first.md", plan_text("001", phase="implementation",
                                            allowed=["hooks/**"]))
        self.plan("002-second.md", plan_text("002", phase="implementation",
                                             allowed=["docs/**"]))
        one = self.linked_worktree(self.repo, "repo-001", branch="plan/001-first")
        two = self.linked_worktree(self.repo, "repo-002", branch="plan/002-second")
        self.assertIsNone(tt.active(self.repo, self.base))
        task = tt.active(self.repo, self.base, held=True)
        self.assertEqual((task["id"], task["held"]), ("001", True))
        self.assertNotIn("held", tt.active(one, self.base, held=True))
        self.assertEqual(tt.active(one, self.base)["id"], "001")
        task = tt.active(two, self.base)
        self.assertEqual((task["id"], task["allowed_paths"]), ("002", ["docs/**"]))
        self.assertEqual(task["path"], os.path.join(self.open, "002-second.md"))
        # a write from the main checkout into a plan worktree answers that plan
        self.assertEqual(tt.worktree_task(os.path.join(two, "docs", "a.md"),
                                          self.repo, self.base)["id"], "002")
        self.assertIsNone(tt.worktree_task(os.path.join(self.repo, "docs", "a.md"),
                                           self.repo, self.base))

    def test_an_unknown_branch_mapping_reads_the_main_checkouts_task(self):
        # fail safe: another branch, a plan with no phase, or a detached HEAD
        # maps to no plan, and the worktree reads the main checkout's task -
        # never no task at all, which would let its writes through unheld
        os.makedirs(os.path.join(self.repo, ".git"))
        self.plan("001-first.md", plan_text("001", phase="implementation",
                                            allowed=["hooks/**"]))
        self.plan("003-third.md", plan_text("003"))
        for name, branch in (("repo-f", "feature"), ("repo-3", "plan/003-third"),
                             ("repo-9", "plan/009-missing"), ("repo-d", None)):
            wt = self.linked_worktree(self.repo, name, branch=branch)
            self.assertEqual(tt.active(wt, self.base)["id"], "001", name)
            self.assertIsNone(tt.worktree_task(os.path.join(wt, "hooks", "a.py"),
                                               self.repo, self.base), name)

    def test_the_main_checkout_reads_the_phased_plan_no_worktree_holds(self):
        os.makedirs(os.path.join(self.repo, ".git"))
        self.plan("001-first.md", plan_text("001", phase="implementation",
                                            allowed=["hooks/**"]))
        self.plan("002-second.md", plan_text("002", phase="discovery",
                                             allowed=["docs/**"]))
        self.assertEqual(tt.active(self.repo, self.base)["id"], "001")
        self.linked_worktree(self.repo, "repo-001", branch="plan/001-first")
        self.assertEqual(tt.active(self.repo, self.base)["id"], "002")
        # every phased plan held: a held plan's scope is its worktree's, so the
        # main checkout and a worktree bound to no plan have no active task
        self.linked_worktree(self.repo, "repo-002", branch="plan/002-second")
        self.assertIsNone(tt.active(self.repo, self.base))
        free = self.linked_worktree(self.repo, "repo-f", branch="feature")
        self.assertIsNone(tt.active(free, self.base))
        self.assertEqual(tt.active(os.path.join(self.base, "repo-001"),
                                   self.base)["id"], "001")

    def test_a_plans_slice_worktrees_bind_to_it_beside_its_declared_branch(self):
        # plan 097 ran slices on plan/097-records beside its declared
        # plan/097-workspace-integrity: each slice is held to 097's scope, and
        # the declared branch's worktree stays the plan's holder
        os.makedirs(os.path.join(self.repo, ".git"))
        self.plan("001-first.md", plan_text("001", phase="implementation",
                                            allowed=["hooks/**"]))
        self.plan("002-second.md", plan_text("002", phase="implementation",
                                             allowed=["docs/**"]).replace(
            "status: open", "status: open\nbranch: plan/002-main"))
        self.linked_worktree(self.repo, "repo-001", branch="plan/001-x")
        piece = self.linked_worktree(self.repo, "repo-002s", branch="plan/002-slice")
        task = tt.active(piece, self.base)
        self.assertEqual((task["id"], task["allowed_paths"]), ("002", ["docs/**"]))
        self.assertEqual(tt.plan_holders(self.repo)["002"], piece)
        main = self.linked_worktree(self.repo, "repo-002", branch="plan/002-main")
        self.assertEqual(tt.plan_holders(self.repo)["002"], main)
        self.assertEqual(tt.active(piece, self.base)["id"], "002")

    def test_concurrent_record_writers_lose_no_write_and_tear_no_read(self):
        # E7: a reader saw a torn record in 29/40 rounds and two writers lost a
        # write in 1/40, because each writer truncated the file in place. Review
        # of plan 097, F5: a tick resolved its line before the lock, so a
        # frontmatter line inserted meanwhile moved the box it ticked
        import threading
        n = 40
        items = "".join("- [ ] item %d\n" % i for i in range(n))
        path = self.plan("001-first.md", plan_text("001", phase="implementation")
                         + "## Acceptance\n" + items + "## State\nnone\n")
        torn = []
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                text = read(path)
                if not text.startswith("---\n") or "## State" not in text:
                    torn.append(text[:40])

        def ticker():
            for i in range(n):
                tt.set_box(path, i + 1, True)

        def noter():
            for i in range(n):
                tt.set_section(path, "State", "note %d" % i)

        def stamper():
            # each round grows `allowed_paths` by one line, shifting the body
            for i in range(n):
                tt.set_fields(path, updated="2026-10-%02d" % (i % 28 + 1),
                              allowed_paths=["p%d/**" % j for j in range(i + 1)])

        watch = threading.Thread(target=reader)
        watch.start()
        writers = [threading.Thread(target=f) for f in (ticker, noter, stamper)]
        for t in writers:
            t.start()
        for t in writers:
            t.join()
        stop.set()
        watch.join()
        text = read(path)
        self.assertEqual(torn, [])
        self.assertEqual([i for i in range(n) if "- [x] item %d\n" % i not in text], [])
        self.assertEqual(text.count("- [x]"), n)
        self.assertIn("## State\nnote %d\n" % (n - 1), text)
        self.assertEqual(tt.frontmatter(text)["updated"], "2026-10-%02d" % ((n - 1) % 28 + 1))
        self.assertEqual(len(tt.allowed_paths(text)), n)
        # no temp file beside the record, and no lock file a private
        # repository's `add -A` could pick up (review of plan 097, F6)
        self.assertEqual(sorted(os.listdir(self.open)), ["001-first.md"])
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.open))), ["open"])
        self.assertIsNone(tt.set_box(path, n + 1, True))

    def test_relative_reads_a_linked_worktree_of_the_same_repository(self):
        # the contract gives every writing slice its own worktree; an allowlist
        # that cannot name a file there refuses the workflow it prescribes
        os.makedirs(os.path.join(self.repo, ".git"))
        wt = self.linked_worktree(self.repo, "repo-slice")
        target = os.path.join(wt, "hooks", "a.py")
        self.assertEqual(tt.relative(target, self.repo, self.base, worktrees=True),
                         "hooks/a.py")
        self.assertIsNone(tt.relative(wt, self.repo, self.base, worktrees=True))
        # without the flag (the record and workspace rules) a sibling is outside
        self.assertIsNone(tt.relative(target, self.repo, self.base))

    def test_relative_reads_one_sibling_worktree_from_another(self):
        os.makedirs(os.path.join(self.repo, ".git"))
        a = self.linked_worktree(self.repo, "repo-a")
        b = self.linked_worktree(self.repo, "repo-b")
        self.assertEqual(tt.relative(os.path.join(b, "hooks", "a.py"), a, self.base,
                                     worktrees=True), "hooks/a.py")
        # the main checkout's .git is a directory, so it is no linked worktree
        self.assertIsNone(tt.relative(os.path.join(self.repo, "hooks", "a.py"), a,
                                      self.base, worktrees=True))

    def test_relative_refuses_a_worktree_of_another_repository(self):
        os.makedirs(os.path.join(self.repo, ".git"))
        other = os.path.join(self.base, "other")
        os.makedirs(os.path.join(other, ".git"))
        wt = self.linked_worktree(other, "other-slice")
        self.assertIsNone(tt.relative(os.path.join(wt, "hooks", "a.py"),
                                      self.repo, self.base, worktrees=True))

    def test_relative_refuses_a_worktree_whose_admin_does_not_point_back(self):
        # a `.git` file planted anywhere can name a real admin directory; git
        # always writes `<admin>/gitdir` back to the worktree, so that is checked
        os.makedirs(os.path.join(self.repo, ".git"))
        wt = self.linked_worktree(self.repo, "repo-slice")
        planted = os.path.join(self.base, "planted")
        os.makedirs(os.path.join(planted, "hooks"))
        with open(os.path.join(planted, ".git"), "w") as fh:
            fh.write(read(os.path.join(wt, ".git")))
        self.assertIsNone(tt.relative(os.path.join(planted, "hooks", "a.py"),
                                      self.repo, self.base, worktrees=True))

    # ------------------------------------------------------------ set_fields

    def test_set_fields_inserts_a_key_and_replaces_the_ones_it_is_given(self):
        path = self.plan("001-first.md", plan_text("001"))
        tt.set_fields(path, phase="implementation", updated="2026-09-18")
        self.assertEqual(tt.frontmatter(read(path)),
                         {"id": "001", "title": "a plan", "status": "open",
                          "created": "2026-01-01", "updated": "2026-09-18",
                          "phase": "implementation"})
        self.assertIn("## Goal\nthe goal\n", read(path))

        tt.set_fields(path, allowed_paths=["hooks/**", "tests/**"], updated="2026-09-18")
        self.assertEqual(tt.allowed_paths(read(path)), ["hooks/**", "tests/**"])
        tt.set_fields(path, allowed_paths=["README.md"], updated="2026-09-19")
        self.assertEqual(tt.allowed_paths(read(path)), ["README.md"])
        self.assertEqual(read(path).count("allowed_paths:"), 1)
        self.assertEqual(read(path).count("updated:"), 1)

    def test_set_fields_clears_a_phase_and_opens_missing_frontmatter(self):
        path = self.plan("001-first.md", plan_text("001", phase="implementation"))
        tt.set_fields(path, phase="", updated="2026-09-18")
        self.assertIsNone(tt.active(self.repo, self.base))

        bare = self.plan("002-second.md", "## Goal\nno frontmatter here\n")
        tt.set_fields(bare, phase="discovery", updated="2026-09-18")
        self.assertEqual(tt.frontmatter(read(bare))["phase"], "discovery")
        self.assertIn("## Goal\nno frontmatter here\n", read(bare))
        self.assertEqual(tt.active(self.repo, self.base)["id"], "002")

    # ------------------------------------------------------- the spike reader

    def test_spike_unanswered_needs_both_keys(self):
        # the question with no recorded answer is the unanswered state; a plan
        # without the question runs no spike, and an answer with no question is
        # not a spike either - neither invents a requirement
        answered = ("---\nspike: does it scale\nspike_recorded: .tezgah/x.md\n---\n")
        asked = "---\nspike: does it scale\nspike_recorded:\n---\n"
        self.assertTrue(tt.spike_unanswered(asked))
        self.assertFalse(tt.spike_unanswered(answered))
        self.assertFalse(tt.spike_unanswered("---\nid: 001\n---\n"))
        self.assertFalse(tt.spike_unanswered("---\nspike_recorded: x.md\n---\n"))

    # ------------------------------------------- the checkpoint the CLI records

    def test_checkpoint_reads_the_record_and_names_the_same_commit(self):
        self.assertEqual(tt.checkpoint("---\ncheckpoint: pending\n---\n"), "pending")
        self.assertIsNone(tt.checkpoint("---\nid: 001\n---\n"))
        self.assertEqual(tt.slug("/x/.tezgah/plans/open/007-a-b.md"), "007-a-b")
        self.assertEqual(tt.checkpoint_command("/x/007-a-b.md"),
                         'git add -A && git commit -m "checkpoint: before 007-a-b"')
        self.assertEqual(tt.checkpoint_command("/x/007-a-b.md", "/w t"),
                         "git -C '/w t' add -A && git -C '/w t' commit -m "
                         '"checkpoint: before 007-a-b"')

    def test_checkpoint_sha_is_the_head_only_a_pending_record_names(self):
        # The one reader of the `pending <sha>` form, shared by the CLI's note and
        # the gate's refusal. Every other shape names no tree to compare, so the
        # gate fails open there instead of locking the phase it guards.
        self.assertEqual(tt.checkpoint_sha("pending abc123"), "abc123")
        for value in ("pending", "", None, "abc123", "pending a b",
                      "pending ", "done abc123"):
            self.assertEqual(tt.checkpoint_sha(value), "", repr(value))

    # ------------------------- progress, ordering and what can run at once

    def test_acceptance_items_carry_whether_their_box_is_checked(self):
        text = acceptance_plan(COMMAND_ITEM, "- [x] shipped: `ruff check .`\n",
                               "- [X] also shipped\n")
        self.assertEqual([i["checked"] for i in tt.acceptance_items(text)],
                         [False, True, True])

    def test_after_reads_the_list_form_and_the_inline_form(self):
        self.assertEqual(tt.after("---\nafter:\n  - 012\n  - 015\n---\n"), ["012", "015"])
        self.assertEqual(tt.after("---\nafter: 012, 015\n---\n"), ["012", "015"])
        self.assertEqual(tt.after("---\nafter:\n---\n"), [])
        self.assertEqual(tt.after(plan_text("001")), [])

    def done_plan(self, name, status="done"):
        directory = os.path.join(self.repo, ".tezgah", "plans", "done")
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, name), "w") as fh:
            fh.write("---\nid: %s\nstatus: %s\n---\n" % (name[:3], status))

    def test_queue_names_what_each_open_plan_waits_on(self):
        self.done_plan("001-built.md")
        self.done_plan("002-dropped.md", status="discarded")
        self.plan("003-a.md", plan_text("003", allowed=["hooks/**"])
                  + "## Acceptance\n" + COMMAND_ITEM + "- [x] done: `ruff check .`\n")
        self.plan("004-b.md", plan_text("004", allowed=["docs/**"]).replace(
            "---\n## Goal", "after: 001, 003\n---\n## Goal"))
        self.plan("005-c.md", plan_text("005", allowed=["tests/**"]).replace(
            "---\n## Goal", "after: 002 009\n---\n## Goal"))
        rows = {row["id"]: row for row in tt.queue(self.repo)}
        self.assertEqual((rows["003"]["checked"], rows["003"]["items"]), (1, 2))
        self.assertEqual(rows["003"]["after"], [])
        self.assertTrue(rows["003"]["ready"])
        self.assertEqual(rows["004"]["after"], [["001", "done"], ["003", "open"]])
        self.assertFalse(rows["004"]["ready"])
        # a discarded plan never lands, and an id no plan carries is a typo
        self.assertEqual(rows["005"]["after"], [["002", "discarded"], ["009", "missing"]])
        self.assertFalse(rows["005"]["ready"])

    def test_a_blocked_plan_is_not_ready_whatever_it_waits_on(self):
        self.plan("001-a.md", plan_text("001").replace("status: open", "status: blocked"))
        self.assertFalse(tt.queue(self.repo)[0]["ready"])

    def test_parallel_picks_ready_plans_whose_scopes_share_no_path(self):
        self.plan("001-a.md", plan_text("001", allowed=["hooks/**"]))
        self.plan("002-b.md", plan_text("002", allowed=["hooks/tezgah_task.py"]))
        self.plan("003-c.md", plan_text("003", allowed=["docs/**", "skills/plan-add/**"]))
        self.plan("004-d.md", plan_text("004"))  # no scope is every path
        rows = tt.queue(self.repo)
        self.assertEqual({r["id"]: r["overlaps"] for r in rows},
                         {"001": ["002", "004"], "002": ["001", "004"],
                          "003": ["004"], "004": ["001", "002", "003"]})
        self.assertEqual(tt.parallel(rows), ["001", "003"])

    def test_scopes_overlap_reads_the_literal_prefix_of_each_glob(self):
        self.assertTrue(tt.scopes_overlap(["hooks/**"], ["hooks/x.py"]))
        self.assertTrue(tt.scopes_overlap(["**/tests/**"], ["docs/x.md"]))
        self.assertTrue(tt.scopes_overlap([], ["docs/x.md"]))
        self.assertFalse(tt.scopes_overlap(["hooks/a*.py"], ["hooks/b*.py"]))
        self.assertFalse(tt.scopes_overlap(["hooks/**", "bin/x"], ["docs/**"]))


class Cli(TempHome):
    """The CLI end to end: one command per record, read back through the same
    parser the gate uses."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.init_repo()
        self.open = os.path.join(self.repo, ".tezgah", "plans", "open")
        os.makedirs(self.open)

    def init_repo(self):
        """A real repository with one commit and the project's own gitignore: the
        CLI asks git for the top-level, so the answer must not depend on what
        happens to sit above the temp directory - and it reads the tree's
        cleanliness for the checkpoint, so the fixture must be able to be clean,
        which `.tezgah/` being ignored (as plan-add writes it) is what makes it."""
        env = dict(os.environ, **GIT_ENV)
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       capture_output=True, env=env)
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("/.tezgah/\n")
        self.commit(".gitignore", message="init")

    def commit(self, *paths, message="a commit"):
        """Commit these repo paths, so the working tree can be clean or dirty at
        a known moment - what the checkpoint records and refuses on."""
        env = dict(os.environ, **GIT_ENV)
        subprocess.run(["git", "-C", self.repo, "add", "--"] + list(paths),
                       check=True, capture_output=True, env=env)
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=t",
                        "-c", "user.email=t@localhost", "commit", "-q",
                        "-m", message], check=True, capture_output=True, env=env)

    def head(self):
        out = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True,
                             env=dict(os.environ, **GIT_ENV))
        return out.stdout.strip()

    def dirty(self, rel):
        """One uncommitted file inside the repo: the state the checkpoint is
        about. Returns its path."""
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("x = 1\n")
        return path

    def plan(self, name, **kwargs):
        path = os.path.join(self.open, name)
        with open(path, "w") as fh:
            fh.write(plan_text(kwargs.pop("ident", name.split("-")[0]), **kwargs))
        return path

    def task(self, *args):
        return support.run([CLI] + list(args), env=self.env(), cwd=self.repo)

    def status(self):
        """The active task as every reader outside this CLI sees it."""
        return tt.active(self.repo, self.roots)

    def snapshot(self):
        return {name: read(os.path.join(self.open, name))
                for name in sorted(os.listdir(self.open))}

    # ---------------------------------------------------------------- start

    def test_start_activates_the_plan_and_clears_the_other_plans_phase(self):
        first = self.plan("001-first.md", phase="discovery")
        second = self.plan("002-second.md")
        proc = self.task("start", "002", "--phase", "implementation",
                         "--allow", "hooks/**", "--allow", "tests/**")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("task 002: phase implementation", proc.stdout)
        task = self.status()
        self.assertEqual(task["id"], "002")
        self.assertEqual(task["phase"], "implementation")
        self.assertEqual(task["allowed_paths"], ["hooks/**", "tests/**"])
        self.assertEqual(tt.frontmatter(read(first)).get("phase"), "")
        self.assertEqual(tt.frontmatter(read(second))["phase"], "implementation")

    def test_start_keeps_an_allowlist_it_was_not_given_a_new_one_for(self):
        self.plan("001-first.md")
        self.task("start", "001", "--phase", "implementation", "--allow", "tests/**")
        proc = self.task("start", "001", "--phase", "verification")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["allowed_paths"], ["tests/**"])

    def test_start_takes_a_path_as_well_as_an_id(self):
        self.plan("001-first.md")
        proc = self.task("start", os.path.join(".tezgah", "plans", "open", "001-first.md"),
                         "--phase", "discovery")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["id"], "001")

    def test_start_with_an_unknown_id_writes_nothing(self):
        self.plan("001-first.md", phase="discovery")
        before = self.snapshot()
        proc = self.task("start", "009", "--phase", "implementation")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL no plan 009", proc.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_an_unknown_phase_is_refused_and_writes_nothing(self):
        self.plan("001-first.md")
        before = self.snapshot()
        proc = self.task("start", "001", "--phase", "shipping")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL phase 'shipping' is not one of", proc.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_misuse_exits_2(self):
        proc = self.task()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("tezgah-task - the active task", proc.stderr)
        self.assertEqual(self.task("start", "001").returncode, 2)
        self.assertEqual(self.task("nonsense").returncode, 2)

    # ------------------------------------------------------- phase and allow

    def test_phase_moves_the_active_task_on(self):
        self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        proc = self.task("phase", "verification")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["phase"], "verification")
        refused = self.task("phase", "shipping")
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertEqual(self.status()["phase"], "verification")

    def test_phase_and_allow_refuse_when_no_task_is_active(self):
        self.plan("001-first.md")
        for proc in (self.task("phase", "implementation"),
                     self.task("allow", "hooks/**", "--why", "x")):
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("FAIL no active task", proc.stdout)
        self.assertEqual(self.task("stop").returncode, 1)

    def test_allow_replaces_the_allowlist_and_records_why(self):
        self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        # the session widens its own scope, so a widening with no reason is misuse
        self.assertEqual(self.task("allow", "tests/**").returncode, 2)
        self.assertEqual(self.status()["allowed_paths"], ["hooks/**"])
        proc = self.task("allow", "tests/**", "README.md", "--why", "the fix needs a test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["allowed_paths"], ["tests/**", "README.md"])
        self.assertIn("(why: the fix needs a test)", self.task("status").stdout)
        # an empty call is not a lift: the scope goes only when it is said
        self.assertEqual(self.task("allow", "--why", "x").returncode, 2)
        self.assertEqual(self.status()["allowed_paths"], ["tests/**", "README.md"])
        self.assertEqual(self.task("allow", "--any-path", "--why", "repo-wide rename").returncode, 0)
        self.assertEqual(self.status()["allowed_paths"], [])
        self.assertIn("any path in the repo (--any-path) (why: repo-wide rename)",
                      self.task("status").stdout)

    # ------------------------------------------------ the plan's own scope

    def test_a_writing_phase_with_no_allowlist_is_refused_unless_any_path(self):
        self.plan("001-first.md")
        before = self.snapshot()
        for phase in ("implementation", "verification"):
            proc = self.task("start", "001", "--phase", phase)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("--any-path", proc.stdout)
            self.assertEqual(self.snapshot(), before)
        # discovery writes nothing, so it needs no scope
        self.assertEqual(self.task("start", "001", "--phase", "discovery").returncode, 0)
        refused = self.task("phase", "implementation")
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertEqual(self.status()["phase"], "discovery")
        proc = self.task("phase", "implementation", "--any-path")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["phase"], "implementation")
        # the explicit grant is on the record, so the next phase keeps it
        self.assertEqual(self.task("phase", "verification").returncode, 0)
        self.assertEqual(self.task("start", "001", "--phase", "implementation",
                                   "--any-path", "--allow", "x").returncode, 2)

    def test_start_without_allow_takes_the_plans_own_allowlist(self):
        self.plan("001-first.md", allowed=["apps/admin/**", "packages/ui/**"])
        proc = self.task("start", "001", "--phase", "implementation")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["allowed_paths"], ["apps/admin/**", "packages/ui/**"])
        self.assertIn("(from the plan)", proc.stdout)
        self.task("allow", "apps/**", "--why", "the admin app imports it")
        payload, _ = run_json([CLI, "status", "--json"], env=self.env(), cwd=self.repo)
        self.assertEqual(payload["active"]["allowed_from"],
                         "from tezgah-task allow (why: the admin app imports it)")
        # a scope set again at start drops the reason that belonged to the old one
        self.task("start", "001", "--phase", "implementation", "--allow", "apps/**")
        payload, _ = run_json([CLI, "status", "--json"], env=self.env(), cwd=self.repo)
        self.assertEqual(payload["active"]["allowed_from"], "from tezgah-task --allow")

    # ------------------------------------ what a writing phase cannot start on

    def test_a_writing_phase_is_refused_when_no_acceptance_item_names_a_command(
            self):
        # What `render_table --acceptance --strict` reports is refused here, before the
        # work rather than after the push: a plan whose every item names no
        # command has nothing the work can be held to. The refusal names the
        # file and the reader, so the plan and the report cannot disagree.
        path = self.plan("001-first.md", allowed=["hooks/**"])
        with open(path, "a") as fh:
            fh.write("## Acceptance\n" + MISSING_ITEM)
        before = self.snapshot()
        refused = self.task("start", "001", "--phase", "implementation")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("hooks/tezgah_task.py:acceptance_items", refused.stdout)
        self.assertIn(path, refused.stdout)
        self.assertEqual(self.snapshot(), before)
        # discovery only reads, so nothing is owed yet; both writing phases are
        self.assertEqual(self.task("start", "001", "--phase", "discovery").returncode, 0)
        for phase in ("implementation", "verification"):
            refused = self.task("phase", phase)
            self.assertEqual(refused.returncode, 1, refused.stdout)
            self.assertIn("acceptance_items", refused.stdout)
        self.assertEqual(self.status()["phase"], "discovery")
        # a command-bearing item beside it does not carry the one that names none
        with open(path, "a") as fh:
            fh.write(COMMAND_ITEM)
        mixed = self.task("phase", "implementation")
        self.assertEqual(mixed.returncode, 1, mixed.stdout)
        self.assertIn("1 of its 2 Acceptance items", mixed.stdout)
        self.assertIn("%s:%d" % (path, line_of(read(path), "The reader lives")), mixed.stdout)
        # every item naming its proof is what moves the phase
        with open(path, "w") as fh:
            fh.write(plan_text("001", allowed=["hooks/**"], phase="discovery")
                     + "## Acceptance\n" + COMMAND_ITEM)
        self.assertEqual(self.task("phase", "implementation").returncode, 0)

    def test_the_phase_move_and_the_strict_report_refuse_the_same_plans(self):
        # two readings of one rule: the refusal a person meets at the phase move
        # and the report `--strict` runs before a commit must agree on every
        # shape of Acceptance section, or one lets through what the other refuses
        shapes = {"mixed": (COMMAND_ITEM, MISSING_ITEM),
                  "missing": (MISSING_ITEM,),
                  "proven": (COMMAND_ITEM, UNVERIFIABLE_ITEM),
                  "empty": ()}
        for name, items in shapes.items():
            for old in os.listdir(self.open):
                os.remove(os.path.join(self.open, old))
            with open(os.path.join(self.open, "001-first.md"), "w") as fh:
                fh.write(plan_text("001", allowed=["hooks/**"])
                         + "## Acceptance\n" + "".join(items))
            moved = self.task("start", "001", "--phase", "implementation")
            strict = support.run([RENDER, "--acceptance", "--strict"],
                                 env=self.env(extra={"PYTHONPATH": ""}), cwd=self.repo)
            self.assertEqual(moved.returncode != 0, strict.returncode != 0,
                             "%s: phase move %d, strict %d\n%s%s" % (
                                 name, moved.returncode, strict.returncode,
                                 moved.stdout, strict.stdout))
            self.assertEqual(moved.returncode != 0, name in ("mixed", "missing"), name)

    def test_a_declared_unverifiable_item_and_an_absent_section_are_not_refused(
            self):
        # the word with a why is a decision the plan made, not a gap; and a plan
        # carrying no Acceptance items at all is the different defect the report
        # does not gate either, so neither reader invents one
        first = self.plan("001-first.md", allowed=["hooks/**"])
        with open(first, "a") as fh:
            fh.write("## Acceptance\n" + UNVERIFIABLE_ITEM)
        self.assertEqual(self.task("start", "001", "--phase", "implementation").returncode, 0)
        self.assertEqual(self.task("stop").returncode, 0)
        self.plan("002-second.md", allowed=["hooks/**"])
        self.assertEqual(self.task("start", "002", "--phase", "implementation").returncode, 0)

    def test_implementation_is_refused_while_the_spike_is_unanswered(self):
        # a spike is a question the plan answers before the build, and the record
        # says which: `spike_recorded:` empty is the unanswered state
        path = self.plan("001-first.md", allowed=["hooks/**"], spike="does it scale")
        before = self.snapshot()
        refused = self.task("start", "001", "--phase", "implementation")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("spike", refused.stdout)
        self.assertIn(path, refused.stdout)
        self.assertEqual(self.snapshot(), before)
        # the reading phase is where the spike is run, so it is not refused
        self.assertEqual(self.task("start", "001", "--phase", "discovery").returncode, 0)
        self.assertEqual(self.task("phase", "implementation").returncode, 1)
        self.assertEqual(self.status()["phase"], "discovery")
        tt.set_fields(path, spike_recorded=".tezgah/research/spike.md")
        self.assertEqual(self.task("phase", "implementation").returncode, 0)

    def test_spike_records_the_answer_through_the_cli(self):
        # the record's only writer answers the spike too: on the active plan and
        # on one that is not active, and the implementation phase then opens
        path = self.plan("001-first.md", allowed=["hooks/**"], spike="does it scale")
        other = self.plan("002-second.md", allowed=["docs/**"], spike="which store")
        self.assertEqual(self.task("start", "001", "--phase", "discovery").returncode, 0)
        proc = self.task("spike", "001", "it scales: .tezgah/research/spike.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(tt.frontmatter(read(path))["spike_recorded"],
                         "it scales: .tezgah/research/spike.md")
        self.assertEqual(self.task("phase", "implementation").returncode, 0)
        self.assertEqual(self.task("spike", "002", "sqlite").returncode, 0)
        fields = tt.frontmatter(read(other))
        self.assertEqual((fields["spike_recorded"], fields.get("phase")), ("sqlite", None))
        self.assertEqual(self.task("spike", "002", " ").returncode, 2)
        self.assertEqual(self.task("spike", "README.md", "x").returncode, 1)

    def test_start_keeps_a_parallel_plans_phase_held_by_its_own_worktree(self):
        # both plans held by their own worktrees, on scopes that share no
        # prefix: they run beside each other; an overlapping one does not
        first = self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        second = self.plan("002-second.md", allowed=["docs/**"])
        third = self.plan("003-third.md", allowed=["docs/x/**"])
        wt = self.slice("plan/001-first", commit=False, merge=False)
        wt2 = self.slice("plan/002-second", commit=False, merge=False)
        proc = self.task("start", "002", "--phase", "implementation")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(tt.frontmatter(read(first))["phase"], "implementation")
        self.assertEqual(tt.frontmatter(read(second))["phase"], "implementation")
        self.assertEqual(tt.active(wt, self.roots)["id"], "001")
        self.assertEqual(tt.active(wt2, self.roots)["id"], "002")
        # 003 overlaps 002, which loses the phase; 001 shares no prefix with 003
        wt3 = self.slice("plan/003-third", commit=False, merge=False)
        self.assertEqual(self.task("start", "003", "--phase", "implementation").returncode, 0)
        self.assertEqual(tt.frontmatter(read(second))["phase"], "")
        self.assertEqual(tt.frontmatter(read(first))["phase"], "implementation")
        self.assertEqual(tt.frontmatter(read(third))["phase"], "implementation")
        # the CLI inside a plan's worktree acts on that plan, not on 001 - the
        # main checkout's first phased plan
        self.assertEqual(support.run([CLI, "stop"], env=self.env(), cwd=wt3).returncode, 0)
        self.assertEqual(tt.frontmatter(read(third))["phase"], "")
        self.assertEqual(tt.frontmatter(read(first))["phase"], "implementation")

    def test_start_of_a_plan_with_no_worktree_clears_a_held_plan(self):
        # the started plan runs in the main checkout, so the main checkout's
        # task is the one it reads: a held plan beside it would leave `phase`
        # in main moving the other plan
        first = self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        second = self.plan("002-second.md", allowed=["docs/**"])
        self.slice("plan/001-first", commit=False, merge=False)
        self.assertEqual(self.task("start", "002", "--phase", "implementation").returncode, 0)
        self.assertEqual(tt.frontmatter(read(first))["phase"], "")
        self.assertEqual(self.status()["id"], "002")
        self.assertEqual(self.task("phase", "verification").returncode, 0)
        self.assertEqual(tt.frontmatter(read(second))["phase"], "verification")

    def test_start_clears_a_worktree_plan_whose_scope_overlaps(self):
        first = self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        self.plan("002-second.md", allowed=["hooks/x/**"])
        self.slice("plan/001-first", commit=False, merge=False)
        self.slice("plan/002-second", commit=False, merge=False)
        self.assertEqual(self.task("start", "002", "--phase", "implementation").returncode, 0)
        self.assertEqual(tt.frontmatter(read(first))["phase"], "")

    def test_a_plan_worktrees_checkpoint_is_read_from_its_own_tree(self):
        # the gate reads the checkpoint against the worktree's HEAD and tree, so
        # the CLI records it from there: a dirty main checkout is not that tree
        first = self.plan("001-first.md", allowed=["hooks/**"])
        second = self.plan("002-second.md", allowed=["docs/**"])
        self.slice("plan/001-first", commit=False, merge=False)
        wt2 = self.slice("plan/002-second", commit=False, merge=False)
        self.dirty("hooks/main.py")
        self.assertEqual(self.task("start", "001", "--phase", "discovery").returncode, 0)
        self.assertEqual(self.task("phase", "implementation").returncode, 0)
        self.assertEqual(tt.frontmatter(read(first))["checkpoint"], self.head())
        self.assertEqual(self.task("start", "002", "--phase", "implementation").returncode, 0)
        self.assertEqual(tt.frontmatter(read(second))["checkpoint"], self.head())
        os.makedirs(os.path.join(wt2, "docs"))
        with open(os.path.join(wt2, "docs", "a.md"), "w") as fh:
            fh.write("the first write\n")
        out, proc = run_json([support.PROBE_GATE],
                             {"tool": "Write", "cwd": self.repo, "session_id": "c",
                              "input": {"file_path": os.path.join(wt2, "docs", "b.md"),
                                        "content": "x"}}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)

    def test_a_slice_is_tagged_with_its_own_plan(self):
        # two phased plans: a slice is the plan its worktree or brief names,
        # not whichever plan the main checkout reads first
        self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        self.plan("002-second.md", phase="implementation", allowed=["docs/**"])
        rec = tt.open_slice(self.repo, "Review002", agent="tezgah-reviewer",
                            brief="Review plan 002's diff.")
        self.assertEqual(rec["plan"], "002")
        wt = self.slice("plan/002-second", commit=False, merge=False)
        rec = tt.open_slice(self.repo, "Slice002", brief="Worktree: %s\nOwns: docs/**" % wt)
        self.assertEqual(rec["plan"], "002")
        self.assertEqual(tt.open_slice(self.repo, "Other", brief="do x")["plan"], "001")

    def test_a_slice_tag_reads_the_shared_context_and_survives_a_reopen(self):
        self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        self.plan("002-second.md", phase="implementation", allowed=["docs/**"])
        rec = tt.open_slice(self.repo, "Ctx", task="Read the diff.",
                            brief="Context: plan 002, round 2.\nRead the diff.")
        self.assertEqual(rec["plan"], "002")
        again = tt.open_slice(self.repo, "Ctx")
        self.assertEqual((again["id"], again["attempts"]), (rec["id"], 2))
        self.assertEqual(again["plan"], "002")

    def test_a_scope_another_worktrees_plan_holds_is_refused(self):
        self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        self.plan("002-second.md", allowed=["docs/**"])
        self.slice("plan/001-first", commit=False, merge=False)
        wt2 = self.slice("plan/002-second", commit=False, merge=False)
        self.assertEqual(self.task("start", "002", "--phase", "implementation").returncode, 0)

        def run(*args):
            return support.run([CLI] + list(args), env=self.env(), cwd=wt2)
        refused = run("allow", "hooks/x/**", "--why", "w")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("001", refused.stdout)
        self.assertEqual(run("phase", "implementation", "--any-path").returncode, 1)
        self.assertEqual(run("allow", "docs/**", "src/**", "--why", "w").returncode, 0)

    def test_the_body_writers_work_from_a_plan_worktree(self):
        path = self.plan("002-second.md", allowed=["docs/**"], spike="which store")
        wt2 = self.slice("plan/002-second", commit=False, merge=False)
        proc = support.run([CLI, "spike", "002", "sqlite"], env=self.env(), cwd=wt2)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(tt.frontmatter(read(path))["spike_recorded"], "sqlite")

    def test_entering_implementation_records_the_pre_work_commit(self):
        # the one state a large refactor has to return to: the commit the work
        # branches from, recorded where the gate reads it
        path = self.plan("001-first.md", allowed=["hooks/**"])
        proc = self.task("start", "001", "--phase", "implementation")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(tt.frontmatter(read(path))["checkpoint"], self.head())
        self.assertIn("checkpoint: %s" % self.head(), proc.stdout)

    def test_only_the_implementation_phase_gets_a_checkpoint(self):
        # discovery writes nothing to return from, and verification is the phase
        # after the build
        path = self.plan("001-first.md", allowed=["hooks/**"])
        self.assertEqual(self.task("start", "001", "--phase", "discovery").returncode, 0)
        self.assertNotIn("checkpoint", tt.frontmatter(read(path)))
        self.assertEqual(self.task("phase", "verification").returncode, 0)
        self.assertNotIn("checkpoint", tt.frontmatter(read(path)))

    def test_a_dirty_tree_records_a_pending_checkpoint_and_names_the_commit(self):
        # uncommitted work has no commit to record, so the record names the HEAD
        # the commit has to move off along with the word `pending` - that sha is
        # what the gate compares, which is why the commit the CLI prints clears the
        # refusal by itself; the same command, and the same sha, are what the CLI
        # prints here
        path = self.plan("001-first.md", allowed=["hooks/**"])
        self.dirty("hooks/x.py")
        head = self.head()
        proc = self.task("start", "001", "--phase", "implementation")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(tt.frontmatter(read(path))["checkpoint"],
                         "%s %s" % (tt.CHECKPOINT_PENDING, head))
        self.assertIn("checkpoint: pending on %s" % head, proc.stdout)
        self.assertIn('git add -A && git commit -m "checkpoint: before 001-first"',
                      proc.stdout)
        # the commit is the way out: re-entering records the sha it created
        self.commit("hooks/x.py", message="checkpoint: before 001-first")
        proc = self.task("phase", "implementation")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(tt.frontmatter(read(path))["checkpoint"], self.head())

    # ---------------------------------------------- verification and close

    def test_the_checkpoint_line_stops_claiming_a_lifted_refusal(self):
        # The gate's refusal is `HEAD != the recorded sha`, so the status line
        # reads the checkout too: after the commit the refusal names - the
        # documented way out - the record still says `pending <sha>` until a
        # later phase move rewrites it, and printing "writes are refused" there
        # would report a boundary the gate has already lifted.
        sha = self.head()
        self.plan("001-a.md", phase="implementation", allowed=["hooks/**"],
                  checkpoint="pending %s" % sha)
        self.dirty("hooks/x.py")          # the dirty tree the checkpoint is about
        first = self.task("status").stdout
        self.assertIn("checkpoint: pending on %s" % sha, first)
        self.commit("hooks/x.py", message="checkpoint: before 001-a")
        after = self.task("status").stdout
        self.assertIn("checkpoint: satisfied - HEAD moved off %s" % sha, after)
        self.assertNotIn("writes are refused", after)

    def test_the_checkpoint_line_reads_the_tree_the_way_the_gate_does(self):
        # The gate refuses only while HEAD is the recorded sha AND the tree is
        # dirty (hooks/tezgah_gate.checkpoint_reason). A user who discards the
        # uncommitted work instead of committing it leaves the tree clean with
        # HEAD still the recorded sha - the gate allows the write, so the status
        # line must not claim the phase is refused.
        sha = self.head()
        self.plan("001-a.md", phase="implementation", allowed=["hooks/**"],
                  checkpoint="pending %s" % sha)
        self.dirty(".gitignore")
        self.assertIn("checkpoint: pending on %s" % sha, self.task("status").stdout)
        subprocess.run(["git", "-C", self.repo, "checkout", "--", ".gitignore"],
                       check=True, capture_output=True, env=dict(os.environ, **GIT_ENV))
        out = self.task("status").stdout
        self.assertIn("checkpoint: satisfied - the tree is clean again", out)
        self.assertNotIn("writes are refused", out)

    def test_verification_lists_every_item_and_the_projects_diff_base(self):
        path = self.plan("001-first.md", allowed=["hooks/**"])
        with open(path, "a") as fh:
            fh.write("## Acceptance\n" + COMMAND_ITEM + UNVERIFIABLE_ITEM)
        env = dict(os.environ, **GIT_ENV)
        ident = ["-c", "user.name=t", "-c", "user.email=t@localhost"]
        heads = []
        # the plan lives in `.tezgah`, which holds its own repository: the diff
        # the reviewer reads is the project's, never the private one's
        for repo in (self.repo, os.path.join(self.repo, ".tezgah")):
            if repo != self.repo:
                subprocess.run(["git", "init", "-q", repo], check=True, env=env)
            subprocess.run(["git", "-C", repo] + ident +
                           ["commit", "-q", "--allow-empty", "-m", repo],
                           check=True, env=env)
            heads.append(subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                                        capture_output=True, text=True, env=env)
                         .stdout.strip()[:12])
        proc = self.task("start", "001", "--phase", "verification")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("bin/tezgah-docs --citations", proc.stdout)
        # an item no command proves is still listed as owed, with its state
        self.assertIn("corpus has no such file.  [unverifiable]", proc.stdout)
        self.assertIn("tezgah-reviewer", proc.stdout)
        self.assertIn("git diff %s..HEAD" % heads[0], proc.stdout)
        self.assertNotIn(heads[1], proc.stdout)
        self.assertIn("tezgah-task review 001", proc.stdout)

    def test_close_done_needs_an_approving_review(self):
        path = self.plan("001-first.md", allowed=["hooks/**"])
        done = os.path.join(self.repo, ".tezgah", "plans", "done", "001-first.md")
        refused = self.task("close", "001", "done")
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertIn("tezgah-task review 001", refused.stdout)
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "changes").returncode, 0)
        self.assertEqual(self.task("close", "001", "done").returncode, 1)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "lgtm").returncode, 2)
        self.task("review", "001", "tezgah-reviewer", "approve")
        proc = self.task("close", "001", "done")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(path))
        fields = tt.frontmatter(read(done))
        self.assertEqual(fields["status"], "done")
        self.assertTrue(fields["review"].startswith("tezgah-reviewer approve "))

    def approved_plan(self, *items):
        """Plan 001 with these Acceptance lines and an approving review: the
        only thing left between it and done is its items."""
        path = self.plan("001-first.md", allowed=["hooks/**"])
        with open(path, "a") as fh:
            fh.write("## Acceptance\n" + "".join(items))
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "approve").returncode, 0)
        return path

    def test_close_done_refuses_an_open_acceptance_item_and_names_it(self):
        # Plan 095 closed done with its item 2 still `[ ]`: close read only the
        # review, never the plan's own Acceptance boxes.
        path = self.approved_plan("- [x] first: `ruff check .`\n", COMMAND_ITEM)
        before = read(path)
        for extra in ((), ("--resolved", "a fix; test_x proves it")):
            proc = self.task("close", "001", "done", *extra)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("item 2: The counts it read are printed.", proc.stdout)
            self.assertNotIn("item 1:", proc.stdout)
            for way in ("tezgah-task tick 001 2", "UNMET:", "close 001 discarded"):
                self.assertIn(way, proc.stdout)
            self.assertEqual(read(path), before)

    def test_close_done_passes_once_every_item_is_ticked(self):
        path = self.approved_plan(COMMAND_ITEM)
        self.assertEqual(self.task("tick", "001", "1").returncode, 0)
        proc = self.task("close", "001", "done")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertFalse(os.path.exists(path))

    def test_close_done_passes_an_item_marked_unmet_with_a_reason(self):
        path = self.approved_plan(
            "- [ ] Calibration band reached: `make cal`\n"
            "      UNMET: 0 of 20 tasks in the band, owner kept them 2026-10-12\n")
        proc = self.task("close", "001", "done")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertFalse(os.path.exists(path))

    def test_a_bare_unmet_marker_is_not_a_reason(self):
        path = self.approved_plan("- [ ] Calibration band reached: `make cal` UNMET:\n")
        proc = self.task("close", "001", "done")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("item 1:", proc.stdout)
        self.assertTrue(os.path.exists(path))

    def test_close_discarded_ignores_open_items(self):
        self.plan("001-first.md", allowed=["hooks/**"])
        with open(os.path.join(self.open, "001-first.md"), "a") as fh:
            fh.write("## Acceptance\n" + COMMAND_ITEM)
        proc = self.task("close", "001", "discarded")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_close_from_inside_a_landed_worktree_keeps_it(self):
        # the session's own cwd is never removed under it
        self.plan("001-first.md", phase="implementation", allowed=["**"])
        wt = self.slice("slice-done")
        proc = support.run([CLI, "close", "001", "discarded"], env=self.env(), cwd=wt)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isdir(wt), proc.stdout)

    def ws(self, *args):
        """git in the private `.tezgah` repository, its stdout."""
        return subprocess.run(["git", "-C", os.path.join(self.repo, ".tezgah")] + list(args),
                              capture_output=True, text=True, check=True,
                              env=dict(os.environ, **GIT_ENV)).stdout.strip()

    def private_repo(self):
        """`.tezgah` as its own git repository with an owner identity, the way
        ensure_workspace seeds it."""
        self.ws("init", "-q")
        self.ws("config", "user.name", "owner")
        self.ws("config", "user.email", "owner@localhost")

    def test_close_done_records_the_commit_that_landed(self):
        # reviewed_sha names the worktree's HEAD, which a squash merge and a
        # branch deletion leave in no branch: `landed` names the main checkout's
        path = self.plan("001-first.md", allowed=["hooks/**"])
        wt = self.slice("plan/001-first", commit=False, merge=False)
        with open(os.path.join(wt, "work.txt"), "w") as fh:
            fh.write("work\n")
        self.git("add", "work.txt", cwd=wt)
        self.git("commit", "-q", "-m", "plan work", cwd=wt)
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "approve").returncode, 0)
        reviewed = tt.frontmatter(read(path))["reviewed_sha"]
        self.git("merge", "-q", "--squash", "plan/001-first")
        self.git("commit", "-q", "-m", "squash")
        self.git("worktree", "remove", "--force", wt)
        self.git("branch", "-D", "plan/001-first")
        proc = self.task("close", "001", "done")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        fields = tt.frontmatter(read(os.path.join(self.repo, ".tezgah", "plans", "done",
                                                  "001-first.md")))
        self.assertEqual(fields.get("landed"), self.head())
        self.assertNotEqual(self.head()[:12], reviewed)
        # a discarded plan landed nothing
        self.plan("002-second.md")
        self.assertEqual(self.task("close", "002", "discarded").returncode, 0)
        self.assertNotIn("landed", tt.frontmatter(read(os.path.join(
            self.repo, ".tezgah", "plans", "done", "002-second.md"))))

    def test_close_done_before_the_merge_records_no_landed(self):
        # review of plan 097, F7: HEAD of a main checkout the reviewed work is not
        # in yet names a commit without it
        self.plan("003-third.md", allowed=["hooks/**"])
        wt = self.slice("plan/003-third", commit=False, merge=False)
        with open(os.path.join(wt, "work.txt"), "w") as fh:
            fh.write("work\n")
        self.git("add", "work.txt", cwd=wt)
        self.git("commit", "-q", "-m", "plan work", cwd=wt)
        self.assertEqual(self.task("review", "003", "tezgah-reviewer", "approve").returncode, 0)
        proc = self.task("close", "003", "done")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("landed", tt.frontmatter(read(os.path.join(
            self.repo, ".tezgah", "plans", "done", "003-third.md"))))
        self.assertIn("no `landed:` recorded", proc.stdout)

    def test_close_commits_only_the_moved_record_in_the_private_repo(self):
        self.private_repo()
        path = self.plan("001-first.md", allowed=["hooks/**"])
        self.ws("add", "plans/open/001-first.md")
        self.ws("commit", "-q", "-m", "plan: add 001")
        staged = os.path.join(self.repo, ".tezgah", "notes.md")
        with open(staged, "w") as fh:
            fh.write("staged by the owner\n")
        self.ws("add", "notes.md")
        with open(os.path.join(self.repo, ".tezgah", "plans", "open", "002-x.md"), "w") as fh:
            fh.write("untracked\n")
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "approve").returncode, 0)
        proc = self.task("close", "001", "done")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.ws("log", "-1", "--format=%s"), "plan: close 001 first")
        self.assertEqual(self.ws("show", "--name-status", "--format=", "HEAD").splitlines(),
                         ["A\tplans/done/001-first.md", "D\tplans/open/001-first.md"])
        # the owner's staged change and an untracked plan stay as they were
        self.assertEqual(self.ws("diff", "--cached", "--name-only"), "notes.md")
        status = self.ws("status", "--porcelain", "-uall")
        self.assertIn("?? plans/open/002-x.md", status)
        # the plans lock leaves no file behind (review of plan 097, F6)
        self.assertNotIn(".lock", status)
        self.assertIn(self.ws("rev-parse", "HEAD")[:12], proc.stdout)

    def test_close_commits_a_record_the_private_repo_never_tracked(self):
        self.private_repo()
        self.plan("001-first.md")
        proc = self.task("close", "001", "discarded")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.ws("show", "--name-status", "--format=", "HEAD").splitlines(),
                         ["A\tplans/done/001-first.md"])

    def test_close_commits_nothing_when_the_workspace_is_no_git_repo(self):
        # `.tezgah` here is a plain directory inside the project's repository:
        # a commit there would land in the project's history
        before = self.head()
        self.plan("001-first.md")
        proc = self.task("close", "001", "discarded")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.head(), before)
        self.assertNotIn("committed", proc.stdout)

    def test_verification_names_the_plan_worktrees_diff(self):
        path = self.plan("001-first.md", allowed=["hooks/**"])
        with open(path, "a") as fh:
            fh.write("## Acceptance\n" + COMMAND_ITEM)
        wt = os.path.realpath(self.slice("plan/001-first", commit=False, merge=False))
        self.git("commit", "-q", "--allow-empty", "-m", "plan work", cwd=wt)
        out = self.task("start", "001", "--phase", "verification").stdout
        self.assertIn("`git -C %s diff " % wt, out)
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "changes").returncode, 0)
        out = self.task("status").stdout
        self.assertIn("`git -C %s diff %s..HEAD`" % (wt, tt.frontmatter(read(path))["reviewed_sha"]),
                      out)

    def test_status_reads_a_worktree_plans_checkpoint_from_its_tree(self):
        path = self.plan("001-first.md", phase="implementation", allowed=["hooks/**"],
                         checkpoint="pending %s" % self.head())
        wt = os.path.realpath(self.slice("plan/001-first", commit=False, merge=False))
        with open(os.path.join(wt, "dirty.txt"), "w") as fh:
            fh.write("x\n")
        out = self.task("status").stdout
        self.assertIn("pending on %s" % self.head(), out)
        self.assertIn(tt.checkpoint_command(path, wt), out)

    def test_review_records_the_plan_worktrees_head(self):
        # a plan held by its own worktree is built on that branch, so round 2's
        # `git diff <reviewed_sha>..HEAD` has to start from that branch's HEAD
        path = self.plan("001-first.md", allowed=["hooks/**"])
        wt = self.slice("plan/001-first", commit=False, merge=False)
        self.git("commit", "-q", "--allow-empty", "-m", "plan work", cwd=wt)
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True,
                              text=True, env=dict(os.environ, **GIT_ENV)).stdout.strip()[:12]
        self.assertNotEqual(head, self.head()[:12])
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "changes").returncode, 0)
        self.assertEqual(tt.frontmatter(read(path))["reviewed_sha"], head)

    def test_review_records_the_sha_so_the_next_round_reads_only_the_delta(self):
        path = self.plan("001-first.md", allowed=["hooks/**"])
        with open(path, "a") as fh:
            fh.write("## Acceptance\n" + COMMAND_ITEM)
        env = dict(os.environ, **GIT_ENV)
        ident = ["-c", "user.name=t", "-c", "user.email=t@localhost"]
        subprocess.run(["git", "-C", self.repo] + ident +
                       ["commit", "-q", "--allow-empty", "-m", "base"],
                       check=True, env=env)
        head = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True, env=env).stdout.strip()[:12]
        self.assertEqual(self.task("review", "001", "tezgah-reviewer", "changes").returncode, 0)
        fields = tt.frontmatter(read(path))
        self.assertEqual(fields["reviewed_sha"], head)
        self.assertEqual(fields["review_round"], "1")
        out = self.task("start", "001", "--phase", "verification").stdout
        self.assertIn("review round 2", out)
        self.assertIn("git diff %s..HEAD" % head, out)
        self.assertNotIn("2-round budget is spent", out)
        self.task("review", "001", "tezgah-reviewer", "changes")
        self.assertEqual(tt.frontmatter(read(path))["review_round"], "2")
        out = self.task("status").stdout
        self.assertIn("2-round budget is spent", out)

    def test_a_third_review_round_is_refused(self):
        # The reviewer text looped while any round confirmed a defect, and this CLI
        # printed a two-round budget and recorded round 3, 4, ... anyway: a plan
        # reviewed fifty times in a row. The budget is this refusal, not prose.
        path = self.plan("001-first.md", allowed=["hooks/**"])
        for _ in range(2):
            self.assertEqual(self.task("review", "001", "tezgah-reviewer",
                                       "changes").returncode, 0)
        before = read(path)
        refused = self.task("review", "001", "tezgah-reviewer", "approve")
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertIn("never a third", refused.stdout)
        self.assertIn("--resolved", refused.stdout)
        self.assertIn("fix-later", refused.stdout)
        self.assertNotIn("the user", refused.stdout)
        self.assertEqual(read(path), before)
        # the session settles what is left itself: done needs the fix on record
        self.assertIn("--resolved", self.task("close", "001", "done").stdout)
        proc = self.task("close", "001", "done", "--resolved",
                         "null check added; test_empty_input proves it")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        done = os.path.join(self.repo, ".tezgah", "plans", "done", "001-first.md")
        fields = tt.frontmatter(read(done))
        self.assertEqual(fields["status"], "done")
        self.assertTrue(fields["resolved"].startswith(
            "null check added; test_empty_input proves it "), fields)

    def test_the_budget_refusal_names_the_configured_languages_token(self):
        # S5 F4: the refusal told an `en` user to write KARAR
        self.plan("001-first.md", allowed=["hooks/**"])
        self.task("start", "001", "--phase", "verification")
        for _ in range(2):
            self.task("review", "001", "tezgah-reviewer", "changes")
        self.assertIn("decision (KARAR)", self.task(
            "review", "001", "tezgah-reviewer", "approve").stdout)
        self.config({"roots": [self.roots], "language": "en"})
        for args in (("review", "001", "tezgah-reviewer", "approve"), ("status",)):
            out = self.task(*args).stdout
            self.assertIn("decision (DECISION)", out, args)
            self.assertNotIn("KARAR", out, args)

    def test_verification_names_the_fan_out_and_the_budget_per_round(self):
        self.plan("001-first.md", allowed=["hooks/**"])
        first = self.task("start", "001", "--phase", "verification").stdout
        for words in ("ONE message", "correctness and contract", "security",
                      "tests and performance", "one reviewer", "at most 2 rounds",
                      "critical or major", "fix-later"):
            self.assertIn(words, first)
        self.task("review", "001", "tezgah-reviewer", "changes")
        second = self.task("status").stdout
        self.assertIn("review round 2 (the last)", second)
        self.assertIn("regression test", second)
        self.task("review", "001", "tezgah-reviewer", "changes")
        spent = self.task("status").stdout
        self.assertIn("2-round budget is spent", spent)
        self.assertIn("refuses a third", spent)
        self.assertNotIn("record its verdict", spent)

    def test_an_approving_round_owes_no_further_round(self):
        self.plan("001-first.md", allowed=["hooks/**"])
        self.task("start", "001", "--phase", "verification")
        self.task("review", "001", "tezgah-reviewer", "approve")
        out = self.task("status").stdout
        self.assertIn("approved in round 1", out)
        self.assertNotIn("review round 2", out)

    def test_close_clears_the_active_task_and_discards_without_review(self):
        # the session closes its own task: no `stop` first, no hand-off
        self.plan("001-first.md", phase="discovery")
        proc = self.task("close", "001", "discarded")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        moved = os.path.join(self.repo, ".tezgah", "plans", "done", "001-first.md")
        fields = tt.frontmatter(read(moved))
        self.assertEqual((fields["status"], fields["phase"]), ("discarded", ""))
        self.assertIsNone(self.status())

    def git(self, *args, cwd=None):
        subprocess.run(["git", "-C", cwd or self.repo, "-c", "user.name=t",
                        "-c", "user.email=t@localhost"] + list(args), check=True,
                       capture_output=True, env=dict(os.environ, **GIT_ENV))

    def slice(self, name, commit=True, merge=True):
        """A linked worktree on branch `name`, optionally with one commit of its
        own merged into the main checkout's branch. Returns its path."""
        path = os.path.join(self.home, "wt-" + name)
        self.git("worktree", "add", "-q", "-b", name, path)
        if commit:
            with open(os.path.join(path, name + ".txt"), "w") as fh:
                fh.write(name)
            self.git("add", name + ".txt", cwd=path)
            self.git("commit", "-q", "-m", name, cwd=path)
        if merge:
            self.git("merge", "-q", "--no-edit", name)
        return path

    def close_lines(self, env=None):
        """`close 001 discarded` with an active plan: its worktree lines by path."""
        self.plan("001-first.md", phase="implementation", allowed=["**"])
        proc = support.run([CLI, "close", "001", "discarded"],
                           env=env or self.env(), cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return {line.split(" ")[2]: line for line in proc.stdout.splitlines()
                if line.startswith("worktree ")}

    def test_close_removes_landed_worktrees_and_keeps_every_other_one(self):
        # A closed plan leaves no checkout behind - and never takes one whose
        # work or data exists nowhere else, or a slice that has not started yet.
        synced = self.slice("slice-synced", commit=False, merge=False)
        picked = self.slice("slice-picked", commit=False, merge=False)
        done = self.slice("slice-done")
        # only main's own work cherry-picked in: content landed, nothing of its own
        self.git("cherry-pick", "slice-done", cwd=picked)
        # commits that cancel out land nothing, though they merge to main's tree
        reverted = self.slice("slice-revert", merge=False)
        self.git("revert", "--no-edit", "HEAD", cwd=reverted)
        squashed = self.slice("slice-squash", merge=False)
        self.git("merge", "-q", "--squash", "slice-squash")
        self.git("commit", "-q", "-m", "squash")
        # an unstarted slice brought up to date has moved, but nobody committed
        self.git("merge", "-q", "--ff-only", self.head(), cwd=synced)
        fresh = self.slice("slice-fresh", commit=False, merge=False)
        open_ = self.slice("slice-open", merge=False)
        dirty = self.slice("slice-dirty")
        with open(os.path.join(dirty, "scratch.txt"), "w") as fh:
            fh.write("only copy")
        secret = self.slice("slice-secret")
        with open(os.path.join(self.repo, ".git", "info", "exclude"), "a") as fh:
            fh.write("/.env\n")
        with open(os.path.join(secret, ".env"), "w") as fh:
            fh.write("TOKEN=only-copy\n")
        data = self.slice("slice-data")
        os.makedirs(os.path.join(data, ".tezgah", "plans"))
        lines = self.close_lines()
        for path, branch in ((done, "slice-done"), (squashed, "slice-squash")):
            self.assertEqual(lines.pop(os.path.realpath(path)),
                             "worktree removed: %s (%s)" % (os.path.realpath(path), branch))
            self.assertFalse(os.path.exists(path))
        for path, why in ((fresh, "no commit of its own"), (synced, "no commit of its own"),
                          (picked, "no commit of its own"), (reverted, "is not merged"),
                          (open_, "is not merged"), (dirty, "uncommitted changes"),
                          (secret, "ignored file .env"), (data, ".tezgah holds data")):
            self.assertTrue(os.path.isdir(path), path)
            line = lines.pop(os.path.realpath(path))
            self.assertTrue(line.startswith("worktree kept: "), line)
            self.assertIn(why, line)
        self.assertEqual(lines, {})
        branches = subprocess.run(["git", "-C", self.repo, "branch", "--list"],
                                  capture_output=True, text=True).stdout
        self.assertNotIn("slice-done", branches)
        self.assertIn("slice-open", branches)

    def test_close_keeps_every_worktree_when_orca_does_not_answer(self):
        # Orca installed but down, or answering in a shape this reader does not
        # know: its agents cannot be checked, so nothing goes
        done = self.slice("slice-done")
        for name, body in (("orca-down", "exit 1"),
                           ("orca-odd", "echo '{\"ok\": true, \"result\": {\"x\": 1}}'")):
            fake = os.path.join(self.home, name)
            with open(fake, "w") as fh:
                fh.write("#!/bin/sh\n%s\n" % body)
            os.chmod(fake, 0o755)
            lines = self.close_lines(dict(self.env(), TEZGAH_ORCA_BIN=fake))
            self.assertIn("Orca did not answer", lines[os.path.realpath(done)], name)
            self.assertTrue(os.path.isdir(done))

    # ----------------------------------------------------------------- stop

    def test_stop_clears_the_phase_and_leaves_the_allowlist(self):
        path = self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        proc = self.task("stop")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("task 001 stopped", proc.stdout)
        self.assertIsNone(self.status())
        self.assertEqual(tt.allowed_paths(read(path)), ["hooks/**"])
        self.assertEqual(tt.frontmatter(read(path))["id"], "001")

    # ------------------------------------------------------------ tick and note

    BODY = ("the goal\n## Acceptance\n- [ ] first, proof `make a`\n"
            "- [x] second, proof\n  `make b`\n## State\nold one\n\n"
            "## State (later)\nold two\n\n## Next\nold next\n")

    def test_tick_and_undo_flip_one_box_and_keep_the_frontmatter(self):
        path = self.plan("001-first.md", phase="implementation",
                         allowed=["hooks/**"], body=self.BODY)
        proc = self.task("tick", "001", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("- [x] first, proof `make a`", proc.stdout)
        proc = self.task("tick", "001", "2", "--undo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("- [ ] second, proof `make b`", proc.stdout)
        text = read(path)
        self.assertEqual([i["checked"] for i in tt.acceptance_items(text)], [True, False])
        self.assertEqual(tt.frontmatter(text)["phase"], "implementation")
        self.assertEqual(tt.allowed_paths(text), ["hooks/**"])
        self.assertNotEqual(tt.frontmatter(text)["updated"], "2026-01-01")

    def test_tick_out_of_range_is_refused_and_writes_nothing(self):
        self.plan("001-first.md", body=self.BODY)
        before = self.snapshot()
        proc = self.task("tick", "001", "3")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("has 2 Acceptance items, not an item 3", proc.stdout)
        self.assertEqual(self.task("tick", "001", "0").returncode, 1)
        self.assertEqual(self.task("tick", "001").returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_note_replaces_the_newest_state_and_the_next_body(self):
        path = self.plan("001-first.md", body=self.BODY)
        self.assertEqual(self.task("note", "001", "state", "new state").returncode, 0)
        self.assertEqual(self.task("note", "001", "next", "new next").returncode, 0)
        text = read(path)
        self.assertIn("## State\nold one\n\n## State (later)\nnew state\n\n## Next\nnew next\n",
                      text)
        self.assertEqual(tt.frontmatter(text)["title"], "a plan")
        self.assertNotEqual(tt.frontmatter(text)["updated"], "2026-01-01")

    def test_note_without_the_section_or_with_a_bad_section_writes_nothing(self):
        self.plan("001-first.md")
        before = self.snapshot()
        proc = self.task("note", "001", "state", "x")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("has no `## State` section", proc.stdout)
        self.assertEqual(self.task("note", "001", "goal", "x").returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_tick_and_note_take_only_an_open_plan(self):
        # they write past the gate, so any other markdown file is refused
        # (review of plan 083, F4)
        readme = os.path.join(self.repo, "README.md")
        with open(readme, "w") as fh:
            fh.write("# x\n## Acceptance\n- [ ] a\n## Next\nold\n")
        before = read(readme)
        for args in (("note", readme, "next", "x"), ("tick", readme, "1"),
                     ("start", readme, "--phase", "discovery"),
                     ("review", readme, "r", "approve")):
            proc = self.task(*args)
            self.assertEqual(proc.returncode, 1, args)
            self.assertIn("is not an open plan", proc.stdout)
        self.assertEqual(read(readme), before)

    # --------------------------------------------------------------- status

    def test_status_names_the_active_task_and_its_scope(self):
        proc = self.task("status")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no active task", proc.stdout)
        self.plan("001-first.md", phase="discovery", allowed=["tests/**"])
        printed = self.task("status")
        self.assertEqual(printed.returncode, 0, printed.stderr)
        self.assertIn("task 001: phase discovery", printed.stdout)
        self.assertIn("allowed: tests/**", printed.stdout)
        self.assertIn(os.path.join(".tezgah", "plans", "open", "001-first.md"), printed.stdout)

    def test_a_reader_that_leaves_early_costs_no_traceback(self):
        # `tezgah-task stop | head -1` died with BrokenPipeError (plan 094). The
        # read end is closed before the CLI starts, so its first write meets
        # EPIPE on every run - a `head` racing the output would not.
        # A closed pipe costs the output, never the exit: a status that finds a
        # problem still exits 1 (review F5), and unbuffered, where every print
        # meets the pipe inside main, main still finishes its work (R2-3).
        cases = ((("status",), 0, "discovery"), (("stop",), 0, "discovery"),
                 (("status",), 1, "implement"))
        for unbuffered in ({}, {"PYTHONUNBUFFERED": "1"}):
            for args, want, phase in cases:
                self.plan("001-first.md", phase=phase, allowed=["tests/**"])
                read_end, write_end = os.pipe()
                os.close(read_end)
                try:
                    proc = subprocess.run([CLI] + list(args), env=self.env(extra=unbuffered),
                                          cwd=self.repo, stdout=write_end,
                                          stderr=subprocess.PIPE, text=True)
                finally:
                    os.close(write_end)
                where = (args, phase, unbuffered, proc.stderr)
                self.assertEqual(proc.returncode, want, where)
                self.assertEqual(proc.stderr, "", where)
                if args == ("stop",):
                    self.assertNotIn("phase: discovery",
                                     read(os.path.join(self.open, "001-first.md")), where)

    def test_status_reports_a_phase_no_reader_accepts(self):
        self.plan("001-first.md", phase="implement")
        proc = self.task("status")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("no active task", proc.stdout)
        self.assertIn("FAIL 001: phase 'implement' is not one of", proc.stdout)
        self.assertIsNone(self.status())

    def test_status_does_not_call_a_cleared_phase_malformed(self):
        self.plan("001-first.md", phase="implementation")
        self.task("stop")
        proc = self.task("status")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no active task", proc.stdout)
        self.assertNotIn("FAIL", proc.stdout)

    def test_status_json_is_parseable(self):
        payload, proc = run_json([CLI, "status", "--json"], env=self.env(), cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(payload["active"])
        self.assertEqual(payload["malformed"], [])
        self.plan("001-first.md", phase="verification", allowed=["tests/**"])
        payload, proc = run_json([CLI, "status", "--json"], env=self.env(), cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(payload["active"]["id"], "001")
        self.assertEqual(payload["active"]["phase"], "verification")
        self.assertEqual(payload["active"]["allowed_paths"], ["tests/**"])
        self.assertEqual([row["id"] for row in payload["open"]], ["001"])
        self.assertEqual(payload["parallel"], [])

    def test_status_lists_each_open_plan_with_its_progress_and_what_it_waits_on(self):
        first = self.plan("001-first.md", allowed=["hooks/**"])
        with open(first, "a") as fh:
            fh.write("## Acceptance\n" + COMMAND_ITEM + "- [x] done: `ruff check .`\n")
        second = self.plan("002-second.md", allowed=["docs/**"])
        tt.set_fields(second, after=["001"])
        self.plan("003-third.md", allowed=["skills/**"])
        proc = self.task("status")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("open plans: 3, 2 ready", proc.stdout)
        self.assertIn("  001 open, acceptance 1/2 checked, ready", proc.stdout)
        self.assertIn("  002 open, acceptance 0/0 checked, waits on 001 (open)", proc.stdout)
        self.assertIn("parallel: 001, 003 - ready, and no two share an allowed_paths "
                      "prefix", proc.stdout)

    def test_status_refuses_a_status_and_a_dependency_no_reader_can_place(self):
        path = self.plan("001-first.md")
        tt.set_fields(path, status="done", after=["009"])
        proc = self.task("status")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL 001: status 'done' is not one of open, blocked, which is "
                      "what a plan under .tezgah/plans/open carries", proc.stdout)
        self.assertIn("FAIL 001: `after: 009` names no plan under .tezgah/plans",
                      proc.stdout)


class Acceptance(unittest.TestCase):
    """The acceptance reader: which items carry the command that proves them,
    over a corpus of plan files (.tezgah/plans/open and .tezgah/plans/done), and the counts the
    report prints so an empty read cannot read as "everything is checkable"."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.open = os.path.join(self.root, ".tezgah", "plans", "open")
        self.done = os.path.join(self.root, ".tezgah", "plans", "done")
        os.makedirs(self.open)
        os.makedirs(self.done)

    def plan(self, directory, name, text):
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(text)

    def report(self):
        return tt.acceptance_report(self.root)

    def by_state(self, state):
        return [item for item in self.report()["items"] if item["state"] == state]

    def where(self, items):
        """[(plan, line)] in corpus order: the lines as numbers, not as strings,
        or line 10 would sort before line 9."""
        return [(item["plan"], item["line"]) for item in items]

    def test_an_item_that_names_a_command_is_not_reported(self):
        self.plan(self.open, "001-a.md", acceptance_plan(COMMAND_ITEM))
        self.assertEqual([i["state"] for i in self.report()["items"]], ["checkable"])
        self.assertEqual(self.by_state("missing"), [])

    def test_a_command_ending_in_the_current_directory_is_checkable(self):
        # `.` is a path like any other: `ruff check .` is the command, and read
        # as a bare word it was reported as naming no command at all - which is
        # exactly the item the repository's own plan carries (`ruff check .`).
        self.plan(self.open, "001-a.md",
                  acceptance_plan("- [ ] lint: `ruff check .`\n"))
        self.assertEqual([i["state"] for i in self.report()["items"]], ["checkable"])

    def test_a_runner_and_its_test_subcommand_is_checkable_and_prose_is_not(self):
        # `pnpm test` carries no option and no path, and read by tokens alone it
        # named no command - which refuses the phase move for the commonest
        # acceptance item there is. A known runner before `test`/`run` is one;
        # a sentence in backticks that starts with a plain word stays missing.
        for span in ("pnpm test", "npm test", "yarn test", "cargo test",
                     "go test ./...", "make test", "bun test", "npm run test",
                     "uv run pytest"):
            self.assertTrue(tt.names_command("- [ ] green: `%s`" % span), span)
        for span in ("run the tests", "test it", "make it work", "npm",
                     "go home", "cargo"):
            self.assertFalse(tt.names_command("- [ ] `%s`" % span), span)

    def test_an_item_with_no_command_is_reported_with_its_plan_and_line(self):
        text = acceptance_plan(COMMAND_ITEM, MISSING_ITEM)
        self.plan(self.open, "002-b.md", text)
        missing = self.by_state("missing")
        self.assertEqual(self.where(missing),
                         [(".tezgah/plans/open/002-b.md", line_of(text, "The reader lives"))])
        # the item wraps onto a second line and stays one item: the report has to
        # carry the whole item, not its first line
        self.assertIn("so there is one reader.", missing[0]["text"])

    def test_an_unverifiable_item_is_reported_as_such_and_not_as_a_defect(self):
        text = acceptance_plan(UNVERIFIABLE_ITEM, BARE_MARKER_ITEM, MENTION_ITEM)
        self.plan(self.open, "003-c.md", text)
        declared = self.by_state("unverifiable")
        self.assertEqual(self.where(declared),
                         [(".tezgah/plans/open/003-c.md", line_of(text, "The fixture cannot"))])
        self.assertEqual(declared[0]["reason"], "the corpus has no such file.")
        # neither a marker with no why nor a sentence that only names the word is
        # a declaration: both are reported, and the counts stay honest
        self.assertEqual(self.where(self.by_state("missing")),
                         [(".tezgah/plans/open/003-c.md", line_of(text, BARE_MARKER_ITEM.strip())),
                          (".tezgah/plans/open/003-c.md", line_of(text, "Read the format"))])

    def test_the_report_counts_the_plans_and_the_items_it_read(self):
        self.plan(self.open, "001-a.md", acceptance_plan(COMMAND_ITEM, MISSING_ITEM))
        self.plan(self.done, "002-b.md", acceptance_plan(UNVERIFIABLE_ITEM))
        self.plan(self.open, "003-c.md", "---\nid: 003\n---\n## Goal\nno items here\n")
        report = self.report()
        self.assertEqual(report["plans"], 3)
        self.assertEqual(len(report["items"]), 3)


class AcceptanceCli(TempHome):
    """The report end to end: `--acceptance` prints the reader's rows, exits 0
    while it flags items, and leaves the table to the table."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       capture_output=True, env=dict(os.environ, **GIT_ENV))
        self.open = os.path.join(self.repo, ".tezgah", "plans", "open")
        os.makedirs(self.open)

    def plan(self, name, text):
        with open(os.path.join(self.open, name), "w") as fh:
            fh.write(text)

    def report(self):
        """The installed tool runs with no PYTHONPATH; the suite's own
        PYTHONPATH=HOOKS would otherwise hide a broken import in the tool."""
        return support.run([RENDER, "--acceptance"],
                           env=self.env(extra={"PYTHONPATH": ""}), cwd=self.repo)

    def test_the_report_names_the_items_with_no_command_and_exits_zero(self):
        text = acceptance_plan(COMMAND_ITEM, MISSING_ITEM)
        self.plan("001-a.md", text)
        proc = self.report()
        # a report, not a gate: items are flagged and the exit code stays 0
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(".tezgah/plans/open/001-a.md:%d  no command: The reader lives"
                      % line_of(text, "The reader lives"), proc.stdout)
        self.assertNotIn("The counts it read", proc.stdout)

    def test_the_report_counts_what_it_read_and_leaves_the_readme_alone(self):
        text = acceptance_plan(COMMAND_ITEM, UNVERIFIABLE_ITEM)
        self.plan("001-a.md", text)
        proc = self.report()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(".tezgah/plans/open/001-a.md:%d  unverifiable: the corpus has no such"
                      % line_of(text, "The fixture cannot"), proc.stdout)
        self.assertIn("plans: 1 read, acceptance items: 2 read; 0 name no command, "
                      "1 declared unverifiable", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".tezgah", "plans", "README.md")))

    def strict(self):
        """The gate `--strict` adds: the report's own rows, plus the reason for a
        non-zero exit when an item still under `.tezgah/plans/open` names neither the
        command that proves it nor why it cannot be proven."""
        return support.run([RENDER, "--acceptance", "--strict"],
                           env=self.env(extra={"PYTHONPATH": ""}), cwd=self.repo)

    def test_strict_exits_one_over_an_open_item_that_names_no_command(self):
        text = acceptance_plan(COMMAND_ITEM, MISSING_ITEM)
        self.plan("001-a.md", text)
        proc = self.strict()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(".tezgah/plans/open/001-a.md:%d  no command: The reader lives"
                      % line_of(text, "The reader lives"), proc.stdout)
        self.assertIn("plans: 1 read, acceptance items: 2 read; 1 name no command, "
                      "0 declared unverifiable", proc.stdout)
        self.assertIn("strict: 1 item(s) under .tezgah/plans/open name no command and "
                      "declare no unverifiable; a done plan is reported, never "
                      "gated", proc.stdout)

    def test_strict_exits_zero_when_every_open_item_names_its_proof(self):
        self.plan("001-a.md", acceptance_plan(COMMAND_ITEM, UNVERIFIABLE_ITEM))
        proc = self.strict()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("strict:", proc.stdout)

    def test_strict_leaves_a_done_plan_a_record(self):
        done = os.path.join(self.repo, ".tezgah", "plans", "done")
        os.makedirs(done)
        text = acceptance_plan(MISSING_ITEM)
        with open(os.path.join(done, "001-a.md"), "w") as fh:
            fh.write(text)
        proc = self.strict()
        # a done plan is history: the same row is printed and nothing is gated
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn(".tezgah/plans/done/001-a.md:%d  no command: The reader lives"
                      % line_of(text, "The reader lives"), proc.stdout)
        self.assertNotIn("strict:", proc.stdout)
