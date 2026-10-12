#!/usr/bin/env python3
"""The tool gate, shared by every host that can block a tool call.

Rules, all only inside a tezgah root:
  1. a grep-only explorer subagent is refused, with the graph tools named as the
     replacement;
  2. the FIRST code-symbol search of a session (grep/search/find tool, or
     grep/rg run through a shell; a plain word is literal text and passes) in a
     repo whose own codegraph index exists is nudged toward the graph once;
     every later one passes, with graph_advice's line beside it while the index
     is current.
  3. a git/gh command that writes an artifact carrying an AI/model credit
     (Co-Authored-By, "Generated with", a robot emoji, ...) is refused.
  4. an identical call that already failed LOOP_ATTEMPTS times in the current
     user turn is refused (`loop`), the same number for every failure class: the
     class names why the last attempt failed, it does not buy another identical
     one. An identical call attempted more than RETRY_CEILING times in the
     session is refused whatever its outcomes were (`retry`). Both read
     hooks/tezgah_integrity.prior_calls and both are under the `verify-off` kill
     switch the integrity rule shares.
  5. a credential on its way into a file is refused (secret): a shell command
     whose own text carries a `name=value` / bearer token next to a sink (a
     redirect, `tee`, `git add` or a curl trace), a `git add` that names a
     credential file (`.env`, a key file; `.env.example` and `.env.sample` are
     templates), and any write - a write tool in every dialect, an apply_patch
     file by file, a heredoc body - that lands a token with a known credential
     prefix (`ghp_`, `sk-live-`, ...) the replaced text did not carry.
  6. a write to a file another session wrote inside RACE_WINDOW_MIN is refused
     (`race`), naming the other session and the file, because the failure it
     closes - one session overwriting another's work from a stale read - leaves
     no trace in either transcript. A shell command's redirect or `tee` target
     is a write here, and in the task rule below, like a write tool's path.
  7. when the current user turn has run past DRIFT_STEPS work rows, the next
     effectful call gets the standing constraints re-stated once (`drift`), in
     the gate's reason string, which is the only channel a PreToolUse hook has.
     The marker row is written before the deny, so the identical call passes on
     the next attempt.
  8. a write while an active task is set - a plan file under .tezgah/plans/open whose
     frontmatter carries a valid `phase` - is refused when that phase is one
     that only reads, or when the file is outside the task's `allowed_paths`
     refused (`task`). The record is written by bin/tezgah-task, which the
     orchestrating session runs itself as the work moves, so the refusal leans
     on a state the CLI vetted (an Acceptance item per command, an answered
     spike, a checkpoint) rather than one this gate inferred: no active task
     means no requirement, and the rule invents nothing. The record also
     carries where the phase returns to - a
     `checkpoint:` sha, or `pending` while the tree still holds work no commit
     names - and a write in `implementation` is refused while it reads `pending`
     and the tree is dirty, so the phase's work starts from a named state rather
     than on top of uncommitted changes; the per-file snapshots are not one
     state to return to. A write whose target IS that record is refused too:
     retyping the frontmatter would skip the preconditions the CLI checks. The
     phase covers the shell too, because the
     write tools are not the only way to change a file: with them refused, the
     armed arm wrote the target with a heredoc redirect in 3 of 25 runs, so a
     reading phase refuses a shell command that writes. A code-execution tool is
     a third route the phase does not cover: the same block measured one row in
     25 writing the target through `eval` after the write tools and the shell
     were both refused, and that one is named rather than closed. The `task-off`
     kill switch removes all three.
  9. a `git commit` (or `--amend`) is refused while the newest check recorded in
     this session failed (`order`): a commit is a claim that the tree passed, and
     the state it would freeze is the one a check just rejected. The state is the
     Stop rule's own fold over the ledger tail, so no check at all and a passing
     newest check both pass - a docs-only commit is not this rule's - and the
     refusal names the failed check and no command, because what lifts it is
     making the newest check green. It rides the `verify-off` switch.
 10. a check piped into a trimmer or filter (`pytest | tail`, `| grep`, `| wc`)
     is refused (`piped`): the line's status is the trimmer's, so the ledger
     records the check as ran and never as passed, and the Stop rule refuses
     every claim the run was meant to carry. The refusal names both ways out -
     output to a file that is then read, or a `set -o pipefail;` prefix, which
     integrity reads as decisive. It rides the `verify-off` switch.
     The three rules that read the text a write lands - the shortcut rule, the
     attribution rule above and the credential rule's prefixed-token half -
     read it on every write route: a write tool in every dialect (an
     apply_patch file by file) and the body a heredoc writes
     (shell_write_body). The write tools and the shell are disjoint sets, so
     the heredoc route was refused by nothing, and it is the one E7c measured
     an armed session taking.
 11. a write, delete, move or chmod of tezgah's own control plane is refused
     (`control`): a kill switch or opt-in marker (tezgah_paths.SWITCHES under
     OFF_DIRS), ~/.config/tezgah, the evidence ledger and the session state in
     the cache, the hook registration files and the installed hook tree, a
     repo's `.no-*` marks, the repository's git hooks, and the CLIs that change
     that state (control_reason); a forced `git add` of `.tezgah/` and an open
     plan's delete or move leave a `disarm` row instead (CONTROL_EVIDENCE). It
     runs first after the root check, and no switch but `pretooluse-off`
     removes it: every other switch is one of the files it protects.
Adapters translate the returned reason into their own permission envelope.
"""
import hashlib
import json
import os
import re
import shlex
import time

import tezgah_store

from tezgah_integrity import (BASH_TOOLS, BEGAN_KIND, ENV_WORD, GIT_VALUE_OPTS,
                              HEREDOC_RISK, HOOKS_KEY, PATCH_FILE,
                              PLAIN_TAIL, SECRET_PREFIXED, STEP_KINDS,
                              WRITE_TOOLS, _blank_heredocs, _heredocs, bind_session,
                              _shell_commands, _shell_lines, _shell_segments,
                              _turn_start,
                              _unquoted_backticks, call_id, cut, events,
                              heredoc_bodies, mask, mcp_class, mcp_text, note,
                              prior_calls, scratch_target, shortcut_command,
                              shortcut_edit, turn_rows, verify_command,
                              write_texts)
from tezgah_integrity import SUBAGENT_TOOLS, TODO_TOOLS, newest_todo, ready_heads
from tezgah_paths import (CACHE, CONFIG_DIR, HOST_DIRS, OFF_DIRS, PLUGIN_ROOT,
                          REPO_MARKS, SWITCHES, _toplevel, cache_dir, fallback_cache,
                          linked_main, off, root_for, roots)

try:  # The ordering rule's two readers (the newest check's state, folded the way
    # the Stop rule folds it, and the command of that check for the refusal), and
    # the plan rule's fold over this turn's write rows. Newer than some checkouts,
    # and a missing name costs the rule, never the session - this import runs on
    # every gated call.
    from tezgah_integrity import _failed_check, _last_verify, turn_rows
except ImportError:  # pragma: no cover - only on an integrity module without them
    _failed_check, _last_verify, turn_rows = None, None, None

try:  # The race rule reads the write history through tezgah_integrity; that
    # reader is newer than some checkouts of the module, and a missing name must
    # cost the rule, never the session (this import runs on every gated call).
    from tezgah_integrity import spawn_of, writers_elsewhere
except ImportError:  # pragma: no cover - only on an integrity module without it
    spawn_of = writers_elsewhere = None

try:  # The bytes a write is about to change. The snapshot module is newer than
    # some checkouts too, and a missing module must cost the snapshot, never the
    # session: a file that cannot be snapshotted is still a file the agent may
    # edit, so this reader is the one that fails open.
    from tezgah_snapshot import capture
except ImportError:  # pragma: no cover - only where the module has not landed
    capture = None

try:  # The credential-file names, the secret rule's `git add` half: lost with
    # the snapshot module, never the session.
    from tezgah_snapshot import SECRET_FILE
except ImportError:  # pragma: no cover - only where the module has not landed
    SECRET_FILE = None

try:  # The lesson ledger's one reader (shared with tezgah_context, which the
    # gate does not import): which file is a ledger, what a write adds to it, the
    # key each line is remembered by, and the taint index writer. A missing
    # module costs the taint row, never the session.
    import tezgah_lessons
    from tezgah_lessons import write_taint
except ImportError:  # pragma: no cover - only where the module has not landed
    tezgah_lessons = write_taint = None

try:  # The piped-check rule's reader: newer than some integrity modules, and a
    # missing name costs the rule, never the session.
    from tezgah_integrity import piped_check
except ImportError:  # pragma: no cover - only on an integrity module without it
    piped_check = None


try:  # The task rule reads the user's own per-task record (a plan file's
    # frontmatter) through tezgah_task. That module is newer than some checkouts,
    # and a missing module costs the rule, never the session.
    import tezgah_task
except ImportError:  # pragma: no cover - only where the module has not landed
    tezgah_task = None

try:  # The language rule's detector: the letter set and the word list, in their
    # own module so a test reads them without a session. Newer than some
    # checkouts, and a missing module costs the rule, never the session.
    import tezgah_lang
except ImportError:  # pragma: no cover - only where the module has not landed
    tezgah_lang = None

# A search for a code symbol, the shape the graph answers: an identifier with an
# inner underscore or a lower-to-upper step (snake_case, camelCase), or any
# identifier inside a definition or call pattern (`def run`, `run\(`). A plain
# word (`TODO`, `error`) is literal text, so it is never nudged or advised.
SEARCH_SYMBOL = re.compile(
    r"(?:\\b)?(?:(def|class|function|func|fn|interface|struct|type)\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]{2,})(\\?\()?(?:\\b)?")
# omp's discovery tools: `find` takes a described behavior plus likely terms,
# `search` and `ast_grep` a pattern; `grep` is every host's regex tool.
PATTERN_SEARCH_TOOLS = ("grep", "search", "ast_grep")
# ponytail: flags with a separate value (grep -A 3 foo) shift the token and the
# search passes unnudged; not worth a real argv parser for a once-a-session hint.
BASH_SEARCH = re.compile(r"(?:^|[|;&(]\s*|\s)(?:grep|rg)\s+((?:-\S+\s+)*)(\S+)")
# the credit forms, not a bare tool name: "OpenAI" or "Claude Code" in a
# sentence (naming a tool to use it) is fine, "Co-Authored-By: ..." or a
# generator named as the author (signing it) is the thing to stop. The "... by
# ..." verbs credit only when their object names the machine or a model: a
# report generated by the build script, or an index built by the gate, is prose,
# while AI / an LLM / GPT / Claude / ... as that object is a signature, so each
# verb is tied to the name it credits. `_CREDIT` is shared with the anchored
# twin below so the two forms cannot drift apart.
#
# The cost of the model-object branch is deliberate and it falls on a message
# that *quotes* the forms: a commit body describing this rule is denied until it
# rephrases (the deny states the reason, and one rephrase clears it). The file
# path pays nothing for it - `ATTRIB_LINE` anchors, so documentation that merely
# names a form mid-sentence lands - and splitting the two sets apart was tried
# and reverted, because the anchored half then missed `-m "Built by GPT"`.
_CREDIT = (
    r"co-authored-by\s*:|generated with|made with|"
    r"(?:generated|written|authored|built|assisted)\s+by\s+"
    r"(?:(?:an?|the)\s+)?"
    r"(?:ai|llm|claude|chatgpt|gpt|copilot|codex|cursor|gemini|deepseek|"
    r"openai|anthropic)\b|noreply@anthropic|\U0001F916")
ATTRIB = re.compile(_CREDIT, re.I)
# The same forms anchored to the start of a line, for the text a write/edit tool
# is about to land. A credit is a signature: it owns its line, bare or behind a
# comment marker, and a patch body prefixes an added line with `+` (`-` stays
# last in the class so it is a literal, not a range). Prose that merely names the
# ban ("Banned forms include `Co-Authored-By`") starts with other words, and a
# markdown list item puts a backtick between the marker and the form, so neither
# matches. That anchoring is what stops the rule from denying the documentation
# that describes it.
# ponytail: a file that quotes a forged trailer on its own line is still denied;
# the deny states the reason, so one rephrase clears it.
ATTRIB_LINE = re.compile(r"(?im)^[\s>#*/<!+-]*(?:" + _CREDIT + r")")
# the payload fields a write/edit tool carries its content in, per host dialect
EDIT_TEXT = ("content", "new_string", "newString", "new_str", "file_text",
             "patch", "text")
# the write subcommand may sit behind git's global options: `git -c k=v commit`,
# `git -C dir commit`, `git --no-pager commit`. `gh api` writes comments/reviews,
# and `gh pr merge` lands a commit, so both count as writes.
# The `gh` subcommands that write to the remote, so this rule counts them as
# write commands: a PR or an issue comment is a message posted to a service
# under the workspace's name.
GH_SUBCOMMANDS = r"(?:create|edit|comment|review|merge|close)"
WRITE_CMD = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*"
    r"(?:commit|merge|tag|notes)\b|"
    r"(?:^|[|;&]\s*|\s)gh\s+api\b|"
    r"(?:^|[|;&]\s*|\s)gh\s+(?:pr|issue|release)\s+" + GH_SUBCOMMANDS + r"\b",
    re.I)

# --- secret: a credential on its way into a file ----------------------------
# The shell half (a command's own text next to a sink; the text a write lands is
# read below, SECRET_EDIT_DENY): only the two shapes the contract names: a
# bearer header, or a `name=value`
# assignment. A trailing quote is allowed because the value is usually quoted,
# and `:` is NOT a separator here - `{"api_key": "x"}` is a JSON field in a
# program's text, while `token=$TOKEN` and `api_key=...` are a credential being
# carried. The value may be an env reference: `OPENROUTER_API_KEY=$KEY` echoed
# into a log is the taxonomy's own case (`$KEY` is resolved by the shell).
# The name alternatives already match the keyword wherever it sits, so the
# unbounded `[A-Za-z0-9_.-]*` prefix only bought a rescan from every start
# position: 16 KB took 4.03 s and 100 KB 174 s, past Claude's 5 s hook budget, so
# the deny never arrived and the evidence row was never written (audit H-3).
SECRET_TOKEN = re.compile(
    r"authorization\s*:\s*bearer\s+\S|"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|"
    r"password|passwd)\s*=\s*[\"']?[^\s\"']", re.I)
