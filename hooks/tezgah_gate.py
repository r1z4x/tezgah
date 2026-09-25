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
  5. a command that would write a credential into a file (a redirect, `tee`,
     `git add` or a curl trace next to a `name=value` / bearer token) is
     refused (secret).
  6. a write to a file another session wrote inside RACE_WINDOW_MIN is refused
     (`race`), naming the other session and the file, because the failure it
     closes - one session overwriting another's work from a stale read - leaves
     no trace in either transcript.
  7. when the current user turn has run past DRIFT_STEPS work rows, the next
     effectful call's *result* carries the standing constraints re-stated once
     (`drift`, whose ledger row is the marker). It is not a refusal: the notice
     is about the turn and not about the call, so it rides the tool-result
     channel each host already has beside the untrusted-content label, and the
     adapters call drift_reason from their PostToolUse side - `decision` never
     refuses for it.
  8. a write while an active task is set - a plan file under .tezgah/plans/open whose
     frontmatter carries a valid `phase` - is refused when that phase is one
     that only reads, or when the file is outside the task's `allowed_paths`
     (`task`). The record is the user's own, written by bin/tezgah-task and
     never by the agent, so the refusal leans on a decision the user made rather
     than one this gate inferred: no active task means no requirement, and the
     rule invents nothing. Two further refusals close the ways a session could
     move the boundary instead of respecting it: a write whose target IS that
     record, and a shell command that would change it through the CLI. Both were
     measured open before they were closed - with the refusal naming the command
     that lifts it, an armed arm removed or disabled the gate in 25 of 25 runs
     and obeyed it in none (benchmarks/lab, PREREGISTRATION-E7.md) - and neither
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
     The three rules that read the text a write tool would land - the shell half
     of the shortcut rule, of the attribution rule above and of the credential
     rule below - read the body a heredoc writes as well (shell_write_body). The
     write tools and the shell are disjoint sets, so that route was refused by
     nothing, and it is the one E7c measured an armed session taking.
Adapters translate the returned reason into their own permission envelope.
"""
import os
import re

from tezgah_integrity import (BASH_TOOLS, HEREDOC, STEP_KINDS, WRITE_TOOLS,
                              _turn_start, call_id, cut, events, mask, note,
                              prior_calls, shortcut_command, shortcut_edit,
                              turn_rows)
from tezgah_paths import cache_dir, off, root_for

try:  # The ordering rule's two readers: the newest check's state, folded the way
    # the Stop rule folds it, and the command of that check for the refusal.
    # Newer than some checkouts, and a missing name costs the rule, never the
    # session - this import runs on every gated call.
    from tezgah_integrity import _failed_check, _last_verify
except ImportError:  # pragma: no cover - only on an integrity module without them
    _failed_check, _last_verify = None, None

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
# Only the two shapes the contract names: a bearer header, or a `name=value`
# assignment. A trailing quote is allowed because the value is usually quoted,
# and `:` is NOT a separator here - `{"api_key": "x"}` is a JSON field in a
# program's text, while `token=$TOKEN` and `api_key=...` are a credential being
# carried. The value may be an env reference: `OPENROUTER_API_KEY=$KEY` echoed
# into a log is the taxonomy's own case (`$KEY` is resolved by the shell).
SECRET_TOKEN = re.compile(
    r"authorization\s*:\s*bearer\s+\S|"
    r"[A-Za-z0-9_.-]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|"
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
    return re.split(r"[\s;&|]", text, 1)[0]


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
    closest-ancestor-first, the root itself excluded, because a root is not a
    project - and the name returned is still the key the index worker stamps HEAD
    under, so index_mark and index_notice keep reading the same file."""
    d = os.path.realpath(cwd)
    base = os.path.realpath(base)
    while d.startswith(base) and d != base:
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


def nudge_reason():
    return ("Code graph index is ready for this repo. For a definition, its "
            "callers or blast radius use the codegraph tools: "
            "`codegraph_explore` over MCP, or `codegraph callers|impact|node` "
            "from a shell. If you need literal text, re-run this search "
            "unchanged; it will pass - this nudge fires once per session.")


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


def loop_reason(tool, inp, session_id):
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
    turn, _, last_exit, klass = prior_calls(session_id, digest)
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


