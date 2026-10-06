"""Gate latency: p95 of `tezgah_gate.decision(..., record=False)` over 200
common calls, in a throwaway HOME and repo (plan 054, part 12).

    python3 tests/bench_gate_latency.py              # this tree's hooks/
    python3 tests/bench_gate_latency.py --hooks DIR  # another revision's hooks/

To compare revisions, export one's hooks and point --hooks at it:
`git archive 44c45e0 hooks | tar -x -C /tmp/base`, then `--hooks /tmp/base/hooks`.
The numbers are this machine's, on a fixture repo: a property of the code path,
not of a live session. The dry run writes no row, so the ledger stays empty and
the rules that read session history read none.
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


def child(repo):
    t0 = time.perf_counter()
    import tezgah_gate  # noqa: E402
    imported = (time.perf_counter() - t0) * 1000
    times, denied = [], 0
    for _ in range(ROUNDS):
        for tool, inp in CALLS:
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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hooks", default=support.HOOKS)
    ap.add_argument("--child", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        child(args.child)
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
        out = subprocess.run([sys.executable, os.path.abspath(__file__), "--child",
                              os.path.realpath(repo)], env=env, check=True,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True)
        sys.stdout.write(out.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