# The sinks that carry a command's own text into a file. `>>?` is read off the
# masked text, so a quoted `>` is not a redirect and `2>&1` is not a file.
# curl's -o/--output writes the response BODY, not the request header, so it is
# not a sink; its traces are, because those do carry the header.
SECRET_SINK = re.compile(
    r">>?(?![&=])|\|\s*tee\b|--trace(?:-ascii)?\b|"
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*add\b")
# The simple commands of a shell line, for the rule below. A sink only carries
# the text of its own simple command, so `git add -A && git commit -m "fix
# api_key= handling"` is a message about the rule rather than a credential in a
# write. `|` is NOT a boundary here but a carrier: `printf 'token=%s' "$T" | tee
# log` hands the piped text to tee. The split is read off the masked text, so a
# quoted `;` does not split.
SEGMENT = re.compile(r"\|\||&&|[;&\n]")
# Plan 096: a token in a leading `NAME=value` word (after an optional `env`)
# reaches only the program's own environment, so that program's redirected
# output carries no key. The value reads quotes, one level of `$( )` and a
# backtick body; a value it cannot read ends the prefix early, and the token
# then sits outside it and holds. Names are ASCII, as bash reads them.
SECRET_PREFIX = re.compile(
    r"[\s;&|]*(?:env\s+)?(?:[A-Za-z_]\w*=(?:'[^']*'|\"(?:\\.|[^\"\\])*\"|"
    r"\$\([^()]*\)|`[^`]*`|\\.|[^\s;&|()<>'\"`\\])*\s+)+", re.ASCII)
# The sinks that carry a program's output, and nothing but it: the only ones a
# key in that program's environment stays out of.
SECRET_OUTPUT = re.compile(r">>?(?![&=])|\|\s*tee\b")
# The ceiling of that relaxation is an allowlist (`_secret_runner`): a script
# runner given a script file, with no option that makes it run its own text,
# stdin or a preload, or trace the commands it runs. Every other program may
# print its environment, so it holds. The rule cannot read the script itself:
# an allowlisted script that prints its own environment still writes the key.
SECRET_RUNNER = re.compile(r"python[\d.]*|node|bun|deno|bash|sh|zsh")
SECRET_SCRIPT = re.compile(r"[^$`\s]+\.(?:py|js|mjs|ts|sh)")
SECRET_INLINE = {"python": re.compile(r"-[A-Za-z]*[cmi]"),
                 "sh": re.compile(r"-[A-Za-z]*[csxv]|-o$|--(?:verbose|debugger)"),
                 "js": re.compile(r"-[A-Za-z]*[epri]|--(?:eval|print|require|"
                                  r"import|loader|experimental-loader|preload|"
                                  r"interactive)(?:=|$)")}
# A line that reads the environment from /proc, sets a variable an interpreter
# reads at startup or a shell trace, turns the shell's own trace on, or defines
# a function that can shadow the program, gets no relaxation.
SECRET_ENVIRON = re.compile(r"/proc/[^/\s]*/environ")
SECRET_STARTUP = re.compile(
    r"(?<![\w$])(?:SHELLOPTS|BASHOPTS|BASH_ENV|ENV|PS4|ZDOTDIR|NODE_OPTIONS|"
    r"PYTHONSTARTUP|PYTHONINSPECT|PERL5OPT|PERL5DB|RUBYOPT|LD_PRELOAD|DYLD_\w*)=",
    re.ASCII)
SECRET_TRACE = re.compile(
    r"(?:^|[\s;&|(])set\s+(?:-[A-Za-z]*[xv]|-o\s+(?:xtrace|verbose))")
SECRET_FUNCTION = re.compile(
    r"(?:^|[\s;&|(])(?:function\s+[^\s(){};&|]+|[^\s(){};&|$=]+\s*\(\s*\))")
# The programs a carried name is printed by when they own a sink. An
# interpreter running its own text is read off `_program`, which names the
# interpreter only then; a program the shell names at run time prints too.
SECRET_PRINTERS = frozenset(("echo", "printf", "cat", "eval", "awk", "perl",
                             "ruby"))

SECRET_DENY = (
    "Credential write denied: this command would land a credential in a file "
    "(`>`/`>>`, `tee`, `git add` or a curl trace). Record the credential's "
    "name, length or a fingerprint instead of its value, pass it through the "
    "tool's own environment, or let the tool read it from there rather than "
    "writing it out.")
# The text a write lands - a write tool's content, a patch's added lines, a
# heredoc's body - is read for the redactor's prefixed token families
# (tezgah_integrity.SECRET_PREFIXED: `ghp_`, `sk-live-`, `AKIA`, ..., without
# the redactor's bare `sk-`/`pk_` branch), never for the
# name=value shape above: in a file's text `password = os.environ[...]` is a
# program reading its credential, and name=value matched 99 of 655 tracked text
# files where the prefixed families matched 4, all fixtures (REPORT.md:5853, not
# re-measured here). Only a token the call brings counts: one already in the
# replaced text is not this call's doing.
SECRET_EDIT_DENY = (
    "Credential write denied: this write lands a token with a known credential "
    "prefix (`ghp_`, `sk-live-`, `AKIA`, ...) in a file. Record the credential's "
    "name, length or a fingerprint instead of its value, or have the program read "
    "it from its environment at run time.")
# `git add` of a credential file puts every value in it into history. The names
# are the snapshot store's (tezgah_snapshot.SECRET_FILE); the templates that
# carry names without values are the carve-out.
# ponytail: only a file the command names is read - `git add -A` or `git add .`
# staging an untracked `.env` is the .gitignore's to stop, not this rule's.
SECRET_TEMPLATES = (".env.example", ".env.sample", ".env.template", ".env.dist",
                    ".env.defaults")
# A token in these files is there to be read, not used: a template (the names
# above, `*.example`) or a test fixture (`tests/**/fixtures/**`).
SECRET_FIXTURE = re.compile(r"(?:^|/)tests?/(?:.+/)?fixtures/|\.example$", re.I)
# Documentation placeholders: a token that says it is an example (AWS's
# `AKIAIOSFODNN7EXAMPLE`), one whose body is a single repeated character
# (`ghp_xxxx...`), and the published keys docs print, held as sha256 digests so
# no file in the tree carries one whole: Stripe's documentation test secret key.
# ponytail: a published key is listed by hand, one per report.
SECRET_PUBLISHED = frozenset((
    "2cafc0970149a84f3b9e62eaf169f36f59907a3b3e31f7b82e68c69cd27f7326",))
SECRET_ADD_DENY = (
    "Credential file add denied: `git add %s` stages a credential file, so every "
    "value in it lands in the repository's history. Keep it out of git (list it "
    "in .gitignore) and commit a `.env.example` that carries the names without "
    "the values.")

# the MCP half of the rule (see `decision`): the same advice, for a server write
MCP_SECRET_DENY = (
    "Credential write denied: this MCP call would land a credential (a prefixed "
    "token such as `ghp_...` or `sk-...`) in what the server writes or posts. "
    "Record the credential's name, length or a fingerprint instead of its value, "
    "or let the server read it from its own environment.")

# The credential shapes the MCP half reads: vendor tokens only, case-sensitive.
# The redactor's families (tezgah_integrity.SECRET_TOKEN) also take any
# `sk|pk|rk` + 16 characters, which is what an identifier or a branch name looks
# like (`pk_users_organization_id`, `sk-telemetry-dashboard-refactor`) - right for
# a redactor, which loses nothing by blanking one, wrong for a refusal.
MCP_TOKEN = re.compile(
    r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"
    r"|\bsk-(?:proj|ant)-[A-Za-z0-9_\-]{16,}"
    r"|\bsk-[A-Za-z0-9]{32,}"
    r"|\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}"
    r"|\bxox[baprs]-[A-Za-z0-9-]{10,}"
    r"|\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"
    r"|\bAIza[0-9A-Za-z_\-]{30,}"
    r"|\bglpat-[A-Za-z0-9_\-]{20,}"
    r"|\bnpm_[A-Za-z0-9]{30,}")

EXPLORE_DENY = (
    "A grep-only explorer subagent is not allowed in this tree: it greps by "
    "design and ignores the code graph. Use the general-purpose agent and name "
    "the codegraph tools in its prompt (`codegraph_explore` over MCP, or "
    "`codegraph callers|impact|node` from a shell), with the tool-loading step "
    "so they are armed.")

ATTRIB_DENY = (
    "Attribution is banned in every artifact tezgah touches. Remove the "
    "Co-Authored-By / \"Generated with\" / robot-emoji / model-name credit from "
    "the commit, PR, issue or review text and re-run. Naming a tool in order to "
    "use it or describe real behavior is fine; crediting it as author is not.")


def attribution(command):
    """True when a git/gh write command carries an AI/model credit.

    The whole command text is read unanchored, so a credit inside a `-m` value is
    caught wherever it sits. A message that *discusses* the forms is denied too,
    and that is the known cost: the deny names the forms, so one rephrase clears
    it (see the note on `_CREDIT`)."""
    c = str(command or "")
    return bool(WRITE_CMD.search(c) and ATTRIB.search(c))


def attribution_edit(inp):
    """True when the text a write/edit tool is about to land carries a credit.

    The bash path needs `WRITE_CMD` to establish that a commit or PR body is
    being written; here the tool itself is the write, so the content is the
    whole question."""
    if not isinstance(inp, dict):
        return False
    return any(isinstance(v, str) and ATTRIB_LINE.search(v)
               for k, v in inp.items() if k in EDIT_TEXT)


# --- language: an identifier that is not English -----------------------------
# What this closes: the contract says code, commits, branches and docs are
# English, and nothing checked it at the one moment it is cheap to check - a plan
# branch was created as `plan/004-admin-durum-onarimi`, and the folded slug is in
# the repository's history for good. The identifiers are the durable half: a
# branch, a commit subject and a PR or issue title are public the moment they
# exist, while the reply that would have said something in Turkish is not kept
# at all. The detector is tezgah_lang (a non-ASCII letter predicate plus a
# curated list of Turkish words, and its own docstring carries what it cannot
# decide); this half is the command shapes that create an identifier.
#
# Read off the RAW text, not mask()'d text: an identifier usually arrives quoted
# (`git commit -m "..."`), and mask() blanks quoted strings by design. That is
# why the shapes below are exact rather than a scan for a foreign word anywhere - a
# command that merely NAMES the words (a `grep`, an `echo`, a `git log --grep`)
# creates nothing and must pass, which is the same line the attribution rule
# draws for its own forms.
#
# `git commit -F <file>` is read from the file, resolved against the call's cwd.
# ponytail: a file that cannot be read (a missing path, an unreadable one, a
# binary) is skipped rather than guessed at - the ceiling is named here, and the
# other commit routes (`--fill`, `-m` used twice) are read for their first
# argument only.
BRANCH_NEW = re.compile(
    r"(?:^|[|;&(]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*"
    r"(?:checkout\s+(?:-\S+\s+)*(?:-b|-B|--branch)\s+"
    r"|switch\s+(?:-\S+\s+)*(?:-c|-C|--create)\s+"
    r"|branch\s+(?!-))"
    r"([^\s;&|]+)")
COMMIT_MSG = re.compile(
    r"(?:^|[|;&(]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*commit\b([^|;&]*)")
# The flag and its value, which may be one token, a quoted string, or `=`-joined.
# The cluster form is read (`git commit -am "..."`), and `(?<![\w-])` is what
# keeps the short flag from matching inside the long one - `--message` holds a
# literal `-m` - and keeps `-am` from being read as a word. `--amend` and
# `--file` are not message flags, and neither is reached: a flag cluster cannot
# start on the second `-` of a long option, because the lookbehind rejects it.
MSG_FLAG = re.compile(r"(?<![\w-])(?:--message|-[A-Za-z]*m)(?:=|\s+|(?=[\"']))")
MSG_FILE = re.compile(r"(?<![\w-])(?:--file|-[A-Za-z]*F)(?:=|\s+|(?=[\"']))")
GH_NEW = re.compile(
    r"(?:^|[|;&(]\s*|\s)gh\s+(pr|issue)\s+create\b([^|;&]*)", re.I)
TITLE_FLAG = re.compile(r"(?<![\w-])--title(?:=|\s+|(?=[\"']))")
# How much of a commit-message file is read: the subject is its first line, so a
# file past this bound loses its tail and not its point.
MSG_READ = 64 * 1024


def _value(text):
    """The value of a flag from the text that follows it: a quoted string when
    the value opens with a quote (that is what carries a multi-word subject),
    else the next token."""
    text = text.lstrip()
    if text[:1] in ("\"", "'"):
        end = text.find(text[0], 1)
        return text[1:end] if end != -1 else text[1:]
    # keyword `maxsplit`: the positional form warns on 3.13+ and a future
    # keyword-only signature would raise, failing the gate open (audit QA-3)
    return re.split(r"[\s;&|]", text, maxsplit=1)[0]


def _flag_value(rest, flag):
    """The value of `flag` in `rest`, or "" when the flag is not there."""
    m = flag.search(rest)
    return _value(rest[m.end():]) if m else ""


def _message_file(path, cwd):
    """The text of a `-F` file, or "" when it cannot be read (see the ceiling
    above: an unreadable path skips the check rather than denying the commit)."""
    if not path:
        return ""
    full = path if os.path.isabs(path) else os.path.join(cwd or "", path)
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            return fh.read(MSG_READ)
    except OSError:
        return ""


def created_texts(command, cwd):
    """Every identifier this command would create, as (what, text) pairs.

    `what` names the thing in the words the command itself uses, so the refusal
    can say which identifier it is about."""
    c = str(command or "")
    out = [("branch name", m.group(1)) for m in BRANCH_NEW.finditer(c)]
    for m in COMMIT_MSG.finditer(c):
        rest = m.group(1)
        subject = _flag_value(rest, MSG_FLAG)
        if subject:
            out.append(("commit subject", subject))
        body = _message_file(_flag_value(rest, MSG_FILE), cwd)
        if body:
            out.append(("commit message", body))
    for m in GH_NEW.finditer(c):
        title = _flag_value(m.group(2), TITLE_FLAG)
        if title:
            kind = "PR" if m.group(1).lower() == "pr" else "issue"
            out.append(("%s title" % kind, title))
    return out


def lang_reason(command, cwd):
    """A deny reason when this command would create a non-English identifier,
    else None. The decision is tezgah_lang's (a word list is not a language
    detector, and its docstring carries the ceiling); this reads the shapes and
    names the identifier."""
    if tezgah_lang is None:
        return None
    for what, text in created_texts(command, cwd):
        reason = tezgah_lang.refusal(what, text)
        if reason:
            return reason
    return None


def explored(subagent_type):
    """True when a subagent request is the grep-only explorer."""
    return str(subagent_type or "").lower() in ("explore", "explorer")


def symbol_in(text):
    """The code symbol a search string names, or None for literal text."""
    m = SEARCH_SYMBOL.fullmatch(str(text or "").strip().strip("'\""))
    if not m:
        return None
    tok = m.group(2)
    if (m.group(1) or m.group(3) or "_" in tok.strip("_")
            or re.search(r"[a-z][A-Z]", tok)):
        return tok
    return None


def searched_symbol(tool, inp):
    """The code symbol this call searches for, or None. Host tool names differ
    in case (Claude `Grep`/`Bash`, Codex/dsh/omp `bash`), so match lowercased.
    omp's `find` is read too: its own prompt sends code discovery there first,
    so a rule that read only grep never met an omp session."""
    t = str(tool or "").lower()
    if t in PATTERN_SEARCH_TOOLS:
        return symbol_in(inp.get("pattern", ""))
    if t == "find" and "query" in inp:
        words = list(inp.get("grep_keywords") or [])
        words += re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}\(?", str(inp["query"]))
        return next(filter(None, map(symbol_in, words)), None)
    if t in ("bash", "shell"):
        for m in BASH_SEARCH.finditer(str(inp.get("command", ""))):
            symbol = symbol_in(m.group(2))
            if symbol:
                return symbol
    return None


def index_slug(cwd, base):
    """The cache stamp name of the enclosing repo whose OWN codegraph index
    exists, or None when no repo up to `base` has one.

    codegraph keeps its index inside the project (`<repo>/.codegraph/codegraph.db`),
    so readiness is a repo-local fact: the old per-user cache slug (a path
    flattened into `~/.cache/<engine>/<slug>.db`) said what some other tool had
    indexed, not what this repo carries. The walk is the old one -
    closest-ancestor-first, and the base itself excluded when it is a configured
    root, because a root is not a project (a base that is an armed worktree is
    one, so its own `.codegraph` is read) - and the name returned is still the
    key the index worker stamps HEAD under, so index_mark and index_notice keep
    reading the same file."""
    d = index_dir(cwd, base)
    return re.sub(r"[^A-Za-z0-9]+", "-", d).strip("-") if d else None


def index_dir(cwd, base):
    """The directory index_slug names: the closest repo up to `base` that holds
    its own codegraph index, or None (none, or a `.no-graph` met first)."""
    d = os.path.realpath(cwd)
    base, rs = os.path.realpath(base), roots()
    while d.startswith(base) and (d != base or base not in rs):
        if os.path.exists(os.path.join(d, ".no-graph")):
            return None  # the repo's own switch: no graph rule here at all
        if os.path.isfile(os.path.join(d, ".codegraph", "codegraph.db")):
            return d
        d = os.path.dirname(d)
    return None


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def git_head(repo):
    """HEAD's commit read from `repo`'s git files, or None - no `git` fork,
    because the gate pays it on a tool call. Covers a plain checkout, a linked
    worktree (`.git` file plus `commondir`) and a packed ref."""
    try:
        gd = os.path.join(repo, ".git")
        if os.path.isfile(gd):
            gd = os.path.join(repo, _read(gd).split("gitdir:", 1)[1].strip())
        head = _read(os.path.join(gd, "HEAD"))
        if not head.startswith("ref: "):
            return head or None
        ref = head[5:]
        common = gd
        if os.path.isfile(os.path.join(gd, "commondir")):
            common = os.path.join(gd, _read(os.path.join(gd, "commondir")))
        for top in (gd, common):
            if os.path.isfile(os.path.join(top, ref)):
                return _read(os.path.join(top, ref))
        with open(os.path.join(common, "packed-refs"), encoding="utf-8") as fh:
            for line in fh:
                if line.rstrip("\n").endswith(" " + ref):
                    return line.split()[0]
    except (OSError, IndexError):
        pass
    return None


def nudge_key(session_id):
    """The once-per-session mark's key in the `nudged` store: sha1(id)[:16],
    the key opencode's oncePerSession writes."""
    return hashlib.sha1((session_id or "nosession").encode("utf-8")).hexdigest()[:16]


def first_nudge(session_id):
    """Consume the once-per-session nudge. False when already spent/unwritable.

    The mark lands in cache_dir()'s database, so a sandboxed host (dsh) still
    gets the one-shot nudge instead of the write failing open. One INSERT, so
    of two calls at once exactly one is first."""
    try:
        # consume BEFORE denying: later greps pass
        return tezgah_store.mark("nudged", nudge_key(session_id))
    except tezgah_store.ERRORS:
        return False


def graph_tool(host=None):
    """The code-graph tool by the name this host's model calls it: omp mounts an
    MCP server's tools as `xd://` devices, Claude and Codex as `mcp__<server>__`
    (`mcp__plugin_tezgah_codegraph__` on a Claude plugin install), Cursor by
    the bare tool name. Unknown host: the two prefixed spellings, so the line is
    right wherever it lands."""
    if host == "omp":
        return "`xd://mcp__codegraph_explore`"
    if host == "cursor":
        return "the codegraph MCP server's `codegraph_explore`"
    claude = ("`mcp__codegraph__codegraph_explore` (plugin install: "
              "`mcp__plugin_tezgah_codegraph__codegraph_explore`)")
    return claude if host else "%s, on omp `xd://mcp__codegraph_explore`" % claude


def nudge_reason(symbol):
    return ("Code graph index is ready for this repo. Call the MCP tool %s with "
            "the query `%s`, or run `codegraph explore %s` (source, callers, "
            "blast radius in one call) or `codegraph callers %s` / `codegraph impact %s` from a shell; "
            "an omp subagent must use this CLI, not the MCP device, because omp's MCP device refuses "
            "concurrent writes. If you need literal text, re-run this search unchanged; it will pass - "
            "this nudge fires once per session."
            % (graph_tool(), symbol, symbol, symbol, symbol))


def graph_advice(tool, inp, cwd, host=None):
    """One non-blocking line for a symbol search the current graph answers, or
    None. The refusal above is spent once per session; every later symbol
    search gets this line beside its result instead, so the graph is named at
    the moment the session reaches for grep. Fresh only: the stamp the index
    worker writes must equal HEAD, because pointing at a graph that lags the
    tree would send the session to a stale answer. A literal search, a repo
    without its own index, `.no-graph` and `pretooluse-off` get nothing."""
    symbol = searched_symbol(tool, inp)  # first: a regex, and most calls end here
    if not symbol or off("pretooluse-off"):
        return None
    base = root_for(cwd)
    repo = index_dir(cwd, base) if base else None
    if not repo:
        return None
    try:
        stamped = _read(os.path.join(cache_dir(), index_slug(cwd, base)))
    except OSError:
        return None
    head = git_head(repo)
    if not head or stamped != head:
        return None
    return ("Graph: `%s` is a code symbol and this repo's code graph is current "
            "(HEAD %s). For its definition, callers or blast radius call %s "
            "with the query `%s` (or `codegraph callers %s` / `codegraph impact "
            "%s` in a shell): one call returns the source and the call path "
            "that this text search cannot."
            % (symbol, head[:7], graph_tool(host), symbol, symbol, symbol))


# The identical attempts a call gets before the loop guard refuses it, whatever
# its failure class. Two failures are the retry the agent may still be fixing
# while it changes the code between them; the third is the loop the contract bans
# ("three attempts on one failure is the ceiling"). The class
# (tezgah_integrity.fail_class) is read from the ledger and named in the refusal
# - it says WHY the last attempt failed - and it does NOT widen this number:
# an identical repeat adds nothing to a transient failure (a timeout, a
# connection error, a rate limit, a 5xx is retried by the host's own client, not
# by the agent re-issuing the same command), and a ceiling that loosened for one
# class would depend on error text the host may not report at all, so the same
# command would have two budgets on two hosts. G7's own row asked for a cap of
# two; the class-scoped ceiling it replaced read as its inverse - the least
# controllable failure bought the most identical repeats.
LOOP_ATTEMPTS = 2
CLASS_NOTE = {
    "transient": "it names a failure the host's own client may retry - a "
                 "timeout, a connection error, a rate limit, a 5xx - and an "
                 "identical repeat by the agent adds nothing to that",
    "user": "it names something only the user can supply - a credential, a "
            "login, an access grant - so take a route that needs none first "
            "(another provider or member, a local run, a public source) and "
            "ask the user once, naming what it unlocks, only when none is left",
    "permanent": "an assertion or a bad argument does not change by re-running "
                 "it",
}
NO_CLASS_NOTE = ("the host reported no error text for it, so the class is "
                 "unknown, and the cap is the same either way")

# The other half of the repeat rule, session-wide and blind to the outcome: a
# call the gate has seen run three times may not run a fourth, whatever those
# runs returned. It is deliberately above LOOP_ATTEMPTS - the loop guard counts
# only the attempts that failed, in the current turn, so a call that keeps
# "succeeding" without moving the work forward is its blind spot - and it is set
# above the common work loop (edit, test, edit, test reaches two identical test
# runs, and a session's third `git status` still passes) so only a genuine spin
# reaches it.
RETRY_CEILING = 3


def loop_reason(tool, inp, session_id, agent=None):
    """A deny reason when this exact call already failed often enough, else None.

    The ledger tail is the only state this reads, and only the outcome rows of
    the current user turn count (tezgah_integrity.prior_calls): the guard's own
    `deny` row carries the same id with no exit, so counting it would put the
    refusal newest, read as "no failure" and let every second repeat through.

    Past the ceiling the identical retry cannot work - the agent has to change
    the approach or stop, which is the contract's loop rule ("never repeat an
    identical failing command") given a mechanical half. A call that never
    failed, or that failed differently, is not this rule's."""
    if not session_id:
        return None
    digest = call_id(tool, inp)
    if not digest:
        return None
    turn, _, last_exit, klass = prior_calls(session_id, digest, agent=agent)
    if last_exit != 1 or turn < LOOP_ATTEMPTS:
        return None
    return ("Loop guard denied: this is attempt %d of an identical call whose "
            "%d previous attempt%s exited 1%s. The cap is %d identical attempts "
            "for every failure class, because %s. Repeating an identical failing "
            "command is not a retry - change the approach (fix what the error "
            "names, or run something else) or stop and report what is still "
            "unknown."
            % (turn + 1, turn, "" if turn == 1 else "s",
               " (a %s failure)" % klass if klass else "",
               LOOP_ATTEMPTS, CLASS_NOTE.get(klass, NO_CLASS_NOTE)))


def retry_reason(tool, inp, session_id, agent=None):
    """A deny reason when this exact call has already been attempted more than
    RETRY_CEILING times in this session, whatever those attempts returned.

    `loop` needs a failure to fire, so the call that runs ten times and returns 0
    each time - the spin that never reaches a decision - passes it forever. This
    is that half: the count is every attempt of the id that ran in the session,
    outcome-blind, and the user's turn does not reset it. A refused call never
    ran, so the gate's own denials are not attempts and cannot walk a call up to
    the ceiling by themselves.

    A verification command is the exception, and the tree is the switch: a check
    re-run after the tree changed is not a blind repeat - the edit-loop cadence
    needs it - so its attempts are counted since the last write row only. What
    still hits the ceiling is a check run four times on an unchanged tree, which
    is the spin this guard exists for."""
    if not session_id:
        return None
    digest = call_id(tool, inp)
    if not digest:
        return None
    attempts = prior_calls(session_id, digest, agent=agent)[1]
    if attempts < RETRY_CEILING:
        return None
    if str(tool or "").lower() in BASH_TOOLS \
            and verify_command((inp or {}).get("command")) \
            and _tree_changed_since_last_attempt(session_id, digest):
        return None
    return ("Retry ceiling denied: this is attempt %d of an identical call in "
            "this session, past the ceiling of %d attempts whatever their "
            "outcome. An unchanged repeat is not a retry - change the arguments "
            "or the target, or stop and report what is still unknown. (The "
            "`loop` guard is the narrower rule: the identical attempts that "
            "FAILED, counted per user turn.)" % (attempts + 1, RETRY_CEILING))


def _tree_changed_since_last_attempt(session_id, digest):
    """True when any write row sits between the newest attempt of this call and
    now: the tree the last check ran on is gone, so a re-run reads a new state.

    prior_calls' scan is reused: the rows it counted attempts over are the rows
    this reads, so there is no second ledger scan. A row with no `id` is a deny
    or a nudge, never a real call. Any failure here fails open - the ceiling is
    the conservative answer."""
    try:
        rows = events(session_id, tail=200)
        idx = [i for i, row in enumerate(rows)
               if row.get("id") == digest and row.get("exit") is not None]
        # the NEWEST attempt, not the oldest: anchoring on the oldest let one
        # early write exempt every later repeat for the rest of the session
        start = idx[-1] if idx else len(rows)
        return any(str(row.get("tool", "")).lower() in WRITE_TOOLS
                   or str(row.get("kind", "")) in ("edit",)
                   for row in rows[start:])
    except Exception:
        return False


def secret_command(command):
    """A deny reason when this command would write a credential into a file.

    Reading an env var or running a tool with a key in its env is the normal work
    this must not touch, so a token only counts next to a write sink, and a sink
    only carries the text of its own simple command. A token held only by the
    leading `NAME=value` words of an allowlisted program is in that program's
    env (`_env_prefix_only`), unless the line reads /proc's environ, sets a
    startup or trace variable, turns `set -x` on or defines a function. A name
    an earlier command assigned a token is carried, and a
    printer owning a sink that reads it still writes it (`_printer_owns_sink`).
    A `git add` that names a credential file is refused whatever its text holds
    (`_secret_add`)."""
    c = str(command or "")
    added = _secret_add(c)
    if added:
        return SECRET_ADD_DENY % added
    if not c or not SECRET_TOKEN.search(c):
        return None
    masked = mask(c)
    relax = not (SECRET_ENVIRON.search(c) or SECRET_STARTUP.search(c)
                 or SECRET_FUNCTION.search(masked) or SECRET_TRACE.search(masked))
    start, carried = 0, set()
    for end in [m.start() for m in SEGMENT.finditer(masked)] + [len(c)]:
        text = c[start:end]
        if SECRET_SINK.search(masked[start:end]):
            if SECRET_TOKEN.search(text) and not (relax and _env_prefix_only(text)):
                return SECRET_DENY
            if (carried & {a or b for a, b in SHELL_VAR.findall(text)}
                    and _printer_owns_sink(text, masked[start:end])):
                return SECRET_DENY
        carried |= {m.group(1) for m in SHELL_ASSIGN.finditer(text)
                    if SECRET_TOKEN.search(m.group(0))}
        start = end
    return None


def _env_prefix_only(text):
    """True when every token in this simple command's text sits in its leading
    `NAME=value` words (SECRET_PREFIX), no sink runs inside them, the sinks after
    them carry only the program's output (SECRET_OUTPUT: a `git add` or a curl
    trace holds), and the program is on the allowlist (`_secret_runner`, plan
    096). Any doubt reads False: the rule holds."""
    m = SECRET_PREFIX.match(text)
    if not m:
        return False
    rest = text[m.end():]
    return not (SECRET_TOKEN.search(rest) or SECRET_SINK.search(text[:m.end()])
                or SECRET_SINK.search(SECRET_OUTPUT.sub(" ", rest))
                or not _secret_runner(rest))


def _first_command(text):
    """The words of the first command `text` runs, a `$( )` body skipped."""
    text = text.lstrip(" \t\n;&|")
    return next((w for w, sep in _shell_commands(text) if sep != "$)"), [])


def _secret_runner(text):
    """True when the first program `text` runs, past the wrappers, is a script
    runner named by itself (SECRET_RUNNER; a path could be any program) given a
    script file (SECRET_SCRIPT), with no `-` or SECRET_INLINE option before it:
    no inline text, stdin, preload, interactive mode or trace."""
    words = _past_wrappers(_first_command(text))
    if not words or not SECRET_RUNNER.fullmatch(words[0]):
        return False
    name = words[0]
    args = words[1:]
    if name == "deno":
        if args[:1] != ["run"]:
            return False
        args = args[1:]
    inline = SECRET_INLINE["python" if name.startswith("python")
                           else "js" if name in ("node", "bun", "deno") else "sh"]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-" or inline.match(arg):
            return False
        if not arg.startswith(("-", "+")):
            return bool(SECRET_SCRIPT.fullmatch(arg))
        i += 2 if arg in INTERPRETER_VALUE_OPTS else 1
    return False


def _printer_owns_sink(text, masked):
    """True when a pipeline stage of this simple command that owns a file sink
    - a `>` to a file other than /dev/null, or a pipe into `tee` - is a printer:
    SECRET_PRINTERS, an interpreter running its own text, or a program the shell
    names at run time. `echo "$T" | docker login --password-stdin > log` hands
    the key to docker's stdin, and docker's output is what lands."""
    cuts = [m.start() for m in re.finditer(r"(?<!>)\|", masked)]
    stages = list(zip([0] + [k + 1 for k in cuts], cuts + [len(text)]))
    for k, (a, b) in enumerate(stages):
        owns = any(text[a + m.end():b].split()[:1] != ["/dev/null"]
                   for m in re.finditer(r">>?(?![&=])", masked[a:b]))
        if k + 1 < len(stages) and re.match(r"\s*tee\b", masked[stages[k + 1][0]:]):
            owns = True
        if owns and _secret_printer(text[a:b]):
            return True
    return False


def _secret_printer(text):
    """True when the first program `text` runs prints a carried name."""
    program = _program(_first_command(text))[0]
    return (program in SECRET_PRINTERS or program in INTERPRETERS
            or bool(re.fullmatch(r"python[\d.]+", program)
                    or UNEXPANDED.search(program)))


def _secret_add(command):
    """The credential file a `git add` in this command names, or None."""
    if SECRET_FILE is None or "add" not in command:
        return None
    for words in _shell_segments(command):
        program, args = _program(words)
        if program != "git":
            continue
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 2 if args[i] in GIT_VALUE_OPTS else 1
        if args[i:i + 1] != ["add"]:
            continue
        for arg in args[i + 1:]:
            name = os.path.basename(arg.rstrip("/"))
            if (not arg.startswith("-") and SECRET_FILE.match(name)
                    and name.lower() not in SECRET_TEMPLATES):
                return arg
    return None


def _placeholder(token):
    """True for a documentation stand-in rather than a credential."""
    if "example" in token.lower():
        return True
    body = re.split(r"[-_]", token)[-1]
    if body == token:          # AKIA/ASIA/AIza: the prefix carries no separator
        body = token[4:]
    if len(set(body)) <= 1:
        return True
    return hashlib.sha256(token.encode()).hexdigest() in SECRET_PUBLISHED


def secret_edit(inp, cwd=None):
    """A deny reason when a write lands a prefixed credential token the file did
    not already carry, else None. Every write dialect is read, an apply_patch
    file by file (tezgah_integrity.write_texts); the heredoc body a shell
    command writes arrives here in the same `{file_path, content}` shape. The
    baseline is the text the call replaces plus the file on disk, resolved
    against the call's cwd, so an edit that repeats a key the file already holds
    is not a new one; the disk is read only when the new text carries a token.
    A template or fixture file and a documentation placeholder are exempt
    (SECRET_FIXTURE, _placeholder)."""
    for path, old, new in write_texts(inp):
        fresh = {t for t in SECRET_PREFIXED.findall(new) if not _placeholder(t)}
        name = path.replace(os.sep, "/")
        if not fresh or (SECRET_FIXTURE.search(name)
                         or os.path.basename(name).lower() in SECRET_TEMPLATES):
            continue
        disk = ""
        if path:
            try:
                with open(os.path.join(cwd or os.getcwd(), path),
                          encoding="utf-8") as fh:
                    disk = fh.read()
            except (OSError, UnicodeDecodeError):
                disk = ""
        if fresh - set(SECRET_PREFIXED.findall((old or "") + "\n" + disk)):
            return SECRET_EDIT_DENY
    return None


# --- concurrent write: another session wrote this file minutes ago -----------
# What this closes: two sessions on one file - a parent and the subagent it
# delegated to, or two worktrees of the same repo. Each reads before the other
# writes, so the second edit lands on a stale read, and the first session's work
# is gone with nothing in either transcript saying so. That is why the collision
# REFUSES instead of annotating: a silent overwrite is the failure, and a note
# the agent may read past leaves the overwrite exactly where it was. One re-read
# is the whole cost of the refusal.
#
# Why ten minutes: the ledger holds no lock, so the window is the only release -
# a session that crashed or was closed mid-edit never says it is finished. Ten
# minutes outlives a slow read-edit-check cycle on one file plus a long tool call
# between the two writes, which is the collision this catches; a shorter window
# let the second write through in the minute that matters. Wider and the refusal
# lands on edits whose other author is long gone, which trains the agent to
# re-issue without reading.
RACE_WINDOW_MIN = 10
# The decision itself, named rather than left as a literal inside the check:
# a foreign write REFUSES (True). See above - a notice does not close a silent
# overwrite, so this rule cannot be a soft one.
RACE_REFUSE = True
RACE_DENY = (
    "Concurrent write refused: %s wrote this file within the last %d "
    "minutes, so the copy of %s in your context may already be stale. Re-read "
    "the file and re-apply your change to what is on disk now; if both sessions "
    "are editing it, say so and let one of them own the file rather than "
    "overwriting the other's work.")
# How RACE_DENY names a writer, by its relation to this session
# (tezgah_integrity._relation): the bare ledger id sent a model to the wrong
# cause - it called an omp fork "a second window of the same session"
# (research orchestrator-flow-audit S7, finding 4).
RACE_WHO = {
    "child": "your own subagent %s (ledger %s), not ended in the slice journal",
    "parent": "your parent session (ledger %s)",
    "sibling": "sibling subagent %s of your parent (ledger %s)",
    "fork": "an omp fork of this session (ledger %s)",
    "forked-from": "the session this one was forked from (ledger %s)",
    "unrelated": "another, unrelated session %s",
}
# The file a write call names, per host dialect, plus the apply_patch headers
# (tezgah_integrity.PATCH_FILE) for the dialect whose paths live in the body.
# The race guard resolves each against the call's cwd to an absolute real path
# and compares it with the `target` the PostToolUse writer stored the same way
# (tezgah_integrity._abs_target): the raw spelling matched `README.md` in one
# repository against `README.md` in another (audit CHAT-03 / M-6).
# The harness's internal channels: a write to one of these is a message or a
# tool device, never a file on disk. Deliberately a list, not `scheme://`: a
# file reached through a URI scheme is still a file two sessions can race on.
URI_CHANNEL = re.compile(
    r"^(?:agent|xd|local|artifact|proc|skill|mcp|omp|issue|pr|history|ssh|cfg|"
    r"conflict)://", re.I)
# The task rule's wider reading: ANY scheme. Its question is "is this a path in
# the checkout", and a URI is not one - `tezgah_task.relative` would read
# `xd://mcp__codegraph_explore` as a relative file and refuse a name that exists
# nowhere (a user session, 2026-10-11: `xd://` and `conflict://` writes refused
# as outside the allowlist).
# `file://` is the one scheme that names a checkout file, so it stays guarded,
# as the race rule already reads it.
URI_TARGET = re.compile(r"^(?!file://)[A-Za-z][A-Za-z0-9+.-]*://", re.I)
# A shell target still holding a variable or a substitution once write_paths
# expanded what it could: the shell names the file at run time, the gate cannot.
UNEXPANDED = re.compile(r"\$[A-Za-z_{(]|`")
# One unexpanded piece of a shell target, for `known_tail`.
UNEXPANDED_PIECE = re.compile(
    r"\$\{[^}]*\}|\$\([^)]*\)|\$[A-Za-z_][A-Za-z0-9_]*|`[^`]*`")
# `NAME=value` at a word start, and the `$NAME`/`${NAME}` a later word reads.
SHELL_ASSIGN = re.compile(
    r"(?:^|(?<=[\s;&|(]))([A-Za-z_][A-Za-z0-9_]*)="
    r"((?:'[^']*'|\"[^\"]*\"|[^\s;&|)'\"])*)")
SHELL_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
WRITE_PATH = ("file_path", "filePath", "path", "notebook_path")
# The write-tool name a shell write's target is handed to `capture` under. capture
# takes a write tool's own path field and no shell tool name, and the row it
# writes carries neither - so one file the shell command changes gets the same
# pre-state a write tool's target gets, and the ledger gains no field it did not
# have. See the capture call at the end of `decision`.
SHELL_AS_WRITE = "write"


def write_paths(inp):
    """Every file this call writes: the tool's own path field, else the paths an
    apply_patch body names per hunk, else the file a shell command's own text
    writes through a redirect or `tee` (the shape SHELL_WRITE reads, the target
    shell_target slices - see the shell section below).

    The shell branch is the one write whose target leaves no path field behind,
    and it is here rather than in a second reader because the two halves of that
    write have to agree on one answer: the gate hands these paths to `capture`
    before the call, and `tezgah_integrity._post_write` reads the same list after
    it to hash the after-state. Raw strings, unresolved - each caller resolves
    them against its own directory - except that a shell target's `$VAR` and
    `~` are expanded as the shell would (`> $TMPDIR/x` is not a file named
    `$TMPDIR` under the cwd). ponytail: a target that is a positional
    argument (`cp`, `mv`, `sed -i`, `patch`, `git apply`) is not read off the
    command at all; which argument of those is the target is a per-program
    question, and the measured route is the redirect."""
    if not isinstance(inp, dict):
        return []
    for key in WRITE_PATH:
        value = inp.get(key)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    paths = [m.group(1) for m in PATCH_FILE.finditer(str(inp.get("patch") or ""))]
    if paths:
        return paths
    command = str(inp.get("command") or inp.get("cmd") or "")
    target = shell_target(command)
    return [os.path.expanduser(_expand(target, command))] if target else []


def _expand(target, command):
    """`target` with each `$VAR`/`${VAR}` the shell would substitute: an
    assignment earlier on the same line (`B=/tmp/x; git diff > $B/f`), else the
    environment. A name with no known value stays as spelled, so
    `unnamed_target` can tell the gate it does not know the file. ponytail: the
    assignments are read off the raw text, so `echo "a B=x"` counts as one; that
    only matters when the target then reads `$B`."""
    env = dict(os.environ)

    def sub(text):
        return SHELL_VAR.sub(
            lambda m: env.get(m.group(1) or m.group(2), m.group(0)), text)

    cut = command.find(target)
    for m in SHELL_ASSIGN.finditer(command[:cut if cut >= 0 else len(command)]):
        name, value = m.group(1), m.group(2)
        if "$(" in value or "`" in value:
            env.pop(name, None)         # a command's output: unknown here
        elif value[:1] == "'":
            env[name] = value.strip("'")
        else:
            env[name] = sub(value.strip('"'))
    return sub(target)


def unnamed_target(path, inp, top=None):
    """True when a write target is no file the task rule can place in the
    checkout: a URI (a host tool device such as `xd://<tool>`, an agent message,
    a `conflict://N` resolution) or a shell target whose variable has no known
    value and that `known_tail` cannot place. Refusing either names a path
    that does not exist. A write tool's own path is never read for `$`:
    `Outer$Inner.java` is a real file name."""
    if URI_TARGET.match(path):
        return True
    if not isinstance(inp, dict):
        return False
    command = str(inp.get("command") or inp.get("cmd") or "")
    return bool(command) and bool(UNEXPANDED.search(path)) and not known_tail(
        path, top, command)


# A value that is the checkout itself: `R=$(git rev-parse --show-toplevel)`,
# `R=$(pwd)`, `R=$PWD`.
ROOT_VALUE = re.compile(
    r"^[\"']?(?:\$\(\s*(?:git\s+rev-parse\s+--show-toplevel|pwd)\s*\)"
    r"|`\s*(?:git\s+rev-parse\s+--show-toplevel|pwd)\s*`|\$\{?PWD\}?)[\"']?$")


def known_tail(path, top, command=""):
    """The checkout path a target names when it opens on a variable the same
    command line set to the checkout (`ROOT_VALUE`), or None. `R=$(git
    rev-parse --show-toplevel); printf x > $R/src/a.py` writes `src/a.py`, so the
    rule holds that file. Any other unknown variable - a `mktemp -d` directory,
    a loop variable, one an earlier call exported - leaves the target unnamed:
    re-rooting `$D/README.md` or `packages/$p/x` at the checkout refused writes
    that never touched it (review of plan 083, N1).
    ponytail: a root exported by an earlier call (`export R=$PWD`, then `> $R/x`)
    is not seen, so that write passes unnamed."""
    if not top:
        return None
    pieces = list(UNEXPANDED_PIECE.finditer(path))
    if len(pieces) != 1 or pieces[0].start() != 0:
        return None
    name = pieces[0].group(0).strip("${}")
    rest = path[pieces[0].end():].lstrip("/")
    if not rest or UNEXPANDED.search(rest):
        return None
    cut = command.find(path)
    head = command[:cut if cut >= 0 else len(command)]
    values = re.findall(r"(?:^|(?<=[\s;&|(]))%s=(\$\([^)]*\)|`[^`]*`|\"[^\"]*\"|\S+)"
                        % re.escape(name), head)
    return (os.path.join(top, rest)
            if values and ROOT_VALUE.match(values[-1]) else None)


# The front matter key that makes a plan the active task (tezgah_task.active).
PLAN_PHASE_LINE = re.compile(r"(?m)^\s*\+?\s*phase\s*:\s*\S")


def workspace_free(rel, inp, path=""):
    """True when `rel` is tezgah's own workspace the plan does not scope: every
    `.tezgah/` path but the slice journal (`tezgah-task slice` writes it) and a
    plan file that could make itself the active task - a shell write into
    `.tezgah/plans/open/` (its text is unknown) or a write tool whose plan text,
    once written, carries a `phase:` line (`_text_after`, read from `path`).
    plan-add's own plan file and README stay free.
    Compared casefolded: on a case-insensitive disk `.tezgah/PLANS/` is the
    plans directory (review of plan 083, N2 and N5)."""
    low = (rel or "").casefold()
    if not low.startswith(".tezgah/") or low.startswith(".tezgah/slices/"):
        return False
    if low.startswith(".tezgah/plans/open/"):
        if not isinstance(inp, dict) or inp.get("command") or inp.get("cmd"):
            return False
        return not PLAN_PHASE_LINE.search(_text_after(inp, path))
    return True


_OLD_TEXT = ("old_string", "oldString", "old_str")
_NEW_TEXT = ("new_string", "newString", "new_str")


def _text_after(inp, path):
    """The file's text once this write lands, as far as the call says: a Write's
    content, the current text with an Edit's (or a MultiEdit's) replacements
    made, and for any other shape (a patch, a host's own edit format) the
    current text beside every new string - the refusing direction. Judging the
    new string alone let two edits each harmless on its own (`xphase:`, then
    `xphase` -> `phase`) give an unphased plan a phase."""
    for key in ("content", "file_text"):
        if isinstance(inp.get(key), str):
            return inp[key]
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except (OSError, TypeError):
        text = ""
    edits = inp.get("edits") if isinstance(inp.get("edits"), list) else [inp]
    pairs = [(next((e[k] for k in _OLD_TEXT if isinstance(e.get(k), str)), None),
              next((e[k] for k in _NEW_TEXT if isinstance(e.get(k), str)), None), e)
             for e in edits if isinstance(e, dict)]
    if pairs and all(old is not None and new is not None for old, new, _ in pairs):
        for old, new, e in pairs:
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
        return text
    return "\n".join([text] + [inp[k] for k in EDIT_TEXT + ("input",)
                               if isinstance(inp.get(k), str)])


def race_reason(inp, session_id, cwd=None):
    """A deny reason when another session wrote one of this call's files inside
    RACE_WINDOW_MIN, else None.

    `writers_elsewhere` is the ledger reader in tezgah_integrity, and its import
    is guarded: an integrity module without it costs this rule, never the
    session. ponytail: the PostToolUse writer records a patch's first path,
    so a foreign patch write is visible here only for that first file while
    this side reads every hunk's: the row is one line, and widening it means
    the ledger row changes shape."""
    if writers_elsewhere is None or not session_id:
        return None
    for path in write_paths(inp):
        # an internal URI (`agent://Main`, `xd://<tool>`) is not a file: two
        # observed refusals today wrote tool replies through those schemes and
        # this guard read the scheme as a relative path. Only the harness's own
        # channels are skipped - a `file://`, `s3://` or editor URI can name a
        # real target two sessions both write, and stays guarded.
        # a shell target whose `$VAR` has no known value names no file the
        # ledger could hold either (unnamed_target)
        if (URI_CHANNEL.match(path) or scratch_target(path, cwd)
                or (not URI_TARGET.match(path) and unnamed_target(path, inp))):
            continue    # a temp file or a device is no one's shared work
        others = [w for w in writers_elsewhere(path, session_id, RACE_WINDOW_MIN,
                                               cwd=cwd, lineage=True)
                  if not ended_child(w, session_id, path, cwd)]
        if others:
            return RACE_DENY % (", ".join(race_who(*w[:3]) for w in others[:3]),
                                RACE_WINDOW_MIN, path)
    return None


def race_who(stem, relation, agent):
    """One writer as RACE_DENY names it (RACE_WHO)."""
    text = RACE_WHO.get(relation, RACE_WHO["unrelated"])
    return text % ((agent or "?", stem) if text.count("%s") == 2 else (stem,))


def ended_child(writer, session_id, path, cwd):
    """True when `writer` (a writers_elsewhere (stem, relation, agent, ts)) is
    this session's own subagent whose slice record closed after its newest
    write of this file: a parent taking over a child that stopped on a quota
    error is no race (research orchestrator-flow-audit S7, finding 3). The
    record is read after `pending` closes an ended omp child, from cwd's journal
    and the written file's. No record, one still open, or a write newer than the
    record's close is a live writer and stays refused. ponytail: the close time
    is stored to the second, so a write in the second the record closed counts
    as before the close."""
    import calendar
    stem, relation, agent, wrote = writer
    if relation != "child" or not agent or tezgah_task is None:
        return False
    repos = {r for r in (tezgah_task.main_repo(os.path.join(cwd or os.getcwd(), path)),
                         tezgah_task.main_repo(cwd or os.getcwd())) if r}
    base = re.sub(r"-\d+$", "", agent)
    recs = []
    try:
        for repo in repos:
            tezgah_task.pending(repo)   # closes an omp child whose transcript ended
            recs += [r for r in tezgah_task.slices(repo) if r.get("parent") == session_id
                     and (r.get("name") or r.get("id")) in (agent, base)]
        closed = max(calendar.timegm(time.strptime(str(r.get("updated")), "%Y-%m-%dT%H:%M:%SZ"))
                     for r in recs) if recs else None
    except Exception:
        return False
    return (closed is not None and closed >= int(wrote)
            and all(r.get("status") != "open" for r in recs))


# --- lease: a sibling slice owns this file (plan 086, S6) --------------------
# What this closes: the race rule refuses only after the other slice wrote, and
# 24 genuine sibling refusals in real transcripts were all in a shared place -
# one worktree for 4 or 10 concurrent slices, a predecessor's tree, a shared
# plan record (research orchestrator-flow-audit S6, findings 3 and 5). A brief's
# `Owns:` line is a lease on the slice record (`tezgah_task.owned_globs`), and a
# write by one slice into a path an open sibling of the same parent owns is
# refused before any work is lost. The second refusal is the checkout itself:
# a slice whose record names a worktree writing into the main checkout (plan
# 086 wave 1: two slices did, by relative paths that resolved against the
# parent's cwd). Refused, not noted: a notice arrives after the file landed in
# the parent's tree, and the fix - the same write under the worktree - costs
# one re-issue. `.tezgah/` (the plan record, research data) and scratch stay
# free: they live in the main checkout by design.
#
# The writing session is mapped to its record two ways. omp: its ledger's
# `spawned` row (`tezgah_integrity.spawn_of`: parent session and spawned name);
# omp writes it for every task child, and the record stays open while the child
# runs. Claude: a background child's calls carry the parent's session id and
# their own `agent_id`, which the spawn's result named and the record keeps as
# `child` (`hooks/projects-posttooluse.py`). Every other case fails open:
# Claude's foreground agents, dsh, Cursor and opencode open the record only when
# the synchronous spawn returns, so no sibling record is open while the child
# writes, and Codex writes no `spawned` row. A slice may write a path its own
# `Owns:` names even when a sibling's names it too: the overlap is the parent's
# brief, and the race rule still stands between the two.
LEASE_DENY = (
    "Lease: %s is owned by sibling slice %s (owns %s), still open under your "
    "parent. Leave the file to it: %s, or ask your parent to move the lease; "
    "once the owner has finished, `tezgah-task slice done %s` frees it. Every "
    "lease is on `tezgah-task slice board`.")
MAIN_CHECKOUT_DENY = (
    "Lease: %s is in the main checkout %s, but your slice %s works in worktree "
    "%s. Write the same path under that worktree: an absolute path, or a shell "
    "whose `cwd` or `cd` is there - a relative path resolves against this "
    "session's cwd.")


def _channel(rec):
    """How a sibling reaches the slice `rec` on its host."""
    if rec.get("host") == "claude" and rec.get("child"):
        return "message the owner (`SendMessage` to %s)" % rec["child"]
    if rec.get("host") == "omp":
        return "message the owner (`write agent://%s`)" % (rec.get("name") or rec["id"])
    return "ask the owner through your parent"


def _shell_dir(inp, cwd):
    """The directory a shell call's redirect or `tee` target resolves against:
    the call's own `cwd`/`workdir`, then each `cd`/`pushd` before the first
    redirect or `tee` that writes a file, read the way `shell_control` walks
    the line. A redirect to `/dev/*`, a descriptor (`2>&1`) or `-` writes no
    file, so `pushd /wt >/dev/null && x > out` resolves `out` under `/wt`."""
    base = inp.get("cwd") or inp.get("workdir")
    where, words, pending = _full(base, cwd) if base else cwd, [], False
    for word, is_op in _shell_words(inp.get("command") or inp.get("cmd") or ""):
        if pending:
            pending = False
            if not is_op:
                target = _unquote(word)
                if not (target.startswith(("&", "/dev/")) or target.isdigit()
                        or target == "-"):
                    return where
                continue
        if is_op and ">" in word:
            if words and words[-1].isdigit():
                words.pop()  # the descriptor before `2>`
            pending = True
            continue
        if not is_op:
            if _unquote(word) == "tee" and not words:
                return where
            words.append(_unquote(word))
            continue
        while words and words[0] in SHELL_KEYWORDS:
            words = words[1:]
        if words and words[0] in ("cd", "pushd"):
            dest = [a for a in words[1:] if not a.startswith("-")]
            where = _full(dest[0] if dest else "~", where)
        words = []
    return where


def lease_reason(inp, session_id, cwd=None, agent=None):
    """LEASE_DENY or MAIN_CHECKOUT_DENY for the first of this call's files
    that meets one, else None. `agent` is Claude's `agent_id`. Fails open: no
    `spawned` row and no `agent_id`, no open record of that slice, an
    unreadable journal."""
    if spawn_of is None or tezgah_task is None or not session_id:
        return None
    spawn = spawn_of(session_id) or ((session_id, agent) if agent else None)
    if not spawn:
        return None
    here = cwd or os.getcwd()
    try:
        if inp.get("command") or inp.get("cmd"):
            here = _shell_dir(inp, here)
        for path in write_paths(inp):
            if (URI_CHANNEL.match(path) or scratch_target(path, here)
                    or unnamed_target(path, inp)):
                continue
            real = os.path.realpath(os.path.join(here, os.path.expanduser(path)))
            repo = tezgah_task.main_repo(real)
            me = tezgah_task.slice_of(repo, *spawn) if repo else None
            if not me or me.get("status") != "open":
                continue
            tree = me.get("declared") or ""
            top = linked_main(real) and tezgah_task._sibling_worktree(real, repo)
            rel = os.path.relpath(real, top or repo).replace(os.sep, "/")
            if rel.startswith((".tezgah/", "../")) or rel == ".tezgah":
                continue
            if not top and tree and tree != repo and os.path.isdir(tree):
                return MAIN_CHECKOUT_DENY % (rel, repo, me["id"], tree)
            if any(tezgah_task.match(rel, g) for g in me.get("owns") or ()):
                continue
            owner = tezgah_task.owner_of(repo, rel, spawn[0], me["id"])
            if owner:
                return LEASE_DENY % (rel, owner.get("name") or owner["id"],
                                     ", ".join(owner["owns"][:3]), _channel(owner),
                                     owner["id"])
    except Exception:
        return None
    return None


def spawn_advice(tool, inp, session_id, cwd=None):
    """The shared-worktree warning for a spawn call (`tezgah_task.worktree_clash`),
    else None. A warning, never a deny: a fan-out of read-only reviewers on one
    checkout is fine, and the agent name is how this reads which ones are. Off
    under `orchestrate-off`, whose rule text it backs."""
    if (str(tool or "").lower() not in SUBAGENT_TOOLS or tezgah_task is None
            or not cwd or off("orchestrate-off")):
        return None
    try:
        root = tezgah_task.main_repo(cwd)
        return tezgah_task.worktree_clash(root, tool, inp, session_id or "") if root else None
    except Exception:
        return None


# The cross-project write notice: a session works under the rules of the
# repository its cwd is in, so a write into another one is under none of that
# repository's plans, lessons or slice journal (research orchestrator-flow-audit
# S7, finding 7). A notice, never a refusal: the write may be the user's ask.
CROSS_PROJECT = (
    "tezgah: this write is in %s, not in this session's repository (%s). That "
    "repository's plans, lessons and slice journal do not apply to this session. "
    "Work on that project from a session opened there.")


def _main_repo(path):
    """The main checkout of the repository holding `path`, else None
    (`tezgah_task.main_repo`: a repository's own `.tezgah` is that repository)."""
    return tezgah_task.main_repo(path) if tezgah_task is not None else None


def cross_project_note(session_id, tool, inp, cwd):
    """CROSS_PROJECT when this write call's file lies in another repository than
    cwd's (a worktree counts as its main checkout), once per session per target
    repository (a `nudged` mark), else None. Every host's post-tool channel
    carries it beside its other notices. Total: any failure is no notice."""
    try:
        name = str(tool or "").lower()
        if (name not in WRITE_TOOLS and name not in BASH_TOOLS) or not cwd \
                or not isinstance(inp, dict) or inp.get("command") == "view":
            return None
        here = _main_repo(cwd)
        for path in write_paths(inp):
            if URI_CHANNEL.match(path) or scratch_target(path, cwd):
                continue
            there = _main_repo(os.path.join(cwd, path))
            if not there or there == here:
                continue
            key = "cross:" + hashlib.sha1(("%s\0%s" % (session_id, there)).encode(
                "utf-8", "replace")).hexdigest()[:16]
            return CROSS_PROJECT % (there, here or cwd) \
                if tezgah_store.mark("nudged", key) else None
    except Exception:
        return None
    return None


# --- task scope: the plan's own phase and path allowlist --------------------
# What this closes: a session that has declared what it is working on - a plan
# file under .tezgah/plans/open is active, so the work has a phase and the
# files it may touch - and then writes anyway. Two shapes cost real work: a
# write in `discovery`, where the whole point of the phase is to read before
# deciding, and a write outside the plan's own allowlist, which is how a
# bounded task quietly becomes an unbounded one. The record is written by
# bin/tezgah-task, which the orchestrating session runs itself: the plan's
# lifecycle is the orchestrator's job, never a hand-off to the user. What keeps
# the boundary is the CLI, not who runs it - a writing phase needs every
# Acceptance item to name its proving command, `implementation` an answered
# spike and a checkpoint, `close done` an approving review - so the record's own
# file is refused to a write (TASK_RECORD_DENY): retyping the frontmatter is the
# direct route that skips those checks. A shell line's positional target (`sed
# -i`, `cp`) is not read here (see write_paths), the residual this rule names.
#
# The direction is fail-open wherever the record is missing, unreadable or out
# of phase vocabulary (tezgah_task.active returns None for those): a rule that
# refused every write until a record appeared would be the fail-closed trap the
# design report names, with the whole session as its blast radius. An empty
# allowlist is no scope declared rather than "nothing is allowed", so the phase
# is the whole requirement there.
#
# The refusals name the CLI move, because running it is the work the rule asks
# for and the CLI vets it. E7 measured a refusal that named a way to take the
# rule off (the armed arm disabled the gate in 25 of 25 runs); the switches that
# do that stay behind the control-plane rule below.
TASK_PHASE_DENY = (
    "Task gate: the active task %s is in phase `%s`, and this call writes. "
    "Writes belong to %s. Finish the reading this phase is for, then move the "
    "phase yourself with `tezgah-task phase implementation` - it refuses until "
    "the plan's Acceptance, spike and checkpoint are in order.")
TASK_SCOPE_DENY = (
    "Task gate: %s is outside the paths the active task %s allows (%s). If the "
    "plan's work genuinely reaches it, widen the scope yourself (allow replaces "
    "the list, so this keeps the current globs): `%s --why \"<what in the plan "
    "reaches it>\"`; otherwise leave the file alone.")
# a target outside the repository: an allow glob is repo-relative, so none reaches it
TASK_SCOPE_OUTSIDE = (
    "Task gate: %s is outside the paths the active task %s allows (%s). It lies "
    "outside this repository, and an allow glob is relative to it, so no "
    "`tezgah-task allow` line reaches it; leave the file alone, or do the work "
    "under that repository's own task.")
TASK_RECORD_DENY = (
    "Task gate: %s is the active task's own record; only `tezgah-task` writes it, checking the plan's "
    "Acceptance, spike and review on the way. The phase and allowlist: `tezgah-task phase|allow`; an "
    "Acceptance box: `tezgah-task tick NNN <n>`; State/Next: `tezgah-task note NNN state|next \"...\"`.")
# The shapes that make a shell command a write, for the phase rule below. The
# tools are not the only way to change a file, and E7b measured the other one:
# with `edit` and `write` refused twelve and six times, the armed arm wrote the
# target with `cat > app/api.py <<'EOF'` instead in 3 of 25 runs - every one of
# them a redirect. The table is the secret rule's sink list plus the in-place
# editors and the copiers, because the shape reached for after the first one is
# refused is the next one here. Masked text is read, so a quoted `>` is not a
# redirect, and `> /dev/null` is not a write to a file.
# ponytail: a write inside a string the shell parses later (`python3 -c
# "open('x','w')"`) is not read - telling a read from a write there needs the
# mode argument, not the call - so the table holds the shapes an agent reaches
# for, and the phase still refuses the ones it holds. A code-execution tool is
# not this rule's at all, and E7c measured what that costs: one row in 25 wrote
# the target through `eval` after both the write tools and the shell were
# refused, so the residual is named here rather than closed.
SHELL_WRITE = re.compile(
    r">>?(?!\s*/dev/null)(?![&=])|"
    r"\|\s*tee\b|"
    r"(?<![\w-])(?:sed|perl)\s+(?:-\S+\s+)*(?:-[A-Za-z]*i[A-Za-z]*)(?![A-Za-z])|"
    r"(?<![\w-])truncate\s|"
    r"\bdd\s+[^|;&]*\bof=|"
    r"(?<![\w-])(?:cp|mv)\s|"
    r"(?<![\w-])patch\s|"
    r"(?<![\w-])git\s+(?:apply\b|restore\b|checkout\s+--)")
TASK_SHELL_DENY = (
    "Task gate: the active task %s is in phase `%s`, and this command writes a "
    "file. The shell is a write route like any other, so the phase covers it. "
    "Finish the reading this phase is for, then move the phase yourself with "
    "`tezgah-task phase implementation`.")


# The marker a caller passes when it has NOT read the record, so a rule reads it
# itself; a resolved `None` (no active task) is passed as None and is never
# re-read. `decision` resolves once and hands the same dict to all four rules,
# because each read re-lists `.tezgah/plans/open/` and re-parses the plan on a
# path every write of every session takes.
_UNRESOLVED = object()


def _task(cwd, base, task):
    """The active record: the caller's when it resolved one, else resolved here.
    A missing tezgah_task module yields None - the rule is lost, never the
    session, the same fail-open the guarded import takes."""
    if task is not _UNRESOLVED:
        return task
    if tezgah_task is None:
        return None
    return tezgah_task.active(cwd, base, held=True)


def _resolved(spelled, top, command):
    """A write target as the task rules read it: a shell target behind a
    variable the same line set to the checkout is that checkout path
    (`known_tail`); any other target is the call's own spelling."""
    return (known_tail(spelled, top, command) or spelled) if command else spelled


# worktree_task per (target, cwd, base) for one decision: the phase, scope and
# checkpoint rules each ask it of the same targets, and each answer costs a
# realpath and a read of the worktree's pointer files. `decision` clears it.
_WORKTREE_TASKS = {}


def _worktree_task(path, cwd, base):
    key = (path, cwd, base)
    if key not in _WORKTREE_TASKS:
        _WORKTREE_TASKS[key] = tezgah_task.worktree_task(path, cwd, base)
    return _WORKTREE_TASKS[key]


# Files under no repository that the task rule still holds: an agent definition,
# an instruction file or a shell rc steers every later session, so it is never
# the repository-free work `_no_repo` exempts. Globs relative to HOME, matched
# without case (a case-insensitive filesystem opens `~/.ZSHRC` as `~/.zshrc`).
HOME_HELD = (".claude/agents/**", ".claude/hooks/**", ".claude/commands/**",
             ".claude/skills/**", ".claude/CLAUDE.md", ".omp/agent/**",
             ".codex/AGENTS.md", ".codex/prompts/**", ".cursor/**",
             ".config/opencode/**", ".zshrc", ".zshenv", ".zprofile", ".zlogin",
             ".bashrc", ".bash_profile", ".bash_login", ".profile")
# A line that makes a link: a path under no checkout may point into one by the
# time the write runs (`ln -s <repo>/hooks ~/l && echo x > ~/l/a.py`).
LINK_MAKER = re.compile(
    r"(?<![\w-])(?:ln|link|install)\s|"
    r"(?<![\w-])cp\s[^;&|\n]*?(?:\s-[A-Za-z]*[sl]|\s--(?:symbolic-)?link\b)")
# A line that moves the directory, however spelled (`builtin cd`, `X=1 cd`,
# `(cd x; ...)`), or reads it back (`$PWD`, quoted or not): where its targets
# land is not read.
DIR_MOVE = re.compile(r"(?<![\w-])(?:cd|pushd|popd)\b")
PWD_READ = re.compile(r"\$\{?(?:OLD)?PWD\b")


def _no_repo(path, inp, cwd, command):
    """True when the write target `path` is no repository's work, so the task
    rules leave it to the rules every write meets (plan 094: the user's
    `~/.config/runpod/key` was refused as outside the repository).

    Every doubt holds it: a line that moves the directory or makes a link, a
    parent directory that does not exist yet, a file with a second hard link
    and HOME_HELD. Then a target under a git checkout or a configured root is
    some repository's; a relative one is read in the call's own directory."""
    masked = mask(command) if command else ""
    if (DIR_MOVE.search(masked) or PWD_READ.search(command or "")
            or LINK_MAKER.search(masked)):
        return False
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(_shell_dir(inp, cwd) if command else cwd or "", path)
    path = os.path.normpath(path)
    real = os.path.realpath(path)
    if root_for(real) or _toplevel(real) or not os.path.isdir(os.path.dirname(real)):
        return False
    try:
        if os.path.isfile(real) and os.stat(real).st_nlink > 1:
            return False
    except OSError:
        return False
    home = os.path.expanduser("~")
    for p, h in ((path, home), (real, os.path.realpath(home))):
        rel = os.path.relpath(p, h).replace(os.sep, "/").casefold()
        if not rel.startswith("../") and any(
                tezgah_task.match(rel, g.casefold()) for g in HOME_HELD):
            return False
    return True


def _write_targets(inp, command):
    """The targets the task rules read: for a shell line that writes, every
    redirect and `tee` target (`shell_targets`, expanded as `write_paths`
    expands its one), else write_paths."""
    if command and SHELL_WRITE.search(mask(command)):
        return [os.path.expanduser(_expand(t, command)) for t in shell_targets(command)]
    return write_paths(inp)


def _owners(inp, cwd, base, task):
    """The records this call's write targets are held to, each once: plan NNN's
    for a target in a sibling worktree on a `plan/NNN-...` branch
    (`tezgah_task.worktree_task`), none for a target that is no repository's
    (`_no_repo`), the active task for every other target, and the active
    task alone when the call names no target.

    A shell line is read target by target (`shell_targets`: every redirect and
    `tee` target). The cwd's task is an owner too when the line writes where no
    target was read: a positional writer (`sed -i`, `cp`, `mv`, `truncate`,
    `dd`, `patch`, `git apply`, a `tee` with other than one operand) or more
    write shapes than targets read.

    A held reading (`tezgah_task.active` with `held`: every phased plan is held
    by its worktree, and this checkout is none of them) owns no target: a
    held plan's scope is its worktree's, so a target outside the plan worktrees
    is held to no plan."""
    scope = None if task.get("held") else task
    top = tezgah_task.repo_root(cwd, base) if cwd else None
    command = str(inp.get("command") or inp.get("cmd") or "") if isinstance(inp, dict) else ""
    paths = _write_targets(inp, command)
    out = []
    for spelled in paths:
        path = _resolved(spelled, top, command)
        if _no_repo(path, inp, cwd, command):
            continue
        own = _worktree_task(path, cwd, base) or scope
        if own and own not in out:
            out.append(own)
    if command and scope and scope not in out:
        masked = mask(command)
        shapes = SHELL_WRITE.findall(masked)
        positional = any(not s.startswith(">") and "tee" not in s for s in shapes) or any(
            len([t for t in re.split(r"[;&|<>\n]", masked[m.end():], maxsplit=1)[0].split()
                 if not t.startswith("-")]) != 1
            for m in re.finditer(r"\|\s*tee\b", masked))
        if positional or len(shapes) > len(paths):
            out.append(scope)
    return out if paths or not scope else [scope]


def task_shell_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when this shell command writes a file and the phase of the
    record its target is held to (`_owners`: a plan worktree's own plan, else
    the active task) only reads, else None.

    The route to the hole the phase rule closes, and the one E7b measured: with
    the write tools refused, the armed arm wrote the target with a heredoc
    redirect in 3 of 25 runs. A phase that excludes writes has to exclude them
    however they are made, so this reads the whole SHELL_WRITE table - the
    copiers and in-place editors whose target is a positional argument too. The
    allowlist is not consulted here: `decision` hands a shell command's redirect
    and `tee` targets (write_paths) to task_reason and task_record_reason like a
    write tool's path, while a positional target is not read at all (see
    write_paths), and the same fail-open holds: no record, no requirement."""
    task = _task(cwd, base, task)
    if not task or not SHELL_WRITE.search(mask(str(inp.get("command") or ""))):
        return None
    for own in _owners(inp, cwd, base, task):
        if own["phase"] not in tezgah_task.WRITE_PHASES:
            return TASK_SHELL_DENY % (own["id"], own["phase"])
    return None


def task_record_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when this write's target IS the active task's record, or
    any other open plan carrying a phase (a plan running beside it in its own
    worktree, `tezgah_task.branch_task`).

    The record is a file in the repo, so an agent that may write files could
    retype the phase instead of running the CLI, and skip the Acceptance, spike
    and review checks the CLI makes on the way. Refused whatever the phase and
    whatever the allowlist says - the record is not inside its own scope."""
    task = _task(cwd, base, task)
    if not task:
        return None
    # read against the main checkout, which keeps the records, so a session in
    # a plan worktree meets the same rule; without case, since a
    # case-insensitive filesystem opens `.TEZGAH/...` as the record
    record = (tezgah_task.main_relative(task["path"], cwd, base) or "").casefold()
    root = tezgah_task.repo_root(cwd, base)
    main = linked_main(root) or root
    for path in write_paths(inp):
        rel = tezgah_task.main_relative(path, cwd, base)
        if rel and (rel.casefold() == record or tezgah_task.phased_record(main, rel)):
            return TASK_RECORD_DENY % path
    return None


