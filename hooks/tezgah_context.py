#!/usr/bin/env python3
"""The one place that decides what tezgah injects, independent of the host.

Each host adapter normalizes its own event names and output envelope, then
calls context_for() here; the text is identical on Claude, Codex, Cursor,
opencode, dsh and omp because it is built once. Stdlib only.
"""
import glob
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time

import tezgah_research
from tezgah_integrity import note_turn
from tezgah_policy import CONDITIONAL_KEYS, CORE, POINTERS, PROMPT_REMINDER
from tezgah_paths import (ai_research_dir, cache_dir, cbm_bin, have_consult_key,
                          off, orx_bin, root_for, roots, tool, writable_dir)

# A prompt that matches one of these arms the matching conditional rule for that
# turn only. Kept as (key, compiled regex) so the arming is one pass and the
# patterns are reviewable. Word-ish boundaries keep "deploy" from firing inside
# an identifier; Turkish hints are included because the user writes Turkish.
#
# Turkish is agglutinative and the hints are verb/noun stems, so an English-style
# trailing \b would kill the most natural phrasing (düzgün çalışsın, hipotezi
# test et): a Turkish alternation therefore carries \w* where a suffix can land,
# which \b then closes. \w is Unicode-aware, so it eats Türkçe letters. A whole
# word keeps its plain boundary, so "deney" still does not fire on "deneyim".
PROMPT_HINTS = (
    ("spec", r"\b(normal (user )?behaviou?r|clean ui|nicer|more intuitive|"
             r"professional|polish(ed)?|improve the (ui|ux)|make it (better|"
             r"usable|look)|look(s)? better|düzgün çalış\w*|güzel görün\w*|"
             r"daha iyi (ol|görün)\w*|kullanıcı dostu)\b"),
    ("consult", r"\b(architect(ure|ural)|root cause|migrat(e|ion)|deploy|"
                r"security|trade-?off|which approach|design decision|"
                r"irreversible|rollback|schema change|mimari\w*|kök neden\w*|"
                r"geri dönüşü olmayan)\b"),
    ("research", r"\b(research|literature|hypothes(is|es)|experiment(al)?|"
                 r"ablation|hyperparameter|benchmark|survey|paper|dataset|"
                 r"araştır\w*|literatür\w*|hipotez\w*|deney)\b"),
    ("cbm", r"\b(who calls|callers?|call sites?|who uses|what breaks|"
            r"blast radius|where is|where's|definition of|who invokes|"
            r"kim çağır\w*|çağrı yerleri|nerede tanımlı|nasıl bağlan\w*|"
            r"etkilenir\w*|hangi dosyalar etkilen\w*)\b"),
)

# the detached auto-index worker (lock-guarded, retrying); same dir as this file
INDEX_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "tezgah_index.py")

# filled in by context_for() once the cwd is known; {ROOT} reads it
ACTIVE_ROOT = [""]

# Each always-on rule in CORE starts with this bold label. A kill switch drops
# exactly its own paragraph from the injected text; the label is the contract,
# so tests pin every one and a label edit fails loudly instead of silently.
CORE_RULES = (
    ("exec", "**Turkish, BLUF.**"),
    ("ponytail", "**Ponytail (minimal code).**"),
    ("fidelity", "**Deliver the whole ask; never the shortcut.**"),
    ("integrity", '**Integrity: evidence, or "doğrulanmadı".**'),
    ("loop", "**Loop discipline.**"),
    ("safety", "**Irreversible or outward-facing actions need an explicit ask "
               "first.**"),
    ("scope", "**Session scope: the user's repo, not tezgah.**"),
    ("spec", "**Spec before building.**"),
    ("lessons", "**Lessons ledger: stop repeating mistakes.**"),
    ("cbm", "**Code discovery: graph first.**"),
    ("consult", "**Consult before irreversible.**"),
    ("research", "**Research: route it to OpenResearch.**"),
    ("attribution", "**No AI attribution, ever, on any host.**"),
)


def render(text, root=""):
    """Fill the path placeholders with stable, existing paths."""
    if not text:
        return text
    return (text.replace("{CONSULT_BIN}", tool("consult"))
                .replace("{CODEGEN_BIN}", tool("codegen"))
                .replace("{ORX_BIN}", orx_bin() or "orx")
                .replace("{RESEARCH_BIN}", tool("tezgah-research"))
                .replace("{AI_RESEARCH_DIR}", ai_research_dir())
                .replace("{ROOT}", root or ACTIVE_ROOT[0]
                         or "the configured tezgah roots"))


def under(path):
    return root_for(path) is not None


# one spawn per (root, args) per process: the session-start path asks for HEAD
# and the top-level twice over (repo_root, autoindex, then the status line's
# index_mark), and every hook process is short-lived, so a remembered answer
# cannot go stale within a run.
_GIT = {}


def git(root, *args):
    key = (root,) + args
    if key not in _GIT:
        try:
            out = subprocess.run(("git", "-C", root) + args, capture_output=True,
                                 text=True, timeout=5)
            _GIT[key] = out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            _GIT[key] = ""
    return _GIT[key]


