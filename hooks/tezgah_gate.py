#!/usr/bin/env python3
"""The tool gate, shared by every host that can block a tool call.

Rules, all only inside a tezgah root:
  1. a grep-only explorer subagent is refused, with the graph tools named as the
     replacement;
  2. the FIRST identifier-shaped search of a session (Grep tool, or grep/rg run
     through a shell) in a repo whose codebase-memory index exists is nudged
     toward the graph once, then every later search passes.
  3. a git/gh command that writes an artifact carrying an AI/model credit
     (Co-Authored-By, "Generated with", a robot emoji, ...) is refused.
  4. an identical call that already failed enough times in the current user turn
     is refused (`loop`), its allowance scoped by the failure class where the
     host reports the error text; an identical call attempted more than
     RETRY_CEILING times in the session is refused whatever its outcomes were
     (`retry`). Both read hooks/tezgah_integrity.prior_calls and both are under
     the `verify-off` kill switch the integrity rule shares.
  5. an irreversible or outward-facing command is refused ONCE per action per
     session, naming its effect class (destructive, schema, deploy, publish or
     outward) rather than the pattern it matched, and writing that class to the
     ledger as a `consent` row, so the ask the gate cannot make reaches the user
     before the action runs (consent).
  6. a command that would write a credential into a file (a redirect, `tee`,
     `git add` or a curl trace next to a `name=value` / bearer token) is
     refused (secret).
  7. a write to a file another session wrote inside RACE_WINDOW_MIN is refused
     (`race`), naming the other session and the file, because the failure it
     closes - one session overwriting another's work from a stale read - leaves
     no trace in either transcript.
  8. when the current user turn has run past DRIFT_STEPS work rows, the next
     effectful call gets the standing constraints re-stated once (`drift`), in
     the gate's reason string, which is the only channel a PreToolUse hook has.
Adapters translate the returned reason into their own permission envelope.
"""
import os
import re

from tezgah_integrity import (BASH_TOOLS, STEP_KINDS, WRITE_TOOLS, _turn_start,
                              call_id, events, mask, note, prior_calls,
                              shortcut_command, shortcut_edit)
from tezgah_paths import cache_dir, off, root_for

try:  # The race rule reads the write history through tezgah_integrity; that
    # reader is newer than some checkouts of the module, and a missing name must
    # cost the rule, never the session (this import runs on every gated call).
    from tezgah_integrity import writers_elsewhere
except ImportError:  # pragma: no cover - only on an integrity module without it
    writers_elsewhere = None

DB_DIR = os.path.join(os.path.expanduser("~"), ".cache", "codebase-memory-mcp")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
# ponytail: flags with a separate value (grep -A 3 foo) shift the token and the
# search passes unnudged; not worth a real argv parser for a once-a-session hint.
BASH_SEARCH = re.compile(r"(?:^|[|;&(]\s*|\s)(?:grep|rg)\s+((?:-\S+\s+)*)(\S+)")
# the credit forms, not a bare tool name: "OpenAI" or "Claude Code" in a
# sentence (naming a tool to use it) is fine, "Co-Authored-By: ..." or
# "Generated with ..." (signing it as author) is the thing to stop
ATTRIB = re.compile(
    r"co-authored-by\s*:|generated with|made with|built by|assisted by|"
    r"authored by|noreply@anthropic|\U0001F916", re.I)
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
ATTRIB_LINE = re.compile(
    r"(?im)^[\s>#*/<!+-]*(?:co-authored-by\s*:|generated with|made with|"
    r"built by|assisted by|authored by|noreply@anthropic|\U0001F916)")
# the payload fields a write/edit tool carries its content in, per host dialect
EDIT_TEXT = ("content", "new_string", "newString", "new_str", "file_text",
             "patch", "text")
# the write subcommand may sit behind git's global options: `git -c k=v commit`,
# `git -C dir commit`, `git --no-pager commit`. `gh api` writes comments/reviews,
# and `gh pr merge` lands a commit, so both count as writes.
WRITE_CMD = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*"
    r"(?:commit|merge|tag|notes)\b|"
    r"(?:^|[|;&]\s*|\s)gh\s+api\b|"
    r"(?:^|[|;&]\s*|\s)gh\s+(?:pr|issue|release)\s+"
    r"(?:create|edit|comment|review|merge|close)\b",
    re.I)