def task_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when the active task's phase or allowlist excludes this
    write, else None. No active task -> None: this rule never invents a
    requirement the user did not set.

    The record is read through tezgah_task, whose import is guarded: a checkout
    without that module costs this rule, never the session. The paths are the
    ones write_paths already extracts, so an apply_patch body is checked hunk by
    hunk like every other write rule's here. A path that resolves outside the
    repo root is refused by `relative` before any pattern is tried - a `**`
    allowlist must not reach out of the repo - unless it is the session's own
    scratch (`scratch_target`: a temp file, a device), which is no task's work,
    or is no repository's at all (`_no_repo`), which is no plan's;
    build output inside the repo is a repo path and stays held. The refusal
    names the file as the call spelled it, because the agent has to recognize
    its own argument.

    A target in a sibling worktree on a `plan/NNN-...` branch is held to plan
    NNN's record when that plan carries a phase (`tezgah_task.worktree_task`):
    two plans run at once, one per worktree, and neither's scope reaches into
    the other's checkout. Every other target keeps the active task."""
    task = _task(cwd, base, task)
    if not task:
        return None
    # a held reading scopes nothing outside the plan worktrees (`_owners`)
    scope = None if task.get("held") else task
    # The targets the plan scopes: not a URI or a shell target with no known
    # value (unnamed_target), and not tezgah's own gitignored workspace under
    # `.tezgah/` (research lines, lessons, briefs) - the active record there is
    # task_record_reason's, refused before this rule runs. A call whose every
    # target is one of those writes no project file, so the phase does not
    # refuse it either; a call with no target at all still meets the phase.
    # A shell line is read target by target: each redirect and `tee` target
    # meets the allowlist of the record it lands under.
    command = str(inp.get("command") or inp.get("cmd") or "") if isinstance(inp, dict) else ""
    paths = _write_targets(inp, command)
    project = []
    top = tezgah_task.repo_root(cwd, base) if cwd else None
    for spelled in paths:
        if unnamed_target(spelled, inp, top):
            continue
        path = _resolved(spelled, top, command)
        rel = tezgah_task.relative(path, cwd, base, worktrees=True)
        if rel is None and _no_repo(path, inp, cwd, command):
            continue
        full = os.path.join(cwd or "", os.path.expanduser(path))
        # the main checkout's `.tezgah` is every checkout's workspace (plan 097),
        # so a worktree session meets the exemption the main checkout gets there
        # (review of plan 097, F1); a phased record stays task_record_reason's
        ws_rel = rel if rel is not None else tezgah_task.main_relative(path, cwd, base)
        if ws_rel is not None and workspace_free(ws_rel, inp, full):
            continue
        own = (_worktree_task(path, cwd, base) if rel is not None else None) or scope
        if own:
            project.append((spelled, path, rel, own))
    if paths and not project:
        return None
    for own in [entry[3] for entry in project] or [o for o in (scope,) if o]:
        if own["phase"] not in tezgah_task.WRITE_PHASES:
            return TASK_PHASE_DENY % (own["id"], own["phase"],
                                      " or ".join(tezgah_task.WRITE_PHASES))
    for spelled, path, rel, own in project:
        patterns = own["allowed_paths"]
        if not patterns or scratch_target(spelled, cwd):
            continue
        if rel is None or not any(tezgah_task.match(rel, p) for p in patterns):
            # the call's own spelling: the agent has to recognize its argument
            if rel is None:
                return TASK_SCOPE_OUTSIDE % (spelled, own["id"], ", ".join(patterns))
            ready = " ".join(["tezgah-task allow"] + [shlex.quote(p) for p in
                                                      list(patterns) + [rel]])
            return TASK_SCOPE_DENY % (spelled, own["id"], ", ".join(patterns), ready)
    return None


