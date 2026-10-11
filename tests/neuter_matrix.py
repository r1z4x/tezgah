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
("<class>", ...)` site of `_stop_block`, `_shape_block`, `_evidence_block` and
`_residual_block` (the functions `stop_triggers` reads; `_stop_block` returns
one class itself, `evidence tampered`), turned into `pass`, so the turn falls
through to the branches below it. A class
returned at two sites (`no ui_ok`, `no verify_ok`) gets a mutant per site. The
guards around those classes - the pass predicate, the empty-run read, the
"doğrulanmadı" clear and the failed check and classes it rests on, the lost
call, the bookkeeping and session fallbacks, the refusal row, the residual
class's work scope and its blocker types - are hand-written rows below.
ponytail: the hand-written rows cover a guard only once a row names it."""
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
TASK = "hooks/tezgah_task.py"
PLUGIN = "hosts/opencode/plugins/tezgah.js"
MODULES = ("test_integrity.py", "test_gate.py", "test_opencode_plugin.py",
           "test_cursor_hook.py", "test_codex_hook.py", "test_control_plane.py",
           "test_omp_hook.py", "test_stop_after_block.py")
# the functions whose `return ("<class>", ...)` sites are the Stop classes
STOP_FUNCS = ("_stop_block", "_shape_block", "_evidence_block", "_residual_block")


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
     anchored("        return (None, None)\n    return admitted\n",
              "        return verdict\n    return admitted\n"),
     "the \"doğrulanmadı\" clear of the check-repair classes"),
    ("admission-needs-a-failure", INTEGRITY,
     anchored("        if not verdict[0] or not _failed_since_change(rows):\n",
              "        if not verdict[0]:\n"),
     "the admission resting on a check that failed since the newest change"),
    ("admission-owed", INTEGRITY,
     anchored("        if owed[0] and owed[0] not in ADMITTED_CLASSES and not (\n",
              "        if False and not (\n"),
     "a screen or design proof the admitted turn still owes"),
    ("admission-screen-attempt", INTEGRITY,
     anchored("                owed[0] == \"no ui_ok\" and _proof_attempt_failed(rows)):\n",
              "                owed[0] == \"no ui_ok\"):\n"),
     "only a failed screen or design check standing for the proof it attempted"),
    ("admission-external", INTEGRITY,
     anchored("        if external is not None and _external_read_row(rows) < 0:\n"
              "            return (\"no external read\", _external_text(external, *where))\n",
              "        if False:\n"
              "            return (\"no external read\", _external_text(external, *where))\n"),
     "an external claim the admitted turn still owes a read for"),
    ("admission-prose", INTEGRITY,
     anchored("    if not NEGATED.search(_prose(text)):\n",
              "    if not NEGATED.search(text):\n"),
     "the admission read on the reply's prose, code blanked"),
    ("residual-scope", INTEGRITY,
     anchored("    if handed or any(str(r.get(\"kind\")) in STEP_KINDS for r in rows):\n",
              "    if True:\n"),
     "the residual class asked only of a turn that did work"),
    ("residual-handed", INTEGRITY,
     anchored("        if handed and not left and not any(\n",
              "        if False and not left and not any(\n"),
     "a subagent's untyped residual items owed by the parent's reply"),
    ("residual-unscoped", INTEGRITY,
     anchored("        if left and session_id and not _turn_count(_ledger_lines(_path(session_id))):\n",
              "        if False:\n"),
     "a ledger with no turn marker left unjudged for residuals"),
    ("stopped-slice-owner", INTEGRITY,
     anchored("            if rec.get(\"status\") == \"stopped\" and rec.get(\"parent\") == session_id:\n",
              "            if rec.get(\"status\") == \"stopped\":\n"),
     "a stopped slice refuses only the session that spawned it"),
    ("stopped-slice-switch", INTEGRITY,
     anchored("    if not (session_id and cwd) or off(\"slices-off\"):\n",
              "    if not (session_id and cwd):\n"),
     "slices-off turns the stopped-slice class off"),
    ("ready-pending", INTEGRITY,
     anchored("             if status == \"pending\" and text not in blocked]\n",
              "             if False]\n"),
     "a pending todo item counted as a ready step"),
    ("ready-typed", INTEGRITY,
     anchored("             if BLOCKER_SAID.search(_prose(line)) or BLOCKER_TRIED.search(_prose(line))]\n",
              "             ]\n"),
     "a ready step named without a blocker is still left"),
    ("ready-scope", INTEGRITY,
     anchored("    if not any(str(r.get(\"kind\")) in STEP_KINDS for r in rows):\n"
              "        return []\n", ""),
     "the ready-steps class asked only of a turn that did work"),
    ("ready-switch", INTEGRITY,
     anchored("    if not session_id or off(\"orchestrate-off\"):\n        return []\n",
              "    if not session_id:\n        return []\n"),
     "orchestrate-off turns the ready-steps class off"),
    ("ready-slices", INTEGRITY,
     anchored("    return [h for h in heads\n"
              "            if not any(word(sid, h.lower()) or word(h.lower(), task)\n"
              "                       for sid, task in running)]\n",
              "    return heads\n"),
     "a step an open slice of this session works on is not ready"),
    ("ready-task", INTEGRITY,
     anchored("r.get(\"task\") or str(r.get(\"brief\") or \"\").rsplit(\"\\n\\n\", 1)[-1]",
              "r.get(\"brief\")"),
     "a slice's own task, not the batch's shared context, takes a step"),
    ("ready-word", INTEGRITY,
     anchored("or word(h.lower(), task)\n", "or h.lower() in task\n"),
     "a step is taken only by a word-bounded match of the whole head"),
    ("ready-agent", INTEGRITY,
     anchored("    return next((r for r in rows if r.get(\"kind\") == \"todo\" and not r.get(\"agent\")), None)\n",
              "    return next((r for r in rows if r.get(\"kind\") == \"todo\"), None)\n"),
     "a subagent's todo list is not the parent's queue"),
    ("ready-wait-idle", GATE,
     anchored("        if name and name != \"wait\" and name not in TODO_TOOLS:\n"
              "            return None\n",
              "        if False:\n"
              "            return None\n"),
     "the idle-wait warning only while nothing ran since the spawn"),
    ("ready-wait-switch", GATE,
     anchored("    if off(\"orchestrate-off\"):\n        return None\n", ""),
     "orchestrate-off turns the idle-wait warning off"),
    ("lease-switch", GATE,
     anchored("    if writes and not off(\"orchestrate-off\") and not off(\"slices-off\"):\n",
              "    if writes:\n"),
     "orchestrate-off turns the lease rule off"),
    ("lease-main-checkout", GATE,
     anchored("            if not top and tree and tree != repo and os.path.isdir(tree):\n",
              "            if False:\n"),
     "a slice whose record names a worktree writing into the main checkout"),
    ("lease-claude", GATE,
     anchored("    spawn = spawn_of(session_id) or ((session_id, agent) if agent else None)\n",
              "    spawn = spawn_of(session_id)\n"),
     "a Claude background child mapped to its slice by its agent_id"),
    ("lease-closed-owner", TASK,
     anchored("                     and r.get(\"status\") == \"open\" and r[\"id\"] != me\n",
              "                     and r[\"id\"] != me\n"),
     "a closed owner frees the files it leased"),
    ("lease-own-closed", GATE,
     anchored("            if not me or me.get(\"status\") != \"open\":\n",
              "            if not me:\n"),
     "a slice whose own record closed is no longer held to the lease"),
    ("lease-tezgah", GATE,
     anchored("            if rel.startswith((\".tezgah/\", \"../\")) or rel == \".tezgah\":\n",
              "            if rel.startswith(\"../\"):\n"),
     "the main checkout's .tezgah stays free for a slice"),
    ("residual-said", INTEGRITY,
     anchored("            if BLOCKER_SAID.search(said):\n",
              "            if False:\n"),
     "a KARAR or GERİ ALINAMAZ item kept as a blocker"),
    ("residual-quoted", INTEGRITY,
     anchored("    return bool(spawn_failed and SPAWN_WORDS.search(_tr_lower(item))) or \\\n"
              "        _quotes_failure(item, failed)\n",
              "    return True\n"),
     "a YETKİ or ORTAM item backed by a failed command or a failed spawn"),
    ("residual-spawn-words", INTEGRITY,
     anchored("    return bool(spawn_failed and SPAWN_WORDS.search(_tr_lower(item))) or \\\n",
              "    return bool(spawn_failed) or \\\n"),
     "a failed spawn backs only an item about the spawn"),
    ("residual-closed-label", INTEGRITY,
     anchored("    if not BLOCKER_LABEL.match(_tr_lower(label)):\n        return False\n",
              "    if False:\n        return False\n"),
     "only an item under a blocker label is closed by its own report"),
    ("subagent-dedupe-agent", INTEGRITY,
     anchored("               and (not parent or entry.get(\"agent\") == (str(agent) if agent else None))\n",
              "               and True\n"),
     "one subagent_end row per child in the parent's ledger"),
    ("sqlite-db-uri", INTEGRITY,
     anchored("            ro = ro or (db.startswith(\"file:\") and \"mode=ro\" in db.partition(\"?\")[2])\n",
              "            ro = ro or any(\"mode=ro\" in a for a in args)\n"),
     "sqlite3 read-only only from the option or the database URI"),
    ("residual-typed", INTEGRITY,
     anchored("            if BLOCKER_TRIED.search(said) and _tried_holds(item, said, failed,\n",
              "            if _quotes_failure(item, failed) or _tried_holds(item, said, failed,\n"),
     "a quoted failure kept only with its YETKİ or ORTAM type"),
    ("residual-error-type", INTEGRITY,
     anchored("               for k in kinds):\n        return False\n",
              "               for k in kinds) and False:\n        return False\n"),
     "a YETKİ or ORTAM item whose quoted error is of its type"),
    ("residual-spawn-class", INTEGRITY,
     anchored("               and r.get(\"fail_class\") in SPAWN_FAIL_CLASSES for r in rows)\n",
              "               for r in rows)\n"),
     "only a spawn the provider failed backs an unquoted YETKİ or ORTAM"),
    ("residual-limit-moves", INTEGRITY,
     anchored("    if kinds & {\"Y\", \"A\"} and _limit_can_move(item):\n",
              "    if False and kinds & {\"Y\", \"A\"} and _limit_can_move(item):\n"),
     "a quota YETKİ refused while another funded family is up"),
    ("scope-ready-globs", GATE,
     anchored("list(patterns) + [rel or spelled]", "[rel or spelled]"),
     "the scope refusal's ready allow line keeps the current globs"),
    ("residual-no-match", INTEGRITY,
     anchored("        if (r.get(\"kind\") != \"verify_fail\" and len(segs) == 1\n",
              "        if False and (r.get(\"kind\") != \"verify_fail\" and len(segs) == 1\n"),
     "a grep that matched nothing is no failed command"),
    ("residual-no-match-alone", INTEGRITY,
     anchored("        if (r.get(\"kind\") != \"verify_fail\" and len(segs) == 1\n"
              "                and segs[0][0] in NO_MATCH_PROGRAMS):\n",
              "        if (r.get(\"kind\") != \"verify_fail\" and segs\n"
              "                and segs[-1][0] in NO_MATCH_PROGRAMS):\n"),
     "a grep behind another command keeps the line's failure"),
    ("residual-now-closed", INTEGRITY,
     anchored("    return (len(sentences) > 1 and bool(NOW.search(last))\n",
              "    return (True or len(sentences) > 1 and bool(NOW.search(last))\n"),
     "only a blocker reported gone closes its item"),
    ("residual-bare-label", INTEGRITY,
     anchored("        if m and not re.search(r\"\\s\", core[m.end():]):\n",
              "        if m:\n"),
     "a colon-less line over a list is a label only as the residual word"),
    ("subagent-parent-ledger", INTEGRITY,
     anchored("        note(parent or session_id, kind, detail, id=key, **shape)\n",
              "        note(session_id, kind, detail, id=key, **shape)\n"),
     "an omp subagent's end recorded in its parent's ledger"),
    ("reask-rows", INTEGRITY,
     anchored("    if end != first:\n", "    if False:\n"),
     "the reply after an omp re-ask judged on the chained turns' rows"),
    ("quiet-reads", INTEGRITY,
     anchored("    quiet = _bookkeeping_turn(rows, GIT_READS)\n",
              "    quiet = _bookkeeping_turn(rows)\n"),
     "a turn is quiet only when every command is a known read"),
    ("residual-list-blocks", INTEGRITY,
     anchored("                    if cls not in LIST_BLOCKS:\n",
              "                    if True:\n"),
     "a residual refusal of a backed claim kept out of false completion"),
    ("lost-began", INTEGRITY,
     anchored("    if lost:\n", "    if False and lost:\n"),
     "a claim resting on a check whose result never arrived"),
    ("bookkeeping", INTEGRITY,
     anchored("def _bookkeeping_turn(rows, git=GIT_BOOKKEEPING):\n",
              "def _bookkeeping_turn(rows, git=GIT_BOOKKEEPING):\n"
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
    ("reask-class", INTEGRITY,
     anchored("    return (int(after_block or 0) >= STOP_REASKS or cls in refused\n",
              "    return (int(after_block or 0) >= STOP_REASKS or False\n"),
     "one Stop class refused twice in a turn"),
    ("reask-budget", INTEGRITY,
     anchored("            or len(refused) >= STOP_REASKS)\n", "            or False)\n"),
     "a third Stop refusal in one turn"),
    ("reask-row", INTEGRITY,
     anchored("               and (entry.get(\"detail\") == detail or not reason)\n",
              "               and True\n"),
     "a second refusal of the same reply text left uncounted"),
    ("reask-chain", INTEGRITY,
     anchored("    while end and len(refused) < STOP_REASKS:\n", "    while False:\n"),
     "omp's continuation turn read as a new user turn"),
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
    if "--stop-generated" in sys.argv[1:]:
        # the temporal spec's table mutants: in-process, no clone (plan 063)
        import stop_spec_eval
        return stop_spec_eval.main(["--mutants"])
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