# --- consent: an irreversible or outward-facing command ---------------------
# A `git push` carrying a force flag, to a branch that is not scratch: a scratch
# branch is disposable, so the history it loses costs nobody else anything. The
# flag has to sit in the push segment the command's own separators bound.
GIT_PUSH = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*push\b([^|;&]*)", re.I)
FORCE_FLAG = re.compile(
    r"(?:^|\s)(?:-f|--force|--force-with-lease|--force-if-includes)(?=[\s=]|$)")
SCRATCH = re.compile(
    r"\b(?:tmp|temp|scratch|wip|spike|throwaway|trash|sandbox)[-/][\w./-]*", re.I)
# `git branch -D`/`--delete`, and the remote delete `git push --delete`/`-d`. The
# delete flag is matched by shape, because `--merged` also carries a `d`.
BRANCH_DELETE = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*"
    r"(?:branch\s+(?:-[A-Za-z]*[dD]\b|--delete\b)|"
    r"push\b[^|;&]*(?:--delete\b|-d\b))",
    re.I)
# A recursive force-delete: both flags have to be there (`rm -f` and `rm -r` on
# their own are not this rule's), and the targets come from the raw text so a
# quoted path still resolves - the `rm` itself is matched on the masked text, so
# a message that describes the command is not the command.
RM = re.compile(r"(?:^|[|;&]\s*|\s)rm\s+((?:-\S+\s+)*)([^|;&]*)")
RM_RECURSIVE = re.compile(r"-[A-Za-z]*r[A-Za-z]*\b|--recursive\b", re.I)
RM_FORCE = re.compile(r"-[A-Za-z]*f[A-Za-z]*\b|--force\b")
# Applying a migration, by the runners that name it. ponytail: a hand-written
# `psql -c "ALTER TABLE ..."` is not caught - reading SQL intent is not a regex.
MIGRATION = re.compile(
    r"(?:^|[|;&]\s*|\s)(?:"
    r"(?:alembic|flyway|goose|dbmate|sqitch)\s+"
    r"(?:upgrade|up|migrate|deploy|down|downgrade|rollback|reset|redo)\b|"
    r"(?:knex|prisma|sequelize|typeorm)\s+\S*migrat\S*|"
    r"(?:django-admin|manage\.py)\s+migrate\b|"
    r"python\d?\s+-m\s+django\s+migrate\b|"
    r"(?:bin/)?rails\s+db:(?:migrate|rollback|reset|schema:load)\b"
    r")", re.I)
# A deploy: putting code in front of users, by the runners that name it.
DEPLOY = re.compile(
    r"(?:^|[|;&]\s*|\s)(?:"
    r"(?:vercel|netlify|fly|flyctl|railway|render|wrangler|firebase|gcloud|eb)\b"
    r"[^|;&]*?\bdeploy\b|"
    r"(?:serverless|sls)\s+deploy\b|"
    r"terraform\s+(?:apply|destroy)\b|"
    r"helm\s+(?:install|upgrade|uninstall)\b|"
    r"kubectl\s+(?:apply|delete|rollout|scale)\b|"
    r"ansible-playbook\b"
    r")", re.I)
# Shipping an artifact outward: a registry, a release, an image.
PUBLISH = re.compile(
    r"(?:^|[|;&]\s*|\s)(?:"
    r"(?:npm|yarn|pnpm|bun)\s+publish\b|"
    r"twine\s+upload\b|docker\s+push\b|"
    r"gh\s+release\s+create\b"
    r")", re.I)
# A push to a target that is live rather than a branch under review.
OUTWARD = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*push\s+\S*\s*"
    r"(?:heroku|production|prod)\b", re.I)

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

# The classes a refused command's effect belongs to, and what each one is. The
# refusal names the class and this clause, never the pattern that matched: the
# agent has to see what it is about to do, not which regex caught it.
EFFECTS = {
    "destructive": "this one rewrites or drops history, a branch or files "
                   "outside the run directory",
    "schema": "this one changes the shape of a database",
    "deploy": "this one puts code in front of users",
    "publish": "this one ships an artifact to a registry or a release",
    "outward": "this one pushes to a live target rather than a branch under "
               "review",
}

