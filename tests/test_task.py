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
# (`.tezgah/plans/open/007-checkable-acceptance.md:24`), which must not hide an item.
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


def plan_text(ident=None, phase=None, allowed=None, title="a plan", body="the goal"):
    """One plan file: the keys a real one carries, plus whichever of the two new
    optional ones the test is about."""
    front = ["id: %s" % ident] if ident else []
    front += ["title: %s" % title, "status: open",
              "created: 2026-01-01", "updated: 2026-01-01"]
    if phase is not None:
        front.append("phase: %s" % phase)
    if allowed is not None:
        front.append("allowed_paths:")
        front += ["  - %s" % glob for glob in allowed]
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

    def test_relative_resolves_a_symlink_out_of_the_root(self):
        outside = os.path.join(self.base, "outside.py")
        open(outside, "w").close()
        link = os.path.join(self.repo, "link.py")
        os.symlink(outside, link)
        self.assertIsNone(tt.relative(link, self.repo, self.base))

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
        """A real repository: the CLI asks git for the top-level, so the answer
        must not depend on what happens to sit above the temp directory."""
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       capture_output=True, env=dict(os.environ, **GIT_ENV))

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
        self.plan("001-first.md", phase="implementation")
        proc = self.task("phase", "verification")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["phase"], "verification")
        refused = self.task("phase", "shipping")
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertEqual(self.status()["phase"], "verification")

    def test_phase_and_allow_refuse_when_no_task_is_active(self):
        self.plan("001-first.md")
        for proc in (self.task("phase", "implementation"), self.task("allow", "hooks/**")):
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("FAIL no active task", proc.stdout)
        self.assertEqual(self.task("stop").returncode, 1)

    def test_allow_replaces_the_allowlist_and_empties_it_when_given_nothing(self):
        self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        proc = self.task("allow", "tests/**", "README.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.status()["allowed_paths"], ["tests/**", "README.md"])
        self.assertEqual(self.task("allow").returncode, 0)
        self.assertEqual(self.status()["allowed_paths"], [])
        self.assertIn("any path in the repo", self.task("status").stdout)

    # ----------------------------------------------------------------- stop

    def test_stop_clears_the_phase_and_leaves_the_allowlist(self):
        path = self.plan("001-first.md", phase="implementation", allowed=["hooks/**"])
        proc = self.task("stop")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("task 001 stopped", proc.stdout)
        self.assertIsNone(self.status())
        self.assertEqual(tt.allowed_paths(read(path)), ["hooks/**"])
        self.assertEqual(tt.frontmatter(read(path))["id"], "001")

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