def retry_reason(tool, inp, session_id):
    """A deny reason when this exact call has already been attempted more than
    RETRY_CEILING times in this session, whatever those attempts returned.

    `loop` needs a failure to fire, so the call that runs ten times and returns 0
    each time - the spin that never reaches a decision - passes it forever. This
    is that half: the count is every attempt of the id that ran in the session,
    outcome-blind, and the user's turn does not reset it. A refused call never
    ran, so the gate's own denials are not attempts and cannot walk a call up to
    the ceiling by themselves."""
    if not session_id:
        return None
    digest = call_id(tool, inp)
    if not digest:
        return None
    attempts = prior_calls(session_id, digest)[1]
    if attempts < RETRY_CEILING:
        return None
    return ("Retry ceiling denied: this is attempt %d of an identical call in "
            "this session, past the ceiling of %d attempts whatever their "
            "outcome. An unchanged repeat is not a retry - change the arguments "
            "or the target, or stop and report what is still unknown. (The "
            "`loop` guard is the narrower rule: the identical attempts that "
            "FAILED, counted per user turn.)" % (attempts + 1, RETRY_CEILING))


def secret_command(command):
    """A deny reason when this command would write a credential into a file.

    Reading an env var or running a tool with a key in its env is the normal work
    this must not touch, so a token only counts next to a write sink, and a sink
    only carries the text of its own simple command."""
    c = str(command or "")
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
# The file a write call names, per host dialect, plus the apply_patch headers for
# the dialect whose paths live in the body. Matched verbatim against the ledger
# row's `detail`, which the PostToolUse hook writes from the same field: the
# ledger keeps no cwd, so normalizing here would compare `a.py` against
# `./sub/../a.py` and disagree with the reader on the far side. A second session
# that spells the path differently therefore escapes this rule.
WRITE_PATH = ("file_path", "filePath", "path", "notebook_path")
PATCH_FILE = re.compile(r"(?m)^\*\*\* (?:Update|Add|Delete) File: (\S.*?)\s*$")
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
    them against its own directory. ponytail: a target that is a positional
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
    return [target] if target else []