CONSENT_DENY = (
    "Consent gate (`%s` effect): %s. The contract requires an explicit ask "
    "before an irreversible or outward-facing action, so put the exact command "
    "and what it cannot undo in front of the user. Once this refusal is in the "
    "transcript, the same command passes on the next attempt.")

SECRET_DENY = (
    "Credential write denied: this command would land a credential in a file "
    "(`>`/`>>`, `tee`, `git add` or a curl trace). Record the credential's "
    "name, length or a fingerprint instead of its value, pass it through the "
    "tool's own environment, or let the tool read it from there rather than "
    "writing it out.")

EXPLORE_DENY = (
    "A grep-only explorer subagent is not allowed in this tree: it greps by "
    "design and ignores the code graph. Use the general-purpose agent and name "
    "the exact codebase-memory-mcp tools (search_graph, trace_path, "
    "search_code) in its prompt, with the tool-loading step so they are armed.")

ATTRIB_DENY = (
    "Attribution is banned in every artifact tezgah touches. Remove the "
    "Co-Authored-By / \"Generated with\" / robot-emoji / model-name credit from "
    "the commit, PR, issue or review text and re-run. Naming a tool in order to "
    "use it or describe real behavior is fine; crediting it as author is not.")


def attribution(command):
    """True when a git/gh write command carries an AI/model credit."""
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
    """The codebase-memory db slug for the enclosing repo, if an index exists."""
    d = os.path.realpath(cwd)
    base = os.path.realpath(base)
    while d.startswith(base) and d != base:
        s = re.sub(r"[^A-Za-z0-9]+", "-", d).strip("-")
        if os.path.exists(os.path.join(DB_DIR, s + ".db")):
            return s
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
        open(mark, "w").close()  # consume BEFORE denying: later greps pass
        return True
    except OSError:
        return False


def nudge_reason(slug):
    return ("Code graph index is ready for this repo (%s). For a definition, its "
            "callers or blast radius use the codebase-memory-mcp search_graph / "
            "trace_path tools (load them first). If you need literal text, re-run "
            "this search unchanged; it will pass - this nudge fires once per "
            "session." % slug)


# The attempt a repeat is refused on, per failure class. Two identical failures
# are the retry the agent may still be fixing while it changes the code between
# them; the third is the loop the contract bans ("three attempts on one failure
# is the ceiling"). The class scopes that allowance where the host's error text
# carries one (tezgah_integrity.fail_class): a transient failure - a timeout, a
# connection error, a rate limit, a 5xx - can clear on its own, so the identical
# call gets one more try, while an assertion or a bad argument cannot change by
# re-running it. A host that reports no error text yields no class and the base
# allowance applies.
LOOP_CEILING = 2
CLASS_CEILING = {"transient": LOOP_CEILING + 1}
CLASS_NOTE = {
    "transient": "the failure it names can clear on its own, so this class gets "
                 "one more identical attempt than a permanent one",
    "permanent": "an assertion or a bad argument does not change by re-running "
                 "it",
}
NO_CLASS_NOTE = ("the host reported no error text for it, so the class is "
                 "unknown and the base allowance applies")

# The other half of the repeat rule, session-wide and blind to the outcome: a
# call the gate has seen run three times may not run a fourth, whatever those
# runs returned. It is deliberately above LOOP_CEILING - the loop guard counts
# only the attempts that failed, in the current turn, so a call that keeps
# "succeeding" without moving the work forward is its blind spot - and it is set
# above the common work loop (edit, test, edit, test reaches two identical test
# runs, and a session's third `git status` still passes) so only a genuine spin
# reaches it.
RETRY_CEILING = 3


