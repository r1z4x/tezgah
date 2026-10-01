#!/usr/bin/env python3
"""Neuter matrix: every anti-shortcut guard is load-bearing in the suite.

Each mutant reverts one guard in a fresh clone of HEAD and runs the test modules
that cover the gate; a mutant whose run still passes is a guard no test notices.
An unmutated control clone runs first the same way and must pass, or no mutant
result can be read. The idea is google/mantis's `reference/scripts/neuter_matrix.py`,
scoped to tezgah's mechanical integrity half (research line
`repo-adoption-google-mantis`, decision d1, experiment E1).

    python3 tests/neuter_matrix.py            # exit 0 all killed, 1 a survivor or a red control

It reads HEAD, not the working tree: commit first. A mutant on the opencode
plugin needs `node`; without it that mutant prints `SKIP` (the plugin tests skip
too), and `TEZGAH_E2E_STRICT=1` turns the skip into a failure, as the e2e
scripts do. ponytail: the list is hand-written; a guard added later is covered
only once a row names it."""
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
INTEGRITY = "hooks/tezgah_integrity.py"
PLUGIN = "hosts/opencode/plugins/tezgah.js"
MODULES = ("test_integrity.py", "test_gate.py", "test_opencode_plugin.py",
           "test_cursor_hook.py", "test_codex_hook.py")
# (id, file, anchor that must occur exactly once, replacement, guard reverted)
MUTANTS = (
    ("no-verify", INTEGRITY, "    if NO_VERIFY.search(c) and GITISH.search(c):\n",
     "    if False and NO_VERIFY.search(c) and GITISH.search(c):\n",
     "--no-verify beside a git command"),
    ("skip-env", INTEGRITY, "    if SKIP_ENV.search(c) and GITISH.search(c):\n",
     "    if False and SKIP_ENV.search(c) and GITISH.search(c):\n",
     "SKIP=/HUSKY=0 beside a git command"),
    ("hooks-path", INTEGRITY, "def _hooks_path_set(c, raw):\n",
     "def _hooks_path_set(c, raw):\n    return False\n",
     "core.hooksPath assignment beside a commit/push"),
    ("neuter", INTEGRITY, "    if verify_command(c) and NEUTER.search(c):\n",
     "    if False and verify_command(c) and NEUTER.search(c):\n",
     "a check chained with || true"),
    ("piped", INTEGRITY, "def piped_check(cmd):\n",
     "def piped_check(cmd):\n    return None\n", "a check piped into a trimmer"),
    ("skip-edit", INTEGRITY, "def shortcut_edit(inp):\n",
     "def shortcut_edit(inp):\n    return None\n", "a test skip added by an edit"),
    ("mask", INTEGRITY, "def mask(text):\n",
     "def mask(text):\n    return str(text or \"\")\n",
     "quoted text and heredocs read as data"),
    ("js-hooks-path", PLUGIN, "function hooksPathSet(c, raw) {\n",
     "function hooksPathSet(c, raw) {\n  return false\n",
     "the opencode mirror of the hooksPath rule"),
)


def run(name, edit, work):
    """(name, exit status, last line) for one clone of HEAD, mutated by `edit`."""
    tree = os.path.join(work, name)
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", HERE, tree], check=True)
    if edit:
        path = os.path.join(tree, edit[0])
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if text.count(edit[1]) != 1:
            return name, 2, "anchor matched %d times in %s" % (text.count(edit[1]), edit[0])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(edit[1], edit[2]))
    home, tmp = os.path.join(work, name + "-home"), os.path.join(work, name + "-tmp")
    os.makedirs(home)
    os.makedirs(tmp)
    env = dict(os.environ, HOME=home, TMPDIR=tmp)
    status, last = 0, ""
    for module in MODULES:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", module],
            cwd=tree, env=env, capture_output=True, text=True)
        lines = [x for x in proc.stderr.splitlines() if x.strip()]
        last = "%s: %s" % (module, lines[-1] if lines else "")
        if proc.returncode:
            return name, proc.returncode, last
    return name, status, last


def main():
    strict = os.environ.get("TEZGAH_E2E_STRICT") == "1"
    if not shutil.which("git"):
        print("SKIP: git is missing")
        return 1 if strict else 0
    rows = [m for m in MUTANTS if m[1] != PLUGIN or shutil.which("node")]
    skipped = [m[0] for m in MUTANTS if m not in rows]
    # a short base: the stale-evidence reasons shorten a long path, and under
    # macOS's /var/folders/.../T/ that cuts the name the tests look for
    work = tempfile.mkdtemp(prefix="nm-", dir="/tmp" if os.path.isdir("/tmp") else None)
    try:
        name, status, last = run("control", None, work)
        if status:
            print("FAIL: the unmutated control is red, so no mutant can be read (%s)" % last)
            return 1
        workers = max(1, (os.cpu_count() or 2) // 2)
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(lambda m: run(m[0], m[1:4], work), rows))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    survivors = 0
    for (name, status, last), mutant in zip(results, rows):
        if status == 2 and last.startswith("anchor"):
            print("FAIL %-14s %s" % (name, last))
            survivors += 1
        elif status:
            print("ok   %-14s killed (%s)" % (name, last))
        else:
            print("FAIL %-14s survived: no test notices %s" % (name, mutant[4]))
            survivors += 1
    for name in skipped:
        print("SKIP %-14s node is missing" % name)
    print("%d mutant(s), %d killed, %d failed, %d skipped" % (
        len(MUTANTS), len(rows) - survivors, survivors, len(skipped)))
    return 1 if survivors or (strict and skipped) else 0


if __name__ == "__main__":
    sys.exit(main())
