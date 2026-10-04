#!/usr/bin/env python3
"""End to end: the plan and decision record rules inside one throwaway project.

The post-0.24 work reads a plan's body in one place and refuses with it in two:
`bin/tezgah-task`, the command a person runs, and the gate on every write. This
runs the CLI half, end to end, in a real `git` repository built under tempfile
with HOME and TEZGAH_ROOTS redirected into it, so the machine's own config, its
ledger and its `.tezgah/` are never read - the same isolation the suite uses.

Five rules, each a step below:

  1. a plan whose Acceptance names no command cannot enter `implementation`, and
     `tezgah-render-table --acceptance --strict` exits 1 on the same item, so
     the refusal a person meets and the report CI runs name one list;
  2. with one item naming the command the move succeeds and names the plan's
     `checkpoint:`;
  3. a dirty tree records `checkpoint: pending <sha>`, and the commit the
     refusal names clears it - the state a reader used to meet as `pending`
     forever;
  4. a plan whose `spike:` has no `spike_recorded:` is refused the same way,
     because the build would start on the guess the spike exists to retire;
  5. an ADR with no `status:` is refused, and the same record with one is
     printed.

Not collected by the stdlib suite (the name does not match `test*.py`), the same
shape as `tests/e2e_packaged_install.py`. Needs `git` on PATH: without it it
prints `SKIP: ...` and exits 0, or 1 under `TEZGAH_E2E_STRICT=1`, so CI cannot
go green on a skip.

    TEZGAH_E2E_STRICT=1 python3 tests/e2e_plan_flow.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STRICT = os.environ.get("TEZGAH_E2E_STRICT") == "1"
TASK = os.path.join(ROOT, "bin", "tezgah-task")
DECISIONS = os.path.join(ROOT, "bin", "tezgah-decisions")
ACCEPTANCE = os.path.join(ROOT, "skills", "plan-add", "render_table.py")


def skipped(reason):
    """A missing tool is a SKIP - a failure when CI asked for no skips."""
    print("SKIP: %s" % reason)
    return 1 if STRICT else 0


def argv(script):
    """A tree script as a command line: itself when it can be started (POSIX,
    where the shebang is the shipped entry point), else the interpreter that
    runs this probe, because on Windows it has no shebang to run."""
    if os.name == "nt" or not os.access(script, os.X_OK):
        return [sys.executable, script]
    return [script]


class Project:
    """One throwaway project: a real repository the CLIs run inside."""

    def __init__(self, home, roots):
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": home,
            "LANG": "C.UTF-8",
            "TEZGAH_ROOTS": roots,
            # paths that do not exist: no codegraph auto-index, no orx routing,
            # no consult option - so no model and no index can be reached here
            "TEZGAH_CODEGRAPH_BIN": os.path.join(home, "no-codegraph"),
            "TEZGAH_ORX_BIN": os.path.join(home, "no-orx"),
            "TEZGAH_CONSULT_CLIS": "",
        }
        self.root = os.path.join(roots, "project")

    def run(self, line):
        return subprocess.run(line, cwd=self.root, env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True)

    def git(self, *args):
        return self.run(["git"] + list(args))

    def cli(self, script, *args):
        return self.run(argv(script) + list(args))

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def setup(self):
        os.makedirs(self.root, exist_ok=True)
        self.git("init", "-q", ".")
        self.git("config", "user.name", "e2e")
        self.git("config", "user.email", "e2e@localhost")
        self.write(".gitignore", "/.tezgah/\n")
        self.write("README.md", "start\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "start")
        os.makedirs(os.path.join(self.root, ".tezgah", "plans", "open"),
                    exist_ok=True)


def plan_body(pid, extra="", items=()):
    """A plan file: the frontmatter the CLI reads plus the Acceptance items.

    `allowed_paths:` is the list the plan declares its own scope in, so `start`
    without `--allow` is held to it - the shape `plan-add` writes."""
    text = ["---", "id: %s" % pid, "title: a plan under test",
            "status: open", "phase: discovery", "allowed_paths:", "  - hooks/**"]
    text.extend(extra.splitlines() if extra else [])
    text.extend(["---", "", "## Acceptance", ""])
    text.extend("- [ ] %s" % item for item in items)
    return "\n".join(text) + "\n"


def flow_row(fails, check, problem):
    """One check's outcome: a line, plus the problem when it did not hold."""
    if problem:
        print("FAIL: %s - %s" % (check, problem))
        fails.append(check)
    else:
        print("OK:   %s" % check)


def first_line(proc):
    return (proc.stdout or "").strip().splitlines()[0] if proc.stdout.strip() else "(no output)"


def check_acceptance_gap(project):
    """1: a plan whose every item names no command is refused the move, and the
    report CI runs exits 1 on the same item."""
    project.write(".tezgah/plans/open/001-gap.md",
                  plan_body("001", items=["the thing works and looks right"]))
    started = project.cli(TASK, "start", "001", "--phase", "discovery")
    moved = project.cli(TASK, "phase", "implementation")
    report = project.run(argv(ACCEPTANCE) + ["--acceptance", "--strict"])
    problems = []
    if started.returncode != 0:
        problems.append("start refused: %s" % first_line(started))
    if moved.returncode == 0:
        problems.append("the move was allowed")
    if "cannot enter implementation" not in moved.stdout:
        problems.append("no refusal text: %s" % first_line(moved))
    if report.returncode != 1 or "name no command" not in report.stdout:
        problems.append("the report read %d: %s"
                        % (report.returncode, first_line(report)))
    return "; ".join(problems)


