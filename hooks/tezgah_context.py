#!/usr/bin/env python3
"""The one place that decides what tezgah injects, independent of the host.

Each host adapter normalizes its own event names and output envelope, then
calls context_for() here; the text is identical on Claude, Codex, Cursor,
opencode, dsh and omp because it is built once. Stdlib only.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

from tezgah_policy import CONDITIONAL_KEYS, CORE, POINTERS, PROMPT_REMINDER
from tezgah_paths import (cache_dir, cbm_bin, have_consult_key, off,
                          orx_bin, root_for, roots, tool, writable_dir)

# A prompt that matches one of these arms the matching conditional rule for that
# turn only. Kept as (key, compiled regex) so the arming is one pass and the
# patterns are reviewable. Word-ish boundaries keep "deploy" from firing inside
# an identifier; Turkish hints are included because the user writes Turkish.
PROMPT_HINTS = (
    ("spec", r"\b(normal (user )?behaviou?r|clean ui|nicer|more intuitive|"
             r"professional|polish(ed)?|improve the (ui|ux)|make it (better|"
             r"usable|look)|look(s)? better|düzgün çalış|güzel görün|"
             r"daha iyi (ol|görün)|kullanıcı dostu)\b"),
    ("consult", r"\b(architect(ure|ural)|root cause|migrat(e|ion)|deploy|"
                r"security|trade-?off|which approach|design decision|"
                r"irreversible|rollback|schema change|mimari|kök neden|"
                r"geri dönüşü olmayan)\b"),
    ("research", r"\b(research|literature|hypothes(is|es)|experiment(al)?|"
                 r"ablation|hyperparameter|benchmark|survey|paper|dataset|"
                 r"araştır|literatür|hipotez|deney)\b"),
    ("cbm", r"\b(who calls|callers?|call sites?|who uses|what breaks|"
            r"blast radius|where is|where's|definition of|who invokes|"
            r"kim çağır|çağrı yerleri|nerede tanımlı|na(?:sıl|sıl) bağlan|"
            r"etkilenir|hangi dosyalar etkilen)\b"),
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
                .replace("{ROOT}", root or ACTIVE_ROOT[0]
                         or "the configured tezgah roots"))


def under(path):
    return root_for(path) is not None


def git(root, *args):
    try:
        out = subprocess.run(("git", "-C", root) + args, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


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


def lessons(root):
    """The most recent lessons from .tezgah/lessons.md as a context block, or "".

    One lesson per line, most recent last. Only the last MAX are injected so the
    block stays bounded no matter how long the ledger grows; blank lines and
    `#` headings are skipped so the file can carry a human header."""
    max_lines = 5
    try:
        with open(os.path.join(root, ".tezgah", "lessons.md")) as fh:
            raw = fh.read().splitlines()
    except OSError:
        return ""
    lines = []
    for ln in raw:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        # a ledger written with markdown bullets must not render as "- - ..."
        lines.append(re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", s))
    if not lines:
        return ""
    recent = lines[-max_lines:]
    more = ("\n(+%d older, see .tezgah/lessons.md)" % (len(lines) - len(recent))
            if len(lines) > len(recent) else "")
    return ("## Lessons from past mistakes in this repo (.tezgah/lessons.md)\n"
            + "\n".join("- " + ln[:200] for ln in recent) + more + "\n"
            "These are standing constraints: check the spec and the change "
            "against each line before you finish.")


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


def context_for(event, cwd, payload=None):
    """The context block for a normalized event, or None when out of scope.

    event: session_start | user_prompt | subagent_start | post_compact
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
        # per-turn nudge: openers decay over long sessions. Kept short because
        # it is paid every turn, and on Claude the output style already carries
        # the same rules on every response. The conditional rules ride along
        # only on the turn whose prompt matches their task class.
        if off("reminder-off"):
            return None
        text = render(PROMPT_REMINDER.strip())
        prompt = prompt_text(payload)
        if prompt:
            _always, conditional, _dis = core_split(cwd)
            matched = classify_prompt(prompt)
            armed = [conditional[k] for k in CONDITIONAL_KEYS
                     if k in conditional and k in matched]
            audit_classification(matched, len(prompt))
            if armed:
                text += "\n\n" + render("\n\n".join(armed))
        else:
            audit_classification(set(), 0)
        return text + ("\n(off this session: %s)" % ", ".join(disabled)
                       if disabled else "")
    # session_start / post_compact / subagent_start: the compact always-on core
    # plus live index/consult state. The deep orchestration/exec detail moved
    # out of the every-session payload into the tezgah-contract skill, which
    # the last line tells the model to load on demand.
    parts = [core]
    _, marks = repo_marks(cwd)
    if ".no-cbm" in marks:
        parts.append("Graph: disabled for this repo (.no-cbm), so use grep/find "
                     "and say the answer came from text search.")
    elif cbm_bin():
        # SubagentStart fires once per delegated agent: a fan-out would race
        # indexers on the same repo, so only the parent session triggers one.
        status = (autoindex(root) if event != "subagent_start"
                  else "index handled by the parent session")
        parts.append("Graph index: %s (project %s)." % (status, slug(root)))
    else:
        parts.append("Graph: codebase-memory-mcp is not installed, so use "
                     "grep/find and say the answer came from text search; never "
                     "claim the index answered.")
    if not off("consult-off") and not have_consult_key():
        parts.append("Consult: no provider key (OpenRouter or DeepSeek), so the "
                     "second opinion cannot run; on a non-trivial call say it was "
                     "skipped and why.")
    if not off("research-off") and not orx_bin():
        parts.append("Research: orx (OpenResearch) is not installed, so route "
                     "research to a host subagent and say the tooling is "
                     "unavailable; do not improvise its protocol.")
    if event == "session_start":
        note = sync_agents(root)
        if note:
            parts.append("Subagents (this repo, generated): %s" % note)
    if event in ("session_start", "post_compact"):
        plans = open_plans(root)
        if plans:
            parts.append(plans)
        if ".no-lessons" not in marks:
            past = lessons(root)
            if past:
                parts.append(past)
    if disabled:
        parts.append(off_note)
        if "orchestrate-off" in disabled:
            parts.append("Orchestration is off (orchestrate-off): do not "
                         "delegate to subagents; do the work in this thread.")
    if event == "subagent_start":
        parts.append("You are a subagent: execute the briefing and report "
                     "evidence back to the router; do not orchestrate or spawn "
                     "subagents. Full rules: the `tezgah-contract` skill.")
    else:
        parts.append("Deep orchestration, codegen, consult detail and the exact "
                     "kill switches: load the `tezgah-contract` skill.")
    return render("\n\n".join(p.strip() for p in parts))


