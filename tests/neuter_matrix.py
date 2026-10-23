#!/usr/bin/env python3
"""Neuter matrix: every anti-shortcut guard is load-bearing in the suite.

Each mutant reverts one guard in a fresh clone of HEAD and runs the test modules
that cover the gate; a mutant whose run still passes is a guard no test notices.
Unmutated control clones run every module beside the mutants and must pass, or
no mutant result can be read. The idea is google/mantis's `reference/scripts/neuter_matrix.py`,
scoped to tezgah's mechanical integrity half (an internal adoption study,
decision d1, experiment E1).

    python3 tests/neuter_matrix.py            # exit 0 all killed, 1 a survivor or a red control
    python3 tests/neuter_matrix.py --only gate-task,no-verify   # those mutants (and the control)

Each mutant first runs alone the test that killed it last run, cached in
tests/neuter_killers.json; that test failing is the kill. When it passes or is
gone the mutant runs the modules (the one reading the mutated file first,
fail-fast) and its first failing test is the new entry; a survivor runs them
all. The cache only moves time: the control runs every cached killer alone too,
and one failing on the unmutated tree voids the run and is dropped from the cache.

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
("<class>", ...)` site of `_stop_block`, `_shape_block`, `_evidence_text` and
`_residual_block` (the functions `stop_triggers` reads; `_stop_block` returns
one class itself, `evidence tampered`), turned into `pass`, so the turn falls
through to the branches below it. A class
returned at two sites (`no ui_ok`, `no verify_ok`) gets a mutant per site. The
evidence classes are picked by the temporal spec (hooks/tezgah_stopspec.py):
its formulas are mutated in-process (`--stop-generated`), its decision list's
two guards by hand rows below. The guards around those classes - the pass
predicate, the empty-run read, the "doğrulanmadı" clear and the failed check
and classes it rests on, the lost call, the unseen pass, the bookkeeping and
session fallbacks, the refusal row, the residual class's work scope and its
blocker types - are hand-written rows below.
ponytail: the hand-written rows cover a guard only once a row names it."""
import ast
import concurrent.futures
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
INTEGRITY = "hooks/tezgah_integrity.py"
GATE = "hooks/tezgah_gate.py"
TASK = "hooks/tezgah_task.py"
PLUGIN = "hosts/opencode/plugins/tezgah.js"
CONTEXT = "hooks/tezgah_context.py"
STOPSPEC = "hooks/tezgah_stopspec.py"
MODULES = ("test_integrity.py", "test_gate.py", "test_opencode_plugin.py",
           "test_cursor_hook.py", "test_codex_hook.py", "test_control_plane.py",
           "test_omp_hook.py", "test_stop_after_block.py")
