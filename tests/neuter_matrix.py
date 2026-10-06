#!/usr/bin/env python3
"""Neuter matrix: every anti-shortcut guard is load-bearing in the suite.

Each mutant reverts one guard in a fresh clone of HEAD and runs the test modules
that cover the gate; a mutant whose run still passes is a guard no test notices.
An unmutated control clone runs first the same way and must pass, or no mutant
result can be read. The idea is google/mantis's `reference/scripts/neuter_matrix.py`,
scoped to tezgah's mechanical integrity half (an internal adoption study,
decision d1, experiment E1).

    python3 tests/neuter_matrix.py            # exit 0 all killed, 1 a survivor or a red control

It reads HEAD, not the working tree: commit first. A mutant on the opencode
plugin needs `node`; without it that mutant prints `SKIP` (the plugin tests skip
too), and `TEZGAH_E2E_STRICT=1` turns the skip into a failure, as the e2e
scripts do.

Two halves. The gate half is generated: one `gate-<rule>` mutant per rule name
`decision` refuses with, read from HEAD's hooks/tezgah_gate.py by the same AST
reader `bin/tezgah-docs --citations` checks the rule list with (`rule_sites`).
A mutant replaces every `return _deny(session_id, "<rule>", ...)` statement of
that rule with `pass` at its own line span, so the rule's guards still run and
let the call fall through to the rules below it - the closest thing to the rule
being reverted. Returning None from `decision` there instead would skip every
later rule too and kill the mutant for the wrong reason. The span, not a text
anchor, is the address because one rule repeats the same `_deny` line (task four
times, shortcut and attribution three).

The Stop half is generated the same way: one `stop-<class>` mutant per `return
("<class>", ...)` site of `_stop_block`, `_shape_block` and `_evidence_block`
(the functions `stop_triggers` reads; `_stop_block` returns one class itself,
`evidence tampered`), turned into `pass`, so the turn falls through to the branches below it. A class
returned at two sites (`no ui_ok`, `no verify_ok`) gets a mutant per site. The
guards around those classes - the pass predicate, the empty-run read, the
"doğrulanmadı" clear, the lost call, the bookkeeping and session fallbacks, the
refusal row - are hand-written rows below. ponytail: the hand-written rows cover
a guard only once a row names it."""
import ast
import concurrent.futures
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
INTEGRITY = "hooks/tezgah_integrity.py"
GATE = "hooks/tezgah_gate.py"
PLUGIN = "hosts/opencode/plugins/tezgah.js"
MODULES = ("test_integrity.py", "test_gate.py", "test_opencode_plugin.py",
           "test_cursor_hook.py", "test_codex_hook.py", "test_control_plane.py",
           "test_omp_hook.py", "test_stop_after_block.py")
# the functions whose `return ("<class>", ...)` sites are the Stop classes
STOP_FUNCS = ("_stop_block", "_shape_block", "_evidence_block")


def anchored(anchor, replacement):
    """An edit that replaces `anchor`, which must occur exactly once."""
    def apply(text):
        count = text.count(anchor)
        if count != 1:
            return None, "anchor matched %d times" % count
        return text.replace(anchor, replacement), None
    return apply


def spanned(marker, spans):
    """An edit that turns each (first, last) line span - a return whose first
    line holds `marker` - into `pass` at its indentation, keeping the file's
    line count."""
    def apply(text):
        lines = text.splitlines(keepends=True)
        for first, last in spans:
            line = lines[first - 1] if first <= len(lines) else ""
            if marker not in line:
                return None, "line %d no longer holds `%s`" % (first, marker)
            lines[first - 1] = line[:len(line) - len(line.lstrip())] + "pass\n"
            for i in range(first, last):
                lines[i] = "\n"
        return "".join(lines), None
    return apply


