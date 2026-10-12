"""Gate latency: p95 of `tezgah_gate.decision(..., record=False)` over 200
common calls, in a throwaway HOME and repo (plan 054, part 12).

    python3 tests/bench_gate_latency.py              # this tree's hooks/
    python3 tests/bench_gate_latency.py --hooks DIR  # another revision's hooks/
    python3 tests/bench_gate_latency.py --plans      # two phased plans, one in a worktree

To compare revisions, export one's hooks and point --hooks at it:
`git archive 44c45e0 hooks | tar -x -C /tmp/base`, then `--hooks /tmp/base/hooks`.
The numbers are this machine's, on a fixture repo: a property of the code path,
not of a live session. The dry run writes no row, so the ledger stays empty and
the rules that read session history read none. `--plans` arms the task rule as
plan 093 runs it: two plans in `implementation`, the second held by a linked
worktree on its `plan/002-` branch, and three more calls write into that
worktree from the main checkout.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

import support

# the shapes a session sends most: shell checks, bookkeeping and reads, and the
# write tools; 20 of them, ten rounds
CALLS = (
    ("Bash", {"command": "git status --short"}),
    ("Bash", {"command": "git diff --stat"}),
    ("Bash", {"command": "git log --oneline -5"}),
    ("Bash", {"command": "python3 -m unittest discover -s tests > /tmp/check.log 2>&1"}),
    ("Bash", {"command": "pytest -q"}),
    ("Bash", {"command": "ls -la src"}),
    ("Bash", {"command": "cat README.md"}),
    ("Bash", {"command": "rg -n 'def main' src"}),
    ("Bash", {"command": "npm test 2>&1 | tail -20"}),
    ("Bash", {"command": "git add -A && git commit -m 'fix: parser'"}),
    ("Bash", {"command": "cd src && python3 -c 'print(1)'"}),
    ("Bash", {"command": "cat <<'E' > notes.txt\nhello\nE"}),
    ("Read", {"file_path": "README.md"}),
    ("Read", {"file_path": "src/app.py"}),
    ("Grep", {"pattern": "main", "path": "src"}),
    ("Glob", {"pattern": "**/*.py"}),
    ("Edit", {"file_path": "src/app.py", "old_string": "x = 1",
              "new_string": "x = 2"}),
    ("Write", {"file_path": "src/new.py", "content": "def f():\n    return 1\n"}),
    ("Write", {"file_path": "tests/test_app.py",
               "content": "import unittest\n\nclass T(unittest.TestCase):\n"
                          "    def test_a(self):\n        self.assertTrue(1)\n"}),
    ("Task", {"subagent_type": "general-purpose", "prompt": "look at src"}),
)
ROUNDS = 10


def child(repo, wt=""):
    t0 = time.perf_counter()
    import tezgah_gate  # noqa: E402
    imported = (time.perf_counter() - t0) * 1000
    calls = CALLS + ((
        ("Write", {"file_path": os.path.join(wt, "docs", "a.md"), "content": "a\n"}),
        ("Edit", {"file_path": os.path.join(wt, "docs", "a.md"), "old_string": "a",
                  "new_string": "b"}),
        ("Bash", {"command": "echo x > %s" % os.path.join(wt, "docs", "b.md")}),
    ) if wt else ())
    times, denied = [], 0
    for _ in range(ROUNDS):
        for tool, inp in calls:
            t = time.perf_counter()
            reason = tezgah_gate.decision(tool, dict(inp), repo, "bench",
                                          record=False)
            times.append((time.perf_counter() - t) * 1000)
            denied += reason is not None
    times.sort()

    def pct(p):
        return round(times[min(len(times) - 1, int(p * len(times)))], 3)

    # `denied` shows the gate was armed: the piped `npm test | tail` is refused
    print(json.dumps({"hooks": os.path.dirname(tezgah_gate.__file__),
                      "calls": len(times), "denied": denied,
                      "import_ms": round(imported, 3),
                      "p50_ms": pct(0.50), "p95_ms": pct(0.95),
                      "max_ms": round(times[-1], 3)}))


def seed_plans(repo, wt, env):
    """Plans 001 (the main checkout's files) and 002 (`docs/**`), both in
    `implementation`, and a linked worktree on 002's own branch."""
    git = ["git", "-C", repo, "-c", "user.name=b", "-c", "user.email=b@localhost"]
    with open(os.path.join(repo, ".gitignore"), "w") as fh:
        fh.write("/.tezgah/\n")
    subprocess.run(git + ["add", "-A"], env=env, check=True)
    subprocess.run(git + ["commit", "-qm", "init"], env=env, check=True)
    subprocess.run(git + ["worktree", "add", "-q", "-b", "plan/002-docs", wt],
                   env=env, check=True)
    directory = os.path.join(repo, ".tezgah", "plans", "open")
    os.makedirs(directory)
    for name, scope in (("001-main.md", ("src/**", "tests/**", "notes.txt")),
                        ("002-docs.md", ("docs/**",))):
        with open(os.path.join(directory, name), "w") as fh:
            fh.write("---\nid: %s\nstatus: open\nphase: implementation\n"
                     "allowed_paths:\n%s---\n" % (name[:3], "".join(
                         "  - %s\n" % glob for glob in scope)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hooks", default=support.HOOKS)
    ap.add_argument("--plans", action="store_true")
    ap.add_argument("--child", help=argparse.SUPPRESS)
    ap.add_argument("--wt", default="", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        child(args.child, args.wt)
        return 0
    with tempfile.TemporaryDirectory() as home:
        roots = os.path.join(home, "Projects")
        repo = os.path.join(roots, "proj")
        os.makedirs(os.path.join(repo, "src"))
        os.makedirs(os.path.join(repo, "tests"))
        for name, text in (("README.md", "# proj\n"), ("src/app.py", "x = 1\n")):
            with open(os.path.join(repo, name), "w") as fh:
                fh.write(text)
        env = support.base_env(home, [roots], {"PYTHONPATH": os.path.abspath(args.hooks)})
        subprocess.run(["git", "init", "-q", repo], env=env, check=True)
        wt = os.path.join(roots, "proj-002") if args.plans else ""
        if wt:
            seed_plans(repo, wt, env)
        out = subprocess.run([sys.executable, os.path.abspath(__file__), "--child",
                              os.path.realpath(repo),
                              "--wt", os.path.realpath(wt) if wt else ""],
                             env=env, check=True,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True)
        sys.stdout.write(out.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
