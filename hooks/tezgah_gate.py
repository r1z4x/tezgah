#!/usr/bin/env python3
"""The tool gate, shared by every host that can block a tool call.

Two rules, both only inside a tezgah root:
  1. a grep-only explorer subagent is refused, with the graph tools named as the
     replacement;
  2. the FIRST identifier-shaped search of a session (Grep tool, or grep/rg run
     through a shell) in a repo whose codebase-memory index exists is nudged
     toward the graph once, then every later search passes.
  3. a git/gh command that writes an artifact carrying an AI/model credit
     (Co-Authored-By, "Generated with", a robot emoji, ...) is refused.
Adapters translate the returned reason into their own permission envelope.
"""
import os
import re

from tezgah_integrity import (BASH_TOOLS, WRITE_TOOLS, note, shortcut_command,
                             shortcut_edit)
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


def _deny(session_id, rule, reason):
    """Record a refusal before returning it: a deny nobody counts is a rule
    whose effect can never be argued about (hooks/tezgah_integrity.counters)."""
    note(session_id, "deny", "%s: %s" % (rule, str(reason)[:80]))
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
        return _deny(session_id, "explorer", EXPLORE_DENY)
    # anti-shortcut: a check neutered so it cannot fail, or a test disabled so a
    # failure disappears. This is the mechanical half of the integrity rule; the
    # reply-level half is the Stop hook (hosts/claude, hosts/codex,
    # hosts/omp). `verify-off`
    # removes that rule, so it drops this half too; `pretooluse-off` above still
    # drops the whole gate, and attribution/explore are other rules and stay
    # armed.
    if not off("verify-off"):
        if t in BASH_TOOLS:
            reason = shortcut_command(inp.get("command"))
            if reason:
                return _deny(session_id, "shortcut", reason)
        if t in WRITE_TOOLS:
            reason = shortcut_edit(inp)
            if reason:
                return _deny(session_id, "shortcut", reason)
    if t in BASH_TOOLS and attribution(inp.get("command")):
        return _deny(session_id, "attribution", ATTRIB_DENY)
    if t in WRITE_TOOLS and attribution_edit(inp):
        return _deny(session_id, "attribution", ATTRIB_DENY)
    if searched_identifier(tool, inp):
        slug = index_slug(cwd, base)
        if slug and first_nudge(session_id):
            note(session_id, "nudge", slug)
            return nudge_reason(slug)
    return None