# (id, file, edit, guard reverted)
MUTANTS = (
    ("no-verify", INTEGRITY,
     anchored("    if (NO_VERIFY.search(c) and GITISH.search(c)) or _git_skips_hooks(cmd):\n",
              "    if False or _git_skips_hooks(cmd):\n"),
     "--no-verify beside a git command"),
    ("skip-env", INTEGRITY,
     anchored("    if SKIP_ENV.search(c) and GITISH.search(c):\n",
              "    if False and SKIP_ENV.search(c) and GITISH.search(c):\n"),
     "SKIP=/HUSKY=0 beside a git command"),
    ("hooks-path", INTEGRITY,
     anchored("def _hooks_redirect(cmd):\n", "def _hooks_redirect(cmd):\n    return False\n"),
     "core.hooksPath assignment beside a commit/push"),
    ("neuter", INTEGRITY,
     anchored("    if verify_command(c) and NEUTER.search(c):\n",
              "    if False and verify_command(c) and NEUTER.search(c):\n"),
     "a check chained with || true"),
    ("piped", INTEGRITY,
     anchored("def piped_check(cmd):\n", "def piped_check(cmd):\n    return None\n"),
     "a check piped into a trimmer"),
    ("skip-edit", INTEGRITY,
     anchored("def shortcut_edit(inp):\n", "def shortcut_edit(inp):\n    return None\n"),
     "a test skip added by an edit"),
    ("mask", INTEGRITY,
     anchored("def mask(text):\n", "def mask(text):\n    return str(text or \"\")\n"),
     "quoted text and heredocs read as data"),
    ("js-hooks-path", PLUGIN,
     anchored("function hooksRedirect(cmd) {\n", "function hooksRedirect(cmd) {\n  return false\n"),
     "the opencode mirror of the hooksPath rule"),
    # the Stop guards around the generated `stop-<class>` rows
    ("passing-check", INTEGRITY,
     anchored("    if entry.get(\"kind\") != \"verify_ok\" or entry.get(\"empty_run\"):\n",
              "    return entry.get(\"kind\") == \"verify_ok\"\n"
              "    if entry.get(\"kind\") != \"verify_ok\" or entry.get(\"empty_run\"):\n"),
     "a verify_ok row counted as a pass with no exit, output or pipe check"),
    ("empty-run-row", INTEGRITY,
     anchored("    if entry.get(\"kind\") != \"verify_ok\" or entry.get(\"empty_run\"):\n",
              "    if entry.get(\"kind\") != \"verify_ok\":\n"),
     "a pass whose output said it ran nothing (`empty_run`)"),
    ("empty-run-read", INTEGRITY,
     anchored("def ran_nothing(result):\n", "def ran_nothing(result):\n    return False\n"),
     "the empty-run read of a check's output (`ran_nothing`)"),
    ("pipe-pass", INTEGRITY,
     anchored("    return not status_hidden(entry.get(\"detail\"))\n",
              "    return True\n"),
     "a pass whose status a pipe or a later command owns"),
    ("negated", INTEGRITY,
     anchored("    if NEGATED.search(t):\n        return (None, None)\n",
              "    if False and NEGATED.search(t):\n        return (None, None)\n"),
     "the \"doğrulanmadı\" clear of the claim branches"),
    ("lost-began", INTEGRITY,
     anchored("    if lost:\n", "    if False and lost:\n"),
     "a claim resting on a check whose result never arrived"),
    ("bookkeeping", INTEGRITY,
     anchored("def _bookkeeping_turn(rows):\n",
              "def _bookkeeping_turn(rows):\n"
              "    return any(str(r.get(\"kind\")) in WORK_KINDS for r in rows)\n"),
     "work after a pass excused as bookkeeping"),
    ("idle-claim", INTEGRITY,
     anchored("            if refused[0]:\n                return refused\n",
              "            if False:\n                return refused\n"),
     "a claim in an idle turn judged against the session before it"),
    ("refusal-row", INTEGRITY,
     anchored("                else \"refusal\")\n", "                else \"claim\")\n"),
     "a blocked reply that claimed nothing recorded as a refusal"),
    ("other-repo-cause", INTEGRITY,
     anchored("        return \"other repo\"\n", "        return \"no check\"\n"),
     "the `other repo` cause on a no verify_ok row"),
)


def docs_module():
    """bin/tezgah-docs, loaded by path (it has no `.py` in its name)."""
    path = os.path.join(HERE, "bin", "tezgah-docs")
    loader = importlib.machinery.SourceFileLoader("tezgah_docs_neuter", path)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("tezgah_docs_neuter", loader))
    loader.exec_module(module)
    return module