# the functions whose `return ("<class>", ...)` sites are the Stop classes
STOP_FUNCS = ("_stop_block", "_shape_block", "_evidence_text", "_residual_block")


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
    ("js-secret-prefix-runner", PLUGIN,
     anchored("           || !secretRunner(rest))\n", "           || false)\n"),
     "the opencode mirror of the env-prefix allowlist (plan 096)"),
    ("js-secret-runner-inline", PLUGIN,
     anchored("    if (arg === \"-\" || inline.test(arg)) return false\n", ""),
     "the opencode mirror of the inline-text hold for a script runner (plan 096)"),
    ("js-secret-relax-startup", PLUGIN,
     anchored("  const relax = !(SECRET_ENVIRON.test(c) || SECRET_STARTUP.test(c)\n",
              "  const relax = !(SECRET_ENVIRON.test(c)\n"),
     "the opencode mirror of the startup and trace variable hold (plan 096)"),
    ("js-secret-carried", PLUGIN,
     anchored("      if ([...text.matchAll(SECRET_VAR)].some((v) => carried.has(v[1] || v[2]))\n",
              "      if (false\n"),
     "the opencode mirror of the carried-name hold (plan 096)"),
    ("js-secret-owner-stage", PLUGIN,
     anchored("    if (owns && secretPrinter(text.slice(a, b))) return true\n",
              "    if (owns && secretPrinter(text)) return true\n"),
     "the opencode mirror of the sink-owning stage of the carried hold (plan 096)"),
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
     anchored("    return not status_hidden(entry.get(\"detail\"), entry.get(\"repo\"))\n",
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
    ("secret-prefix-runner", GATE,
     anchored("                or not _secret_runner(rest))\n",
              "                or False)\n"),
     "an env-prefixed key passes only for an allowlisted program (plan 096)"),
    ("secret-runner-inline", GATE,
     anchored("        if arg == \"-\" or inline.match(arg):\n", "        if False:\n"),
     "a script runner running its own text or stdin holds (plan 096)"),
    ("secret-runner-script", GATE,
     anchored("            return bool(SECRET_SCRIPT.fullmatch(arg))\n",
              "            return True\n"),
     "a script runner passes only with a script file (plan 096)"),
    ("secret-runner-named", GATE,
     anchored("    if not words or not SECRET_RUNNER.fullmatch(words[0]):\n",
              "    if not words or not SECRET_RUNNER.fullmatch(os.path.basename(words[0])):\n"),
     "a runner passes only named by itself, not by a path (plan 096)"),
    ("secret-relax-environ", GATE,
     anchored("    relax = not (SECRET_ENVIRON.search(c) or SECRET_STARTUP.search(c)\n",
              "    relax = not (SECRET_STARTUP.search(c)\n"),
     "a line reading /proc's environ gets no env-prefix relaxation (plan 096)"),
    ("secret-relax-startup", GATE,
     anchored("    relax = not (SECRET_ENVIRON.search(c) or SECRET_STARTUP.search(c)\n",
              "    relax = not (SECRET_ENVIRON.search(c)\n"),
     "a line setting a startup or trace variable gets none (plan 096)"),
    ("secret-relax-function", GATE,
     anchored("                 or SECRET_FUNCTION.search(masked) or SECRET_TRACE.search(masked))\n",
              "                 or SECRET_TRACE.search(masked))\n"),
     "a line defining a function gets no env-prefix relaxation (plan 096)"),
    ("secret-relax-trace", GATE,
     anchored("                 or SECRET_FUNCTION.search(masked) or SECRET_TRACE.search(masked))\n",
              "                 or SECRET_FUNCTION.search(masked))\n"),
     "a line turning the shell's trace on gets none (plan 096)"),
    ("secret-prefix-ascii", GATE,
     anchored("+\", re.ASCII)\n", "+\")\n"),
     "a non-ASCII word is not an assignment, as bash reads it (plan 096)"),
    ("secret-prefix-token", GATE,
     anchored("    return not (SECRET_TOKEN.search(rest) or SECRET_SINK.search(text[:m.end()])\n",
              "    return not (SECRET_SINK.search(text[:m.end()])\n"),
     "a token outside the env prefix still a write (plan 096)"),
    ("secret-prefix-sink", GATE,
     anchored("    return not (SECRET_TOKEN.search(rest) or SECRET_SINK.search(text[:m.end()])\n",
              "    return not (SECRET_TOKEN.search(rest)\n"),
     "a sink inside the env prefix's own value still a write (plan 096)"),
    ("secret-prefix-output", GATE,
     anchored("                or SECRET_SINK.search(SECRET_OUTPUT.sub(\" \", rest))\n", ""),
     "a git add or a curl trace after an env prefix still a write (plan 096)"),
    ("secret-carried", GATE,
     anchored("            if (carried & {a or b for a, b in SHELL_VAR.findall(text)}\n",
              "            if False and (carried & {a or b for a, b in SHELL_VAR.findall(text)}\n"),
     "a printer reading a name the line assigned a key (plan 096)"),
    ("secret-owner-stage", GATE,
     anchored("        if owns and _secret_printer(text[a:b]):\n",
              "        if owns and _secret_printer(text):\n"),
     "the carried hold reads the stage that owns the sink (plan 096)"),
    ("secret-owner-devnull", GATE,
     anchored("        owns = any(text[a + m.end():b].split()[:1] != [\"/dev/null\"]\n",
              "        owns = any(True or text[a + m.end():b].split()[:1] != [\"/dev/null\"]\n"),
     "a `> /dev/null` is not a file sink for the carried hold (plan 096)"),
    ("residual-said", INTEGRITY,
     anchored("            if BLOCKER_SAID.search(said) and (\n",
              "            if False and (\n"),
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
     anchored("    if _limit_move(item, failed, spawn_failed):\n",
              "    if False and _limit_move(item, failed, spawn_failed):\n"),
     "a model quota YETKİ refused while another allowed family is up"),
    ("residual-limit-env", INTEGRITY,
     anchored("    if _limit_move(item, failed, spawn_failed):\n",
              "    if \"access\" in kinds and _limit_move(item, failed, spawn_failed):\n"),
     "a model quota ORTAM refused like a YETKİ"),
    ("residual-limit-provider", INTEGRITY,
     anchored("        if not (tezgah_models.named_families(item)\n",
              "        if False and (tezgah_models.named_families(item)\n"),
     "a GitHub or npm rate limit stays a YETKİ"),
    ("residual-limit-settles", INTEGRITY,
     anchored("        _settle_slices(cwd)\n", ""),
     "the limit move is picked after the journal holds a stopped child's family"),
    ("scope-ready-globs", GATE,
     anchored("list(patterns) + [rel]]", "[rel]]"),
     "the scope refusal's ready allow line keeps the current globs"),
    ("scope-outside-no-allow", GATE,
     anchored("            if rel is None:\n                return TASK_SCOPE_OUTSIDE",
              "            if False:\n                return TASK_SCOPE_OUTSIDE"),
     "a target outside the repository gets no allow line"),
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
    ("loop-claim-fold", INTEGRITY,
     anchored("    quiet = _bookkeeping_turn(rows, GIT_READS)\n",
              "    quiet = _bookkeeping_turn(rows, GIT_READS, loops=True)\n"),
     "a done/tested claim over a turn of read loops keeps the worked fold"),
    ("loop-unseen-values", INTEGRITY,
     anchored("        if unseen and program not in OPTION_FREE and any(\"$\" in a for a in args):\n",
              "        if False:\n"),
     "a loop word or substitution output reaches only an option-free reader"),
    ("loop-name", INTEGRITY,
     anchored("words[i + 1:] and LOOP_NAME.fullmatch(words[i + 1])",
              "words[i + 1:]"),
     "a loop variable a shell reads (PATH, zsh's path) is no read"),
    ("loop-quoted-subst", INTEGRITY,
     anchored("(cmd.startswith(\"$(\", i) and (quote or not subst))",
              "(cmd.startswith(\"$(\", i) and not subst)"),
     "a `$( )` inside double quotes stays an effect in loop reads"),
    ("printf-assign", INTEGRITY,
     anchored("    \"printf\": re.compile(r\"-v\"),\n", ""),
     "`printf -v` assigns a variable, so it is no read"),
    ("operator-expansion", INTEGRITY,
     anchored("        if \"$\" in word and (\"[\" in word or \"$\" in PLAIN_DOLLAR.sub(\"\", word)):\n",
              "        if False:\n"),
     "a `$` word other than a plain `$name` (`$[x]`, `${x:--delete}`) is no read"),
    ("arith-expansion", INTEGRITY,
     anchored(" or \"$((\" in dq:", ":"),
     "a `$(( ))` is arithmetic, not a substitution whose body reads"),
    ("brace-expansion", INTEGRITY,
     anchored("BRACE_EXPANSION.search(lit) or ", ""),
     "an unquoted `{a,b}` is two words, so it is no read"),
    ("function-definition", INTEGRITY,
     anchored("re.search(r\"\\(\\s*\\)\", lit) or ", ""),
     "a function definition runs its body with unseen arguments: no read"),
    ("positional-unseen", INTEGRITY,
     anchored("    if subst and POSITIONAL.search(dq):\n        return True, \"\"\n", ""),
     "a positional parameter is a value loop reads never see"),
    ("line-continuation", INTEGRITY,
     anchored("            if cmd.startswith(CONTINUATION, i):\n                i += 2\n"
              "                continue\n", ""),
     "bash deletes a backslash-newline, so `$\\<nl>1` is `$1`"),
    ("comment-word-start", INTEGRITY,
     anchored("    return not prev or prev in WORD_BREAKS\n",
              "    return True\n"),
     "a `#` after an escaped character is part of the word, not a comment"),
    # review of plan 126, round 3h: one continuation and comment rule
    # (`_opens_comment`, CONTINUATION) for every shell reader
    ("heredoc-comment-word-start", INTEGRITY,
     anchored('if ch == "#" and _opens_comment(before):',
              'if ch == "#" and (i == 0 or cmd[i - 1] in " \\t\\n;&|()<>"):'),
     "a `#` mid-word opens no comment that hides a heredoc operator"),
    ("heredoc-continuation", INTEGRITY,
     anchored("            if cmd.startswith(CONTINUATION, i):\n"
              "                last = before\n", ""),
     "`x\\<nl>#<<cat` is the word `x#<<cat`: the heredoc reader sees the operator"),
    ("lines-continuation", INTEGRITY,
     anchored("            if not text.startswith(CONTINUATION, i):\n"
              "                cur.append(text[i:i + 2])\n",
              "            if True:\n                cur.append(text[i:i + 2])\n"),
     "`-de\\<nl>lete` is `-delete` to the segment reader"),
    ("lines-dq-continuation", INTEGRITY,
     anchored("if quote != '\"' or not text.startswith(CONTINUATION, i):", "if True:"),
     "a continuation inside double quotes is deleted too"),
    ("lines-comment-word-start", INTEGRITY,
     anchored('elif ch == "#" and _opens_comment(prev):',
              'elif ch == "#" and (not prev or prev.isspace() or prev in ";&|()<>"):'),
     "a `#` after a `\\r` or a non-breaking space is mid-word to the segment reader"),
    ("mask-word-break", INTEGRITY,
     anchored("start, prev = _opens_comment(_kept(ch, prev, parens)), ch",
              'start, prev = ch.isspace() or ch in ";&|()<>", ch'),
     "the masked text opens a comment only after a bash word break"),
    ("kept-paren", INTEGRITY,
     anchored("    elif ch == \")\" and parens and parens.pop():\n", "    elif False:\n"),
     "a `)` closing a substitution ends no word, so a `#` after it is no comment"),
    ("mask-continuation", INTEGRITY,
     anchored("                cuts.append((word, i))\n            else:\n"
              '                start, prev = False, ""\n',
              "                cuts.append((word, i))\n            if True:\n"
              '                start, prev = False, ""\n'),
     "a continuation in the masked text keeps the word state before it"),
    ("backtick-cont-hash", INTEGRITY,
     anchored("            while text.startswith(CONTINUATION, j):\n                j += 2\n", ""),
     "a continuation between a backtick and a `#` still leaves the `#` mid-word"),
    ("backtick-hash", INTEGRITY,
     anchored('                out.append(";" + text[i + 1:j] + "\\\\#")\n', ''),
     "a `#` after a backtick opens no comment in the gate's word reader"),
    ("gate-words-comment", GATE,
     anchored("        out.extend((word.translate(_UNESCAPE), bool(SHELL_OPS.match(word)))\n"
              "                   for word in words)\n",
              "        for word in words:\n            if word.startswith(\"#\"):\n"
              "                break\n"
              "            out.append((word.translate(_UNESCAPE), bool(SHELL_OPS.match(word))))\n"),
     "the gate's word reader drops only the comments `_shell_lines` drops"),
    ("gate-words-continuation", GATE,
     anchored('        str(command or ""))))\n',
              '        str(command or ""))).replace("\\\\\\n", " "))\n'),
     "the gate's word reader deletes a continuation only where bash does"),
    ("js-heredoc-comment-word-start", PLUGIN,
     anchored('if (ch === "#" && opensComment(before)) {',
              'if (ch === "#" && (i === 0 || " \\t\\n;&|()<>".includes(cmd[i - 1]))) {'),
     "the opencode mirror of the heredoc reader's comment rule"),
    ("js-heredoc-continuation", PLUGIN,
     anchored("      if (cmd.startsWith(CONTINUATION, i)) last = before\n", ""),
     "the opencode mirror of the heredoc reader's continuation"),
    ("js-lines-comment-word-start", PLUGIN,
     anchored('} else if (ch === "#" && opensComment(prev)) {',
              '} else if (ch === "#" && (!prev || /\\s/.test(prev) || ";&|()<>".includes(prev))) {'),
     "the opencode mirror of the segment reader's comment rule"),
    ("js-lines-continuation", PLUGIN,
     anchored("      if (!text.startsWith(CONTINUATION, i)) {\n"
              '        cur += text.slice(i, i + 2); prev = "_"; dollar = false\n',
              '      if (true) {\n        cur += text.slice(i, i + 2); prev = "_"; dollar = false\n'),
     "the opencode mirror of the segment reader's continuation"),
    ("js-lines-dq-continuation", PLUGIN,
     anchored("if (quote !== '\"' || !text.startsWith(CONTINUATION, i)) cur +=",
              "if (true) cur +="),
     "the opencode mirror of a continuation inside double quotes"),
    ("js-kept-paren", PLUGIN,
     anchored("  else if (ch === \")\" && parens.length && parens.pop()) return \"_\"\n", ""),
     "the opencode mirror of the substitution `)` rule"),
    ("js-mask-word-break", PLUGIN,
     anchored("      start = opensComment(kept(ch, prev, parens))\n",
              '      start = /\\s/.test(ch) || ";&|()<>".includes(ch)\n'),
     "the opencode mirror of the masked text's comment rule"),
    ("js-mask-continuation", PLUGIN,
     anchored('      if (text.startsWith(CONTINUATION, i)) cuts.push([word, i])\n'
              '      else { start = false; prev = "" }',
              '      if (false) cuts.push([word, i])\n'
              '      else { start = false; prev = "" }'),
     "the opencode mirror of the masked text's continuation"),
    ("js-shellwords-space", PLUGIN,
     anchored('    if (" \\t\\r\\n".includes(c)) { push(); i += 1; continue }\n',
              "    if (/\\s/.test(c)) { push(); i += 1; continue }\n"),
     "the opencode word reader splits only at shlex's whitespace"),
    ("fd-redirect-glued", INTEGRITY,
     anchored('        line = FD_REDIRECT.sub(r"\\2", line)\n', ""),
     "an fd number glued to its redirect is no program word, a spaced one is"),
    ("or-arm-branch", CONTEXT,
     anchored('        if "||" in sep:\n            alive, safe = not safe, True\n',
              '        if "||" in sep:\n            alive = True\n'),
     "an arm behind a `true` that cannot fail is no program the line runs"),
    ("js-or-arm-branch", PLUGIN,
     anchored('    if (sep.includes("||")) {\n      alive = !safe\n', '    if (sep.includes("||")) {\n      alive = true\n'),
     "the opencode mirror of the dead `||` arm"),
    ("set-options", INTEGRITY,
     anchored("            if not _set_options(args):\n", "            if False:\n"),
     "`set` is a read only with shell options, never positional words"),
    ("residual-list-blocks", INTEGRITY,
     anchored("                    if cls not in LIST_BLOCKS:\n",
              "                    if True:\n"),
     "a residual refusal of a backed claim kept out of false completion"),
    ("needless-default", INTEGRITY,
     anchored("or DEFAULT_MARK.search(_tr_lower(re.split(",
              "or False and DEFAULT_MARK.search(_tr_lower(re.split("),
     "a question inside a defaulted approval batch is no needless ask"),
    ("needless-never-default", INTEGRITY,
     anchored("if (never_default(last) or PLAN_BUILD",
              "if (False or PLAN_BUILD"),
     "a never-default step (a spend over the cap) is asked, not refused"),
    ("needless-plan-build", INTEGRITY,
     anchored("or PLAN_BUILD.search(_tr_lower(t))",
              "or False and PLAN_BUILD.search(_tr_lower(t))"),
     "building a plan the turn wrote is asked, not refused (plan 105)"),
    ("needless-granted", INTEGRITY,
     anchored("return last if outward <= set(granted()) else None",
              "return None"),
     "a question about a granted outward step is a needless ask"),
    ("needless-process", INTEGRITY,
     anchored("    if PROCESS_ASK.search(low):\n", "    if False:\n"),
     "a process question at the end is a needless ask"),
    ("needless-wired", INTEGRITY,
     anchored("    asked = needless_ask(text, lambda: grants_in_force(session_id))\n",
              "    asked = None\n"),
     "the needless-ask class is asked at the Stop exit"),
    ("grant-polarity", CONTEXT,
     anchored("        if not lift and _refuses(text, start, at, to, stop, *rules):\n",
              "        if False:\n"),
     "a sentence that forbids, complains or asks grants nothing"),
    ("grant-soft-verb", CONTEXT,
     anchored("        soft.fullmatch(m.group(0)) and not outward_classes(text[start:m.start()]))",
              "        False)"),
     "'durma' or 'unutma' with no outward word before it takes no grant back"),
    ("lift-outward-classes", CONTEXT,
     anchored("        classes = (sorted(outward_classes(text[at:to])) if rules == \"outward\"",
              "        classes = (sorted(outward_classes(text[at:to])) or [\"all\"] if rules == \"outward\""),
     "a negated outward step lifts only the class it names, never all"),
    ("grant-lift", CONTEXT,
     anchored("            out.append((clause, (\"lift:\" if lift else \"\") + cls))",
              "            out.append((clause, cls))"),
     "a lift shape lifts, it never grants"),
    ("ask-granted", GATE,
     anchored("    if granted and not never_default(text):", "    if False:"),
     "an ask about a granted step is named as granted"),
    ("decision-options", INTEGRITY,
     anchored("IRREVERSIBLE_SAID.search(said) or OPTIONS_MARK.search(_tr_lower(said))",
              "True"),
     "a KARAR item with no options or default is no blocker"),
    ("ask-advice-default", GATE,
     anchored('if defaulted < asked else ""', 'if False else ""'),
     "an ask-tool question with no recommended option is warned"),
    ("lost-began", INTEGRITY,
     anchored("    if lost:\n", "    if False and lost:\n"),
     "a claim resting on a check whose result never arrived"),
    ("unseen-pass", INTEGRITY,
     anchored("    unseen = (done or verified) and any(\n",
              "    unseen = False and any(\n"),
     "a claim resting on a check nobody saw pass (plan 101)"),
    ("spec-fresh-unread", STOPSPEC,
     anchored("        if not unread:\n            return None\n",
              "        return None\n"),
     "a fresh tree still owes an unread external claim its read"),
    ("spec-work-flag", STOPSPEC,
     anchored("    elif worked or holds(\"worked\"):\n", "    elif holds(\"worked\"):\n"),
     "the selector's work flag (a lost check, an unseen pass, the session paths)"),
    ("bookkeeping", INTEGRITY,
     anchored("def _bookkeeping_turn(rows, git=GIT_BOOKKEEPING, loops=False):\n",
              "def _bookkeeping_turn(rows, git=GIT_BOOKKEEPING, loops=False):\n"
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


# the module that reads a mutated file runs first, so a killed mutant stops
# there; the order only moves time, every module still runs on a survivor
FIRST = {GATE: "test_gate.py", INTEGRITY: "test_integrity.py",
         PLUGIN: "test_opencode_plugin.py"}
# {mutant: the test id that killed it last run}: a cache, never a verdict
KILLERS = os.path.join(HERE, "tests", "neuter_killers.json")
FAILED = re.compile(r"^(?:FAIL|ERROR): (\w+) \(([\w.]+)\)", re.M)


def failed_ids(stderr):
    """The test ids unittest names FAIL/ERROR in `stderr`, in order. A module
    that failed to import (`unittest.loader._FailedTest`) or a class fixture is
    no test id to rerun."""
    out = []
    for method, where in FAILED.findall(stderr):
        # 3.11+ prints `(module.Class.method)`, 3.10 `(module.Class)`
        test = where if where.endswith("." + method) else where + "." + method
        if method.startswith("test") and not test.startswith("unittest."):
            out.append(test)
    return out


def unittest_argv(module, *tests):
    # -f: a mutant is killed by its first failing test, not by the module's last
    argv = [sys.executable, "-m", "unittest", "discover", "-f", "-s", "tests", "-p", module]
    for test in tests:
        argv += ["-k", test]
    return argv


def subprocess_runner(argv, cwd, env):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)  # a hook test reading an inherited tty hangs


def verdict(first, known, tree, env, runner=subprocess_runner):
    """(exit status, last line, killer test id or None) for one mutated tree.
    The test that killed this mutant last run (`known`) goes alone first; it
    kills only when that very id fails, so a renamed or deleted test falls
    through to the modules - `first` at the front, fail-fast - where the first
    failing test is the new killer. A survivor runs every module."""
    if known:
        proc = runner(unittest_argv(known.split(".")[0] + ".py", known), tree, env)
        if known in failed_ids(proc.stderr):
            return proc.returncode or 1, "%s failed (cached killer)" % known, known
    last = ""
    for module in ((first,) if first else ()) + tuple(m for m in MODULES if m != first):
        # its own HOME and TMPDIR, as each control module has: state one module
        # leaves must not kill a mutant in the next (review of plan 099, F2)
        own = {k: os.path.join(env[k], module) for k in ("HOME", "TMPDIR") if k in env}
        for path in own.values():
            os.makedirs(path, exist_ok=True)
        proc = runner(unittest_argv(module), tree, dict(env, **own))
        lines = [x for x in proc.stderr.splitlines() if x.strip()]
        last = "%s: %s" % (module, lines[-1] if lines else "")
        if proc.returncode:
            ids = failed_ids(proc.stderr)
            return proc.returncode, last, ids[0] if ids else None
    return 0, last, None


def prepare(name, edit, work):
    """(tree, env, error) for one clone of HEAD mutated by `edit` ((file, apply)
    or None); error is the reason when the edit cannot apply."""
    tree = os.path.join(work, name)
    # --shared borrows HEAD's objects instead of copying them: the clone only
    # reads them, and nothing collects garbage in HERE while the matrix runs
    subprocess.run(["git", "clone", "-q", "--shared", HERE, tree], check=True)
    if edit:
        path = os.path.join(tree, edit[0])
        with open(path, encoding="utf-8") as fh:
            text, error = edit[1](fh.read())
        if error:
            return tree, None, "edit: %s in %s" % (error, edit[0])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    home, tmp = os.path.join(work, name + "-home"), os.path.join(work, name + "-tmp")
    os.makedirs(home)
    os.makedirs(tmp)
    return tree, dict(os.environ, HOME=home, TMPDIR=tmp, TEZGAH_UPDATE_CHECK="0"), None


def run(name, edit, known, work):
    """(name, exit status, last line, killer) for one mutant; status 2 with the
    reason when the edit cannot apply."""
    tree, env, error = prepare(name, edit, work)
    if error:
        return name, 2, error, None
    return (name,) + verdict(FIRST.get(edit[0]), known, tree, env)


def control(name, module, test, work, runner=subprocess_runner):
    """None when the unmutated clone `name` passes `module` - or, given `test`,
    passes that cached killer alone - else why not. A killer that fails alone
    on the unmutated tree leans on an earlier test and proves nothing on a
    mutant. Each module and each killer is its own clone and pool task: run in
    one clone in order, the control was the matrix's critical path."""
    tree, env, _error = prepare(name, None, work)
    # with `test`, the very command a mutant's cached run is
    proc = runner(unittest_argv(module, *((test,) if test else ())), tree, env)
    if test:
        return "%s fails alone" % test if test in failed_ids(proc.stderr) else None
    if not proc.returncode:
        return None
    # a red control is read on a runner nobody can open: say why
    lines = [x for x in proc.stderr.splitlines() if x.strip()]
    return "%s: %s\n%s" % (module, lines[-1] if lines else "", "\n".join(
        x for x in lines if x.startswith(("FAIL:", "ERROR:")) or "Error" in x)[-4000:])


def updated(killers, results, names):
    """The cache after a run: entries of mutants not in `names` dropped, each
    killed mutant's killer recorded, the entry of a mutant with none (a survivor,
    an edit that did not apply, a kill no test id names) dropped."""
    out = {k: v for k, v in killers.items() if k in names}
    for name, _status, _last, killer in results:
        if killer:
            out[name] = killer
        else:
            out.pop(name, None)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--stop-generated" in argv:
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
    names = {m[0] for m in mutants}
    if "--only" in argv:
        # one mutant (a new deny rule's row) without the whole matrix; the
        # control still runs every module
        only = set(argv[argv.index("--only") + 1].split(",")) \
            if argv.index("--only") + 1 < len(argv) else set()
        if not only or only - names:
            print("--only: no mutant named %s" % ",".join(sorted(only - names) or ["(none)"]))
            return 2
        mutants = tuple(m for m in mutants if m[0] in only)
    rows = [m for m in mutants if m[1] != PLUGIN or shutil.which("node")]
    skipped = [m[0] for m in mutants if m not in rows]
    try:
        with open(KILLERS, encoding="utf-8") as fh:
            killers = json.load(fh)
    except FileNotFoundError:
        killers = {}
    work = tempfile.mkdtemp(prefix="tezgah-neuter-")
    try:
        # the control runs beside the mutants rather than before them: its
        # verdict is read first, and a red control discards every result.
        # Its checks go in first, so they end early instead of in the tail.
        # Half the cores: every worker forks a unittest process of its own,
        # and cpu_count workers ran the cached matrix slower (304 s against
        # 240 s, one session on 10 cores, 2026-10-13)
        workers = max(1, (os.cpu_count() or 2) // 2)
        alone = sorted({killers[m[0]] for m in rows if m[0] in killers})
        checks = [(m, None) for m in MODULES] + [(t.split(".")[0] + ".py", t) for t in alone]
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            controls = [pool.submit(control, "control-%d" % i, module, test, work)
                        for i, (module, test) in enumerate(checks)]
            results = list(pool.map(lambda m: run(m[0], m[1:3], killers.get(m[0]), work),
                                    rows))
            red = [(test, why) for (_m, test), f in zip(checks, controls)
                   for why in [f.result()] if why]
        if red:
            lonely = {test for test, _why in red if test}
            if lonely:
                # dropped from the cache, so the next run reads those mutants
                # through their modules
                write_killers(killers, {k: v for k, v in killers.items() if v not in lonely})
            print("FAIL: the unmutated control is red, so no mutant can be read (%s)%s" % (
                "; ".join(why for _test, why in red),
                " - dropped from tests/neuter_killers.json, rerun" if lonely else ""))
            return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    # a `--only` or node-less run keeps every other mutant's entry
    write_killers(killers, updated(killers, results, names))
    survivors = 0
    for (name, status, last, _killer), mutant in zip(results, rows):
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


def write_killers(old, new):
    if new != old:
        with open(KILLERS, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(new, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    sys.exit(main())
