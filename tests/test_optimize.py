"""bin/tezgah-optimize: the verification-cost decision the session calls.

The fixture is a real git repository under a temp HOME: its own store under
`.tezgah/taste/`, a plan that names its Acceptance commands in backticks, and the
CLI run in a subprocess the way a session runs it. Nothing here asserts what the
planner meant: the answers are read back from the same store the next session
would read.
"""
import json
import os
import subprocess
import unittest

import support
from support import TempHome

OPT = os.path.join(support.REPO, "bin", "tezgah-optimize")
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_TERMINAL_PROMPT": "0"}
FAST = "python3 -m unittest discover -s tests -p test_x.py"
SLOW = "python3 tests/impacted.py --all"
PLAN = ("---\nid: 001\ntitle: a plan\nstatus: open\nphase: implementation\n"
        "allowed_paths:\n  - '**'\n---\n## Goal\nthe goal\n## Acceptance\n"
        "- [ ] The fast check passes: `%s`\n"
        "- [ ] The full suite passes: `%s`\n" % (FAST, SLOW))


class Optimize(TempHome):

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.git("init", "-q", "-b", "main", self.repo, cwd=self.home)
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("/.tezgah\n")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "init")
        folder = os.path.join(self.repo, ".tezgah", "plans", "open")
        os.makedirs(folder)
        with open(os.path.join(folder, "001-a-plan.md"), "w") as fh:
            fh.write(PLAN)

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", "-C", cwd or self.repo, "-c", "user.name=t",
             "-c", "user.email=t@localhost"] + list(args),
            check=True, capture_output=True, text=True,
            env=dict(os.environ, **GIT_ENV)).stdout.strip()

    def opt(self, *args):
        return support.run([OPT] + list(args), env=self.env(), cwd=self.repo)

    def verdicts(self, *args):
        proc = self.opt("next", "--json", *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return {row["command"]: row["verdict"]
                for row in json.loads(proc.stdout)["commands"]}

    def test_next_reads_the_plans_commands_and_starts_from_run_now(self):
        proc = self.opt("next", "--files", "hooks/x.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("changed: hooks/x.py", proc.stdout)
        self.assertEqual(self.verdicts(), {FAST: "run now", SLOW: "run now"})

    def test_a_measured_slow_command_defers_and_a_green_row_for_the_sha_wins(self):
        for _ in range(2):
            out = self.opt("record", SLOW, "--seconds", "180", "--exit", "1")
            self.assertEqual(out.returncode, 0, out.stderr)
        # a failing run is not green, so the measured median decides
        self.assertEqual(self.verdicts()[SLOW], "defer")
        sha = self.git("rev-parse", "--short", "HEAD")
        self.assertEqual(self.opt("record", SLOW, "--seconds", "181", "--exit", "0",
                                  "--sha", sha).returncode, 0)
        # the same change already has a green row: running it again adds nothing
        self.assertEqual(self.verdicts()[SLOW], "already green")
        # and the fast command's own median keeps it in the turn
        self.assertEqual(self.opt("record", FAST, "--seconds", "12",
                                  "--exit", "1").returncode, 0)
        self.assertEqual(self.verdicts()[FAST], "run now")

    def test_a_prose_backtick_is_not_a_check(self):
        # an item's prose is backticked too; a planner that read every token
        # would hand the session `stale` and a bare `tool subcommand` as checks
        path = os.path.join(self.repo, ".tezgah", "plans", "open", "001-a-plan.md")
        with open(path, "a") as fh:
            fh.write("- [ ] Nothing is left `stale`, `tezgah-optimize push` runs, "
                     "and `--files <paths>` is a placeholder.\n")
        self.assertEqual(sorted(self.verdicts()), sorted([FAST, SLOW]))

    def test_the_replay_counts_a_repeat_and_the_failure_it_would_lose(self):
        import replay_optimize as ro
        check = lambda code: ("verify", "pytest -q", code)  # noqa: E731
        # green then the same command again: the rule saves one, and loses nothing
        self.assertEqual(ro.replay([check(0), check(0)]), (2, 1, 0))
        # the repeat that failed is the failure the rule would have skipped
        self.assertEqual(ro.replay([check(0), check(1)]), (2, 1, 1))
        # a first run that fails is not green, so the next one is not a repeat
        self.assertEqual(ro.replay([check(1), check(0)]), (2, 0, 0))
        # an edit between them clears the green row: the tree moved, so the rule's
        # dirty-tree guard would have run the check again
        self.assertEqual(ro.replay([check(0), ("edit", "", 0), check(0)]), (2, 0, 0))
        self.assertEqual(ro.replay([check(0), ("edit", "", 0), check(1)]), (2, 0, 0))

    def test_baseline_compares_the_rule_against_the_policy(self):
        # review of plan 109, round 2: --baseline ran the baseline policy twice and
        # never the guarded one, so its two printed lines were the same numbers.
        # They differ on exactly this corpus shape - an edit between two green runs
        # of one command, which clears the guarded rule's green row and not the
        # baseline's.
        import replay_optimize as ro
        rows = [("verify", "pytest -q", 0), ("edit", "", 0), ("verify", "pytest -q", 0)]
        self.assertEqual(ro.replay(rows, guard=True), (2, 0, 0))
        self.assertEqual(ro.replay(rows, guard=False), (2, 1, 0))

    def test_a_green_row_over_a_dirty_tree_is_not_spent(self):
        # review of plan 109, F2: inside a turn the edits are uncommitted, so HEAD
        # does not move and a green row for that sha can describe a tree the
        # session has already changed
        sha = self.git("rev-parse", "--short", "HEAD")
        self.opt("record", FAST, "--seconds", "5", "--exit", "0", "--sha", sha)
        self.assertEqual(self.verdicts()[FAST], "already green")
        with open(os.path.join(self.repo, "a.py"), "w") as fh:
            fh.write("x = 1\n")
        self.assertEqual(self.verdicts()[FAST], "run now")

    def test_a_program_is_a_check_and_a_path_is_not(self):
        # review of plan 109, F3: the old rule kept `hooks/tezgah_store.py`, a path,
        # and dropped `ruff check .`
        path = os.path.join(self.repo, ".tezgah", "plans", "open", "001-a-plan.md")
        with open(path, "a") as fh:
            fh.write("- [ ] Linted: `ruff check .`, and `hooks/tezgah_store.py` is a "
                     "path rather than a check.\n")
        verdicts = self.verdicts()
        self.assertIn("ruff check .", verdicts)
        self.assertNotIn("hooks/tezgah_store.py", verdicts)

    def test_a_full_sha_row_matches_the_short_one(self):
        # review of plan 109, F4: `record --sha $(git rev-parse HEAD)` used to be
        # invisible to `next`, which reads the short sha
        full = self.git("rev-parse", "HEAD")
        self.opt("record", FAST, "--seconds", "5", "--exit", "0", "--sha", full)
        self.assertEqual(self.verdicts()[FAST], "already green")

    def test_push_coalesces_one_change(self):
        first = self.opt("push")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("git push -u origin main", first.stdout)
        second = self.opt("push")
        self.assertEqual(second.returncode, 1, second.stdout)
        self.assertIn("already pushed", second.stdout)
        # another commit is another change, so it may push
        self.git("commit", "-q", "--allow-empty", "-m", "next")
        third = self.opt("push")
        self.assertEqual(third.returncode, 0, third.stderr)

    def test_misuse_and_the_empty_case(self):
        self.assertEqual(self.opt("record", "x", "--exit", "0").returncode, 2)
        self.assertEqual(self.opt("record", "x", "--seconds", "-1", "--exit", "0")
                         .returncode, 2)
        self.assertEqual(self.opt("nonsense").returncode, 2)
        self.assertEqual(self.opt("next", "--nope").returncode, 2)
        # no plan and no --cmd: nothing to answer, and it says so rather than
        # guessing a command
        os.remove(os.path.join(self.repo, ".tezgah", "plans", "open",
                               "001-a-plan.md"))
        empty = self.opt("next")
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertIn("no candidate command", empty.stdout)


if __name__ == "__main__":
    unittest.main()