def check_move_and_checkpoint(project):
    """2: with one item naming the command the move succeeds and writes the
    checkpoint - the record the phase returns to."""
    project.write(".tezgah/plans/open/001-gap.md",
                  plan_body("001", items=["`python3 -m unittest` is green"]))
    moved = project.cli(TASK, "phase", "implementation")
    status = project.cli(TASK, "status")
    problems = []
    if moved.returncode != 0:
        problems.append("move refused: %s" % first_line(moved))
    if "checkpoint:" not in moved.stdout:
        problems.append("no checkpoint written: %s" % first_line(moved))
    if "phase implementation" not in status.stdout:
        problems.append("status reads: %s" % first_line(status))
    return "; ".join(problems)


def check_pending_clears(project):
    """3: a dirty tree records `pending <sha>`; the commit that moves HEAD off
    it answers the refusal the gate then reads."""
    project.git("checkout", "-q", "-b", "work")
    project.write(".tezgah/plans/open/002-dirty.md",
                  plan_body("002", items=["`python3 -m unittest` is green"]))
    project.cli(TASK, "start", "002", "--phase", "discovery")
    sha = project.head()
    project.write("README.md", "start\nuncommitted work\n")
    moved = project.cli(TASK, "phase", "implementation")
    problems = []
    if "checkpoint: pending on %s" % sha not in moved.stdout:
        problems.append("no pending record: %s" % first_line(moved))
    project.git("add", "-A")
    project.git("commit", "-qm", "the pre-work commit")
    status = project.cli(TASK, "status")
    if "satisfied - HEAD moved off %s" % sha not in status.stdout:
        problems.append("the commit did not clear it: %s" % first_line(status))
    return "; ".join(problems)


def check_spike_blocks(project):
    """4: `implementation` is refused while the plan's spike is unanswered."""
    project.write(".tezgah/plans/open/003-spike.md",
                  plan_body("003", extra="spike: does the grid render at 40 columns?",
                            items=["`python3 -m unittest` is green"]))
    project.cli(TASK, "start", "003", "--phase", "discovery")
    moved = project.cli(TASK, "phase", "implementation")
    problems = []
    if moved.returncode == 0 or "spike is unanswered" not in moved.stdout:
        problems.append("the unanswered spike passed: %s" % first_line(moved))
    project.write(".tezgah/plans/open/003-spike.md",
                  plan_body("003", extra="spike: does the grid render at 40 columns?\n"
                                         "spike_recorded: 2026-09-30 - 40 columns wrap",
                            items=["`python3 -m unittest` is green"]))
    answered = project.cli(TASK, "phase", "implementation")
    if answered.returncode != 0:
        problems.append("the answered spike was refused: %s" % first_line(answered))
    return "; ".join(problems)


def check_adr_status(project):
    """5: the record layer refuses a decision with no status, and prints one
    that carries it."""
    record = ("---\nid: 001\ntitle: a decision\nstatus: %s\ndate: 2026-09-30\n"
              "---\n\n## Context\n")
    project.write(".tezgah/decisions/001-record.md", record % "")
    refused = project.cli(DECISIONS, "check")
    project.write(".tezgah/decisions/001-record.md", record % "accepted")
    accepted = project.cli(DECISIONS, "check")
    problems = []
    if refused.returncode != 1 or "no `status:`" not in refused.stdout:
        problems.append("no refusal: %s" % first_line(refused))
    if accepted.returncode != 0 or "accepted" not in accepted.stdout:
        problems.append("the record was not read: %s" % first_line(accepted))
    return "; ".join(problems)


CHECKS = (
    ("a plan whose Acceptance names no command cannot enter implementation",
     check_acceptance_gap),
    ("one command-bearing item moves the phase and writes the checkpoint",
     check_move_and_checkpoint),
    ("a dirty tree records pending, and the commit clears it",
     check_pending_clears),
    ("an unanswered spike blocks implementation",
     check_spike_blocks),
    ("an ADR with no status is refused, with one it is printed",
     check_adr_status),
)


def main():
    if not shutil.which("git"):
        return skipped("git is not on PATH")
    fails = []
    with tempfile.TemporaryDirectory(prefix="tezgah-plan-flow-") as tmp:
        home = os.path.join(tmp, "home")
        roots = os.path.join(tmp, "Projects")
        os.makedirs(home)
        os.makedirs(roots)
        project = Project(home, roots)
        project.setup()
        for title, check in CHECKS:
            flow_row(fails, title, check(project))
    if fails:
        print("FAILED: %d of %d checks" % (len(fails), len(CHECKS)))
        return 1
    print("OK: %d checks" % len(CHECKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
