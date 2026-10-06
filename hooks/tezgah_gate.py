#!/usr/bin/env python3
"""The tool gate, shared by every host that can block a tool call.

Rules, all only inside a tezgah root:
  1. a grep-only explorer subagent is refused, with the graph tools named as the
     replacement;
  2. the FIRST identifier-shaped search of a session (Grep tool, or grep/rg run
     through a shell) in a repo whose own codegraph index exists is nudged
     toward the graph once, then every later search passes.
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
     refused (`task`). The record is the user's own, written by bin/tezgah-task and
     never by the agent, so the refusal leans on a decision the user made rather
     than one this gate inferred: no active task means no requirement, and the
     rule invents nothing. The record also carries where the phase returns to - a
     `checkpoint:` sha, or `pending` while the tree still holds work no commit
     names - and a write in `implementation` is refused while it reads `pending`
     and the tree is dirty, so the phase's work starts from a named state rather
     than on top of uncommitted changes; the per-file snapshots are not one
     state to return to. Two further refusals close the ways a session could
     move the boundary instead of respecting it: a write whose target IS that
     record, and a shell command that would change it through the CLI. Both were
     measured open before they were closed - with the refusal naming the command
     that lifts it, an armed arm removed or disabled the gate in 25 of 25 runs
     and obeyed it in none (an internal benchmark, block E7) - and neither
     refusal names a command now. The phase covers the shell too, because the
     write tools are not the only way to change a file: with them refused, the
     armed arm wrote the target with a heredoc redirect in 3 of 25 runs, so a
     reading phase refuses a shell command that writes. A code-execution tool is
     a third route the phase does not cover: the same block measured one row in
     25 writing the target through `eval` after the write tools and the shell
     were both refused, and that one is named rather than closed. The `task-off`
     kill switch removes all four.
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
     repo's `.no-*` marks, the repository's git hooks, a forced `git add` of a
     `.tezgah/` path, a delete or move under `.tezgah/plans/open/`, and the CLIs
     that change that state (control_reason). It runs first after the root
     check, and no switch but `pretooluse-off` removes it: every other switch is
     one of the files it protects.
Adapters translate the returned reason into their own permission envelope.
"""
import hashlib
import json
import os
import re
import shlex

from tezgah_integrity import (BASH_TOOLS, BEGAN_KIND, ENV_WORD, GIT_VALUE_OPTS,
                              GIT_WRAPPER, HOOKS_KEY, PATCH_FILE,
                              SECRET_PREFIXED, STEP_KINDS, WRITE_TOOLS,
                              _blank_heredocs, _shell_segments, _turn_start,
                              _unquoted_backticks, call_id, cut, events,
                              heredoc_bodies, mask, note, prior_calls,
                              scratch_target, shortcut_command, shortcut_edit,
                              turn_rows, verify_command, write_texts)
