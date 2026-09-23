#!/usr/bin/env python3
"""omp (oh-my-pi) lifecycle hook: the python half of the omp extension.

omp's extension API is TypeScript, so `hosts/omp/tezgah-hook.ts` forwards each
event here as one JSON payload on stdin and puts the answer back into the host.
The envelope is omp's own - its event fields are not Claude's - but the contract,
the gate and the evidence ledger underneath are the shared core in `hooks/`,
the same code every other host runs.

    {"event": "session_start", "cwd": ..., "session_id": ...}
        -> {"context": <this repo's live state>, "status": "pony✓ ...", "idx": glyph}
    {"event": "status", "cwd": ..., "session_id": ...}
        -> {"status": "pony✓ ...", "idx": glyph}  (ANSI-colored; see status_line)
    {"event": "user_prompt", "cwd": ..., "prompt": ...}
        -> {"context": <reminder + the rules this prompt arms>}
    {"event": "pre_tool_use", "cwd": ..., "tool": ..., "input": {...}}
        -> {"deny": reason}
    {"event": "post_tool_use", "cwd": ..., "tool": ..., "input": {...},
     "failed": bool, "idx": glyph}
        -> {"status": "pony✓ ...", "idx": glyph, "label": one line}
           (records the evidence the Stop rule reads; `idx` echoed from the
           payload skips the git probe; `label` is the untrusted-content notice
           for a result that came from outside the user and the workspace, and
           is absent for every ordinary result)
    {"event": "stop", "last_assistant_message": ..., "stop_hook_active": bool}
        -> {"decision": "block", "reason": reason}

Every answer that carries the line carries `idx` with it - the glyph of the
line's idx mark - so the caller can hand it back on the redraws that must not
pay for a git probe (see status_line).

The status line is the one signal that is not root-scoped - tezgah ships as a
globally loaded rules file, so the indicator must not go silent off-root - and
`status` therefore answers anywhere. Every other event is inert outside a
configured root.

The line carries ANSI foreground per mark, because the extension draws it
through omp's widget path, which renders the string as it is. `setStatus`, the
fallback, strips the escapes and shows the same marks uncolored.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import (  # noqa: E402
    color_default, command_text, context_for, health_segments, record,
    render_line, shell_kind, skill_read_kind)
from tezgah_gate import decision, drift_reason  # noqa: E402
from tezgah_guard import safe  # noqa: E402
from tezgah_integrity import (  # noqa: E402
    note_tool, stop_reason, untrusted_label, untrusted_source)
from tezgah_paths import off, root_for  # noqa: E402


def classify(tool, inp):
    """The used-tool kind for one omp tool call, or None.

    omp names MCP tools `mcp__<server>_<tool>` (it also accepts Claude Code's
    doubled separator), so the server is matched by substring rather than by an
    exact prefix. Same kinds as the other hosts: graph, orch, consult, research.
    The kind is claimed only when the command really ran the tool - a mention in
    an argument used to be enough, which made the line report a consult that
    never happened.
    """
    name = str(tool or "")
    if name.startswith("mcp__") and "codegraph" in name:
        return "graph"
    read_kind = skill_read_kind(name, inp)
    if read_kind:
        return read_kind
    low = name.lower()
    if low in ("task", "agent", "spawn_agent"):
        return "orch"
    if low in ("bash", "shell", "command"):
        kind = shell_kind(command_text(inp))
        if kind:
            return kind
    return None


IDX_GLYPHS = ("\u2713", "\u21bb", "\u2717", "?", "\u2013")


def status_line(cwd, session_id, idx=None):
    """The checklist as omp should draw it, plus the idx glyph it carries.

    The line is colored per mark, plain when the environment opts out (NO_COLOR
    / TEZGAH_STATUS_COLOR=0). `idx` is the glyph the session already shows: the
    stamp probe behind it is the line's only subprocess, so the redraw that
    follows every watched tool sends it back and forks nothing, while the used
    marks, the plans and the kill-switch state stay live. Anything that is not a
    mark is ignored rather than drawn as one that states nothing."""
    segs = health_segments(cwd, session_id,
                           idx_override=idx if idx in IDX_GLYPHS else None)
    glyph = next((s["glyph"] for s in segs if s["key"] == "idx"), None)
    return render_line(segs, color=color_default()), glyph


def answered(line, glyph):
    """The status fields one answer carries: the line, and the glyph the next
    cheap redraw should reuse."""
    out = {"status": line} if line else {}
    if glyph:
        out["idx"] = glyph
    return out


def handle(payload):
    event = payload.get("event") or ""
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")
    if event == "status":
        # turn end and the session switch: the probe runs, so the idx mark is
        # answered at every turn boundary
        return answered(*status_line(cwd, session_id))
    if event == "pre_tool_use":
        reason = decision(payload.get("tool", ""), payload.get("input") or {},
                          cwd, session_id)
        return {"deny": reason} if reason else {}
    if not root_for(cwd):
        return {}
    if event == "session_start":
        # omp's always-on RULES.md already carries the core contract, so the
        # session payload is the part a static file cannot know: this repo's
        # index, its open plans, its lessons and the live kill switches.
        out = {}
        context = context_for("session_start", cwd, payload, with_core=False)
        if context:
            out["context"] = context
        out.update(answered(*status_line(cwd, session_id)))
        return out
    if event == "user_prompt":
        context = context_for("user_prompt", cwd, payload)
        return {"context": context} if context else {}
    if event == "post_tool_use":
        tool = payload.get("tool", "")
        inp = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        failed = payload.get("failed")
        source = untrusted_source(tool, inp)
        # The long turn's re-statement, on the same field as the label below -
        # `label` is the one line this event puts in front of the result (see
        # tezgah_gate.drift_reason). Read before this call's own row lands, so
        # its step count is the turn's work up to this call.
        drift = safe(session_id, drift_reason, tool, inp, cwd, session_id)
        record(session_id, classify(tool, inp))
        # failed is tri-state on purpose: None means omp reported no outcome,
        # and the ledger then records a check that ran, never one that passed.
        # `source` is the untrusted channel the result came through, and is left
        # out of the row for every result that is the user's or the workspace's.
        # `result_len` is the size the bridge measured, never the body, and only
        # an integer counts: a value of any other shape is left unstated so the
        # row cannot claim a size nobody measured.
        size = payload.get("result_len")
        note_tool(session_id, tool, inp,
                  failed=failed if isinstance(failed, bool) else None,
                  out_bytes=size if isinstance(size, int) and size >= 0 else None,
                  source=source)
        # the call is already paid for, so the status line's used marks are
        # refreshed from the same answer instead of a second subprocess, and
        # from the idx glyph the session already carries instead of a git fork
        out = answered(*status_line(cwd, session_id, payload.get("idx")))
        # The result is the other thing this event carries. A label is not a
        # deny: the bridge puts it in front of the content itself, so the model
        # reads where the text came from while it reads the text.
        label = "\n".join(t for t in (untrusted_label(source), drift) if t)
        if label:
            out["label"] = label
        return out
    if event == "stop":
        if payload.get("stop_hook_active") or off("verify-off"):
            return {}
        reason = stop_reason(payload.get("last_assistant_message"), session_id)
        return {"decision": "block", "reason": reason} if reason else {}
    return {}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    # one guard around the whole dispatch: omp's bridge turns a crash here into a
    # session-wide disable of the gate, the ledger and the status line, so this
    # host must answer with the empty envelope it uses for "nothing to say"
    # rather than let an exception out (hooks/tezgah_guard.safe)
    out = safe(payload.get("session_id"), handle, payload) or {}
    if out:
        print(json.dumps(out))


main()