def loop_ceiling(klass):
    """The identical attempts `loop` allows for this failure class."""
    return CLASS_CEILING.get(klass, LOOP_CEILING)


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
    ceiling = loop_ceiling(klass)
    if last_exit != 1 or turn < ceiling:
        return None
    return ("Loop guard denied: this is attempt %d of an identical call whose "
            "%d previous attempt%s exited 1%s. This class allows %d identical "
            "attempt%s, because %s. Repeating an identical failing command is "
            "not a retry - change the approach (fix what the error names, or run "
            "something else) or stop and report what is still unknown."
            % (turn + 1, turn, "" if turn == 1 else "s",
               " (a %s failure)" % klass if klass else "",
               ceiling, "" if ceiling == 1 else "s",
               CLASS_NOTE.get(klass, NO_CLASS_NOTE)))


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


# How much of the ledger tail the one-shot consent check reads before a matched
# command may be repeated, the same bound the loop guard reads its attempts from.
# It is read only after a class has matched, so a normal call pays nothing.
CONSENT_TAIL = 200


def asked_before(session_id, digest):
    """True when this exact action was already put in front of the user once, so
    the one-shot mark is spent.

    The `consent` row the refusal writes is the mark (see effect_class), and it
    is read here by kind and id alone: the row also carries the effect class in
    its detail, so "who was asked to confirm what" is a query over these rows -
    each one names an action and its class - rather than a string match on a
    deny message that a later reword would silently break. The window is the
    ledger tail like the loop guard's, so an action refused more than
    `CONSENT_TAIL` rows ago can be asked about once more."""
    if not (session_id and digest):
        return False
    return any(row.get("kind") == "consent" and row.get("id") == digest
               for row in events(session_id, tail=CONSENT_TAIL))


def rm_outside(masked, raw, cwd, base):
    """True when this line recursively force-deletes a path outside the run
    directory (`cwd`, the directory the command runs in).

    The `rm` is found on the masked text - a message that names the command
    deletes nothing - while the flags and targets are read from the raw text at
    the same offset, so a quoted path still resolves. The run directory itself
    counts as outside: deleting where the command runs is not a delete inside it.
    A target this cannot resolve (`$VAR`, `~`, a URL) counts as outside too; the
    conservative direction is the one that stops to ask. ponytail: a target
    behind a `cd` in the same line resolves against `cwd`, not against the `cd`,
    so that case can pass - it fails open, never closed."""
    root = os.path.realpath(cwd or base)
    for m in RM.finditer(masked):
        # The args come from the raw text at the offset the masked match proved is
        # a real `rm`: on the masked text a blanked target reads as more flags.
        r = RM.match(raw, m.start())
        if not r:
            continue
        flags, rest = r.group(1), r.group(2)
        if not (RM_RECURSIVE.search(flags) and RM_FORCE.search(flags)):
            continue
        for tok in (t.strip("'\"")
                    for t in rest.split()
                    if not t.startswith("-")):
            if not tok:
                continue
            if "$" in tok or "~" in tok or "://" in tok:
                return True
            p = os.path.realpath(tok if os.path.isabs(tok)
                                 else os.path.join(root, tok))
            if p == root or not p.startswith(root + os.sep):
                return True
    return False


def effect_class(command, cwd, base):
    """The effect class of an irreversible or outward-facing command, or None.

    `destructive` rewrites or drops history, a branch or files outside the run
    directory; `schema` changes the shape of a database; `deploy` puts code in
    front of users; `publish` ships an artifact to a registry or a release;
    `outward` pushes to a live target rather than a branch under review. A
    command carries the first class that matches, so the refusal says what the
    action is instead of listing the patterns it hit and the ledger row records
    the class rather than a rule name.

    One call is all the gate sees and it cannot ask, so the ask becomes a refusal
    the user reads: the identical command passes on its second attempt because
    the `consent` row the refusal writes is the mark (asked_before). That is the
    least friction that still stops an agent spending someone else's branch,
    database or deployment unasked. Tradeoff: a user who did ask pays one
    round-trip, and an agent that ignores the reason twice can still proceed - in
    front of a user who has now seen the refusal. A session whose ledger cannot
    be written refuses every time, so there the ask has to happen outside the
    agent."""
    c = str(command or "")
    if not c:
        return None
    masked = mask(c)
    for m in GIT_PUSH.finditer(masked):
        seg = m.group(1)
        if FORCE_FLAG.search(seg) and not SCRATCH.search(seg):
            return "destructive"
    if BRANCH_DELETE.search(masked) or rm_outside(masked, c, cwd, base):
        return "destructive"
    if MIGRATION.search(masked):
        return "schema"
    if DEPLOY.search(masked):
        return "deploy"
    if PUBLISH.search(masked):
        return "publish"
    if OUTWARD.search(masked):
        return "outward"
    return None