def repo_root(cwd):
    """The unit of work: the git top-level under a root, else the first path
    component below the root (so a non-git project still gets one slug)."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top and under(top):
        return os.path.realpath(top)
    base = root_for(cwd)
    if not base:
        return os.path.realpath(cwd)
    rel = os.path.relpath(os.path.realpath(cwd), base)
    first = rel.split(os.sep)[0]
    if first in (".", "..", ""):
        return os.path.realpath(cwd)
    return os.path.join(base, first)


def slug(path):
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def autoindex(root):
    """Detached incremental index. Returns a one-line status for the context."""
    if root in roots():
        # a root is not a project: indexing it swallows every repo below into
        # one multi-GB graph. Sessions started there get no auto-index.
        return "not indexed: cwd is a configured tezgah root, cd into a repo"
    if os.path.exists(os.path.join(root, ".no-cbm")):
        return "indexing disabled for this repo (.no-cbm present)"
    cbm = cbm_bin()
    if not cbm:
        return "codebase-memory-mcp is not installed on this machine, so there is no graph"
    # The worker writes the codebase-memory-mcp cache. A host that sandboxes
    # hook file writes (dsh workspace-write) denies that path, so do not spawn a
    # doomed worker and report it as running: the MCP server is not sandboxed
    # and serves the graph instead.
    cbm_cache = os.environ.get("CBM_CACHE_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "codebase-memory-mcp")
    if not writable_dir(cbm_cache):
        return ("graph index not started: hook writes are sandboxed on this host, "
                "so the codebase-memory-mcp cache (%s) cannot be written from the "
                "session hook. The codebase-memory-mcp MCP server is not sandboxed "
                "and serves the graph; call index_repository for a repo it has not "
                "indexed yet" % cbm_cache)
    cache = cache_dir()
    name = slug(root)
    head = git(root, "rev-parse", "HEAD") or "nogit"
    stamp_path = os.path.join(cache, name)
    try:
        os.makedirs(os.path.join(cache, "logs"), exist_ok=True)
        with open(stamp_path) as fh:
            stamped = fh.read().strip()
    except OSError:
        stamped = ""
    if stamped == head and head != "nogit":
        return "index current (HEAD unchanged since last index)"
    # a failed worker leaves this marker; surface it and clear it once, so the
    # session learns the last index failed instead of it looping invisibly
    failure = stamp_path + ".failed"
    note = None
    if os.path.exists(failure):
        try:
            os.remove(failure)
        except OSError:
            pass
        note = "last auto-index failed (see %s/%s.log)" % (cache, name)
    try:
        log = open(os.path.join(cache, "logs", name + ".log"), "ab")
        # Spawn the lock-guarded worker rather than indexing inline. Two sessions
        # in the same repo must not index at once, and a concurrent CBM
        # generation makes the CLI refuse to start (transient); the worker holds
        # an exclusive lock for the repo and retries. It stamps HEAD only after
        # exit 0, so a failed run is retried on the next session start.
        subprocess.Popen(
            [sys.executable, INDEX_WORKER, cbm, root, head,
             stamp_path, os.path.join(cache, "locks", name + ".lock")],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, cwd=root,
        )
    except Exception as exc:
        return "auto-index could not start (%s); run index_repository manually" % exc
    verb = "re-indexing" if stamped else "indexing (first time)"
    if note:
        return "%s; %s in background now" % (note, verb)
    return "%s in background now" % verb


def sync_agents(root):
    """Generate/refresh this repo's per-host subagent definitions (best effort)."""
    try:
        from tezgah_agents import sync_root
        return sync_root(root)
    except Exception:
        return None


def open_plans(root):
    """Max 3 open plans (plans/open/*.md, lowest id first) as a context block, or ""."""
    paths = sorted(glob.glob(os.path.join(root, "plans", "open", "*.md")))
    lines = []
    for path in paths[:3]:
        try:
            with open(path) as fh:
                text = fh.read().splitlines()
        except OSError:
            continue
        pid, title, nxt, fences, in_next = "", "", "", 0, False
        for line in text:
            if line.strip() == "---":
                fences += 1
                continue
            if fences < 2:
                key, _, val = line.partition(":")
                if key.strip() == "id":
                    pid = val.strip()
                elif key.strip() == "title":
                    title = val.strip()
            elif line.startswith("## "):
                in_next = line.strip() == "## Next"
            elif in_next and line.strip() and not nxt:
                nxt = line.strip()[:80]
        lines.append("- %s %s -> %s" % (pid, title, nxt))
    if not lines:
        return ""
    if len(paths) > 3:
        lines.append("(+%d more)" % (len(paths) - 3))
    return ("## Open plans in this repo (plans/open)\n%s\n"
            "Run the plan-status skill for the full table before starting work; "
            "open plan work happens on its `plan/NNN-slug` branch." % "\n".join(lines))