# --- the implementation phase's checkpoint -----------------------------------
# What this closes: a large refactor has no single restore point. The reversible
# boundary the gate keeps is per file, not per work unit - hooks/tezgah_snapshot.py
# captures the pre-write bytes, 200 snapshots at 2 MiB each with the oldest
# evicted, and the glossary says so outright: "Not a checkpoint of the session,
# only of the files a write was about to change" (docs/glossary.md:143). The plan
# machine already names the exact moment the risky work starts - bin/tezgah-task
# writes `phase: implementation` and this module then holds writes to the plan's
# own allowlist - so that moment gets a named state too: the CLI records
# `checkpoint:` as the pre-work commit's sha when the tree was clean, or as
# `pending <sha>` when it was not, `<sha>` being the HEAD of that moment.
#
# Why the refusal is here and not only in the CLI: the CLI stands at the phase
# move and is where the sha is written, but the write is the moment the un-named
# state would be built on, and a plan can already be in `implementation` when
# this rule lands.
#
# The recorded sha is what the refusal is keyed on, and the tree only says the
# two states apart inside it: the sha is written at the phase move, and the commit
# the refusal names moves HEAD off it, so the refusal clears itself and the phase
# proceeds. Keying on the word `pending` alone did not: the commit left the record
# saying `pending`, only bin/tezgah-task rewrites that record, the agent may not
# run it, and the phase was then locked until the user happened to re-run the
# phase command - a gate that refuses the thing it asks for. Keying on the live
# tree alone would refuse the phase's own work, since the first write makes the
# tree dirty and it stays that way.
#
# Fail-open wherever the question cannot be answered: no record, no `checkpoint:`
# key, a checkpoint that is a plain sha (the boundary is already real), a `pending`
# with no sha, a sha this checkout's HEAD does not name, a repo whose HEAD cannot
# be read, and `task-off` above. A refusal has to rest on something a reader can
# check, and a rule that cannot answer must not refuse.
#
# The refusal names the one command that makes the boundary real: running it is
# the work the rule asks for, so naming it is naming what the rule wants rather
# than a way around it.
CHECKPOINT_DENY = (
    "Checkpoint gate: the active task %s is in phase `implementation` and its "
    "plan records a pending checkpoint (`checkpoint: pending <sha>`), so this "
    "write would start the work on top of changes no commit names - and the "
    "per-file snapshots are not one state to return to. The command that makes "
    "the boundary real is %s; it moves HEAD off the recorded sha, so running it "
    "satisfies this rule and moves nothing.")