def consent_reason(klass):
    """The refusal for one effect class: the class, what it means, and what to
    ask - never the list of patterns the command happened to match."""
    return CONSENT_DENY % (klass, EFFECTS[klass])


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
WRITE_PATH = ("file_path", "filePath", "path")
PATCH_FILE = re.compile(r"(?m)^\*\*\* (?:Update|Add|Delete) File: (\S.*?)\s*$")


def write_paths(inp):
    """Every file this call writes: the tool's own path field, else the paths an
    apply_patch body names per hunk."""
    if not isinstance(inp, dict):
        return []
    for key in WRITE_PATH:
        value = inp.get(key)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return [m.group(1) for m in PATCH_FILE.finditer(str(inp.get("patch") or ""))]


def race_reason(inp, session_id):
    """A deny reason when another session wrote one of this call's files inside
    RACE_WINDOW_MIN, else None.

    `writers_elsewhere` is the ledger reader in tezgah_integrity, and its import
    is guarded: an integrity module without it costs this rule, never the
    session. ponytail: the PostToolUse writer records no path for an apply_patch
    row (`detail` comes from file_path), so a foreign patch write stays
    invisible to the reader even though this side reads the patch's own paths -
    the gap is the writer's, and closing it means the ledger row changes shape."""
    if writers_elsewhere is None or not session_id:
        return None
    for path in write_paths(inp):
        others = writers_elsewhere(path, session_id, RACE_WINDOW_MIN)
        if others:
            return RACE_DENY % (", ".join(str(s) for s in others[:3]),
                                RACE_WINDOW_MIN, path)
    return None


# --- constraint drift: a long turn loses the rules it started with ----------
# The re-statement that keeps the rules alive rides the user prompt
# (tezgah_context.context_for writes PROMPT_REMINDER on every turn), so the
# stretch nothing covers is one turn that runs long: by step 25 the prompt that
# armed the rules is dozens of tool results back and has stopped steering. The
# threshold counts work rows in the CURRENT user turn - the same rows counters()
# counts, a run/an edit/a check - which a normal turn reaches a handful of, and
# the mark is per turn: one re-statement in a turn that drifted is useful, the
# same one in every short turn is noise the agent learns to skip.
DRIFT_STEPS = 25
# How far back the count reads: past it a very long turn's count saturates at the
# window (the notice fires once per turn regardless), the same 200-row bound the
# repeat guards read.
DRIFT_TAIL = 200
DRIFT_DENY = (
    "Long turn (%d work rows in, past the %d this notice waits for): the "
    "constraints this session was armed with are still in force - %s. This is a "
    "re-statement, not a violation report: re-issue this call unchanged and "
    "carry on.")


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


def drift_reason(session_id, cwd):
    """A one-shot re-statement of the standing constraints when this user turn
    has run past DRIFT_STEPS work rows, else None.

    What this deliberately is NOT: a detector of the rule the user meant. A
    PreToolUse payload carries the tool call, not the prompt - no host hook sees
    the text the user typed - so "which rule is being forgotten" would be a guess
    about intent wearing a check's clothes. Re-stating the standing constraints
    is the honest half, and it is the whole of what this does. The host gives a
    PreToolUse hook no non-blocking way to reach the model either (the reason
    string is the only channel), so the notice arrives as a refusal whose reason
    is the re-statement, and the mark is written here - before the deny - so the
    identical call passes on the next attempt."""
    if not session_id:
        return None
    rows = events(session_id, tail=DRIFT_TAIL)
    rows = rows[_turn_start(rows):]
    if any(row.get("kind") == "drift" for row in rows):
        return None
    steps = sum(1 for row in rows if row.get("kind") in STEP_KINDS)
    if steps < DRIFT_STEPS:
        return None
    note(session_id, "drift", str(steps), workspace=root_for(cwd))
    # POINTERS ends in its own full stop; the template supplies the next
    # sentence's, so the joined text would otherwise read ".."
    return DRIFT_DENY % (steps, DRIFT_STEPS, constraints_line(cwd).rstrip("."))