def _lesson_lines(root):
    """The lesson lines as injected: one per line, markdown bullets stripped.

    One reader for the injected block and for the per-turn stamp, so the digest
    can only move when the text the model was shown moves."""
    try:
        with open(os.path.join(root, ".tezgah", "lessons.md")) as fh:
            raw = fh.read().splitlines()
    except OSError:
        return []
    out = []
    for ln in raw:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        # a ledger written with markdown bullets must not render as "- - ..."
        out.append(re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", s))
    return out


def lessons(root):
    """The most recent lessons from .tezgah/lessons.md as a context block, or "".

    One lesson per line, most recent last. Only the last MAX are injected so the
    block stays bounded no matter how long the ledger grows; blank lines and
    `#` headings are skipped so the file can carry a human header."""
    max_lines = 5
    lines = _lesson_lines(root)
    if not lines:
        return ""
    recent = lines[-max_lines:]
    more = ("\n(+%d older, see .tezgah/lessons.md)" % (len(lines) - len(recent))
            if len(lines) > len(recent) else "")
    return ("## Lessons from past mistakes in this repo (.tezgah/lessons.md)\n"
            + "\n".join("- " + ln[:200] for ln in recent) + more + "\n"
            "These are standing constraints: check the spec and the change "
            "against each line before you finish.")


# --- the per-turn state stamp: what moved since the last turn ---------------
# The standing constraints ride every turn (PROMPT_REMINDER) and a long one gets
# a re-statement; what no surface could say is which fact moved. So the state the
# blocks are built from gets a small comparable stamp - HEAD, the open-plan
# filenames, a digest of the lesson lines as injected - written once per turn,
# and the next turn pays one line naming the difference instead of re-reading the
# whole re-statement. A stamp that cannot be compared is not an error: the turn
# falls back to the full re-statement it always carried.


def _plan_ids(root):
    """The open-plan filenames, sorted: the comparable half of the plans block."""
    return sorted(os.path.basename(p) for p in
                  glob.glob(os.path.join(root, "plans", "open", "*.md")))


def _lessons_state(root):
    """(count, digest) over the injected lesson lines; (0, "-") with no ledger."""
    lines = _lesson_lines(root)
    if not lines:
        return [0, "-"]
    return [len(lines),
            hashlib.sha1("\n".join(lines).encode()).hexdigest()[:8]]


def state_stamp(root):
    """The comparable state of the repo this turn is about."""
    return {"head": git(root, "rev-parse", "HEAD") or "nogit",
            "plans": _plan_ids(root),
            "lessons": _lessons_state(root)}


def _stamp_path(session_id):
    return os.path.join(cache_dir(), "turns", slug(str(session_id)) + ".json")


def read_stamp(session_id):
    """The stamp this session's previous turn wrote, or None when there is none."""
    if not session_id:
        return None
    try:
        with open(_stamp_path(session_id)) as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("root") else None


def write_stamp(session_id, root, stamp):
    """Remember this turn's stamp. Best effort: a host may sandbox hook writes."""
    if not session_id:
        return
    try:
        os.makedirs(os.path.join(cache_dir(), "turns"), exist_ok=True)
        with open(_stamp_path(session_id), "w") as fh:
            json.dump(dict(stamp, root=root), fh)
    except OSError:
        pass


def state_delta(root, previous, stamp=None):
    """One line naming what moved into this turn, or "" when nothing is
    comparable: no previous stamp, a stamp taken in another repo, or no change.

    The delta half of C1. The full re-statement is the fallback, and it stays
    cheap because this is what the model was missing from it."""
    if not isinstance(previous, dict) or previous.get("root") != root:
        return ""
    now = stamp if stamp is not None else state_stamp(root)
    moved = []
    was_head = str(previous.get("head") or "-")
    if was_head != str(now["head"]):
        moved.append("HEAD %s -> %s" % (was_head[:7], str(now["head"])[:7]))
    was_plans = list(previous.get("plans") or [])
    if was_plans != now["plans"]:
        added = [p for p in now["plans"] if p not in was_plans]
        gone = [p for p in was_plans if p not in now["plans"]]
        moved.append("open plans %d -> %d%s%s" % (
            len(was_plans), len(now["plans"]),
            " (+%s)" % ", ".join(added[:3]) if added else "",
            " (-%s)" % ", ".join(gone[:3]) if gone else ""))
    was_lessons = list(previous.get("lessons") or [0, "-"])
    if was_lessons != now["lessons"]:
        note = ("" if was_lessons[0] != now["lessons"][0] else
                " (an older line changed: digest %s -> %s)"
                % (was_lessons[1], now["lessons"][1]))
        moved.append("lessons %s -> %s%s"
                     % (was_lessons[0], now["lessons"][0], note))
    if not moved:
        return ""
    return ("State since your last turn: " + "; ".join(moved)
            + ". Re-read the file before relying on an old value.")


def constraint_notice(cwd, session_id):
    """The text a long turn's drift notice should carry.

    The delta when this session has a stamp comparable to the turn it is in (the
    state moved since the turn began, which is the one thing a re-statement
    cannot say), else the full re-statement of the standing constraints - the
    gate's own `constraints_line`, unchanged, so there is one copy of that text.

    Wiring, and it is one line: `tezgah_gate.drift_reason` calls
    `constraints_line(cwd)` today; its replacement is
    `constraint_notice(cwd, session_id)`."""
    line = state_delta(repo_root(cwd), read_stamp(session_id))
    if line:
        return line
    from tezgah_gate import constraints_line  # lazy: the fallback's own text
    return constraints_line(cwd)


def classify_prompt(text):
    """The conditional rule keys a prompt arms, from the shared hint table."""
    low = (text or "").lower()
    return {key for key, pattern in PROMPT_HINTS if re.search(pattern, low)}


def prompt_text(payload):
    """Best-effort extraction of the user's prompt from a host payload."""
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    for key in ("prompt", "user_prompt", "message", "text", "input", "command"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def audit_classification(matched, length):
    """One line per user prompt: which conditional rules were armed, and the
    prompt length. No prompt text is stored. A missed keyword is silent by
    nature, so this log is the only way to audit false negatives later; it is
    truncated to the last 200 lines once it passes 64 KB."""
    path = os.path.join(cache_dir(), "classify.log")
    try:
        with open(path, "a") as fh:
            fh.write("%d armed=%s chars=%d\n"
                     % (int(time.time()), ",".join(sorted(matched)) or "none",
                        length))
        if os.path.getsize(path) > 65536:
            with open(path) as fh:
                tail = fh.readlines()[-200:]
            with open(path, "w") as fh:
                fh.writelines(tail)
    except OSError:
        pass


def core_split(cwd):
    """(always-on text, {key: paragraph}, disabled) after kill-switch filtering.

    The conditional paragraphs (tezgah_policy.CONDITIONAL_KEYS) come back
    separately so a host can arm them for the one prompt whose task class
    matches, instead of paying their text every session."""
    _, marks = repo_marks(cwd)
    drop, disabled = set(), []
    if off("exec-mode.off"):
        drop.add("exec")
        disabled.append("exec-mode.off")
    if off("ponytail-auto.off") or ".no-ponytail" in marks:
        drop.add("ponytail")
        disabled.append("ponytail-auto.off" if off("ponytail-auto.off")
                        else ".no-ponytail")
    if off("spec-off"):
        drop.add("spec")
        disabled.append("spec-off")
    if off("verify-off"):
        drop.add("integrity")
        disabled.append("verify-off")
    if ".no-lessons" in marks:
        drop.add("lessons")
        disabled.append(".no-lessons")
    if off("consult-off"):
        drop.add("consult")
        disabled.append("consult-off")
    if off("research-off"):
        drop.add("research")
        disabled.append("research-off")
    if off("orchestrate-off"):
        disabled.append("orchestrate-off")
    if ".no-cbm" in marks:
        drop.add("cbm")
        disabled.append(".no-cbm")
    always, conditional = [], {}
    for paragraph in CORE.split("\n\n"):
        key = next((k for k, label in CORE_RULES if paragraph.startswith(label)),
                   None)
        if key in drop:
            continue
        if key in CONDITIONAL_KEYS:
            conditional[key] = paragraph
        else:
            always.append(paragraph)
    return "\n\n".join(always), conditional, disabled


def core_for(cwd):
    """The always-on CORE (conditional paragraphs removed) plus the pointer line.

    A kill switch that only flips a status mark is not a switch: the rule it
    names must also leave the text the model reads. Returns (text, disabled)."""
    always, _conditional, disabled = core_split(cwd)
    return always.strip() + "\n\n" + POINTERS.strip(), disabled


def always_on_core():
    """CORE minus the conditional paragraphs, plus the pointer line.

    No repo marks are consulted: this is the text a host writes to a static
    always-on file (opencode's contract), so it must be repo-independent."""
    always = [p for p in CORE.split("\n\n")
              if next((k for k, label in CORE_RULES if p.startswith(label)), None)
              not in CONDITIONAL_KEYS]
    return "\n\n".join(always).strip() + "\n\n" + POINTERS.strip()


def subagent_core(core=None):
    """The invariants as a labelled brief, for a delegated agent.

    A subagent is a fresh context that must know every rule exists, but it does
    not need the long-form rationale the main thread pays for once: each rule
    keeps its bold label and its opening clause, and the full text stays one hop
    away in the `tezgah-contract` skill. The brief is built from CORE_RULES, so
    it can neither drop a rule nor invent one, and a test asserts exactly that."""
    text = core or always_on_core()
    paragraphs = {}
    for block in text.split("\n\n"):
        if block.startswith("**") and "**" in block[2:]:
            paragraphs[block.split("**")[1]] = block
    short = []
    for key, label in CORE_RULES:
        if key in CONDITIONAL_KEYS:
            continue
        block = paragraphs.get(label.strip("*"))
        if block is None:
            continue
        body = block.split("**", 2)[2].strip()
        first = body.split(". ", 1)[0].strip()
        if first and not first.endswith((".", ":")):
            first += "."
        short.append("%s %s" % (label, first) if first else label)
    return ("**Contract.** Full text in the `tezgah-contract` skill; the rules "
            "below are the short form and all of them are in force.\n\n"
            + "\n".join(short))


def session_of(payload):
    """The session id a prompt payload carries, under whichever name the host
    uses.

    This is what keys the turn marker, so it has to be the same string the host
    hands its PreToolUse hook - otherwise the marker lands in a different ledger
    and resets nothing. Cursor's adapter reads `conversation_id` first and falls
    back, so the order is the same here; Claude, Codex and omp send only
    `session_id`, which the fallback covers."""
    p = payload if isinstance(payload, dict) else {}
    return (p.get("conversation_id") or p.get("session_id")
            or p.get("parent_conversation_id"))


# --- the byte budget: bloat as a measured decision ---------------------------
# Every block below is individually capped (lessons 5, plans 3), but the sum was
# bounded by nothing and no decision about it was recorded, so growth showed up
# as a feeling. Each budget sits at ~1.5x the largest text that event was
# measured to build in this repository - session_start 7830 B, post_compact
# 7830 B, subagent_start 2436 B, user_prompt 4004 B with all four conditional
# rules armed - so it never fires on a healthy repo and always fires before a
# pathological one (a lessons ledger or an armed set that grew past its cap)
# reaches the model. A budget in bytes, not tokens: this file has no tokenizer
# and a wrong estimate would be worse than a bound.
CONTEXT_BUDGET = {"session_start": 12000, "post_compact": 12000,
                  "subagent_start": 4000, "user_prompt": 6000}
DEFAULT_BUDGET = 12000
# The blocks in the order they are given up when the budget is exceeded, lowest
# value first: text another surface already carries (the plan table lives in the
# plan-status skill, the lessons file is on disk, the generated-subagent note is
# a one-time fact), then the tooling-availability lines, then the live state
# lines, the delta, and the skill pointer last. A key absent from this tuple is
# never dropped: the always-on core and the per-turn reminder ARE the rules, and
# a budget that can spend them turns bloat into rule loss.
DROP_ORDER = ("lessons", "plans", "subagents", "consult", "research",
              "research_broken", "graph", "offnote", "orchestrate", "index",
              "delta", "pointer")


def _drop_note(event, limit, dropped, size):
    """One line naming what the budget gave up, and the order it went in: a drop
    is a decision, so the turn carries it instead of losing it in silence. When
    even that was not enough the note says so and who is left, rather than
    reporting a trim that never reached the limit."""
    note = ("(Context budget for %s: dropped %s - lowest value first; the "
            "dropped text is still on disk and this drop is logged to %s"
            % (event, ", ".join("%s (%d B)" % d for d in dropped),
               os.path.join(cache_dir(), "context-drops.log")))
    if size > limit:
        note += ("; still %d B against the %d B budget, because what remains is "
                 "the always-on core and that is never dropped" % (size, limit))
    return note + ")"


def log_drop(event, limit, dropped):
    """Record the budget decision: what went, from what, at what size. Truncated
    the way classify.log is, so the log cannot grow without bound itself."""
    path = os.path.join(cache_dir(), "context-drops.log")
    try:
        with open(path, "a") as fh:
            fh.write("%d event=%s limit=%d dropped=%s\n"
                     % (int(time.time()), event, limit,
                        ",".join("%s:%d" % d for d in dropped)))
        if os.path.getsize(path) > 65536:
            with open(path) as fh:
                tail = fh.readlines()[-200:]
            with open(path, "w") as fh:
                fh.writelines(tail)
    except OSError:
        pass


def budgeted(event, parts):
    """Join this event's (key, text) blocks under the event's byte budget.

    Over budget, whole blocks are given up in DROP_ORDER (lowest value first)
    until the blocks fit. The note that says what went is appended after that
    count rather than inside it: it exists only when a drop happened, and the
    sentence explaining a trim must not be able to force another one - so a
    trimmed turn returns at most `limit` bytes of blocks plus the ~250 B note.
    `parts` is consumed; callers build it for one event. Every droppable key gone
    and the blocks still over (the protected core alone is bigger than the limit)
    is reported by the note, not hidden."""
    limit = CONTEXT_BUDGET.get(event, DEFAULT_BUDGET)
    dropped = []

    def content():
        return "\n\n".join(t for _key, t in parts if t)

    for key in DROP_ORDER:
        if len(content().encode()) <= limit:
            break
        for i, (k, text) in enumerate(parts):
            if k == key and text:
                dropped.append((k, len(text.encode())))
                del parts[i]
                break
    text = content()
    if not dropped:
        return text
    log_drop(event, limit, dropped)
    return text + "\n" + _drop_note(event, limit, dropped, len(text.encode()))


def context_for(event, cwd, payload=None, with_core=True):
    """The context block for a normalized event, or None when out of scope.

    event: session_start | user_prompt | subagent_start | post_compact

    with_core=False drops the always-on core and leaves only the live state.
    It is for a host whose always-on file already carries `always_on_core()` -
    omp's managed RULES.md - so its session hook does not pay for the contract
    twice; the rest of the text (index, plans, lessons, kill switches) is the
    part no static file can know.
    """
    if not under(cwd):
        return None
    root = repo_root(cwd)
    ACTIVE_ROOT[0] = root_for(cwd) or ""
    core, disabled = core_for(cwd)
    # A disabled rule is also removed from the on-demand skill's reach, because
    # the skill is loaded separately and would otherwise re-enable it.
    off_note = ("Kill switches active this session: %s. Those rules are OFF; "
                "ignore the matching section in the `tezgah-contract` skill."
                % ", ".join(disabled)) if disabled else ""
    if event == "user_prompt":
        # One marker per user turn, written before the reminder check: the loop
        # guard counts an identical call's failures in the current turn only, so
        # a repeat the user asked for again is a fresh attempt, and that reset is
        # guard state rather than part of the reminder. Only a hash of the prompt
        # is stored - note_turn keys the row on it so one submission cannot write
        # two markers and hide the failures the guard had just counted.
        prompt = prompt_text(payload)
        session_id = session_of(payload)
        note_turn(session_id, prompt, workspace=root_for(cwd))
        # per-turn nudge: openers decay over long sessions. Kept short because
        # it is paid every turn, and on Claude the output style already carries
        # the same rules on every response. The conditional rules ride along
        # only on the turn whose prompt matches their task class.
        if off("reminder-off"):
            return None
        parts = [("reminder", render(PROMPT_REMINDER.strip()))]
        if prompt:
            _always, conditional, _dis = core_split(cwd)
            matched = classify_prompt(prompt)
            armed = [conditional[k] for k in CONDITIONAL_KEYS
                     if k in conditional and k in matched]
            audit_classification(matched, len(prompt))
            if armed:
                parts.append(("armed", render("\n\n".join(armed))))
        else:
            audit_classification(set(), 0)
        # C1 and C3 ride this turn because it is the only channel a live state
        # fact has on a per-prompt hook: the delta names what moved since the
        # session's previous turn (the full re-statement is the fallback, see
        # state_delta/constraint_notice), and the glance says whether the graph
        # is behind that move - a comparison that used to end in a status glyph
        # the model never reads.
        stamp = state_stamp(root)
        delta = state_delta(root, read_stamp(session_id), stamp)
        write_stamp(session_id, root, stamp)
        if delta:
            parts.append(("delta", delta))
        stale = index_notice(cwd)
        if stale:
            parts.append(("index", stale))
        if disabled:
            parts.append(("offnote", "(off this session: %s)"
                          % ", ".join(disabled)))
        return budgeted(event, parts)

    # session_start / post_compact / subagent_start: the compact always-on core
    # plus live index/consult state. The deep orchestration/exec detail moved
    # out of the every-session payload into the tezgah-contract skill, which
    # the last line tells the model to load on demand.
    parts = ([("brief", subagent_core(core))] if event == "subagent_start"
             else [("core", core)]) if with_core else []
    _, marks = repo_marks(cwd)
    if ".no-cbm" in marks:
        parts.append(("graph", "Graph: disabled for this repo (.no-cbm), so use "
                               "grep/find and say the answer came from text "
                               "search."))
    elif cbm_bin():
        # SubagentStart fires once per delegated agent: a fan-out would race
        # indexers on the same repo, so only the parent session triggers one.
        status = (autoindex(root) if event != "subagent_start"
                  else "index handled by the parent session")
        parts.append(("graph", "Graph index: %s (project %s)."
                      % (status, slug(root))))
    else:
        parts.append(("graph", "Graph: codebase-memory-mcp is not installed, so "
                               "use grep/find and say the answer came from text "
                               "search; never claim the index answered."))
    if not off("consult-off") and not have_consult_key():
        parts.append(("consult",
                      "Consult: no provider key (OpenRouter or DeepSeek), so the "
                      "second opinion cannot run; on a call that needed it, say "
                      "it was skipped and why."))
    if not off("research-off") and not orx_bin():
        parts.append(("research",
                      "Research: orx (OpenResearch) is not installed, so route "
                      "research to a host subagent and say the tooling is "
                      "unavailable; do not improvise its protocol."))
    if event == "session_start":
        note = sync_agents(root)
        if note:
            parts.append(("subagents",
                          "Subagents (this repo, generated): %s" % note))
    if event in ("session_start", "post_compact"):
        plans = open_plans(root)
        if plans:
            parts.append(("plans", plans))
        if ".no-lessons" not in marks:
            past = lessons(root)
            if past:
                parts.append(("lessons", past))
        broken = tezgah_research.failing(root) if not off("research-off") else []
        if broken:
            line_slug, err = broken[0]
            parts.append(("research_broken",
                          "Research: %s has %d problem(s), first: %s - run "
                          "`%s check` before reporting a result"
                          % (line_slug, len(broken), err,
                             tool("tezgah-research"))))
    if disabled:
        parts.append(("offnote", off_note))
        if "orchestrate-off" in disabled:
            parts.append(("orchestrate",
                          "Orchestration is off (orchestrate-off): do not "
                          "delegate to subagents; do the work in this thread."))
    if event == "subagent_start":
        parts.append(("pointer",
                      "You are a subagent: execute the briefing and report "
                      "evidence back to the router; do not orchestrate or spawn "
                      "subagents. Full rules: the `tezgah-contract` skill."))
    else:
        parts.append(("pointer",
                      "Deep orchestration, codegen, consult detail and the exact "
                      "kill switches: load the `tezgah-contract` skill."))
    return budgeted(event, [(key, render(text.strip())) for key, text in parts])


# A tool name that only appears as an ARGUMENT is not a use of that tool: the
# status line used to turn `consult✓` green for `grep -n consult hooks/`. So a
# shell line is tokenized and only its command positions are read - which means
# the words that stand between the shell and the program have to be understood:
# a wrapper (`sudo env X=1 consult q`), a keyword (`if consult q`), a wrapper's
# own argument (`timeout 30 consult q`), a shell running a command string
# (`bash -c 'consult q'`) and a heredoc body (data, not commands). A line it
# cannot parse contributes nothing - under-reporting beats claiming a tool ran.
_SHELL_WRAPPERS = frozenset((
    "sudo", "env", "nohup", "time", "timeout", "command", "exec", "xargs",
    "bash", "sh", "zsh", "dash", "ksh",
))
_SHELL_KEYWORDS = frozenset(("if", "elif", "while", "until", "then", "do", "!",
                             "{", "}"))
# whose own argument is positional, so the word after it is still not the
# program: `timeout 30 consult q`
_WRAPPER_ARG = frozenset(("timeout",))
# options carrying a value, so the word after them is the option's argument and
# not the program: `sudo -u root consult q`
_OPTION_ARG = frozenset(("-u", "-g", "-k", "-o", "-C", "-h", "-T", "-r", "-t",
                         "--user", "--group", "--prompt", "--chdir"))
_SHELL_SEPARATORS = (";", "&&", "||", "|", "&", "(", ")", "<", ">", ">>")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# A heredoc opener. The delimiter has to look like a word, so arithmetic such as
# `$((1<<2))` is not mistaken for one.
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def shell_programs(command, _depth=0):
    """Every word a shell line would run as a program, in order."""
    out = []
    lines = str(command or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        opener = _HEREDOC.search(line)
        if opener:
            # the body is data, not commands: skip to the delimiter line
            while i < len(lines) and lines[i].strip() != opener.group(2):
                i += 1
            i += 1
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=";&|()<>")
            lex.whitespace_split = True
            words = list(lex)
        except ValueError:
            continue
        out += _command_words(words, _depth)
    return out


def _command_words(words, depth):
    """The command positions of one tokenized shell line."""
    out = []
    want = True
    skip = 0
    shell_c = False
    for word in words:
        if word in _SHELL_SEPARATORS:
            want, skip, shell_c = True, 0, False
            continue
        if not want:
            continue
        if skip and not word.startswith("-"):
            skip -= 1
            continue
        if word.startswith("-"):
            skip = 1 if word in _OPTION_ARG else 0
            # `bash -c '<line>'` runs that line, so it is a command line of its
            # own and not an argument
            shell_c = word == "-c"
            continue
        if word in _SHELL_WRAPPERS:
            skip = 1 if word in _WRAPPER_ARG else 0
            shell_c = False
            continue
        if word in _SHELL_KEYWORDS or _ASSIGNMENT.match(word):
            continue
        if shell_c and depth < 2:
            out += shell_programs(word, depth + 1)
            want, shell_c = False, False
            continue
        out.append(os.path.basename(word))
        want = False
    return out


def shell_kind(command):
    """The used-tool kind a shell command really ran: consult, research or None."""
    ran = shell_programs(command)
    if "consult" in ran:
        return "consult"
    if "orx" in ran:
        return "research"
    return None


def command_text(raw):
    """The shell command a tool input carries, or "" when it carries none."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("command", "cmd"):
            if isinstance(raw.get(key), str):
                return raw[key]
    return ""


def record(session_id, kind):
    """Append a used-tool kind for the status line (any host, best effort).

    A missing kind is not an event: the hosts classify every tool and most
    tools are not one of ours, so writing those would fill the ledger with
    no-ops (a real session: 395 null lines against 30 kinds) and make every
    later read walk them.
    """
    if not session_id or not kind:
        return
    try:
        d = os.path.join(cache_dir(), "sessions")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, slug(session_id) + ".jsonl"), "a") as fh:
            fh.write(json.dumps({"kind": kind}) + "\n")
    except OSError:
        pass


def used(session_id):
    if not session_id:
        return set()
    out = set()
    try:
        with open(os.path.join(cache_dir(), "sessions",
                               slug(session_id) + ".jsonl")) as fh:
            for line in fh:
                try:
                    out.add(json.loads(line)["kind"])
                except (ValueError, KeyError):
                    pass
    except OSError:
        pass
    return out


def repo_marks(cwd):
    """The per-repo opt-out flags (.no-ponytail/.no-cbm/.no-lessons) walking up
    to the enclosing root, and that root. Outside every root: empty set, None."""
    marks = set()
    base = root_for(cwd)
    p = os.path.realpath(cwd)
    while base and p.startswith(base):
        for f in (".no-ponytail", ".no-cbm", ".no-lessons"):
            if os.path.exists(os.path.join(p, f)):
                marks.add(f)
        if p == base:
            break
        p = os.path.dirname(p)
    return base, marks


# the idx mark is a cosmetic line: remember its answer per process
_IDX = {}


def index_mark(cwd, base):
    """Code-graph readiness for the enclosing repo.

    ✓ indexed, ↻ indexed but HEAD moved since the stamp, ✗ not indexed yet,
    – not applicable (outside a root, codebase-memory-mcp absent, or .no-cbm).
    Remembered per (cwd, base) for the life of the process: the comparison costs
    two git forks, and a long hook process that renders the line twice would pay
    them twice for the same answer."""
    key = (cwd, base)
    if key not in _IDX:
        _IDX[key] = _index_mark(cwd, base)
    return _IDX[key]


def _index_mark(cwd, base):
    if not base or not cbm_bin():
        return "–"
    p = os.path.realpath(cwd)
    while p.startswith(base):
        if os.path.exists(os.path.join(p, ".no-cbm")):
            return "–"
        if p == base:
            break
        p = os.path.dirname(p)
    from tezgah_gate import index_slug  # lazy: keep hook import cost minimal
    slug = index_slug(cwd, base)
    if not slug:
        return "✗"
    try:
        head = git(repo_root(cwd), "rev-parse", "HEAD")
        with open(os.path.join(cache_dir(), slug)) as fh:
            stamped = fh.read().strip()
        if head and stamped and stamped != head:
            return "↻"
    except OSError:
        pass
    return "✓"


def index_notice(cwd):
    """One line when the graph's stamp is behind HEAD, else "".

    The comparison already existed and ended in a status glyph (`index_mark` ->
    "↻"), which is a surface the model does not read, so the turn that decides
    from the graph was told nothing. Same comparison, moved onto the turn.
    Reuses index_mark: the HEAD fork it guards is already cached for the process,
    so a turn that renders both pays for one. A session start already says this
    in its own graph line, so this is the mid-session turn's copy."""
    base, _marks = repo_marks(cwd)
    if not base or index_mark(cwd, base) != "\u21bb":
        return ""
    from tezgah_gate import index_slug  # lazy: keep hook import cost minimal
    slug = index_slug(cwd, base)
    try:
        with open(os.path.join(cache_dir(), slug)) as fh:
            stamped = fh.read().strip()
    except OSError:
        return ""
    head = git(repo_root(cwd), "rev-parse", "HEAD")
    if not head or not stamped:
        return ""
    return ("Graph index: the graph is indexed at %s, HEAD is %s - the index is "
            "behind, so a graph answer may describe code that has moved since. "
            "Re-index before trusting one, or say the answer came from text "
            "search." % (stamped[:7], head[:7]))


def plan_mark(cwd, base):
    """`plans N` (+ `(M blk)`) for the enclosing repo, or None."""
    if not base:
        return None
    p = os.path.realpath(cwd)
    while p.startswith(base):
        plans = glob.glob(os.path.join(p, "plans", "open", "*.md"))
        if plans:
            blocked = 0
            for f in plans:
                try:
                    with open(f) as fh:
                        blocked += "status: blocked" in fh.read(400)
                except OSError:
                    pass
            return "plans %d" % len(plans) + (" (%d blk)" % blocked if blocked else "")
        if p == base:
            break
        p = os.path.dirname(p)
    return None


# The marks read in groups, "  ·  " between them: the two always-on switches,
# the on-demand capabilities, then the per-repo facts (idx, and the plan count
# as its own). The group rides each segment so a renderer that builds its own
# line from --json (opencode's TUI plugin, dsh's Web status line) separates them
# the same way instead of keeping a second copy of the partition.
_GROUP = {"pony": 0, "exec": 0, "consult": 1, "research": 1, "cbm": 1, "orch": 1}
GLYPHS = {"on": "✓", "ready": "○", "off": "✗", "info": ""}
# ANSI foreground for each state: green in force, yellow on-demand, red off,
# dim for a mark that carries no state (idx n/a, the plan count).
COLORS = {"on": "\033[32m", "ready": "\033[33m", "off": "\033[31m", "info": "\033[2m"}
DIM = "\033[2m"
RESET = "\033[0m"
IDX_STATE = {"✓": "on", "↻": "ready", "✗": "off", "–": "info"}
LEGEND = """\
tezgah status marks (state first, glyph after the name; the whole name+glyph is
colored, and the glyph carries the state on its own where color does not):
  name\u2713  green   armed and in force this session (or always-on)
  name\u25cb  yellow  armed, on demand - not used yet this session
  name\u2717  red     turned off by a kill switch or a per-repo .no-* mark
  dim               no state to report: idx n/a, or no blocked plan
  idx\u2713 indexed   idx\u21bb stale (HEAD moved)   idx\u2717 not indexed   idx\u2013 n/a
  plans N (M blk)   open plans under the repo, M of them blocked
Outside a tezgah root the per-repo extras (idx, plans) are omitted.
"""


def health_segments(cwd, session_id=None, used_override=None, idx_override=None):
    """The armed/used checklist as structured segments, host-neutral.

    Each segment is {"key", "state", "glyph", "text", "group"} with state in
    {on, ready, off, info}; `text` is the human name and `glyph` the mark. Hosts
    that can color (Claude/Cursor ANSI, opencode TUI, dsh Web, omp's widget
    path) map `state` to a color; hosts that cannot (Codex systemMessage, omp's
    setStatus) render text+glyph plain. `health_lines()` renders this to the
    exact plain string for the rest. `group` is the separator's own datum (see
    _GROUP): a renderer that builds its line from this JSON inserts "  ·  "
    between groups and one space inside one, so it matches `health_lines()`
    without keeping a second copy of the partition.

    Global, not root-scoped: tezgah ships as a globally loaded instructions file
    on opencode, so the indicator must not go silent off-root; the per-repo
    additions (idx, plans) appear only inside a root.

    used_override: the tool kinds a host already resolved from its own record
    (Claude parses the transcript because it does not write tezgah's recorder);
    None falls back to tezgah's recorder for session_id.

    idx_override: an idx glyph the host already resolved (one of "✓↻✗–"), for a
    redraw that must not fork git for a cosmetic line - omp re-renders on every
    turn_end and tool_result. None probes as before; the other marks stay live."""
    base, marks = repo_marks(cwd)
    seen = set(used_override) if used_override is not None else used(session_id)
    flags = [
        ("pony", not off("ponytail-auto.off") and ".no-ponytail" not in marks, None),
        ("exec", not off("exec-mode.off"), None),
        ("consult", not off("consult-off") and have_consult_key(), "consult"),
        ("research", not off("research-off") and bool(orx_bin()), "research"),
        ("cbm", ".no-cbm" not in marks, "cbm"),
        ("orch", not off("orchestrate-off"), "orch"),
    ]
    segs = []
    for name, on, meas in flags:
        if not on:
            state = "off"
        elif meas is None or meas in seen:
            state = "on"
        else:
            state = "ready"
        segs.append({"key": name, "state": state, "glyph": GLYPHS[state],
                     "text": name, "group": _GROUP[name]})
    if base:
        glyph = (idx_override if idx_override is not None
                 else index_mark(cwd, base))
        segs.append({"key": "idx", "state": IDX_STATE.get(glyph, "info"),
                     "glyph": glyph, "text": "idx", "group": 2})
        plan = plan_mark(cwd, base)
        if plan:
            segs.append({"key": "plans", "state": "ready" if "blk" in plan else "info",
                         "glyph": "", "text": plan, "group": 3})
    return segs


def color_default():
    """Whether the environment allows ANSI: NO_COLOR or TEZGAH_STATUS_COLOR=0
    opts out. One place, so every surface drops color for the same reason."""
    return (os.environ.get("NO_COLOR") is None
            and os.environ.get("TEZGAH_STATUS_COLOR") != "0")


def _seg_text(seg, color):
    """One mark as a chip, colored by state.

    The whole name+glyph is colored, not the glyph alone, so the line reads at a
    glance the way omp's own footer does. The glyph stays either way: the state
    is never carried by color only (WCAG 1.4.1)."""
    chip = seg["text"] + seg["glyph"]
    if not color or not chip:
        return chip
    return COLORS[seg["state"]] + chip + RESET


def render_line(segs, color=False):
    """Render segments to the one-line status string; `color` adds ANSI."""
    sep = (DIM + "  \u00b7  " + RESET) if color else "  \u00b7  "
    groups = {}
    for seg in segs:
        groups.setdefault(seg.get("group", 0), []).append(_seg_text(seg, color))
    return sep.join(" ".join(chips) for _, chips in sorted(groups.items()))


def health_lines(cwd, session_id=None, used_override=None, color=False,
                 idx_override=None):
    """The armed/used checklist, one line, plain text unless `color` is asked
    for.

    A host whose surface renders ANSI (Claude/Cursor status line, omp's widget
    path) passes color=True; a host that sanitizes it (omp's setStatus, Codex's
    systemMessage) or a pipe stays plain - the marks are then uncolored, never
    wrong. `idx_override` is health_segments': a host redrawing a cosmetic line
    passes the glyph it already resolved and forks no git."""
    return render_line(health_segments(cwd, session_id, used_override,
                                       idx_override=idx_override), color=color)