from tezgah_paths import (CACHE, CONFIG_DIR, HOST_DIRS, OFF_DIRS, PLUGIN_ROOT,
                          REPO_MARKS, SWITCHES, cache_dir, fallback_cache,
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
    from tezgah_integrity import writers_elsewhere
except ImportError:  # pragma: no cover - only on an integrity module without it
    writers_elsewhere = None

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

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
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


def searched_identifier(tool, inp):
    """The bare identifier this call searches for, or None. Host tool names
    differ in case (Claude `Grep`/`Bash`, Codex/dsh `bash`), so match lowercased."""
    t = str(tool or "").lower()
    if t == "grep":
        pat = str(inp.get("pattern", ""))
        return pat if IDENT.match(pat) else None
    if t in ("bash", "shell"):
        for m in BASH_SEARCH.finditer(str(inp.get("command", ""))):
            tok = m.group(2).strip("'\"")
            if IDENT.match(tok):
                return tok
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
    d = os.path.realpath(cwd)
    base, rs = os.path.realpath(base), roots()
    while d.startswith(base) and (d != base or base not in rs):
        if os.path.isfile(os.path.join(d, ".codegraph", "codegraph.db")):
            return re.sub(r"[^A-Za-z0-9]+", "-", d).strip("-")
        d = os.path.dirname(d)
    return None


def first_nudge(session_id):
    """Consume the once-per-session nudge. False when already spent/unwritable.

    The mark lands in cache_dir(), so a sandboxed host (dsh) still gets the
    one-shot nudge instead of the write failing open."""
    d = os.path.join(cache_dir(), "nudged")
    mark = os.path.join(d, session_id or "nosession")
    if os.path.exists(mark):
        return False
    try:
        os.makedirs(d, exist_ok=True)
        open(mark, "w", encoding="utf-8").close()  # consume BEFORE denying: later greps pass
        return True
    except OSError:
        return False


def nudge_reason(symbol):
    return ("Code graph index is ready for this repo. Run `codegraph explore %s` (source, callers, "
            "blast radius in one call) or `codegraph callers %s` / `codegraph impact %s` from a shell; "
            "an omp subagent must use this CLI, not the MCP device, because omp's MCP device refuses "
            "concurrent writes. If you need literal text, re-run this search unchanged; it will pass - "
            "this nudge fires once per session." % (symbol, symbol, symbol))


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
    "user": "it names something only the user can fix - a credential, a "
            "login, an access grant - so stop and ask the user for it rather "
            "than change the approach",
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
    only carries the text of its own simple command. A `git add` that names a
    credential file is refused whatever its text holds (`_secret_add`)."""
    c = str(command or "")
    added = _secret_add(c)
    if added:
        return SECRET_ADD_DENY % added
    if not c or not SECRET_TOKEN.search(c):
        return None
    masked = mask(c)
    start = 0
    for end in [m.start() for m in SEGMENT.finditer(masked)] + [len(c)]:
        if (SECRET_TOKEN.search(c[start:end])
                and SECRET_SINK.search(masked[start:end])):
            return SECRET_DENY
        start = end
    return None


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
    "Concurrent write refused: session %s wrote this file within the last %d "
    "minutes, so the copy of %s in your context may already be stale. Re-read "
    "the file and re-apply your change to what is on disk now; if both sessions "
    "are editing it, say so and let one of them own the file rather than "
    "overwriting the other's work.")
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
    r"^(?:agent|xd|local|artifact|proc|skill|mcp|omp|issue|pr|history|ssh|cfg)://",
    re.I)
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
    target = shell_target(inp.get("command") or inp.get("cmd") or "")
    return [os.path.expanduser(os.path.expandvars(target))] if target else []


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
        if URI_CHANNEL.match(path) or scratch_target(path, cwd):
            continue    # a temp file or a device is no one's shared work
        others = writers_elsewhere(path, session_id, RACE_WINDOW_MIN, cwd=cwd)
        if others:
            return RACE_DENY % (", ".join(str(s) for s in others[:3]),
                                RACE_WINDOW_MIN, path)
    return None


# --- task scope: the user's own phase and path allowlist --------------------
# What this closes: a session that has been told what it is working on - the
# user activated a plan file under .tezgah/plans/open, so the work has a phase and the
# files it may touch - and then writes anyway. Two shapes cost the user real
# work: a write in `discovery`, where the whole point of the phase is to read
# before deciding, and a write outside the plan's own allowlist, which is how a
# bounded task quietly becomes an unbounded one. Both are the user's own
# decisions, which is why this rule may refuse at all: the record is written by
# bin/tezgah-task, by hand, and never by the agent - a rule the agent could
# satisfy by editing its own record would be a nudge wearing a gate's clothes.
#
# The direction is fail-open wherever the record is missing, unreadable or out
# of phase vocabulary (tezgah_task.active returns None for those), because a
# refusal has to rest on an ask the user actually made: a rule that refused
# every write until a record appeared would be the fail-closed trap the design
# report names, with the whole session as its blast radius. Nothing is named
# that the user did not name either: an empty allowlist is no scope asked for
# rather than "nothing is allowed", so the phase is the whole requirement there.
TASK_PHASE_DENY = (
    "Task gate: the active task %s is in phase `%s`, and this call writes. "
    "Writes belong to %s. The phase is the user's to move: ask them, or do the "
    "reading this phase asks for and say what the write was for.")
TASK_SCOPE_DENY = (
    "Task gate: %s is outside the paths the active task %s allows (%s). The "
    "allowlist is the user's to widen: ask them, or leave the file alone and say "
    "why it looked in scope.")
# The two refusals above deliberately name no command. They used to end with the
# one that lifts them, and the E7 block measured what that costs: with the unlock
# printed in the refusal, the armed arm removed or disabled the gate in 25 of 25
# runs and obeyed it in none (an internal benchmark, block E7). A refusal
# is a boundary or it is an instruction; it cannot be both.
TASK_RECORD_DENY = (
    "Task gate: %s is the active task's own record. The phase and the allowlist "
    "live in that file, so a session that edits it is editing the boundary it is "
    "being held to. Ask the user to change the task; the record is theirs.")
TASK_UNLOCK_DENY = (
    "Task gate: this command changes the active task's own record. The phase and "
    "the allowlist are the user's, and a session that can move them is held to "
    "nothing. Ask the user to change the task instead.")
# A shell command that changes the record. Matched on the masked text, so a
# command that merely names the CLI - a grep over the docs, a commit message -
# is not refused. The token is the CLI's own basename, with or without `.py`
# and run through any interpreter, so any path to it counts.
TASK_CHANGE = re.compile(
    r"(?:^|[|;&(]\s*|\s)(?:python3?\s+)?\S*tezgah-task(?:\.py)?\s+"
    r"(?:start|phase|allow|stop)\b")
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
    "The phase is the user's to move: ask them, or do the reading this phase "
    "asks for and say what the write was for.")


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
    return tezgah_task.active(cwd, base)


def task_shell_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when the active task's phase only reads and this shell
    command writes a file, else None.

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
    if not task or task["phase"] in tezgah_task.WRITE_PHASES:
        return None
    if not SHELL_WRITE.search(mask(str(inp.get("command") or ""))):
        return None
    return TASK_SHELL_DENY % (task["id"], task["phase"])


def task_record_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when this write's target IS the active task's record.

    The other route to the same hole as TASK_UNLOCK_DENY, and the one a write
    tool takes: the record is a file in the repo, so an agent that may write
    files can retype the phase instead of running the CLI. Refused whatever the
    phase and whatever the allowlist says - the record is not inside its own
    scope, because a scope that can widen itself is not one."""
    task = _task(cwd, base, task)
    if not task:
        return None
    record = os.path.relpath(task["path"],
                             tezgah_task.repo_root(cwd, base)).replace(os.sep, "/")
    for path in write_paths(inp):
        if tezgah_task.relative(path, cwd, base) == record:
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
    scratch (`scratch_target`: a temp file, a device), which is no task's work;
    build output inside the repo is a repo path and stays held. The refusal
    names the file as the call spelled it, because the agent has to recognize
    its own argument."""
    task = _task(cwd, base, task)
    if not task:
        return None
    if task["phase"] not in tezgah_task.WRITE_PHASES:
        return TASK_PHASE_DENY % (task["id"], task["phase"],
                                  " or ".join(tezgah_task.WRITE_PHASES))
    patterns = task["allowed_paths"]
    if not patterns:
        return None
    for path in write_paths(inp):
        if scratch_target(path, cwd):
            continue
        rel = tezgah_task.relative(path, cwd, base)
        if rel is None or not any(tezgah_task.match(rel, p) for p in patterns):
            return TASK_SCOPE_DENY % (path, task["id"], ", ".join(patterns))
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
# The refusal names the one command that makes the boundary real. That is not the
# mistake TASK_PHASE_DENY records: the E7 lesson is a refusal that names how to
# take the constraint off (the phase is the user's to move), while the checkpoint
# command *satisfies* the requirement - running it is the work the rule asks for,
# so naming it is naming what the rule wants rather than a way around it.
CHECKPOINT_DENY = (
    "Checkpoint gate: the active task %s is in phase `implementation` and its "
    "plan records a pending checkpoint (`checkpoint: pending <sha>`), so this "
    "write would start the work on top of changes no commit names - and the "
    "per-file snapshots are not one state to return to. The command that makes "
    "the boundary real is %s; it moves HEAD off the recorded sha, so running it "
    "satisfies this rule and moves nothing.")


def checkpoint_reason(inp, cwd, base, task=_UNRESOLVED):
    """A deny reason when the active task is in `implementation`, its plan's
    `checkpoint:` waits for a commit (`pending <sha>`), that sha is still HEAD,
    and the tree still holds uncommitted work - else None.

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
    task = _task(cwd, base, task)
    if not task or task["phase"] != "implementation":
        return None
    sha = tezgah_task.checkpoint_sha(task.get("checkpoint"))
    if not sha:
        return None
    # HEAD read from the ref file, not a fork: this question is asked on every
    # write of the phase, and an unreadable HEAD fails open.
    root = tezgah_task.repo_root(cwd, base)
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
    return CHECKPOINT_DENY % (task["id"], tezgah_task.checkpoint_command(task["path"]))


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
    if not m:
        return ""
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
    if off("reminder-off") or not effectful(str(tool or "").lower(), inp or {}):
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


def effectful(t, inp):
    """True when this call is one the constraints are about: a write tool, or a
    git/gh command that lands an artifact. A read changes nothing, so the notice
    spent on it would be spent where no rule applies."""
    if t in WRITE_TOOLS:
        return True
    if t in BASH_TOOLS:
        return bool(WRITE_CMD.search(mask(str(inp.get("command") or ""))))
    return False


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
    unanswerable question must pass. ponytail: a worktree's packed refs live in
    the common dir, not in the worktree gitdir this reads, so a repacked ref in a
    linked worktree falls back to "" - the fail-open direction."""
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
# The CLIs that change control state, by basename with or without `.py`, and the
# first argument that makes a call a change: None is any call, "" any argument.
# `tezgah-gate decide` writes a genuine `began` row with `check=1`; the capture
# CLI writes snapshot rows; pony and adhd write CONFIG_DIR; `tezgah-context
# attest` re-attests a session, and a clean result clears its drift mark. The
# task CLI is not here: it is the task rule's (TASK_CHANGE), which `task-off`
# removes, and that switch is one of the files this rule protects.
CONTROL_CLIS = {"tezgah-gate": ("decide",), "tezgah-capture": "",
                "tezgah-pony": "", "tezgah-adhd": ("on", "off"),
                "tezgah-context": ("attest",)}
# Programs that change a path named in their arguments. Every positional is a
# target, except for the copiers, whose last one is (`cp switch /tmp` reads it).
# `sed`/`perl` count only with an in-place flag.
CONTROL_PROGRAMS = frozenset(("touch", "rm", "rmdir", "unlink", "shred",
                              "truncate", "chmod", "chown", "chgrp", "mv",
                              "mkdir", "tee", "cp", "ln", "install", "rsync",
                              "dd", "sed", "perl"))
CONTROL_COPIERS = frozenset(("cp", "mv", "ln", "install", "rsync"))
# The programs that remove, disable or move a path. A directory that holds
# protected state, a repository's husky hooks and the open plans are refused for
# these only: husky's own setup writes `.husky/pre-commit` with a redirect.
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
# The cache subtrees whose rows the rules read: the evidence ledger, the session
# store, the switch baseline (tezgah_context.disarmed), the gate mark, and the
# marks the status line reads for a drifted hook entry
# (tezgah_attest.drift_mark) and a core that failed to import
# (tezgah_guard.import_crash_mark).
CONTROL_CACHE = ("evidence", "sessions", "switches", "gate-inactive",
                 "harness-drift", "import-crash", "workspace-index.json")
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
    the install trees, and the session checkout's git hooks and open plans."""
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
    'owned' for a hook file that is wholly tezgah's, else None."""
    claude = HOST_DIRS["claude"]
    name = os.path.basename(real)
    shared = (os.path.join(HOST_DIRS["codex"], "hooks.json"),
              os.path.join(HOST_DIRS["codex"], "config.toml"),
              os.path.join(HOST_DIRS["cursor"], "hooks.json"),
              os.path.join(claude, "plugins", "installed_plugins.json"),
              os.path.join(claude, "plugins", "known_marketplaces.json"))
    if (name in ("settings.json", "settings.local.json")
            and ".claude" in real.split(os.sep)) \
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
    if kind or any(_under(real, tree) for tree in _install_trees(origin)):
        return "tezgah's hook wiring"
    if not name.endswith(".sample") and any(
            _under(real, os.path.join(top, ".git", "hooks")) for top in _tops(origin)):
        return "the repository's git hooks"
    if remove and ".husky" in real.split(os.sep):
        return "the repository's git hooks"
    if remove and "%s.tezgah%splans%sopen%s" % ((os.sep,) * 4) in real + os.sep:
        return "an open plan"
    return None


def control_target(path, cwd, remove=False, origin=None):
    """What `path` is in tezgah's control plane, or None.

    `remove` is a delete, chmod or move: a directory that holds protected state
    (`_held`), a repository's husky hooks and the open plans are protected only
    from those. `origin` is the session's own directory (the checkout whose git
    hooks count), `cwd` the one a `cd` in the line moved to. The path is judged
    as spelled and with every link resolved. A shared registration file comes
    back as its own real path, for the caller to judge by key: an edit of a key
    that is not tezgah's is the user's business."""
    origin = origin or cwd
    real = _real(path, cwd)
    for spelling in dict.fromkeys((real, _full(path, cwd))):
        label = _target_label(spelling, remove, origin)
        if label:
            return label
    if remove and any(_under(held, real) for held in _held(origin)):
        return "a directory that holds tezgah's control state"
    return None


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


def _shell_words(command):
    """The line as (word, operator?) pairs with quotes kept on each word, so a
    quoted `>` stays data: shlex in non-posix mode, heredoc bodies blanked, an
    unquoted backtick read as `;`, a continued line joined and every line ended
    by `;` - the way `_shell_segments` reads a line, minus dropping redirects. A
    line shlex cannot read is read roughly rather than dropped."""
    text = _unquoted_backticks(
        _blank_heredocs(str(command or "")).replace("\\\n", " "))
    out = []
    for line in re.split(r"\r\n|\r|\n", text):
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
            out.append((word, bool(SHELL_OPS.match(word))))
        out.append((";", True))
    return out


def _program(words):
    """(program basename without `.py`, its arguments) for one simple command,
    past compound keywords, env assignments, the wrappers and an interpreter
    running a script."""
    i = 0
    while i < len(words) and (ENV_WORD.match(words[i]) or words[i] in GIT_WRAPPER
                              or words[i] in SHELL_KEYWORDS):
        i += 2 if words[i] == "timeout" else 1
    words = words[i:]
    if words and words[0] == "[":
        # the test command: its operands are not a program, and the command
        # after the `]` is (`if [ -d x ]; then touch y; fi`)
        close = words.index("]") if "]" in words else len(words)
        words = words[close + 1:]
    if not words:
        return "", []
    if len(words) > 1 and os.path.basename(words[0]) in INTERPRETERS \
            and not words[1].startswith("-"):
        words = words[1:]
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
            return "a private `.tezgah/` path forced into the project's history"
    if sub in ("rm", "mv") and "--cached" not in rest:
        for path in paths:
            label = control_target(path, where, remove=True, origin=origin)
            if label:
                return _shell_label(label)
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
    for target, remove in checks:
        label = control_target(target, cwd, remove=remove, origin=origin)
        if label:
            return _shell_label(label)
    return None


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
    where, words, pending = cwd, [], None
    for word, is_op in _shell_words(command):
        if pending:
            judged, pending = pending, None
            if not is_op:
                target = _unquote(word)
                if judged == ">" and not (target.isdigit() or target == "-"):
                    label = control_target(target, where, origin=origin)
                    if label:
                        return _shell_label(label)
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
        if label:
            return label
    return None


def control_reason(t, inp, cwd):
    """The control-plane label this call changes, or None (see CONTROL_DENY)."""
    if t in BASH_TOOLS:
        return shell_control(inp.get("command") or inp.get("cmd"), cwd)
    deletes = set(PATCH_DELETE.findall(str(inp.get("patch") or "")))
    for path in write_paths(inp):
        label = control_target(path, cwd, remove=path in deletes)
        if label and not os.path.isabs(label):
            return label
        if label and _shared_change(label, inp):
            return "tezgah's hook wiring"
    return None


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
    if not record:
        return _dry_decision(tool, inp, cwd, session_id, agent)
    if off("pretooluse-off"):
        return None
    base = root_for(cwd)
    if not base:
        return None
    t = str(tool or "").lower()
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
    # removes it, and that one is among the files.
    if t in WRITE_TOOLS + BASH_TOOLS:
        what = control_reason(t, inp, cwd)
        if what:
            return _deny(session_id, "control", CONTROL_DENY % what, tool, inp,
                         base)
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
    # Task scope: the user's own record for this work - its phase and the files
    # its allowlist names (see task_reason). The
    # record itself is refused first of all, and a shell that would change it
    # through the CLI is refused with it: a boundary the agent can move is not a
    # boundary, and both routes to moving this one were measured open (E7).
    if not off("task-off"):
        # The record is read once and handed to every rule below: each read lists
        # `.tezgah/plans/open/` and parses a plan, and this path is every write of
        # every session. Reads and non-write tools pay nothing.
        task = _UNRESOLVED
        if tezgah_task is not None and t in WRITE_TOOLS + BASH_TOOLS:
            task = tezgah_task.active(cwd, base)
        if writes:
            reason = task_record_reason(inp, cwd, base, task)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
        if t in BASH_TOOLS and TASK_CHANGE.search(
                mask(str(inp.get("command") or ""))):
            return _deny(session_id, "task", TASK_UNLOCK_DENY, tool, inp, base)
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
    if symbol := searched_identifier(tool, inp):
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
    # A write or shell call let through also leaves its first row here
    # (tezgah_integrity.BEGAN_KIND): the PostToolUse hook writes the second, and
    # one with no answer is a call whose outcome nobody saw. Through `note`, so
    # the dry run writes none. `check` is decided here, from the whole command:
    # the stored detail is cut at DETAIL_MAX, and a check past that cut read as
    # no check at all.
    if t in WRITE_TOOLS or t in BASH_TOOLS:
        digest = call_id(tool, inp)
        if digest:
            command = str(inp.get("command") or inp.get("cmd") or "")
            note(session_id, BEGAN_KIND,
                 command or (write_paths(inp) or [""])[0],
                 id=digest, tool=str(tool or "").strip() or None,
                 workspace=base,
                 check=1 if t in BASH_TOOLS and verify_command(command) else None)
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
    deny, drift and nudge rows, `first_nudge` for the once-per-session mark,
    `capture` for the snapshot), so one swap covers every rule and a new rule
    that records through them is dry here without being told. Safe because
    the dry run is its own process (bin/tezgah-gate check): nothing else in it
    reads these names while they are swapped, and the finally puts them back.
    The nudge is still answered as the live path would answer it - spent when
    its mark exists - only the mark is not written."""
    g = globals()
    saved = {name: g[name] for name in ("note", "first_nudge", "capture")}

    def unspent(sid):
        return not os.path.exists(
            os.path.join(cache_dir(), "nudged", sid or "nosession"))

    g.update(note=lambda *a, **k: None, first_nudge=unspent, capture=None)
    try:
        return decision(tool, inp, cwd, session_id, agent=agent)
    finally:
        g.update(saved)



# Every rule slug `decision` records a refusal under (`_deny`'s second argument),
# with the kill switch that disarms it beside `pretooluse-off`, which disarms
# them all; None means only that one. A lesson the ledger retires with
# `|| enforced_by: <slug>` (tezgah_context._lesson_lines) leaves the injected
# block only while its rule is armed, so `piped` brings its lesson back under
# `verify-off`. `tests/test_lessons.py` holds this map to the `_deny` literals.
DENY_RULES = {"control": None, "explorer": None, "shortcut": "verify-off",
              "piped": "verify-off",
              "attribution": None, "lang": "lang-off", "race": None,
              "task": "task-off", "workspace": "workspace-off", "secret": None,
              "plan": None, "order": "verify-off", "loop": "verify-off",
              "retry": "verify-off", "drift": "reminder-off"}