def effectful(t, inp):
    """True when this call is one the constraints are about: a write tool, or a
    git/gh command that lands an artifact. A read changes nothing, so the notice
    spent on it would be spent where no rule applies."""
    if t in WRITE_TOOLS:
        return True
    if t in BASH_TOOLS:
        return bool(WRITE_CMD.search(mask(str(inp.get("command") or ""))))
    return False


def _deny(session_id, rule, reason, tool=None, inp=None, workspace=None):
    """Record a refusal before returning it: a deny nobody counts is a rule
    whose effect can never be argued about (hooks/tezgah_integrity.counters).

    The row carries the refused call's id and workspace, so the ledger says
    which action was stopped and where - the same two facts a PostToolUse row
    carries."""
    note(session_id, "deny", "%s: %s" % (rule, str(reason)[:80]),
         id=call_id(tool, inp), workspace=workspace)
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
    if t in ("agent", "task", "subagent") and explored(sub):
        return _deny(session_id, "explorer", EXPLORE_DENY, tool, inp, base)
    # anti-shortcut: a check neutered so it cannot fail, or a test disabled so a
    # failure disappears. This is the mechanical half of the integrity rule; the
    # reply-level half is the Stop hook in hooks/projects-stop.py (Claude),
    # hosts/codex/hook.py, hosts/cursor/hook.py and hosts/omp/hook.py. `verify-off`
    # removes that rule, so it drops this half too; `pretooluse-off` above still
    # drops the whole gate, and attribution/explore are other rules and stay
    # armed.
    if not off("verify-off"):
        if t in BASH_TOOLS:
            reason = shortcut_command(inp.get("command"))
            if reason:
                return _deny(session_id, "shortcut", reason, tool, inp, base)
        if t in WRITE_TOOLS:
            reason = shortcut_edit(inp)
            if reason:
                return _deny(session_id, "shortcut", reason, tool, inp, base)
    if t in BASH_TOOLS and attribution(inp.get("command")):
        return _deny(session_id, "attribution", ATTRIB_DENY, tool, inp, base)
    if t in WRITE_TOOLS and attribution_edit(inp):
        return _deny(session_id, "attribution", ATTRIB_DENY, tool, inp, base)
    # Concurrent write: another session wrote one of this call's files inside
    # RACE_WINDOW_MIN (the constant carries why it refuses). Ahead of the repeat
    # guards, so a colliding write is counted as this rule and not as a repeat of
    # one.
    if t in WRITE_TOOLS and RACE_REFUSE:
        reason = race_reason(inp, session_id)
        if reason:
            return _deny(session_id, "race", reason, tool, inp, base)
    # Consent: an irreversible or outward-facing command, refused once per action
    # per session so the ask reaches the user (see effect_class for the design
    # and its tradeoff). The row this writes is both the classification and the
    # one-shot mark, and the second identical attempt falls through every other
    # rule, so a user who asked is not looped.
    if t in BASH_TOOLS:
        digest = call_id(tool, inp)
        klass = effect_class(inp.get("command"), cwd, base)
        if klass and not asked_before(session_id, digest):
            note(session_id, "consent", klass, id=digest, workspace=base)
            return _deny(session_id, "consent", consent_reason(klass), tool, inp,
                         base)
        # A credential on its way into a file. No escape hatch: the deny text
        # names the rephrase (a name, a length, a fingerprint), so the write can
        # be replaced rather than repeated.
        reason = secret_command(inp.get("command"))
        if reason:
            return _deny(session_id, "secret", reason, tool, inp, base)
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
            return nudge_reason(slug)
    # Constraint drift, last: a re-statement yields to every refusal above (a
    # refusal's reason is the same channel), and `verify-off` does not drop it -
    # the rules it re-states are not the verify rule. The switch that governs it
    # is the per-turn reminder's own, because this is that reminder's mid-turn
    # half.
    if not off("reminder-off") and effectful(t, inp):
        reason = drift_reason(session_id, cwd)
        if reason:
            return _deny(session_id, "drift", reason, tool, inp, base)
    return None