def gate_mutants(text):
    """One (id, file, edit, guard) row per rule `decision` refuses with in `text`."""
    spans = {}
    for rule, first, last, _switches, _tools in docs_module().rule_sites(text):
        spans.setdefault(rule, []).append((first, last))
    return [("gate-" + rule, GATE, spanned('_deny(session_id, "%s"' % rule, where),
             "the gate's `%s` rule" % rule)
            for rule, where in spans.items()]


def stop_mutants(text):
    """One (id, file, edit, guard) row per `return ("<class>", ...)` site of
    STOP_FUNCS in `text`, numbered when a class has more than one site."""
    sites = []
    for node in ast.walk(ast.parse(text)):
        if not (isinstance(node, ast.FunctionDef) and node.name in STOP_FUNCS):
            continue
        for sub in ast.walk(node):
            value = sub.value if isinstance(sub, ast.Return) else None
            if isinstance(value, ast.Tuple) and value.elts \
                    and isinstance(value.elts[0], ast.Constant) \
                    and isinstance(value.elts[0].value, str):
                sites.append((value.elts[0].value, sub.lineno, sub.end_lineno))
    sites.sort(key=lambda site: site[1])
    rows = []
    for cls, first, last in sites:
        same = [s for s in sites if s[0] == cls]
        name = "stop-" + cls.replace(" ", "-").replace("_", "-")
        if len(same) > 1:
            name += "-%d" % (same.index((cls, first, last)) + 1)
        rows.append((name, INTEGRITY, spanned('return ("%s"' % cls, [(first, last)]),
                     "the Stop class `%s` (line %d)" % (cls, first)))
    return rows


def run(name, edit, work):
    """(name, exit status, last line) for one clone of HEAD, mutated by `edit`
    ((file, apply) or None); status 2 with the reason when the edit cannot apply."""
    tree = os.path.join(work, name)
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", HERE, tree], check=True)
    if edit:
        path = os.path.join(tree, edit[0])
        with open(path, encoding="utf-8") as fh:
            text, error = edit[1](fh.read())
        if error:
            return name, 2, "edit: %s in %s" % (error, edit[0])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    home, tmp = os.path.join(work, name + "-home"), os.path.join(work, name + "-tmp")
    os.makedirs(home)
    os.makedirs(tmp)
    env = dict(os.environ, HOME=home, TMPDIR=tmp, TEZGAH_UPDATE_CHECK="0")
    status, last = 0, ""
    for module in MODULES:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", module],
            cwd=tree, env=env, capture_output=True, text=True,
            stdin=subprocess.DEVNULL)  # a hook test reading an inherited tty hangs
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
    def head(path):
        return subprocess.run(["git", "-C", HERE, "show", "HEAD:" + path],
                              capture_output=True, text=True, check=True).stdout
    mutants = MUTANTS + tuple(gate_mutants(head(GATE))) \
        + tuple(stop_mutants(head(INTEGRITY)))
    rows = [m for m in mutants if m[1] != PLUGIN or shutil.which("node")]
    skipped = [m[0] for m in mutants if m not in rows]
    work = tempfile.mkdtemp(prefix="tezgah-neuter-")
    try:
        name, status, last = run("control", None, work)
        if status:
            print("FAIL: the unmutated control is red, so no mutant can be read (%s)" % last)
            return 1
        workers = max(1, (os.cpu_count() or 2) // 2)
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(lambda m: run(m[0], m[1:3], work), rows))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    survivors = 0
    for (name, status, last), mutant in zip(results, rows):
        if status == 2 and last.startswith("edit:"):
            print("FAIL %-24s %s" % (name, last))
            survivors += 1
        elif status:
            print("ok   %-24s killed (%s)" % (name, last))
        else:
            print("FAIL %-24s survived: no test notices %s" % (name, mutant[3]))
            survivors += 1
    for name in skipped:
        print("SKIP %-24s node is missing" % name)
    print("%d mutant(s), %d killed, %d failed, %d skipped" % (
        len(mutants), len(rows) - survivors, survivors, len(skipped)))
    return 1 if survivors or (strict and skipped) else 0


if __name__ == "__main__":
    sys.exit(main())