def race_reason(inp, session_id):
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
        others = writers_elsewhere(path, session_id, RACE_WINDOW_MIN)
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
# runs and obeyed it in none (benchmarks/lab, PREREGISTRATION-E7.md). A refusal
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
# is not refused. The token is the CLI's own name, so any path to it counts.
TASK_CHANGE = re.compile(
    r"(?:^|[|;&(]\s*|\s)(?:python3\s+)?\S*tezgah-task\s+"
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


def task_shell_reason(inp, cwd, base):
    """A deny reason when the active task's phase only reads and this shell
    command writes a file, else None.

    The route to the hole the phase rule closes, and the one E7b measured: with
    the write tools refused, the armed arm wrote the target with a heredoc
    redirect in 3 of 25 runs. A phase that excludes writes has to exclude them
    however they are made. The allowlist is not consulted here - a shell line's
    targets are not read (see SHELL_WRITE), so the reading phases are the whole
    requirement, and the same fail-open holds: no record, no requirement."""
    if tezgah_task is None:
        return None
    task = tezgah_task.active(cwd, base)
    if not task or task["phase"] in tezgah_task.WRITE_PHASES:
        return None
    if not SHELL_WRITE.search(mask(str(inp.get("command") or ""))):
        return None
    return TASK_SHELL_DENY % (task["id"], task["phase"])


def task_record_reason(inp, cwd, base):
    """A deny reason when this write's target IS the active task's record.

    The other route to the same hole as TASK_UNLOCK_DENY, and the one a write
    tool takes: the record is a file in the repo, so an agent that may write
    files can retype the phase instead of running the CLI. Refused whatever the
    phase and whatever the allowlist says - the record is not inside its own
    scope, because a scope that can widen itself is not one."""
    if tezgah_task is None:
        return None
    task = tezgah_task.active(cwd, base)
    if not task:
        return None
    record = os.path.relpath(task["path"],
                             tezgah_task.repo_root(cwd, base)).replace(os.sep, "/")
    for path in write_paths(inp):
        if tezgah_task.relative(path, cwd, base) == record:
            return TASK_RECORD_DENY % path
    return None


def task_reason(inp, cwd, base):
    """A deny reason when the active task's phase or allowlist excludes this
    write, else None. No active task -> None: this rule never invents a
    requirement the user did not set.

    The record is read through tezgah_task, whose import is guarded: a checkout
    without that module costs this rule, never the session. The paths are the
    ones write_paths already extracts, so an apply_patch body is checked hunk by
    hunk like every other write rule's here. A path that resolves outside the
    repo root is refused by `relative` before any pattern is tried - a `**`
    allowlist must not reach out of the repo - and the refusal names the file as
    the call spelled it, because the agent has to recognize its own argument."""
    if tezgah_task is None:
        return None
    task = tezgah_task.active(cwd, base)
    if not task:
        return None
    if task["phase"] not in tezgah_task.WRITE_PHASES:
        return TASK_PHASE_DENY % (task["id"], task["phase"],
                                  " or ".join(tezgah_task.WRITE_PHASES))
    patterns = task["allowed_paths"]
    if not patterns:
        return None
    for path in write_paths(inp):
        rel = tezgah_task.relative(path, cwd, base)
        if rel is None or not any(tezgah_task.match(rel, p) for p in patterns):
            return TASK_SCOPE_DENY % (path, task["id"], ", ".join(patterns))
    return None


# --- the shell's write body: three write-tool rules reached through a heredoc -
# What this closes (the route E7c measured): SKIP_TEST, ATTRIB_LINE and the
# credential scan are attached to WRITE_TOOLS, which is disjoint from BASH_TOOLS,
# so a heredoc that wrote a test skip, an attribution line or a key into a file
# was refused by nothing - and E7c watched the armed arm take exactly that route
# once the write tools were refused (3 of 25 runs wrote the target with `cat >
# app/api.py <<'EOF'`). Each of the three now also reads the body a shell command
# writes, and the body is the RAW text because mask() blanks heredoc bodies by
# design: a command that merely names a rule must not be denied.
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


def _heredoc_bodies(text):
    """Every heredoc body in `text`, in order, read off the raw text."""
    lines = str(text or "").split("\n")
    out, i = [], 0
    while i < len(lines):
        m = HEREDOC.search(lines[i])
        if not m:
            i += 1
            continue
        tag = m.group(1)
        j = i + 1
        while j < len(lines) and lines[j].strip() != tag:
            j += 1
        if j == len(lines):  # unterminated: nothing was written by it
            i += 1
            continue
        out.append("\n".join(lines[i + 1:j]))
        i = j + 1
    return out


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
    bodies = _heredoc_bodies(c)
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
# It is delivered on the tool-result channel (the one that carries
# tezgah_untrusted's label and taint notice), so `decision` never refuses for
# it: the notice is about the turn and not about the call it lands on, and a
# refusal spent that call.
DRIFT_STEPS = 25
# How far back the count reads: the same 200-row bound the repeat guards read, so
# one gated call parses at most that many rows. Past that bound the window holds
# neither the turn's own marker nor the one the notice wrote, so the read falls
# back to the turn's own start (the module's own turn-scoped reader).
DRIFT_TAIL = 200
DRIFT_NOTICE = (
    "Long turn (%d work rows in, past the %d this notice waits for): the "
    "constraints this session was armed with are still in force. %s This is a "
    "re-statement, not a violation report: nothing was refused, so carry on.")


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
    label plus its opening clause, under the same kill-switch filtering), and
    POINTERS is the on-demand rules' own one-liner, so the notice can neither
    name a rule that is off nor miss one that is on: it is a re-statement, never
    a second copy of the contract. Imported inside the call because only the
    call that crosses DRIFT_STEPS pays for it."""
    from tezgah_context import core_for, subagent_core
    from tezgah_policy import POINTERS
    return " ".join((subagent_core(core_for(cwd)[0]) + " " + POINTERS).split())


def drift_reason(tool, inp, cwd, session_id):
    """The one-shot re-statement a long turn's next effectful result carries, or
    None.

    What this deliberately is NOT: a detector of the rule the user meant. A host
    payload carries the tool call, not the prompt - no hook sees the text the
    user typed - so "which rule is being forgotten" would be a guess about intent
    wearing a check's clothes. Re-stating the standing constraints, or the delta
    since the turn began where the context module has one, is the honest half,
    and it is the whole of what this does (see drift_text).

    The tool and its input are arguments because the notice only belongs on an
    effect (`effectful`): the result channel answers for every call, so a read
    would otherwise spend the turn's one notice on a call no rule applies to.

    The marker row is written HERE, when the line is produced, and it is that
    row - not the delivery - that makes the notice once per turn: nothing tells
    a hook whether the host put the field in front of the model, and a host that
    drops it still leaves the turn marked."""
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
    return DRIFT_NOTICE % (steps, DRIFT_STEPS, drift_text(cwd, session_id))


def effectful(t, inp):
    """True when this call is one the constraints are about: a write tool, or a
    git/gh command that lands an artifact. A read changes nothing, so the notice
    spent on it would be spent where no rule applies."""
    if t in WRITE_TOOLS:
        return True
    if t in BASH_TOOLS:
        return bool(WRITE_CMD.search(mask(str(inp.get("command") or ""))))
    return False


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


def decision(tool, inp, cwd, session_id=None):
    """A deny reason for this call, or None to let it pass."""
    if off("pretooluse-off"):
        return None
    base = root_for(cwd)
    if not base:
        return None
    t = str(tool or "").lower()
    sub = inp.get("subagent_type") or (inp.get("args") or {}).get("subagent_type")
    # The body a shell call writes, read once: the three write-tool-only rules
    # below reach it through the shell (see the section above). None for every
    # tool that is not a shell, and for a shell line that writes no body.
    shell_body = (shell_write_body(inp.get("command"), cwd)
                  if t in BASH_TOOLS else None)
    if t in ("agent", "task", "subagent") and explored(sub):
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
    # one.
    if t in WRITE_TOOLS and RACE_REFUSE:
        reason = race_reason(inp, session_id)
        if reason:
            return _deny(session_id, "race", reason, tool, inp, base)
    # Task scope: the user's own record for this work - its phase and the files
    # its allowlist names (see task_reason). The
    # record itself is refused first of all, and a shell that would change it
    # through the CLI is refused with it: a boundary the agent can move is not a
    # boundary, and both routes to moving this one were measured open (E7).
    if not off("task-off"):
        if t in WRITE_TOOLS:
            reason = task_record_reason(inp, cwd, base)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
        if t in BASH_TOOLS and TASK_CHANGE.search(
                mask(str(inp.get("command") or ""))):
            return _deny(session_id, "task", TASK_UNLOCK_DENY, tool, inp, base)
        if t in BASH_TOOLS:
            reason = task_shell_reason(inp, cwd, base)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
        if t in WRITE_TOOLS:
            reason = task_reason(inp, cwd, base)
            if reason:
                return _deny(session_id, "task", reason, tool, inp, base)
    # A credential on its way into a file. No escape hatch: the deny text
    # names the rephrase (a name, a length, a fingerprint), so the write can
    # be replaced rather than repeated. The body a heredoc writes is read
    # here too: mask() blanks it, so the text-level scan above cannot see a
    # key that sits in it.
    if t in BASH_TOOLS:
        reason = secret_command(inp.get("command"))
        if reason:
            return _deny(session_id, "secret", reason, tool, inp, base)
        if shell_body and SECRET_TOKEN.search(shell_body["content"]):
            return _deny(session_id, "secret", SECRET_DENY, tool, inp, base)
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
        reason = loop_reason(tool, inp, session_id)
        if reason:
            return _deny(session_id, "loop", reason, tool, inp, base)
        reason = retry_reason(tool, inp, session_id)
        if reason:
            return _deny(session_id, "retry", reason, tool, inp, base)
    if searched_identifier(tool, inp):
        slug = index_slug(cwd, base)
        if slug and first_nudge(session_id):
            note(session_id, "nudge", slug, id=call_id(tool, inp),
                 workspace=base)
            return nudge_reason()
    # Constraint drift is deliberately NOT refused here. The re-statement (see
    # drift_reason) is about the turn, not about this call, so it rides the
    # tool-result channel each host already has for tezgah_untrusted's label and
    # taint notice - hooks/projects-posttooluse.py (claude, dsh),
    # hosts/codex/hook.py, hosts/cursor/hook.py and hosts/omp/hook.py call it
    # from their PostToolUse side. As a refusal it consumed the call it landed
    # on, and the marker row it leaves there is the same once-per-turn state this
    # branch used to write. `reminder-off` still governs it, checked in the
    # producer.
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