def checkpoint_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when the record a write target is held to (`_owners`: a
    plan worktree's own plan, else the active task) is in `implementation`, its
    plan's `checkpoint:` waits for a commit (`pending <sha>`), that sha is still
    HEAD of the checkout the plan works in (the plan's worktree, else this
    root), and that tree still holds uncommitted work - else None.

    The recorded sha, not the word `pending`, is the switch: the commit the
    refusal names moves HEAD off it, so the refusal clears by itself. The section
    above carries what this closes, why the record and not the tree is the
    switch, and every shape that fails open."""
    if tezgah_task is None:
        return None
    command = inp.get("command")
    if command is not None and not SHELL_WRITE.search(mask(str(command))):
        # a shell line that changes no file is not this rule's, the same read of
        # the same shape table task_shell_reason makes
        return None
    paths = write_paths(inp)
    if command is None and paths and all(URI_TARGET.match(p) for p in paths):
        return None     # a tool device or a message changes no tree state
    task = _task(cwd, base, task)
    if not task:
        return None
    for own in _owners(inp, cwd, base, task):
        reason = _pending_checkpoint(own, own.get("worktree")
                                     or tezgah_task.repo_root(cwd, base))
        if reason:
            return reason
    return None


def _pending_checkpoint(task, root):
    """checkpoint_reason for one record against the checkout `root`."""
    if task["phase"] != "implementation":
        return None
    sha = tezgah_task.checkpoint_sha(task.get("checkpoint"))
    if not sha:
        return None
    # HEAD read from the ref file, not a fork: this question is asked on every
    # write of the phase, and an unreadable HEAD fails open.
    if _head(root) != sha:
        return None
    import subprocess  # deferred: only a plan still pending its checkpoint pays
    try:
        listed = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if listed.returncode != 0 or not listed.stdout.strip():
        return None
    return CHECKPOINT_DENY % (task["id"], tezgah_task.checkpoint_command(
        task["path"], task.get("worktree")))


# --- workspace: per-project tezgah state lives under <repo>/.tezgah only ------
# What this closes: sessions wrote `plans/`, `research/` and `analysis/` at the
# project root (observed across several unrelated projects on one machine),
# where the project's own git picks them up. A root directory the project itself
# already tracks files under is the project's own and is left alone.
# ponytail: `mkdir research` and a positional shell target (`cp x research/`) are
# not read, the same ceiling as write_paths; the first file written through a
# tool or a redirect is.
WORKSPACE_KINDS = ("plans", "research", "analysis")
WORKSPACE_DENY = (
    "Workspace gate: %s puts tezgah state in the project's own `%s/`. Per-project "
    "plans, research and analysis live under `.tezgah/%s/` - ignored by the "
    "project, committed with `git -C .tezgah ...` - so write it there.")


def workspace_reason(inp, cwd, base):
    """A deny reason when this write lands in a root `plans/`, `research/` or
    `analysis/` the project does not track, else None."""
    if tezgah_task is None:
        return None
    for path in write_paths(inp):
        rel = tezgah_task.relative(path, cwd, base)
        seg = rel.split("/", 1)[0] if rel and "/" in rel else None
        if seg not in WORKSPACE_KINDS:
            continue
        import subprocess  # deferred: only a write under one of the three pays
        try:
            listed = subprocess.run(
                ["git", "-C", tezgah_task.repo_root(cwd, base), "ls-files", "--", seg],
                capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        if listed.returncode == 0 and not listed.stdout.strip():
            return WORKSPACE_DENY % (path, seg, seg)
    return None


# --- lesson lineage: a ledger write in a turn that read untrusted text -------
# What this records (security-08): any session can append a standing constraint
# to `.tezgah/lessons.md`, and a line written in a turn that read a web page, an
# MCP answer or a subagent's report is injected into every later session like
# one the user asked for. Owner decision ADR 010: a tainted lesson costs a row,
# never a refusal - so this is not a rule, has no `_deny` slug and no switch of
# its own beyond `pretooluse-off`. The fold is over every row of the user turn
# (`turn_rows`, scoped to the calling subagent), not `tezgah_untrusted.
# turn_channel`: that is a pending state the first effect after the read spends,
# and a lesson is usually written after other work.
# ponytail: a shell write whose body is not a heredoc (`echo x >> lessons.md`),
# or whose target is a positional argument (`cp`, `sed -i`), leaves a row with
# no `key` or no row at all - the gate cannot read the line it adds - so the
# context cannot label that line.
#
# History, whatever the turn read (plan 077, rsi-borrow-screen idea 2): a write
# that rewrites or removes a ledger line leaves one `lesson_changed` row per such
# line, keyed by the old line and carrying its text, so a standing constraint
# that was edited away can be read back from the ledger. Still never a refusal.
# ponytail: a shell write the gate cannot read the new text of (`sed -i`, an
# `echo >` body) leaves no `lesson_changed` row, and a rewritten line carries no
# `new_key`: the row contract (`tezgah_integrity.LEDGER_FIELDS`) has no field
# for it, so the line's new key rides only its `lesson_tainted` row, if any.
LESSON_CHANGED_MAX = 10


def lesson_taint(tool, inp, cwd, session_id, agent=None, shell_body=None):
    """Write one `lesson_tainted` row per lesson line this call leaves in a
    ledger that the ledger did not hold, when the user turn already holds a row
    carrying `source`; a single row with no `key` when the call names no new
    line the gate can read (an unread body, an edit whose old text is not there,
    a removal). A write tool's lines are read off the file as it will be once
    the call lands (`_after_text`), so a partial-line edit names the line it
    leaves, not its fragment. The keyed rows also go to the ledger's repository
    index (`tezgah_lessons.write_taint`), which the context labels lines from.
    In any turn, one `lesson_changed` row per ledger line the call drops - its
    old `key`, its old text in `detail` (redacted by `note`), the ledger in
    `target`: read off the post-write text, a patch's `-` lines, or a shell
    heredoc that overwrites the file; an append drops nothing.
    Returns nothing: it is never a refusal."""
    if tezgah_lessons is None or not session_id:
        return
    t = str(tool or "").lower()

    def norm(path):
        return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))

    written = write_texts(inp if t in WRITE_TOOLS else shell_body)
    texts = {norm(path): new for path, _old, new in written}
    targets = sorted(p for p in set(texts) | set(map(norm, write_paths(inp)))
                     if tezgah_lessons.is_ledger(p))
    if not targets:
        return
    source = next((row["source"] for row in reversed(
        turn_rows(session_id, agent=agent)) if row.get("source")),
        None) if turn_rows else None
    minus = {norm(path): old for path, old, _new in written}
    key_of = tezgah_lessons.lesson_key
    for path in targets:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                current = fh.read()
        except OSError:
            current = ""
        lines = tezgah_lessons.entries(current)
        have = set(map(key_of, lines))
        new = texts.get(path)
        gone = ()
        if t in WRITE_TOOLS and new is not None:
            after = _after_text(inp, current)
            if after is None and path in _patch_deletes(inp, norm):
                gone = list(dict.fromkeys(lines))    # a patch's Delete File
            elif after is None:  # a patch: its `-` lines leave, its `+` lines land
                gone = _dropped(tezgah_lessons.entries(minus.get(path) or ""), new)
            else:
                new, gone = after, _dropped(lines, after)
        elif new is not None and not _shell_appends(inp.get("command")):
            gone = _dropped(lines, new)
        fields = dict(target=path, agent=agent, workspace=root_for(cwd),
                      id=call_id(tool, inp))
        # a rewrite of the whole ledger would otherwise push the refusal rules'
        # fixed tails (the last verify, prior calls) out of their window
        for line in gone[:LESSON_CHANGED_MAX]:
            note(session_id, "lesson_changed", line, key=key_of(line), **fields)
        if len(gone) > LESSON_CHANGED_MAX:
            rest = len(gone) - LESSON_CHANGED_MAX
            note(session_id, "lesson_changed", "%d more lines changed" % rest,
                 items=rest, **fields)
        if not source:
            continue
        keys = [k for k in dict.fromkeys(map(key_of, tezgah_lessons.entries(
            new or ""))) if k not in have] or [None]
        for key in keys:
            note(session_id, "lesson_tainted", source, key=key, source=source,
                 **fields)
        if keys != [None]:
            write_taint(os.path.dirname(os.path.dirname(path)), have | set(keys),
                        [{"key": k, "source": source, "ts": int(time.time())}
                         for k in keys])


PATCH_DELETE = re.compile(r"^\*\*\* Delete File: (.+?)\s*$", re.M)


def _patch_deletes(inp, norm):
    """The paths an apply_patch input deletes (`*** Delete File: <path>`), normed;
    read from the patch text itself, so a hunk of blank lines is not a delete."""
    text = "\n".join(v for v in (inp or {}).values() if isinstance(v, str))
    return {norm(p) for p in PATCH_DELETE.findall(text)}


def _dropped(lines, after):
    """The ledger `lines` the text `after` no longer holds, once each, in order."""
    keep = set(map(tezgah_lessons.lesson_key, tezgah_lessons.entries(after)))
    return [ln for ln in dict.fromkeys(lines)
            if tezgah_lessons.lesson_key(ln) not in keep]


def _shell_appends(command):
    """Whether a shell write's body is added to its target (`>>`, `tee -a`) rather
    than replacing it; True when the target is not read (no row beats a false one)."""
    m = SHELL_TARGET.search(mask(str(command or "")))
    return not m or m.group(0).startswith(">>") or bool(
        re.search(r"\s-(?:[A-Za-z]*a[A-Za-z]*|-append)\s", m.group(0)))


# --- the shell's write body: three write-tool rules reached through a heredoc -
# What this closes (the route E7c measured): SKIP_TEST, ATTRIB_LINE and the
# prefixed-token credential scan (secret_edit) read the text a write tool lands,
# and the write tools are disjoint from BASH_TOOLS, so a heredoc that wrote a
# test skip, an attribution line or a key into a file was refused by nothing -
# and E7c watched the armed arm take exactly that route once the write tools
# were refused (3 of 25 runs wrote the target with `cat > app/api.py <<'EOF'`).
# Each of the three now also reads the body a shell command writes, and the body
# is the RAW text because mask() blanks heredoc bodies by design: a command that
# merely names a rule must not be denied.
#
# The shape test is the task rule's own SHELL_WRITE, read off the masked text, so
# a quoted `>` is not a redirect; the bodies come from the raw text under it, one
# per marker, with an unterminated heredoc skipped the way tezgah_integrity's own
# blanker skips it (the ceiling the two share).
# ponytail: only a heredoc's body is read. A write whose content is a quoted
# argument (`echo "Co-Authored-By: x" > f`) is not, and cannot be: the credit
# there sits inside a string no line-start anchor can see, while widening this to
# the whole command text would deny a search for the form (`grep "Co-Authored-By"
# x > out`). The measured route is the heredoc, and that route is closed.
SHELL_TARGET = re.compile(r">>?(?![&=])\s*(\S+)|(?<![\w-])tee\s+(?:-\S+\s+)*(\S+)")


def shell_target(command):
    """The file a shell command's own text writes, or "" - the real redirect's
    target, or `tee`'s argument, sliced from the raw text at the offset the masked
    match proved (masking keeps length), so a quoted `>` is not a redirect and
    `> /dev/null` is not a file.

    The one reader of a shell write's target: `write_paths` uses it for the file
    a shell call changes (which is what makes the gate capture a pre-state for
    that write and `_post_write` hash its after-state), and `shell_write_body`
    uses it for the file whose body the three write-tool twins read. Empty for a
    command that writes nothing, and for every write whose target is a positional
    argument rather than a redirect - see `write_paths`.

    ponytail: a target that is a QUOTED name (`printf a > "a;b.txt"`) is not read
    at all - the slice is taken by offset from the masked text, and masking blanks
    a quoted string, so the match never lands. Measured 2026-09-19: the call
    captures nothing and its write stays out of the freshness fold, the same hole
    the separator trim closed for an unquoted chain. Closing it means reading the
    target off the raw text with a quote-aware scan."""
    c = str(command or "")
    if not c:
        return ""
    masked = mask(c)
    if not SHELL_WRITE.search(masked):
        return ""
    m = SHELL_TARGET.search(masked)
    return _target_slice(c, m) if m else ""


def _target_slice(c, m):
    """The target one SHELL_TARGET match `m` (over the masked text) names in the
    raw command `c`."""
    start, end = m.span(1) if m.group(1) else m.span(2)
    raw = c[start:end]
    # `\S+` runs to the next whitespace, so the separator of a chained command
    # came with the name: `printf a > x; printf b > y` sliced `x;`, a path
    # nothing is ever written to - no pre-state captured, no after-state hashed,
    # and the write invisible to the freshness fold. A quoted target keeps its
    # name whole, so only an unquoted slice is trimmed.
    if raw[:1] in ("'", '"'):
        return raw.strip("'\"")
    return raw.strip("'\"").rstrip(";|&)")


def shell_targets(command):
    """Every redirect and `tee` target a shell command's text names, in order,
    `> /dev/null` aside - the per-target reading the task rules need where
    `shell_target` gives the first one only."""
    c = str(command or "")
    masked = mask(c)
    return [t for t in (_target_slice(c, m) for m in SHELL_TARGET.finditer(masked))
            if t and t != "/dev/null"]


def shell_write_body(command, cwd=None):
    """The `{file_path, content}` a shell command writes into a file, or None when
    this command writes no file's content of its own.

    The shape test is SHELL_WRITE on the masked text, so a quoted `>` is not a
    redirect; the path is that real redirect's target, or `tee`'s argument, sliced
    from the raw text at the offset the masked match proved (masking keeps
    length), and resolved against the call's own directory - so a write to a test
    file is compared against the file the call named and not against whichever one
    the hook process happens to sit in."""
    c = str(command or "")
    if not c or not SHELL_WRITE.search(mask(c)):
        return None
    # the bodies bash reads (tezgah_integrity._heredocs): a `<<'X'` inside a
    # quoted string or a comment is not one (review R1)
    bodies = heredoc_bodies(c)
    if not bodies:
        return None
    path = shell_target(c)
    if path and not os.path.isabs(path):
        path = os.path.join(cwd or os.getcwd(), path)
    return {"file_path": path, "content": "\n".join(bodies)}


# --- ordering: a commit while the newest check failed -----------------------
# The one rule here that asserts a relation between two actions rather than
# reading one call plus a ledger tail - the shape FAVA found in 90% of real
# agent-instruction projects ("do not commit before running the tests") and the
# one this gate did not carry (C9). It is the contract's own claim - nothing is
# reported done unless the output was seen - given a mechanical half at the one
# moment a claim is written into the repository's history.
#
# The reader is the Stop rule's own fold over the tail (`_last_verify` on the
# last ORDER_TAIL rows), and the rule is structurally incapable of firing in
# either direction that would punish honest work: no check at all folds to None
# and a passing newest check folds to "ok", so a commit in a session that ran no
# check, and a commit after a green run, both pass. Only "fail" refuses - the
# newest check in this session rejected the tree the commit would freeze - and
# the refusal names that check. What lifts it is making the newest check pass
# (fix what it reported and run it again), so the reason names no command, the
# way the task refusals do not: a refusal is a boundary or it is an instruction.
# ponytail: the state is session-wide, not turn-scoped, so a probe the user asked
# to fail and a check that failed before this turn's prompt both count; the
# repair is the same either way, and a turn-scoped reader would let a commit
# through on a tree the failed check still describes.
ORDER_TAIL = 200
COMMIT_CMD = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*commit(?=\s|$|[|;&])")
ORDER_DENY = (
    "Commit order denied: the newest check in this session failed, and a commit "
    "is a claim that the tree passed. What would be frozen is the state that "
    "check just rejected - the newest failing one was %s - so fix what it "
    "reported and run it again, commit once the newest check is green, or say "
    "plainly that it is failing and why the commit is wanted anyway.")


def commit_order_reason(command, session_id):
    """A deny reason when this session's newest check failed and this command is
    a commit, else None.

    Not a rule about commits: with no check in the tail the fold is None and
    nothing is refused, which is what keeps an ordinary commit in a session that
    ran nothing - a docs edit, a message-only change - out of it."""
    if not (session_id and _last_verify):
        return None
    if not COMMIT_CMD.search(mask(str(command or ""))):
        return None
    rows = events(session_id, tail=ORDER_TAIL)
    if _last_verify(rows) != "fail":
        return None
    return ORDER_DENY % _failed_check(rows)


# --- constraint drift: a long turn loses the rules it started with ----------
# The re-statement that keeps the rules alive rides the user prompt
# (tezgah_context.context_for writes PROMPT_REMINDER on every turn), so the
# stretch nothing covers is one turn that runs long: by step 25 the prompt that
# armed the rules is dozens of tool results back and has stopped steering. The
# threshold counts work rows in the CURRENT user turn - the same rows counters()
# counts, a run/an edit/a check - which a normal turn reaches a handful of, and
# the mark is per turn: one re-statement in a turn that drifted is useful, the
# same one in every short turn is noise the agent learns to skip.
#
# It is delivered as a refusal - the gate's reason string - and nowhere else: no
# host's result side carries it. An internal plan measured the result-channel delivery
# and its pre-registered counter-metric sent it back here.
DRIFT_STEPS = 25
# How far back the count reads: the same 200-row bound the repeat guards read, so
# one gated call parses at most that many rows. Past that bound the window holds
# neither the turn's own marker nor the one the notice wrote, so the read falls
# back to the turn's own start (the module's own turn-scoped reader).
DRIFT_TAIL = 200
DRIFT_DENY = (
    "Long turn (%d work rows in, past the %d this notice waits for): the "
    "constraints this session was armed with are still in force. %s This is a "
    "re-statement, not a violation report: re-issue this call unchanged and "
    "carry on.")


def drift_text(cwd, session_id):
    """The body of the drift notice: the delta since this turn began where the
    context module can produce one, else the standing constraints themselves.

    A long turn's actual failure is often that a value moved under it - HEAD, a
    lessons count, the plan set - and a re-statement cannot say that: it repeats
    what the session was armed with rather than what changed since. So the newer
    half wins where it is available: `tezgah_context.constraint_notice` folds the
    per-turn stamp the prompt path writes into one line ("state since your last
    turn: ..."), and it hands back this module's own `constraints_line` verbatim
    when it has no stamp for this session, so a session it cannot speak about
    reads exactly as before. Imported inside the call (only the call that crosses
    DRIFT_STEPS pays for it) and guarded twice over: a checkout without the
    helper, or a stamp it cannot read, falls back to the re-statement, because a
    crash here would cost the host's whole envelope (tezgah_guard.safe wraps the
    adapter, and this is the one place a cheap fallback buys more than it costs)."""
    try:
        from tezgah_context import constraint_notice
        return constraint_notice(cwd, session_id)
    except Exception:
        return constraints_line(cwd)


def constraints_line(cwd):
    """The standing constraints as one line, from tezgah_policy's own text.

    `subagent_core` is the tested short form of every always-on rule (its bold
    label plus its opening clause, under the same kill-switch filtering), and its
    header already carries the on-demand rules' pointer, so the notice can
    neither name a rule that is off nor miss one that is on: it is a
    re-statement, never a second copy of the contract. POINTERS is not appended
    again - it printed the On-demand paragraph twice (audit CHAT-06). Imported
    inside the call because only the call that crosses DRIFT_STEPS pays for it."""
    from tezgah_context import core_for, render, subagent_core
    return " ".join(render(subagent_core(core_for(cwd)[0])).split())


def drift_reason(tool, inp, cwd, session_id):
    """A one-shot re-statement of the standing constraints when this user turn
    has run past DRIFT_STEPS work rows and this call is an effect, else None.

    What this deliberately is NOT: a detector of the rule the user meant. A
    PreToolUse payload carries the tool call, not the prompt - no host hook sees
    the text the user typed - so "which rule is being forgotten" would be a guess
    about intent wearing a check's clothes. Re-stating the standing constraints,
    or the delta since the turn began where the context module has one, is the
    honest half, and it is the whole of what this does (see drift_text). The host
    gives a PreToolUse hook no non-blocking way to reach the model either (the
    reason string is the only channel), so the notice arrives as a refusal whose
    reason is the re-statement, and the mark is written here - before the deny -
    so the identical call passes on the next attempt."""
    if off("reminder-off") or not effectful(tool, inp or {}):
        return None
    if not session_id:
        return None
    rows = events(session_id, tail=DRIFT_TAIL)
    start = _turn_start(rows)
    rows = rows[start:] if start else turn_rows(session_id)
    if any(row.get("kind") == "drift" for row in rows):
        return None
    steps = sum(1 for row in rows if row.get("kind") in STEP_KINDS)
    if steps < DRIFT_STEPS:
        return None
    note(session_id, "drift", str(steps), workspace=root_for(cwd))
    return DRIFT_DENY % (steps, DRIFT_STEPS, drift_text(cwd, session_id))


def effectful(tool, inp):
    """True when this call is one the constraints are about: a write tool, a
    git/gh command that lands an artifact, or an MCP effect
    (`tezgah_integrity.mcp_class`, which reads the name as the host matcher does,
    case-sensitive). A read changes nothing, so the notice spent on it would be
    spent where no rule applies."""
    t = str(tool or "").lower()
    if t in WRITE_TOOLS:
        return True
    if t in BASH_TOOLS:
        return bool(WRITE_CMD.search(mask(str(inp.get("command") or ""))))
    return mcp_class(tool) is not None


# --- ready: an idle `wait` while ready steps are open (plan 086, S1) ----------
# omp's `wait` blocks the parent until a job settles. Measured over 15 omp
# sessions, 68.3% of spawns were followed by `wait` with no other call between,
# and at 86 of the 163 such waits that had a todo list two or more items were
# open. The owner's default is a warning, never a deny: the line rides back with
# the wait's result, as the graph line does (`graph_advice`).
READY_WAIT = (
    "tezgah: idle wait - nothing ran since the spawn while %d ready todo "
    "step(s) are open: %s. Dispatch every ready step now, independent ones as "
    "subagents in one message, or mark it blocked on the slice it waits for. "
    "Ending the turn is the non-blocking alternative to `wait`: the host wakes "
    "you on the result.")


def ready_advice(tool, session_id, cwd=None):
    """The idle-wait warning for a `wait` call, else None: the newest spawn in
    the ledger tail is followed by no call but waits and todo updates, and the
    session's newest `todo` row (`tezgah_integrity.newest_todo`) holds a ready
    item no open slice of this session is working on
    (`tezgah_integrity.ready_heads`). A row with no `tool` (a turn marker, a
    `spawn` row) is no call. Off under `orchestrate-off`, whose rule text it
    backs."""
    if str(tool or "").lower() != "wait" or not session_id:
        return None
    if off("orchestrate-off"):
        return None
    rows = events(session_id, tail=DRIFT_TAIL)
    for row in reversed(rows):
        name = str(row.get("tool") or "").lower()
        if name in SUBAGENT_TOOLS:
            break
        if name and name != "wait" and name not in TODO_TOOLS:
            return None
    else:
        return None
    todo = newest_todo(reversed(rows))
    heads = ready_heads(todo, session_id, cwd) if todo else []
    if not heads:
        return None
    return READY_WAIT % (len(heads), "; ".join(cut(h, 48) for h in heads[:3]))


# --- plan required: work that spans files on main has no plan ----------------
# What this closes: a turn that wrote four product files - a hook, its tests, its
# docs and the changelog - straight onto `main`, with the plan opened afterwards.
# The task rule constrains a write only through a record the user made, so with
# no active task every product write passes and "work for a plan happens on its
# branch" is advice rather than a mechanism. Here the checkout is the record: on
# `main`/`master` the third distinct product file a single turn writes is
# refused, while a one- or two-file fix stays free - a plan is what makes work
# that spans files reviewable and closeable.
#
# The count is a fold over the turn's own write rows (`turn_rows`), so it needs
# no state of its own, and the call in hand contributes the files it names before
# the comparison: an `apply_patch` naming three product files is the third file by
# itself.
#
# Fail-open wherever the question cannot be answered: no session, no ledger, a
# checkout that is not a git repository, a detached HEAD (no branch to name), and
# a repo carrying the `.no-plan-gate` mark all pass - the direction every rule
# here takes, because a refusal has to rest on something a reader can check.
#
# ponytail: a PRIOR write recorded through the shell is a `run` row whose detail
# is the command, so it is not counted; only the call in hand contributes a shell
# target (`write_paths` reads the redirect). The turn this rule answers is the
# write-tool turn, and reading a shell command's target off a stored command line
# would be a second reader of the same table, not a new fact.
PLAN_BRANCHES = ("main", "master")
# The product paths the count reads, relative to the checkout holding the write:
# the code and docs a plan exists to scope. `.tezgah/` - and every other
# directory - is not one of them, and neither is a path outside any git checkout
# or a checkout outside every configured root (a scratch fixture repo).
PLAN_DIRS = ("hooks", "tests", "bin", "skills", "docs")
PLAN_FILES = ("statusline.py", "MANIFEST")
# The third file: two writes in a turn are a fix, three are work that spans files.
PLAN_WRITES = 3
PLAN_DENY = (
    "This turn has written %d distinct product files while the checkout is on "
    "`%s`. Work that spans files on `main`/`master` has no plan to review or "
    "close, so the third product file in one turn is refused: open a plan with "
    "the `plan-add` skill (`/tezgah:plan-add <description>`) and do the work on "
    "the `plan/NNN-slug` branch it creates. A one- or two-file fix stays free. "
    "Only `hooks/`, `tests/`, `bin/`, `skills/`, `docs/`, `statusline.py` and "
    "`MANIFEST` are counted; a `.tezgah/` path never is.")


def _gitdir(root):
    """The `.git` directory the checkout at `root` keeps its refs in, or "" when
    `root` does not name one: no `.git` entry, or a `.git` file that is not the
    `gitdir:` pointer a worktree writes."""
    dot = os.path.join(root, ".git")
    if not os.path.isfile(dot):
        return dot
    try:
        with open(dot, encoding="utf-8", errors="replace") as fh:
            line = fh.readline().strip()
    except OSError:
        return ""
    if not line.startswith("gitdir:"):
        return ""
    target = line[len("gitdir:"):].strip()
    return target if os.path.isabs(target) else os.path.join(root, target)


def _branch(root):
    """The branch the checkout at `root` is on, or "" when there is none to name:
    not a git repository (no `.git`), an unreadable HEAD, or a detached HEAD.

    Read from `.git/HEAD` rather than a `git` fork: the gate runs this on every
    product write, and one file read is the whole cost. A worktree's `.git` is a
    file naming the real gitdir, which is followed."""
    gitdir = _gitdir(root)
    if not gitdir:
        return ""
    try:
        with open(os.path.join(gitdir, "HEAD"), encoding="utf-8",
                  errors="replace") as fh:
            ref = fh.readline().strip()
    except OSError:
        return ""
    head = "ref: refs/heads/"
    return ref[len(head):] if ref.startswith(head) else ""


# A commit id as git writes it: 40 hex for the default object store, 64 for
# sha256. Both are accepted so the reader does not fail open on a repo whose
# object format the module never had to know.
_SHA = re.compile(r"[0-9a-fA-F]{40,64}")


def _packed_sha(gitdir, ref):
    """The sha `gitdir/packed-refs` names for `ref`, or "": a ref `git gc` folded
    out of its loose file still resolves, which is what keeps the reader from
    failing open on a repacked repository. The header line and a tag's `^`-peeled
    line carry no `ref` match, so only the ref's own line can answer."""
    try:
        with open(os.path.join(gitdir, "packed-refs"), encoding="utf-8",
                  errors="replace") as fh:
            for line in fh:
                sha, _, name = line.strip().partition(" ")
                if name.strip() == ref and _SHA.fullmatch(sha):
                    return sha
    except OSError:
        pass
    return ""


def _head(root):
    """The sha `HEAD` names for the checkout at `root`, or "" when the question
    cannot be answered: not a git repository, an unreadable HEAD, a ref with
    neither a loose file nor a packed-refs line, or a detached HEAD holding
    something that is not a sha.

    Read from `.git/HEAD` - the ref file, or the packed-refs line beside it -
    rather than a `git` fork, the way `_branch` reads the branch: the checkpoint
    rule asks this on every write of an `implementation` phase, and an
    unanswerable question must pass. A linked worktree keeps only its HEAD in
    its own gitdir; its branch refs, loose or packed, live in the common dir its
    `commondir` file names, so that is where the ref is read (plan 093 reads a
    plan worktree's checkpoint against that worktree's HEAD)."""
    gitdir = _gitdir(root)
    if not gitdir:
        return ""
    try:
        with open(os.path.join(gitdir, "HEAD"), encoding="utf-8",
                  errors="replace") as fh:
            ref = fh.readline().strip()
    except OSError:
        return ""
    if not ref.startswith("ref: "):
        return ref if _SHA.fullmatch(ref) else ""
    name = ref[len("ref: "):].strip()
    try:
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as fh:
            gitdir = os.path.join(gitdir, fh.readline().strip())
    except (OSError, UnicodeDecodeError):
        pass    # a main checkout's gitdir is its own common dir
    try:
        with open(os.path.join(gitdir, name), encoding="utf-8",
                  errors="replace") as fh:
            sha = fh.readline().strip()
    except OSError:
        sha = ""
    return sha if _SHA.fullmatch(sha) else _packed_sha(gitdir, name)


def _checkout(path, cwd):
    """`(top, rel)` for a write target: the nearest git checkout holding it and
    its path inside that checkout, or None when no checkout holds it or the path
    lies under a `.tezgah/` (which keeps a repository of its own and is never a
    product path).

    The branch question belongs to this checkout, not to the session's cwd: a
    session on `main` writing into a linked worktree on a plan branch is plan
    work, and one on a plan branch writing into a `main` checkout is not. A
    relative path is resolved against the call's own `cwd`."""
    text = str(path or "").strip()
    if not text or not cwd and not os.path.isabs(text):
        return None
    full = os.path.realpath(os.path.join(cwd or "", text))
    if ".tezgah" in full.split(os.sep):
        return None
    cur = os.path.dirname(full)
    while not os.path.lexists(os.path.join(cur, ".git")):
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    return cur, os.path.relpath(full, cur)


def _product(rel):
    """True when a checkout-relative path is one a plan exists to scope."""
    parts = rel.split(os.sep)
    return parts[0] in PLAN_DIRS or len(parts) == 1 and parts[0] in PLAN_FILES


def plan_reason(inp, cwd, session_id):
    """A deny reason when this write would be a turn's third distinct product
    file in a checkout on `main`/`master`, else None. The section above carries
    the trigger, the counted paths and the fail-open direction."""
    if not session_id or turn_rows is None:
        return None
    targets = {}
    for path in write_paths(inp):
        hit = _checkout(path, cwd)
        if hit and _product(hit[1]) and root_for(hit[0]):
            targets.setdefault(hit[0], set()).add(hit[1])
    if not targets:
        return None
    rows = None
    for top, written in targets.items():
        branch = _branch(top)
        if branch not in PLAN_BRANCHES \
                or os.path.exists(os.path.join(top, ".no-plan-gate")):
            continue
        if rows is None:
            # a row's `target` is already absolute against the cwd it was
            # recorded from; an older row without one resolves against this cwd
            rows = [_checkout(row.get("target") or row.get("detail"), cwd)
                    for row in turn_rows(session_id) if row.get("kind") == "edit"]
        written |= {rel for hit in rows if hit and hit[0] == top
                    for rel in (hit[1],) if _product(rel)}
        if len(written) >= PLAN_WRITES:
            return PLAN_DENY % (len(written), branch)
    return None


# ---------------------------------------------------------------------------
# Control plane. Every other rule here is held by a file the session can write:
# a kill switch is a file under OFF_DIRS, the Stop rule reads a ledger in the
# cache, the hooks are wired by files in each host's config. The REPORT measured
# 12 of 12 tamper shapes passing this gate (`touch ~/.config/tezgah/verify-off`,
# a Write to the same file, `rm .git/hooks/pre-commit`, an `echo` into the
# ledger, `git add -f .tezgah/x`, ...). The threat model is a cooperative but
# fallible agent (SECURITY.md): one that reaches for a switch it was shown,
# never one that writes a Python one-liner to get around the gate - that route,
# and any other interpreter, is named as a residual rather than closed.
#
# The deny names no command: with the unlock in the refusal the E7 block
# measured 25 of 25 armed runs disabling the gate. What the user runs to change
# the state is theirs to know.
CONTROL_DENY = (
    "Control plane: this call changes %s. That state is the user's, not the "
    "session's: they change it in their own terminal. Say what you wanted "
    "changed and why, and carry on without it.")
# The two targets plan 050's replay of three weeks of real ledgers (2026-10-07,
# rows 1, 3, 5 and 8) found refused without the user's say-so more than once a
# week: its falsifier (REPORT.md 5430, ADR 018) keeps the tamper evidence and
# drops the refusal. A call that changes one of these and nothing else the rule
# protects passes and leaves a `disarm` row (`decision`); a refusing target in
# the same call still refuses. Only a path strictly under the open plans counts:
# their directory or an ancestor of it takes every plan at once (HELD).
OPEN_PLAN = "an open plan"
FORCED_ADD = "a private `.tezgah/` path forced into the project's history"
CONTROL_EVIDENCE = frozenset((OPEN_PLAN, FORCED_ADD))
HELD = "a directory that holds tezgah's control state"
# A word the shell expands into names (a glob or a brace): directly under the
# open plans it names every plan, not one.
GLOB_CHARS = re.compile(r"[*?\[{]")


def _refusing(label):
    """True for a control label that refuses rather than leaves evidence."""
    return bool(label) and label not in CONTROL_EVIDENCE


# The CLIs that change control state, by basename with or without `.py`, and the
# first argument that makes a call a change: None is any call, "" any argument.
# `tezgah-gate decide` writes a genuine `began` row with `check=1`; the capture
# CLI writes snapshot rows; pony and adhd write CONFIG_DIR; `tezgah-context
# attest` re-attests a session, and a clean result clears its drift mark. The
# task CLI is not here: the orchestrating session runs it, and the checks that
# matter live in the CLI itself (see the task rule above).
# `tezgah-context user_prompt` is a prompt event, and a prompt naming a switch
# writes the `authorized` row the switch latch honors (tezgah_paths.off).
CONTROL_CLIS = {"tezgah-gate": ("decide",), "tezgah-capture": "",
                "tezgah-pony": "", "tezgah-adhd": ("on", "off"),
                "tezgah-context": ("attest", "user_prompt")}
# The hook entries a host runs, by basename without `.py`: run from a tool call
# with a forged payload on stdin, any of them writes genuine rows - a prompt's
# `authorized` row, a `began` row, a Stop verdict. A host adapter is `hook.py`
# under `hosts/<host>/` (HOOK_HOSTS); its launchers carry their own names.
HOOK_ENTRIES = frozenset(("projects-auto-init", "projects-pretooluse",
                          "projects-posttooluse", "projects-stop",
                          "tezgah-codex-hook", "tezgah-cursor-hook"))
HOOK_HOSTS = frozenset(("codex", "cursor", "omp"))
# Programs that change a path named in their arguments. Every positional is a
# target, except for the copiers, whose last one is (`cp switch /tmp` reads it).
# `sed`/`perl` count only with an in-place flag. `sqlite3` rewrites the cache
# stores, rows of `tezgah.db`, as `rm` would remove the files they were; its
# SQL argument names no protected path.
CONTROL_PROGRAMS = frozenset(("touch", "rm", "rmdir", "unlink", "shred",
                              "truncate", "chmod", "chown", "chgrp", "mv",
                              "mkdir", "tee", "cp", "ln", "install", "rsync",
                              "dd", "sed", "perl", "sqlite3"))
CONTROL_COPIERS = frozenset(("cp", "mv", "ln", "install", "rsync"))
# The programs that remove, disable or move a path. A directory that holds
# protected state, a repository's husky hooks and the open plans (evidence) are
# judged for these only: husky's own setup writes `.husky/pre-commit` with a
# redirect.
CONTROL_REMOVERS = frozenset(("rm", "rmdir", "unlink", "shred", "truncate",
                              "chmod", "chown", "chgrp", "mv"))
# Options whose value is a write target (`cp -t dir`, `curl -o file`).
_INTO = ("-t", "--target-directory")
OPTION_TARGETS = {"cp": _INTO, "mv": _INTO, "ln": _INTO, "install": _INTO,
                  "curl": ("-o", "--output", "--output-dir"),
                  "wget": ("-O", "--output-document"), "unzip": ("-d",)}
INTERPRETERS = frozenset(("python", "python3", "sh", "bash", "zsh", "dash"))
SHELL_NAMES = frozenset(("sh", "bash", "zsh", "dash", "ksh"))
# Words that open a compound command: the command after one is read as if it
# were not there (`if touch x; then`, `! rm x`, `do touch x`). `[`/`]` are not
# here: the test command is skipped in `_program`, so the command after it in
# an `if` line is read.
SHELL_KEYWORDS = frozenset(("if", "then", "elif", "else", "do", "while",
                            "until", "!", "{", "time"))
SHELL_OPS = re.compile(r"^[;&|()<>]+$")
# The cache subtrees whose rows the rules read: the cache database with its WAL
# files (the evidence ledger, the used-kind marks, the switch baselines of
# tezgah_context.disarmed, the gate mark, and the marks the status line reads
# for a drifted hook entry and a core that failed to import), the evidence
# JSONL files it imports, and the files the other stores it imports once
# (tezgah_store.CACHE_LEGACY) had, until that import reads them.
CONTROL_CACHE = ("evidence", "tezgah.db", "tezgah.db-wal", "tezgah.db-shm", "sessions",
                 "switches", "gate-inactive", "harness-drift", "import-crash",
                 "workspace-index.json")
# Top-level keys tezgah writes into Claude's settings (bin/tezgah-setup
# wire_claude_statusline, wire_claude_attribution), and the one that turns every
# hook off at once; any other key or entry is tezgah's only when it names tezgah.
CLAUDE_OWNED = ("statusLine", "attribution", "disableAllHooks")
PATCH_DELETE = re.compile(r"(?m)^\*\*\* Delete File: (\S.*?)\s*$")


def _real(path, cwd):
    """`path` as an absolute path: `~`, `$HOME` and the XDG variables expanded
    the way the shell would, relative to `cwd`, its directory resolved and its
    last component kept. A hook file the installer symlinked into a host's
    config is still that host's file, and the checkout it points at is not."""
    path = os.path.expandvars(os.path.expanduser(str(path)))
    parent, name = os.path.split(os.path.normpath(os.path.join(cwd or os.sep, path)))
    return os.path.join(os.path.realpath(parent), name)


def _full(path, cwd):
    """`path` with every link resolved, the last component's too: a write
    through a link lands on what it points at."""
    path = os.path.expandvars(os.path.expanduser(str(path)))
    return os.path.realpath(os.path.join(cwd or os.sep, path))


def _under(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _install_trees(cwd):
    """The trees tezgah's hooks run from: the install prefix, the Claude plugin
    copies (`_registration`), and the tree this module was loaded from - unless
    the session works inside that tree, which is then a checkout of tezgah
    being developed, not an install."""
    prefix = os.environ.get("TEZGAH_PREFIX") or os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"), "tezgah")
    trees = [os.path.realpath(prefix)]
    plugin = os.path.realpath(PLUGIN_ROOT)
    if not _under(os.path.realpath(cwd), plugin):
        trees.append(plugin)
    return trees


def _tops(cwd):
    """The checkouts the session works in: the nearest `.git`-holding ancestor
    of `cwd`, and the main checkout when that is a linked worktree (its hooks
    live there). A clone elsewhere is not one of them."""
    out, here = [], os.path.realpath(cwd or os.sep)
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            out.append(here)
            break
        if os.path.dirname(here) == here:
            break
        here = os.path.dirname(here)
    main = linked_main(cwd) if cwd else None
    return out + ([os.path.realpath(main)] if main else [])


def _held(origin):
    """The protected paths a remove or move of a directory holding one takes
    with it: tezgah's configuration, the switches that exist, the cache state,
    the install trees, and the session checkout's git hooks and open plans. A
    single plan under the open plans is evidence (OPEN_PLAN); the directory
    and its ancestors take every plan at once and stay refused."""
    out = [os.path.realpath(CONFIG_DIR)]
    out += [p for d in OFF_DIRS for p in (os.path.join(os.path.realpath(d), n)
                                          for n in SWITCHES) if os.path.exists(p)]
    out += [os.path.join(c, d) for c in {os.path.realpath(CACHE),
                                        os.path.realpath(fallback_cache())}
            for d in CONTROL_CACHE]
    out += _install_trees(origin)
    for top in _tops(origin):
        out += [os.path.join(top, ".git", "hooks"),
                os.path.join(top, ".tezgah", "plans", "open")]
    return out


def _registration(real):
    """'shared' for a file tezgah writes entries into beside the user's,
    'owned' for a hook file that is wholly tezgah's, else None. A Claude
    `settings*.json` counts in the user's own `~/.claude` or in a project under
    a root, not in a fixture under /tmp or another temp HOME."""
    claude = HOST_DIRS["claude"]
    name = os.path.basename(real)
    shared = (os.path.join(HOST_DIRS["codex"], "hooks.json"),
              os.path.join(HOST_DIRS["codex"], "config.toml"),
              os.path.join(HOST_DIRS["cursor"], "hooks.json"),
              os.path.join(claude, "plugins", "installed_plugins.json"),
              os.path.join(claude, "plugins", "known_marketplaces.json"))
    if (name in ("settings.json", "settings.local.json")
            and ".claude" in real.split(os.sep)
            and (os.path.dirname(real) == os.path.realpath(claude)
                 or root_for(real))) \
            or real in {_real(p, None) for p in shared}:
        return "shared"
    owned = [os.path.join(HOST_DIRS["opencode"], d, "tezgah.js")
             for d in ("plugins", "plugin")]
    owned.append(os.path.join(HOST_DIRS["omp"], "agent", "hooks", "pre",
                              "tezgah-hook.ts"))
    cache = os.path.realpath(os.path.join(claude, "plugins", "cache"))
    if real in {_real(p, None) for p in owned} or (
            _under(real, cache) and "tezgah" in real[len(cache):].lower()):
        return "owned"
    return None


def _target_label(real, remove, origin):
    """`control_target` for one spelling of the path."""
    name, parent = os.path.basename(real), os.path.dirname(real)
    if name in SWITCHES and parent in {os.path.realpath(d) for d in OFF_DIRS}:
        return "a kill switch (`%s`)" % name
    if _under(real, os.path.realpath(CONFIG_DIR)):
        return "tezgah's own configuration"
    for cache in {os.path.realpath(CACHE), os.path.realpath(fallback_cache())}:
        if any(_under(real, os.path.join(cache, d)) for d in CONTROL_CACHE):
            return "tezgah's evidence ledger or session state"
    if name in REPO_MARKS and root_for(parent):
        return "a repository opt-out mark (`%s`)" % name
    kind = _registration(real)
    if kind == "shared":
        return real
    # an install tree's own `.tezgah/` is the private workspace of a checkout
    # used as the install, not code the hooks run
    if kind or any(_under(real, tree) and not _under(real, os.path.join(tree, ".tezgah"))
                   for tree in _install_trees(origin)):
        return "tezgah's hook wiring"
    if not name.endswith(".sample") and any(
            _under(real, os.path.join(top, ".git", "hooks")) for top in _tops(origin)):
        return "the repository's git hooks"
    if remove and ".husky" in real.split(os.sep):
        return "the repository's git hooks"
    opened = "%s.tezgah%splans%sopen%s" % ((os.sep,) * 4)
    if remove and opened in real + os.sep:
        # strictly under it is one named plan; the directory itself, or a glob
        # or brace that names its entries (`open/*`, `open/{a,b}`), is all
        rest = real.split(opened, 1)[1] if opened in real else ""
        plan = rest.split(os.sep, 1)[0]
        return OPEN_PLAN if plan and not GLOB_CHARS.search(plan) else HELD
    return None


def control_target(path, cwd, remove=False, origin=None):
    """What `path` is in tezgah's control plane, or None.

    `remove` is a delete, chmod or move: a directory that holds protected state
    (`_held`), a repository's husky hooks and the open plans are protected only
    from those. `origin` is the session's own directory (the checkout whose git
    hooks count), `cwd` the one a `cd` in the line moved to. The path is judged
    as spelled and with every link resolved. A shared registration file comes
    back as its own real path, for the caller to judge by key: an edit of a key
    that is not tezgah's is the user's business. An evidence label
    (CONTROL_EVIDENCE) comes back only when no spelling refuses."""
    origin = origin or cwd
    real = _real(path, cwd)
    noted = None
    for spelling in dict.fromkeys((real, _full(path, cwd))):
        label = _target_label(spelling, remove, origin)
        if _refusing(label):
            return label
        noted = noted or label
    # a delete through a link (`rm -rf link/`) takes what it points at: judge
    # the resolved target too
    if remove and any(_under(held, spelling) for held in _held(origin)
                      for spelling in (real, _full(path, cwd))):
        return HELD
    return noted


def _names_tezgah(value):
    return "tezgah" in json.dumps(value, sort_keys=True).lower()


def _project(node):
    """`node` with every list cut to its items that name tezgah: a matcher group
    that holds tezgah's hook and the user's keeps the group's own fields and
    tezgah's entry, so the user's entry beside it is theirs to edit."""
    if isinstance(node, dict):
        return {k: _project(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_project(v) for v in node if _names_tezgah(v)]
    return node


def _owned(node, path=()):
    """The tezgah-owned entries of a parsed JSON document, position-free: the
    CLAUDE_OWNED top-level keys, any key naming tezgah, and each list item that
    names tezgah, projected (`_project`)."""
    def dump(value):
        return json.dumps(value, sort_keys=True)
    if isinstance(node, dict):
        out = []
        for key, value in node.items():
            if (not path and key in CLAUDE_OWNED) or "tezgah" in key.lower():
                out.append((path + (key,), dump(value)))
            else:
                out += _owned(value, path + (key,))
        return out
    if isinstance(node, list):
        return [(path, dump(_project(v))) for v in node if _names_tezgah(v)]
    return [(path, dump(node))] if "tezgah" in dump(node).lower() else []


def _toml_owned(text):
    """The lines of a Codex config.toml that arm hooks: every `[hooks...]`
    section (the trust entries live under `[hooks.state]`), the `codex_hooks`
    feature and any line naming tezgah. ponytail: which trust entry is
    tezgah's is a hash codex computes, so all of them count."""
    out, keep = [], False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            keep = stripped.lstrip("[").startswith("hooks")
        if keep or "tezgah" in line.lower() or re.match(r"\s*codex_hooks\s*=", line):
            out.append(stripped)
    return sorted(out)


def _parsed(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _after_text(inp, current):
    """The file's text once this write tool call lands, or None for a shape
    this does not model (a patch): the caller then treats it as a change."""
    for key in ("content", "file_text", "contents", "text"):
        if isinstance(inp.get(key), str):
            return inp[key]
    edits = inp.get("edits") if isinstance(inp.get("edits"), list) else [inp]
    text = current
    for edit in edits:
        if not isinstance(edit, dict):
            return None
        old = next((edit[k] for k in ("old_string", "oldString", "old_str")
                    if isinstance(edit.get(k), str)), None)
        new = next((edit[k] for k in ("new_string", "newString", "new_str")
                    if isinstance(edit.get(k), str)), None)
        if old is None or new is None:
            return None
        text = text.replace(old, new, -1 if edit.get("replace_all") else 1)
    return text


def _shared_change(real, inp):
    """True when this write changes a tezgah-owned entry of a shared file."""
    try:
        with open(real, encoding="utf-8") as fh:
            current = fh.read()
    except OSError:
        current = ""
    after = _after_text(inp, current)
    if after is None:
        return True
    if real.endswith(".toml"):
        return _toml_owned(current) != _toml_owned(after)
    return sorted(_owned(_parsed(current))) != sorted(_owned(_parsed(after)))


def _shell_label(label):
    """A label for the deny text; a shared file is named with why a shell write
    to it is refused whole."""
    if not os.path.isabs(label):
        return label
    return ("%s, which holds tezgah's hook wiring. A shell write is not read "
            "key by key, so it is refused whole; an edit that leaves tezgah's "
            "entries as they are is not" % label)


def _unquote(word):
    try:
        return "".join(shlex.split(word))
    except ValueError:
        return word.strip("'\"")


# An escaped `"`, `'` or `\` outside single quotes, as one private-use character
# each while shlex reads the line: shlex's non-posix mode knows no escape, so
# `"a \"b\" c"` ended its word at the `\"`.
_ESCAPES = {'\\"': "\ue000", "\\'": "\ue001", "\\\\": "\ue002"}
_UNESCAPE = str.maketrans({v: k for k, v in _ESCAPES.items()})


def _hide_escapes(line):
    out, quote, i = [], None, 0
    while i < len(line):
        pair = line[i:i + 2]
        if quote != "'" and pair in _ESCAPES:
            out.append(_ESCAPES[pair])
            i += 2
            continue
        if quote and line[i] == quote:
            quote = None
        elif not quote and line[i] in "'\"":
            quote = line[i]
        out.append(line[i])
        i += 1
    return "".join(out)


def _blank_script_heredocs(text):
    """`text` with the body of each heredoc fed to a non-shell interpreter
    (`python3 - <<PY`) blanked even when its tag is unquoted, length and
    newlines kept: that body is the interpreter's script, data to this rule
    (SECURITY.md's interpreter residual). Only when bash would expand nothing
    in it - no `$` and no backtick in the body - and nothing on the operator's
    line before it opens a context (`HEREDOC_RISK`) or follows it on its line
    (`PLAIN_TAIL`, and no quote there); a body handed to a shell stays
    commands. The consumer is the last simple command before the operator,
    read by a plain split, so a quote or a backslash before the operator on
    its line, or a continued line above it, keeps the body visible: `bash -s
    \\| python3 <<EOF` and `bash -s "x | python3 " <<EOF` hand it to bash. Its
    word must be the bare interpreter name - no path, no env assignment - and
    nothing earlier in the call may define a function or alias of that name
    (`python3(){ bash; }`, `alias python3=bash`)."""
    out = list(text)
    for start, stop, _tag, _quoted, body, term, safe in _heredocs(text):
        line = text.rfind("\n", 0, start) + 1
        head = re.split(r"[;&|(]", text[line:start])[-1].split()
        name = re.escape(head[0]) if head else ""
        tail = PLAIN_TAIL.match(text, stop).end()
        end = text.find("\n", stop)
        if (safe or not term or not head
                or head[0] not in INTERPRETERS - SHELL_NAMES
                or re.search(r"[$`]", text[body:term[0]])
                or re.search(r"[\\'\"]", text[line:start])
                or re.search(r"['\"]", text[stop:end if end >= 0 else len(text)])
                or re.search(r"\balias\b|\bfunction\s+%s\b|\b%s\s*\(\s*\)"
                             % (name, name), text[:start])
                or text[max(0, line - 2):line] == "\\\n"
                or HEREDOC_RISK.search(text, line, start)
                or tail < len(text) and text[tail] != "\n"):
            continue
        for k in range(body, term[0]):
            if out[k] != "\n":
                out[k] = " "
    return "".join(out)


def _shell_words(command):
    """The line as (word, operator?) pairs with quotes kept on each word, so a
    quoted `>` stays data: shlex in non-posix mode, heredoc bodies blanked, an
    unquoted backtick read as `;`, a continued line joined and every command
    line ended by `;` - the way `_shell_segments` reads a line, minus dropping
    redirects. A newline inside quotes does not end a line (`_shell_lines`), so
    a multi-line `python3 -c '...'` is one word, not lines of commands. A line
    shlex cannot read is read roughly rather than dropped."""
    text = _unquoted_backticks(_blank_heredocs(_blank_script_heredocs(
        str(command or ""))).replace("\\\n", " "))
    out = []
    for line in map(_hide_escapes, _shell_lines(text)):
        try:
            lex = shlex.shlex(line, posix=False, punctuation_chars=";&|()<>")
            lex.whitespace_split = True
            lex.commenters = ""
            words = list(lex)
        except ValueError:
            words = re.findall(r"[;&|()<>]+|[^\s;&|()<>]+", line)
        for word in words:
            if word.startswith("#"):
                break  # bash: a comment starts a word
            out.append((word.translate(_UNESCAPE), bool(SHELL_OPS.match(word))))
        out.append((";", True))
    return out


# The wrappers `_program` reads past, by basename, with the options that take
# the next word as their value; `timeout` also takes its duration.
WRAPPER_VALUE_OPTS = {"sudo": ("-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U"),
                      "env": ("-u", "--unset", "-C", "--chdir"),
                      "nice": ("-n", "--adjustment"), "nohup": (), "exec": ("-a",),
                      "time": ("-f", "-o"), "command": (),
                      "timeout": ("-s", "--signal", "-k", "--kill-after"),
                      "stdbuf": ("-i", "-o", "-e")}
# An interpreter's options that take the next word as their value, and the ones
# that make the program its own text rather than a script (`python3 -c`, `-m`).
INTERPRETER_VALUE_OPTS = ("-X", "-W", "-o", "+o", "-O")


def _past_wrappers(words):
    """`words` past compound keywords, env assignments and the wrappers
    (WRAPPER_VALUE_OPTS, by basename, with their options)."""
    i = 0
    while i < len(words):
        word = words[i]
        wrapper = os.path.basename(word)
        if ENV_WORD.match(word) or word in SHELL_KEYWORDS:
            i += 1
            continue
        if wrapper not in WRAPPER_VALUE_OPTS:
            break
        i += 1
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in WRAPPER_VALUE_OPTS[wrapper] else 1
        if wrapper == "timeout" and i < len(words):
            i += 1  # the duration
    return words[i:]


def _program(words):
    """(program basename without `.py`, its arguments) for one simple command,
    past compound keywords, env assignments, the wrappers (`_past_wrappers`)
    and an interpreter's options before the script it runs."""
    words = _past_wrappers(words)
    if words and words[0] == "[":
        # the test command: its operands are not a program, and the command
        # after the `]` is (`if [ -d x ]; then touch y; fi`)
        close = words.index("]") if "]" in words else len(words)
        words = words[close + 1:]
    if not words:
        return "", []
    name = os.path.basename(words[0])
    if name in INTERPRETERS or re.fullmatch(r"python[\d.]+", name):
        j = 1
        while j < len(words) and words[j].startswith(("-", "+")) and words[j] != "-":
            flag = words[j]
            if re.fullmatch(r"-[A-Za-z]*[cm]" if name.startswith("python")
                            else r"-[A-Za-z]*c[A-Za-z]*", flag):
                j = len(words) + 1  # the program is its own text: no script word
                break
            j += 2 if flag in INTERPRETER_VALUE_OPTS else 1
        if j < len(words):
            words = words[j:]
    if not words:
        return "", []
    name = os.path.basename(words[0])
    return (name[:-3] if name.endswith(".py") else name), words[1:]


def _option_values(args, opts):
    """The values `args` gives the options in `opts`: `-o v`, `--output=v`, a
    short option closing a cluster (`-xzf v`) and one with its value attached
    (`-ov`)."""
    out = []
    for i, arg in enumerate(args):
        for opt in opts:
            if opt.startswith("--") and arg.startswith(opt + "="):
                out.append(arg[len(opt) + 1:])
            elif (arg == opt or not opt.startswith("--") and re.fullmatch(
                    r"-[A-Za-z]*" + re.escape(opt[1:]), arg)) and i + 1 < len(args):
                out.append(args[i + 1])
            elif not opt.startswith("--") and arg.startswith(opt) and len(arg) > 2:
                out.append(arg[2:])
    return out


def _chmod_removes(args):
    """True when a chmod mode can take a permission away (`-x`, `a=r`, `644`)."""
    mode = next((a for a in args if not a.startswith("-") or re.fullmatch(
        r"-[rwxXst]+", a)), "")
    if re.fullmatch(r"[0-7]{3,4}", mode):
        return not int(mode[-3]) & 1
    return "-" in mode or "=" in mode and "x" not in mode.split("=", 1)[1]


def _git_change(args, cwd, origin):
    """The control-plane label for a `git` command's own change, or None: a
    forced add of a `.tezgah/` path, an `rm`/`mv` of protected state that is not
    `--cached` (plan-sync records a move with `git -C .tezgah rm -q --cached`),
    or a `core.hooksPath` that is set or unset rather than read."""
    i, where = 0, cwd
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            where = _real(args[i + 1], where)
        i += 2 if args[i] in GIT_VALUE_OPTS else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    paths = [a for a in rest if not a.startswith("-")]
    if sub == "add" and any(a == "--force" or re.match(r"-[A-Za-z]*f", a)
                            for a in rest):
        if any(".tezgah" in a.replace("\\", "/").split("/") for a in paths):
            return FORCED_ADD
    if sub in ("rm", "mv") and "--cached" not in rest:
        noted = None
        for path in paths:
            label = control_target(path, where, remove=True, origin=origin)
            if _refusing(label):
                return _shell_label(label)
            noted = noted or label
        return noted
    if sub == "config" and HOOKS_KEY in (a.lower() for a in rest):
        head = rest[:rest.index("--")] if "--" in rest else rest
        positional = [a for a in head if not a.startswith("-")]
        if any(a.startswith(("--get", "--list")) or a == "-l" for a in head) \
                or positional[:1] in (["get"], ["list"]):
            return None
        # the session's own checkout, or every repository at once
        mine = any(a in ("--global", "--system") for a in head) or any(
            _under(os.path.realpath(where), top) for top in _tops(origin))
        if mine and (len(positional) > 1 or any(a.startswith("--unset") for a in head)):
            return "the repository's git hooks"
    return None


def _host_hook(words, cwd):
    """True when the `hook.py` this command runs sits under `hosts/<host>/`
    (HOOK_HOSTS), as written or with its links resolved."""
    word = next((w for w in words if os.path.basename(w) == "hook.py"), "")
    written = os.path.join(cwd or os.sep, os.path.expanduser(word))
    return any(os.path.basename(os.path.dirname(p)) in HOOK_HOSTS
               and os.path.basename(os.path.dirname(os.path.dirname(p))) == "hosts"
               for p in (os.path.normpath(written), _full(word, cwd)))


def _command_change(words, cwd, depth, origin):
    """The control-plane label one simple command changes, or None."""
    program, args = _program(words)
    if program == "eval" and depth < 3:
        return shell_control(" ".join(args), cwd, depth + 1, origin)
    if program in SHELL_NAMES and depth < 3:
        # `-c`, or any flag cluster holding it (`-lc`, `-ec`); a `--` after it
        # ends the options and the script is the word after that
        at = next((k for k, a in enumerate(args)
                   if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a)), None)
        script = args[at + 1:] if at is not None else []
        script = script[1:] if script[:1] == ["--"] else script
        if script:
            return shell_control(script[0], cwd, depth + 1, origin)
    if program in HOOK_ENTRIES or (program == "hook" and _host_hook(words, cwd)):
        return "tezgah's hook state through one of its hook entries"
    if program in CONTROL_CLIS:
        verbs = CONTROL_CLIS[program]
        positional = [a for a in args if not a.startswith("-")]
        if verbs is None or (positional and (verbs == "" or
                                             positional[0].lower() in verbs)):
            return "tezgah's control state through one of its own CLIs"
        return None
    if program == "git":
        return _git_change(args, cwd, origin)
    checks = [(v, False) for v in _option_values(args, OPTION_TARGETS.get(program, ()))]
    if program == "tar":
        if any(a in ("--extract", "--get") or re.fullmatch(r"-?[A-Za-z]*x[A-Za-z]*", a)
               for a in args[:1] + [a for a in args if a.startswith("-")]):
            checks += [(v, False) for v in _option_values(args, ("-C", "--directory"))]
        checks += [(v, False) for v in _option_values(args, ("-f", "--file"))]
    if program in CONTROL_PROGRAMS and not (program in ("sed", "perl") and not any(
            re.match(r"-[A-Za-z]*i", a) for a in args)):
        remove = program in CONTROL_REMOVERS and (
            program != "chmod" or _chmod_removes(args))
        if program == "dd":
            checks += [(a[3:], False) for a in args if a.startswith("of=")]
        else:
            targets = [a for a in args if not a.startswith("-")]
            if program in CONTROL_COPIERS and targets:
                checks += [(t, remove) for t in targets[:-1]] if program == "mv" else []
                # `rsync --delete` empties the destination of what the source lacks
                targets, remove = targets[-1:], program == "rsync" and any(
                    a.startswith("--delete") for a in args)
            checks += [(t, remove) for t in targets]
    noted = None
    for target, remove in checks:
        label = control_target(target, cwd, remove=remove, origin=origin)
        if _refusing(label):
            return _shell_label(label)
        noted = noted or label
    return noted


def shell_control(command, cwd, depth=0, origin=None):
    """The control-plane label a shell command changes, or None.

    CONTROL_WRITE in the plan's words, read rather than matched, one simple
    command at a time and in order: a `cd` (or `pushd`) moves the directory the
    words after it resolve against; a redirect's target, the arguments of a
    program that changes a path (CONTROL_PROGRAMS, OPTION_TARGETS, `tar`) and a
    CLI that changes tezgah's state (CONTROL_CLIS) are judged, each expanded the
    way the shell would (`~`, `$HOME`, the XDG variables). Compound keywords
    (`if`, `do`, `!`) are read past, and `eval` and `bash -c` (any flag cluster
    holding `c`) are opened. A quoted word is a word and not a command, so a
    grep or a commit message that names a switch is not one. SHELL_WRITE is not
    widened for this: it feeds the task phase rule and the JS mirror.
    ponytail: an interpreter (`python3 -c "open(...)"`), `find -delete`,
    `xargs`, a glob or brace in a directory, a link made earlier in the same
    line and a path assembled at run time are not read; SECURITY.md names them
    as the residual routes."""
    origin = origin or cwd
    where, words, pending, noted = cwd, [], None, None
    for word, is_op in _shell_words(command):
        if pending:
            judged, pending = pending, None
            if not is_op:
                target = _unquote(word)
                if judged == ">" and not (target.isdigit() or target == "-"):
                    label = control_target(target, where, origin=origin)
                    if _refusing(label):
                        return _shell_label(label)
                    noted = noted or label
                continue
        if is_op and ("<" in word or ">" in word):
            if words and words[-1].isdigit():
                words.pop()  # the descriptor before `2>`
            pending = ">" if ">" in word else "<"
            continue
        if not is_op:
            words.append(word)
            continue
        plain = [_unquote(w) for w in words]
        words = []
        # `[`/`]` are left to `_program: the test command is skipped there, so
        # the command after it in an `if` line is read
        while plain and plain[0] in SHELL_KEYWORDS:
            plain = plain[1:]
        if plain and plain[0] in ("cd", "pushd"):
            dest = [a for a in plain[1:] if not a.startswith("-") or a == "-"]
            if not dest or dest[0] != "-":
                where = _full(dest[0] if dest else "~", where)
            continue
        label = plain and _command_change(plain, where, depth, origin)
        if _refusing(label):
            return label
        noted = noted or label or None
    # bash runs the `$( )` and backtick substitutions of an unquoted-tag
    # heredoc body, whatever the consumer and whatever quotes the body holds,
    # and the line reader above sees them as data (blanked or quoted)
    text = str(command or "")
    if "<<" in text and depth < 3:
        from tezgah_context import _substitutions
        for h in _heredocs(text):
            if h[3]:
                continue
            for a, b in _substitutions(text, h[4], h[5][0] if h[5] else len(text)):
                inner = text[a + (2 if text[a] == "$" else 1):b - 1]
                for base in dict.fromkeys((cwd, where)):
                    label = shell_control(inner, base, depth + 1, origin)
                    if _refusing(label):
                        return label
                    noted = noted or label
    return noted


def control_reason(t, inp, cwd):
    """The control-plane label this call changes, or None (see CONTROL_DENY).
    A CONTROL_EVIDENCE label comes back only when nothing in the call refuses."""
    if t in BASH_TOOLS:
        return shell_control(inp.get("command") or inp.get("cmd"), cwd)
    deletes = set(PATCH_DELETE.findall(str(inp.get("patch") or "")))
    noted = None
    for path in write_paths(inp):
        label = control_target(path, cwd, remove=path in deletes)
        if label and not os.path.isabs(label):
            if _refusing(label):
                return label
            noted = noted or label
        elif label and _shared_change(label, inp):
            return "tezgah's hook wiring"
    return noted


def _deny(session_id, rule, reason, tool=None, inp=None, workspace=None,
          extra=None):
    """Record a refusal before returning it: a deny nobody counts is a rule
    whose effect can never be argued about (hooks/tezgah_integrity.counters).

    The row carries the refused call's id and workspace, so the ledger says
    which action was stopped and where - the same two facts a PostToolUse row
    carries. `extra` appends a fact the row must keep beyond the 80 characters
    of the reason it truncates."""
    detail = "%s: %s" % (rule, cut(reason, 80))
    if extra:
        detail = "%s; %s" % (detail, extra)
    note(session_id, "deny", detail, id=call_id(tool, inp), workspace=workspace)
    return reason


def decision(tool, inp, cwd, session_id=None, record=True, agent=None):
    """A deny reason for this call, or None to let it pass.

    `record=False` is the dry run `tezgah-gate check` and the MCP
    `tezgah_gate_check` promise ("without running it"): the same answer, with
    no deny/drift/nudge row, no nudge mark and no snapshot. A dry run against a
    live session id wrote refusal rows into that session's counters (audit
    CHAT-07 / L-14b).

    `agent` is the host's subagent id when the call came from one (Claude's
    `agent_id`): the repeat ceilings count that agent's own attempts, so one
    sibling's failures are not spent as another's."""
    bind_session(session_id)  # the switch latch: off() below answers for this session
    if not record:
        return _dry_decision(tool, inp, cwd, session_id, agent)
    if off("pretooluse-off"):
        return None
    base = root_for(cwd)
    if not base:
        return None
    t = str(tool or "").lower()
    # A write or shell call's first row (tezgah_integrity.BEGAN_KIND), written
    # before any rule runs: a host that kills a slow gate still runs the call,
    # and a pass with no `began` reads as an orphan (`_pair`). The PostToolUse
    # hook writes the second row; a refusal below answers it with its `deny`.
    # Through `note`, so the dry run writes none. `check` is decided here, from
    # the whole command: the stored detail is cut at DETAIL_MAX.
    if t in WRITE_TOOLS or t in BASH_TOOLS:
        digest = call_id(tool, inp)
        if digest:
            command = str(inp.get("command") or inp.get("cmd") or "")
            note(session_id, BEGAN_KIND, command or (write_paths(inp) or [""])[0],
                 id=digest, tool=str(tool or "").strip() or None, workspace=base,
                 check=1 if t in BASH_TOOLS and verify_command(command) else None)
    # Claude's Task names the agent `subagent_type`; omp's task names it `agent`,
    # on the call (flat shape) or on each `tasks[]` item (batch shape).
    subs = [inp.get("subagent_type"),
            (inp.get("args") or {}).get("subagent_type"), inp.get("agent")]
    subs += [item.get("agent") for item in inp.get("tasks") or ()
             if isinstance(item, dict)]
    # The body a shell call writes, read once: the three write-tool-only rules
    # below reach it through the shell (see the section above). None for every
    # tool that is not a shell, and for a shell line that writes no body.
    shell_body = (shell_write_body(inp.get("command"), cwd)
                  if t in BASH_TOOLS else None)
    # Control plane, first after the root check: every rule below is held by a
    # file this one protects (control_reason). No switch but `pretooluse-off`
    # removes it, and that one is among the files. A CONTROL_EVIDENCE target is
    # not refused: the call goes on to the rules below, and a call they let
    # through leaves a `disarm` row beside its `began` row.
    evidence = None
    if t in WRITE_TOOLS + BASH_TOOLS:
        what = control_reason(t, inp, cwd)
        if _refusing(what):
            return _deny(session_id, "control", CONTROL_DENY % what, tool, inp,
                         base)
        evidence = what
    if t in ("agent", "task", "subagent") and any(explored(s) for s in subs):
        return _deny(session_id, "explorer", EXPLORE_DENY, tool, inp, base)
    # anti-shortcut: a check neutered so it cannot fail, or a test disabled so a
    # failure disappears. This is the mechanical half of the integrity rule; the
    # reply-level half is the Stop hook in hooks/projects-stop.py (Claude),
    # hosts/codex/hook.py, hosts/cursor/hook.py and hosts/omp/hook.py. `verify-off`
    # removes that rule, so it drops this half too; `pretooluse-off` above still
    # drops the whole gate, and attribution/explore are other rules and stay
    # armed. The shell half of the write rule reads the body a heredoc writes,
    # which is the route E7c measured once the write tools were refused.
    if not off("verify-off"):
        if t in BASH_TOOLS:
            reason = shortcut_command(inp.get("command"))
            if reason:
                return _deny(session_id, "shortcut", reason, tool, inp, base)
            reason = piped_check and piped_check(inp.get("command"))
            if reason:
                return _deny(session_id, "piped", reason, tool, inp, base)
            if shell_body:
                reason = shortcut_edit(shell_body)
                if reason:
                    return _deny(session_id, "shortcut", reason, tool, inp, base)
        if t in WRITE_TOOLS:
            reason = shortcut_edit(inp)
            if reason:
                return _deny(session_id, "shortcut", reason, tool, inp, base)
    if t in BASH_TOOLS and attribution(inp.get("command")):
        return _deny(session_id, "attribution", ATTRIB_DENY, tool, inp, base)
    if shell_body and attribution_edit(shell_body):
        return _deny(session_id, "attribution", ATTRIB_DENY, tool, inp, base)
    if t in WRITE_TOOLS and attribution_edit(inp):
        return _deny(session_id, "attribution", ATTRIB_DENY, tool, inp, base)
    # Language: the identifiers this command would create. Beside the
    # attribution rule because both read the command's own text for a form it
    # carries, and both are about what the artifact will say for good. The rule
    # has its own switch, and the whole-gate one above drops it with everything
    # else: a heuristic that refuses a word the user chose has to be one the
    # user can take off (see tezgah_lang's docstring for what it cannot decide).
    if not off("lang-off") and t in BASH_TOOLS:
        reason = lang_reason(inp.get("command"), cwd)
        if reason:
            return _deny(session_id, "lang", reason, tool, inp, base)
    # Concurrent write: another session wrote one of this call's files inside
    # RACE_WINDOW_MIN (the constant carries why it refuses). Ahead of the repeat
    # guards, so a colliding write is counted as this rule and not as a repeat of
    # one. A shell command that writes a file through a redirect or `tee` is a
    # write here too: the rules below read its target from `write_paths`, the
    # reader `capture` and the PostToolUse row already share - unless all it
    # writes is its own scratch (`scratch_target`), such as a `> /tmp/check.log`.
    writes = t in WRITE_TOOLS or (t in BASH_TOOLS and any(
        not scratch_target(p, cwd) for p in write_paths(inp)))
    if writes and RACE_REFUSE:
        reason = race_reason(inp, session_id, cwd)
        if reason:
            return _deny(session_id, "race", reason, tool, inp, base)
    # Lease: a write into a file an open sibling slice owns, or into the main
    # checkout by a slice whose record names a worktree (see LEASE_DENY). After
    # the race rule, which names a write already lost; before the task scope,
    # since the allowlist is the plan's and the lease is one slice's share of it.
    # It backs the fan-out rule's text, so its switch is that rule's; with the
    # journal off there is no record to read.
    if writes and not off("orchestrate-off") and not off("slices-off"):
        reason = lease_reason(inp, session_id, cwd, agent)
        if reason:
            return _deny(session_id, "lease", reason, tool, inp, base)
    # Task scope: the active plan's phase and the files its allowlist names (see
    # task_reason). The record itself is refused first of all: only
    # bin/tezgah-task writes it, through the checks it makes on the way.
    if not off("task-off"):
        # The record is read once and handed to every rule below: each read lists
        # `.tezgah/plans/open/` and parses a plan, and this path is every write of
        # every session. Reads and non-write tools pay nothing.
        task = _UNRESOLVED
        _WORKTREE_TASKS.clear()
        if tezgah_task is not None and t in WRITE_TOOLS + BASH_TOOLS:
            # held: with every phased plan held by its worktree the record rule
            # still refuses a direct write to it, and the scope rules hold a
            # target outside the plan worktrees to none (`_owners`)
            task = tezgah_task.active(cwd, base, held=True)
        if writes:
            reason = task_record_reason(inp, cwd, base, task)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
        if t in BASH_TOOLS:
            reason = task_shell_reason(inp, cwd, base, task)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
        if writes:
            reason = task_reason(inp, cwd, base, task)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
        # The checkpoint: the same phase, the state it starts from. After the
        # scope rule, because a path outside the allowlist is the more specific
        # fault in the same call (see checkpoint_reason for why the rule is here
        # at all and not only at the phase move).
        if t in WRITE_TOOLS + BASH_TOOLS:
            reason = checkpoint_reason(inp, cwd, base, task)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
    # Workspace: tezgah state belongs under .tezgah/, never a root plans/,
    # research/ or analysis/ the project does not own (see workspace_reason).
    if not off("workspace-off") and t in WRITE_TOOLS + BASH_TOOLS:
        reason = workspace_reason(inp, cwd, base)
        if reason:
            return _deny(session_id, "workspace", reason, tool, inp, base)
    # MCP: a server's effect tool lands text the way a write tool or a `gh`
    # write does, so its payload meets the same content rules. The verb class
    # (tezgah_integrity.MCP_VERBS) only picks which rules read it - it never
    # refuses or asks by itself - and the payload is read through the bounded
    # walk (mcp_text). The credential half reads vendor token shapes only
    # (MCP_TOKEN), never the shell's name=value shape.
    verb = mcp_class(tool)
    if verb in ("write", "publish"):
        text = mcp_text(inp)
        if verb == "write" and not off("verify-off"):
            reason = shortcut_edit({"file_path": (write_paths(inp) or [""])[0],
                                    "content": text})
            if reason:
                return _deny(session_id, "shortcut", reason, tool, inp, base)
        if ATTRIB_LINE.search(text):
            return _deny(session_id, "attribution", ATTRIB_DENY, tool, inp, base)
        if MCP_TOKEN.search(text):
            return _deny(session_id, "secret", MCP_SECRET_DENY, tool, inp, base)
    # A credential on its way into a file. No escape hatch: the deny text
    # names the rephrase (a name, a length, a fingerprint), so the write can
    # be replaced rather than repeated. The shell's own text is read for the
    # name=value and bearer shapes next to a sink; the text a write lands - a
    # write tool's content, or the body a heredoc writes, which mask() blanks -
    # for the prefixed token families (see SECRET_EDIT_DENY for why the two
    # differ), so a Write and a heredoc landing the same text agree.
    if t in BASH_TOOLS:
        reason = secret_command(inp.get("command"))
        if reason:
            return _deny(session_id, "secret", reason, tool, inp, base)
    body = inp if t in WRITE_TOOLS else shell_body
    if body and secret_edit(body, cwd):
        return _deny(session_id, "secret", SECRET_EDIT_DENY, tool, inp, base)
    # Plan required: the turn's third product file while the checkout is on
    # main/master (see plan_reason). Below the task, workspace and secret rules,
    # because each names a more specific fault in the same write, and above the
    # repeat guards, because it is the call that is refused and not a repeat of
    # one. Standing: only changing the tree's state changes it.
    if t in WRITE_TOOLS + BASH_TOOLS:
        reason = plan_reason(inp, cwd, session_id)
        if reason:
            return _deny(session_id, "plan", reason, tool, inp, base)
    # Ordering: a commit asserted over a check that just failed (see
    # commit_order_reason). An argument-shaped rule, so it sits with them and
    # above the repeat guards; it rides `verify-off`, the switch that governs the
    # rest of the integrity rule, because this is that rule's claim read at the
    # one moment it lands in the repository's history.
    if not off("verify-off") and t in BASH_TOOLS:
        reason = commit_order_reason(inp.get("command"), session_id)
        if reason:
            return _deny(session_id, "order", reason, tool, inp, base)
    # Repeat guards, under the same kill switch as the other integrity denials
    # and after every argument-shaped rule: a call another rule would have
    # refused has to be counted as that rule, not as a repeat. `loop` is the
    # failure-scoped half (identical attempts that failed, per user turn), `retry`
    # the session-wide ceiling above it (every attempt of the call, whatever it
    # returned). Both read the ledger tail, which is the only file I/O this path
    # is allowed.
    if not off("verify-off") and t in BASH_TOOLS + WRITE_TOOLS:
        reason = loop_reason(tool, inp, session_id, agent)
        if reason:
            return _deny(session_id, "loop", reason, tool, inp, base)
        reason = retry_reason(tool, inp, session_id, agent)
        if reason:
            return _deny(session_id, "retry", reason, tool, inp, base)
    if symbol := searched_symbol(tool, inp):
        slug = index_slug(cwd, base)
        if slug and first_nudge(session_id):
            note(session_id, "nudge", slug, id=call_id(tool, inp),
                 workspace=base)
            return nudge_reason(symbol)
    # Constraint drift, last: a re-statement yields to every refusal above (a
    # refusal's reason is the same channel), and `verify-off` does not drop it -
    # the rules it re-states are not the verify rule. The switch that governs it
    # is the per-turn reminder's own (checked in drift_reason), because this is
    # that reminder's mid-turn half.
    reason = drift_reason(tool, inp, cwd, session_id)
    if reason:
        return _deny(session_id, "drift", reason, tool, inp, base)
    # Lesson lineage: a ledger write about to land in a turn that read untrusted
    # text leaves its rows and is let through (see lesson_taint; ADR 010). After
    # every refusal, so a refused write that will be re-issued is counted once;
    # a failure costs the rows, never the write.
    if t in WRITE_TOOLS + BASH_TOOLS:
        try:
            lesson_taint(tool, inp, cwd, session_id, agent, shell_body)
        except Exception:
            pass
    # Nothing refused this call, so a write is about to land: keep the bytes it
    # is about to change, which is what bin/tezgah-rollback restores by hand.
    # Nothing automatic undoes work here - see tezgah_snapshot's own note on why.
    # A refused write changes no file, so it is never captured, and this is the
    # only place the gate writes anything the deny path does not. capture returns
    # None rather than raising, but no host wraps decision(), so the outer try is
    # cheap insurance in the one path where a failure would block an edit.
    #
    # A shell call that writes a file is the same call for this purpose (see
    # write_paths): without the pre-state, the after-state alone cannot tell a
    # write that landed from one that was a no-op, and the freshness rule would
    # count every redirect as a change. `capture` reads a write tool's own path
    # field and takes no shell tool name, so the target goes in the shape it
    # reads - SHELL_AS_WRITE - and the row it writes carries no tool name, so
    # nothing on the ledger claims a write tool ran.
    #
    # A control-plane change the rules let through (CONTROL_EVIDENCE) leaves
    # its `disarm` row here, on the allow path. The call's `began` row is
    # written before the rules (see the top of this function).
    if evidence and (t in WRITE_TOOLS or t in BASH_TOOLS):
        note(session_id, "disarm", "control: %s" % evidence,
             id=call_id(tool, inp), workspace=base)
    if capture and t in WRITE_TOOLS:
        try:
            capture(tool, inp, cwd, session_id)
        except Exception:
            pass
    elif capture and t in BASH_TOOLS:
        try:
            for path in write_paths(inp):
                capture(SHELL_AS_WRITE, {"file_path": path}, cwd, session_id)
        except Exception:
            pass
    return None


def _dry_decision(tool, inp, cwd, session_id, agent=None):
    """`decision` with every write it makes swapped out for the call.

    The writers are module names `decision` reaches through (`note` for the
    deny, drift, nudge, lesson_tainted and lesson_changed rows, `write_taint`
    for the lesson taint index, `first_nudge` for the once-per-session mark,
    `capture` for the
    snapshot), so one swap covers every rule and a new rule
    that records through them is dry here without being told. Safe because
    the dry run is its own process (bin/tezgah-gate check): nothing else in it
    reads these names while they are swapped, and the finally puts them back.
    The nudge is still answered as the live path would answer it - spent when
    its mark exists - only the mark is not written."""
    g = globals()
    saved = {name: g[name] for name in ("note", "write_taint", "first_nudge",
                                        "capture")}

    g.update(note=lambda *a, **k: None, write_taint=lambda *a, **k: None,
             capture=None,
             first_nudge=lambda sid: not tezgah_store.marked("nudged", nudge_key(sid)))
    try:
        return decision(tool, inp, cwd, session_id, agent=agent)
    finally:
        g.update(saved)



# Every rule slug `decision` records a refusal under (`_deny`'s second argument),
# with the kill switch that disarms it beside `pretooluse-off`, which disarms
# them all; None means only that one. A lesson the ledger retires with
# `|| enforced_by: <slug>` (tezgah_lessons.lines) leaves the injected
# block only while its rule is armed, so `piped` brings its lesson back under
# `verify-off`. `tests/test_lessons.py` holds this map to the `_deny` literals.
DENY_RULES = {"control": None, "explorer": None, "shortcut": "verify-off",
              "piped": "verify-off",
              "attribution": None, "lang": "lang-off", "race": None,
              "lease": "orchestrate-off",
              "task": "task-off", "workspace": "workspace-off", "secret": None,
              "plan": None, "order": "verify-off", "loop": "verify-off",
              "retry": "verify-off", "drift": "reminder-off"}


# --- ask: an ask-tool question with no recommended option (plan 086, S3) -----
# The ask policy's structured half: omp's `ask` and Claude's AskUserQuestion
# carry their questions as data, so the check needs no word list for the
# question itself. 7 of 51 distinct `ask` questions in the owner's omp
# transcripts carried no `recommended` option (research orchestrator-flow-audit
# S3, finding 4). A warning, never a deny (the owner's 2026-09-26 decision
# removed the per-command consent gate): the line rides back with the call's
# result, as the graph line does (`graph_advice`). Every such call leaves an
# `ask` row, the counts `tezgah-gate replay` and the ledger read.
ASK_NO_DEFAULT = (
    "tezgah: %d of %d question(s) in this %s call carry no "
    "recommended option. Each question put to the user names a recommended "
    "default (omp `ask`: `recommended`; AskUserQuestion: a \"({RECOMMENDED})\" "
    "option), and the work proceeds on it unless the step waits on the user's "
    "answer by nature (a force push, a delete of what the session did not "
    "make, production, a credential, a spend over the cap). ")
ASK_GRANTED = (
    "tezgah: the user already granted %s this session; that step is taken, "
    "not asked again.")


def ask_advice(tool, inp, session_id, cwd=None):
    """The ask-policy warning for an ask-tool call, else None: a question with
    no recommended option (`tezgah_integrity.undefaulted`), or one about an
    outward step the user granted this session (`grants_in_force`). Records
    one `ask` row per call with the counts. Off under `verify-off`, whose Stop
    rule the policy's other half rides, and `pretooluse-off`."""
    from tezgah_integrity import (ASK_TOOLS, _said as said, grants_in_force,
                                  never_default, outward_classes, undefaulted)
    name = str(tool or "").lower()
    if name not in ASK_TOOLS or not session_id or not (cwd and root_for(cwd)) \
            or off("pretooluse-off") or off("verify-off"):
        return None
    asked, defaulted = undefaulted(inp)
    if not asked:
        return None
    qs = inp.get("questions") if isinstance(inp.get("questions"), list) else [inp]
    text = " ".join(str(q.get("question") or "") for q in qs if isinstance(q, dict))
    note(session_id, "ask", cut(" ".join(text.split()), 120), tool=str(tool),
         questions=asked, defaults=defaulted)
    out = ASK_NO_DEFAULT % (asked - defaulted, asked, tool) if defaulted < asked else ""
    granted = outward_classes(text) & grants_in_force(session_id)
    if granted and not never_default(text):
        out += ASK_GRANTED % ", ".join(sorted(granted))
    return said(out.strip()) if out else None
