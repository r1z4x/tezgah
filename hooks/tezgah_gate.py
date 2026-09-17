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
  4. an identical call that already failed enough times in this session is
     refused (hooks/tezgah_integrity.prior_calls), under the `verify-off` kill
     switch the integrity rule shares. This is the mechanical half of the
     taxonomy's "repeated identical call" mode; a repeat that did NOT fail is
     deliberately out of its scope (see loop_reason).
  5. an irreversible or outward-facing command - a force-push to a non-scratch
     branch, a branch delete, `rm -rf` outside the run directory, a migration, a
     deploy or a publish - is refused ONCE per action per session, so the ask
     the gate cannot make reaches the user before the action runs (consent).
  6. a command that would write a credential into a file (a redirect, `tee`,
     `git add` or a curl trace next to a `name=value` / bearer token) is
     refused (secret).
Adapters translate the returned reason into their own permission envelope.
"""
import os
import re

from tezgah_integrity import (BASH_TOOLS, WRITE_TOOLS, call_id, events, mask,
                              note, prior_calls, shortcut_command, shortcut_edit)
from tezgah_paths import cache_dir, off, root_for

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
# A deploy, plus the outward-facing publish/upload half of the same clause.
DEPLOY = re.compile(
    r"(?:^|[|;&]\s*|\s)(?:"
    r"(?:vercel|netlify|fly|flyctl|railway|render|wrangler|firebase|gcloud|eb)\b"
    r"[^|;&]*?\bdeploy\b|"
    r"(?:serverless|sls)\s+deploy\b|"
    r"terraform\s+(?:apply|destroy)\b|"
    r"helm\s+(?:install|upgrade|uninstall)\b|"
    r"kubectl\s+(?:apply|delete|rollout|scale)\b|"
    r"ansible-playbook\b|"
    r"(?:npm|yarn|pnpm|bun)\s+publish\b|"
    r"twine\s+upload\b|docker\s+push\b|"
    r"gh\s+release\s+create\b|"
    r"git\s+push\s+\S*\s*(?:heroku|production|prod)\b"
    r")", re.I)

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

CONSENT_DENY = (
    "Consent gate: this is an irreversible or outward-facing action "
    "(force-push to a shared branch, a branch delete, `rm -rf` outside the run "
    "directory, a database migration, a deploy or a publish). The contract "
    "requires an explicit ask first, so put the exact command and what it "
    "cannot undo in front of the user. Once this refusal is in the transcript, "
    "the same command passes on the next attempt.")

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


# The attempt a repeat is refused on: two identical failures are the retry the
# agent may still be fixing, the third is the loop the contract bans ("three
# attempts on one failure is the ceiling"). One ceiling for every fail_class -
# the class is a metric on the row, not a second policy that would refuse a
# legitimate fix-and-re-run on the second try.
LOOP_CEILING = 2


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
    attempts, last_exit, klass = prior_calls(session_id, digest)
    if last_exit != 1 or attempts < LOOP_CEILING:
        return None
    return ("Loop guard denied: this is attempt %d of an identical call whose "
            "%d previous attempt%s exited 1%s. Repeating an identical failing "
            "command is not a retry - change the approach (fix what the error "
            "names, or run something else) or stop and report what is still "
            "unknown." % (attempts + 1, attempts, "" if attempts == 1 else "s",
                          " (a %s failure)" % klass if klass else ""))


# How much of the ledger tail the one-shot consent check reads before a matched
# command may be repeated, the same bound the loop guard reads its attempts from.
# It is read only after a rule has matched, so a normal call pays nothing.
CONSENT_TAIL = 200


def refused_before(session_id, rule, digest):
    """True when this session's ledger already holds this rule's refusal of this
    exact action, i.e. the one-shot mark is spent.

    The `deny` row the gate itself writes is the mark: the refusal the user reads
    and the thing that lets the repeat through are one row, so nothing new is
    written and there is no second mark to fall out of step with the ledger. The
    window is the ledger tail like the loop guard's, so an action refused more
    than `CONSENT_TAIL` rows ago can be refused once more."""
    if not (session_id and digest):
        return False
    return any(row.get("kind") == "deny" and row.get("id") == digest
               and str(row.get("detail") or "").startswith(rule + ":")
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


def consent_command(command, cwd, base):
    """A deny reason when this command is irreversible or outward-facing.

    One call is all the gate sees and it cannot ask, so the ask becomes a refusal
    the user reads: the identical command passes on its second attempt because
    the `consent` deny row is the mark (refused_before). That is the least
    friction that still stops an agent spending someone else's branch, database
    or deployment unasked. Tradeoff: a user who did ask pays one round-trip, and
    an agent that ignores the reason twice can still proceed - in front of a user
    who has now seen the refusal. A session whose ledger cannot be written
    refuses every time, so there the ask has to happen outside the agent."""
    c = str(command or "")
    if not c:
        return None
    masked = mask(c)
    for m in GIT_PUSH.finditer(masked):
        seg = m.group(1)
        if FORCE_FLAG.search(seg) and not SCRATCH.search(seg):
            return CONSENT_DENY
    if (BRANCH_DELETE.search(masked) or MIGRATION.search(masked)
            or DEPLOY.search(masked) or rm_outside(masked, c, cwd, base)):
        return CONSENT_DENY
    return None


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
    # Consent: an irreversible or outward-facing command, refused once per action
    # per session so the ask reaches the user (see consent_command for the design
    # and its tradeoff). The second identical attempt falls through every other
    # rule, so a user who asked is not looped.
    if t in BASH_TOOLS:
        reason = consent_command(inp.get("command"), cwd, base)
        if reason and not refused_before(session_id, "consent",
                                         call_id(tool, inp)):
            return _deny(session_id, "consent", reason, tool, inp, base)
        # A credential on its way into a file. No escape hatch: the deny text
        # names the rephrase (a name, a length, a fingerprint), so the write can
        # be replaced rather than repeated.
        reason = secret_command(inp.get("command"))
        if reason:
            return _deny(session_id, "secret", reason, tool, inp, base)
    # Loop guard, under the same kill switch as the other integrity denials and
    # after every argument-shaped rule: a call another rule would have refused
    # has to be counted as that rule, not as a repeat. It reads the ledger tail,
    # which is the only file I/O this path is allowed.
    if not off("verify-off") and t in BASH_TOOLS + WRITE_TOOLS:
        reason = loop_reason(tool, inp, session_id)
        if reason:
            return _deny(session_id, "loop", reason, tool, inp, base)
    if searched_identifier(tool, inp):
        slug = index_slug(cwd, base)
        if slug and first_nudge(session_id):
            note(session_id, "nudge", slug, id=call_id(tool, inp),
                 workspace=base)
            return nudge_reason(slug)
    return None