def record(session_id, kind):
    """Append a used-tool kind for the status line (any host, best effort)."""
    if not session_id:
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


def index_mark(cwd, base):
    """Code-graph readiness for the enclosing repo.

    ✓ indexed, ↻ indexed but HEAD moved since the stamp, ✗ not indexed yet,
    – not applicable (outside a root, codebase-memory-mcp absent, or .no-cbm)."""
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


_FLAG_KEYS = ("pony", "exec", "consult", "research", "cbm", "orch")
GLYPHS = {"on": "✓", "ready": "○", "off": "✗", "info": ""}
# ANSI foreground for each state: green in force, yellow on-demand, red off.
COLORS = {"on": "\033[32m", "ready": "\033[33m", "off": "\033[31m", "info": ""}
RESET = "\033[0m"
IDX_STATE = {"✓": "on", "↻": "ready", "✗": "off", "–": "info"}
LEGEND = """\
tezgah status marks (state first, glyph after the name):
  name\u2713  green   armed and in force this session (or always-on)
  name\u25cb  yellow  armed, on demand - not used yet this session
  name\u2717  red     turned off by a kill switch or a per-repo .no-* mark
  idx\u2713 indexed   idx\u21bb stale (HEAD moved)   idx\u2717 not indexed   idx\u2013 n/a
  plans N (M blk)   open plans under the repo, M of them blocked
Outside a tezgah root the per-repo extras (idx, plans) are omitted.
"""


def health_segments(cwd, session_id=None, used_override=None):
    """The armed/used checklist as structured segments, host-neutral.

    Each segment is {"key", "state", "glyph", "text"} with state in
    {on, ready, off, info}; `text` is the human name and `glyph` the mark. Hosts
    that can color (Claude/Cursor ANSI, opencode TUI, dsh Web) map `state` to a
    color; hosts that cannot (Codex systemMessage) render text+glyph plain.
    `health_lines()` renders this to the exact plain string for the rest.

    Global, not root-scoped: tezgah ships as a globally loaded instructions file
    on opencode, so the indicator must not go silent off-root; the per-repo
    additions (idx, plans) appear only inside a root.

    used_override: the tool kinds a host already resolved from its own record
    (Claude parses the transcript because it does not write tezgah's recorder);
    None falls back to tezgah's recorder for session_id."""
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
        segs.append({"key": name, "state": state, "glyph": GLYPHS[state], "text": name})
    if base:
        glyph = index_mark(cwd, base)
        segs.append({"key": "idx", "state": IDX_STATE.get(glyph, "info"),
                     "glyph": glyph, "text": "idx"})
        plan = plan_mark(cwd, base)
        if plan:
            segs.append({"key": "plans", "state": "ready" if "blk" in plan else "info",
                         "glyph": "", "text": plan})
    return segs


def _seg_text(seg, color):
    glyph = seg["glyph"]
    if not color or not glyph or seg["state"] == "info":
        return seg["text"] + glyph
    return seg["text"] + COLORS[seg["state"]] + glyph + RESET


def render_line(segs, color=False):
    """Render segments to the one-line status string; `color` adds ANSI."""
    flags = [s for s in segs if s["key"] in _FLAG_KEYS]
    line = (" ".join(_seg_text(s, color) for s in flags[:2])
            + "  ·  " + " ".join(_seg_text(s, color) for s in flags[2:]))
    extra = [_seg_text(s, color) for s in segs if s["key"] in ("idx", "plans")]
    if extra:
        line += "  ·  " + "  ·  ".join(extra)
    return line


def health_lines(cwd, session_id=None, used_override=None):
    """The plain armed/used checklist every host can render (no ANSI)."""
    return render_line(health_segments(cwd, session_id, used_override))

