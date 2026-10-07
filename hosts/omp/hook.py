#!/usr/bin/env python3
"""omp (oh-my-pi) lifecycle hook: the python half of the omp extension.

omp's extension API is TypeScript, so `hosts/omp/tezgah-hook.ts` forwards each
event here as one JSON payload on stdin and puts the answer back into the host.
The envelope is omp's own - its event fields are not Claude's - but the contract,
the gate and the evidence ledger underneath are the shared core in `hooks/`,
the same code every other host runs.

    {"event": "session_start", "cwd": ..., "session_id": ..., "subagent": bool,
     "parent": <the main session's id>, "agent": <the child's AgentId>}
        -> {"context": <this repo's live state, or the subagent brief>,
            "status": "pony✓ ...", "idx": glyph}
    {"event": "status", "cwd": ..., "session_id": ...}
        -> {"status": "pony✓ ...", "idx": glyph}  (ANSI-colored; see status_line)
    {"event": "post_compact", "cwd": ..., "session_id": ...,
     "compact_summary": ...}
        -> {"context": <this repo's live state after a compaction>}
    {"event": "user_prompt", "cwd": ..., "prompt": ...}
        -> {"context": <reminder + the rules this prompt arms>}
    {"event": "pre_tool_use", "cwd": ..., "tool": ..., "input": {...}}
        -> {"deny": reason}
    {"event": "post_tool_use", "cwd": ..., "tool": ..., "input": {...},
     "failed": bool, "idx": glyph}
        -> {"status": "pony✓ ...", "idx": glyph, "label": one line}
           (records the evidence the Stop rule reads; `idx` echoed from the
           payload skips the git probe; `label` is the untrusted-content notice
           for a result that came from outside the user and the workspace, or
           the taint notice on the first effect after such a result in a turn,
           and is absent for every ordinary result)
    {"event": "stop", "last_assistant_message": ..., "stop_hook_active": bool}
        -> {"decision": "block", "reason": reason}
           (with `stop_hook_active` the reply is recorded as an `after_block`
           row and never blocked a second time)

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
from tezgah_guard import attest_session, import_failed, safe  # noqa: E402
try:
    from tezgah_context import (  # noqa: E402
        color_default, command_text, context_for, health_segments, record,
        render_tiers, shell_kind, skill_read_kind)
    from tezgah_gate import decision  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        SUBAGENT_CHANNEL, note, note_tool, stop_reason, untrusted_label,
        untrusted_source)
    from tezgah_paths import off, root_for  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# How many times one stop chain may be refused (hooks/projects-stop.py names the
# same constant): one, deliberately; raising it is owner decision 11. omp has no
# subagent-end event: `session_stop` does not fire for task sessions.
STOP_REASKS = 1


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
    mark is ignored rather than drawn as one that states nothing.

    Returns the width tiers too (render_tiers): the widget knows its width only
    when it draws, so it picks the widest line that fits there."""
    segs = health_segments(cwd, session_id,
                           idx_override=idx if idx in IDX_GLYPHS else None)
    glyph = next((s["glyph"] for s in segs if s["key"] == "idx"), None)
    color = color_default()
    tiers = render_tiers(segs, color=color)
    return tiers[0][0], glyph, tiers


def answered(line, glyph, tiers=None):
    """The status fields one answer carries: the line, the glyph the next
    cheap redraw should reuse, and the tiers ([line, cells] widest first)."""
    out = {"status": line} if line else {}
    if glyph:
        out["idx"] = glyph
    if tiers:
        out["tiers"] = [[text, width] for text, width in tiers]
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
        # index, its open plans, its lessons and the live kill switches. A task
        # subagent (`subagent`, detected by the bridge) gets the subagent brief
        # instead: no indexer, no agent regeneration, no plan-status line, and
        # the line that tells it it is a subagent. `host` points the specialist
        # line at omp's user agent dir.
        out = {}
        kind = "subagent_start" if payload.get("subagent") else "session_start"
        if not payload.get("subagent"):
            safe(session_id, attest_session, "omp", session_id, cwd)
        if payload.get("subagent") and payload.get("parent"):
            # the child's ledger opens with its parent: the worker's checks land
            # here while the route that sent it is in the parent's ledger, and
            # `tezgah-route --report` joins the two through this row
            note(session_id, "spawned", "", parent=str(payload["parent"]),
                 agent=payload.get("agent"))
        context = context_for(kind, cwd, dict(payload, host="omp"),
                              with_core=False)
        if context:
            out["context"] = context
        out.update(answered(*status_line(cwd, session_id)))
        return out
    if event == "post_compact":
        # the bridge's session_compact (audit L-3): the live state re-sent after
        # a compaction, without the core RULES.md already holds; context_for
        # records the compaction from `compact_summary` before it builds this.
        context = context_for("post_compact", cwd, dict(payload, host="omp"),
                              with_core=False)
        return {"context": context} if context else {}
    if event == "user_prompt":
        context = context_for("user_prompt", cwd, payload)
        return {"context": context} if context else {}
    if event == "post_tool_use":
        tool = payload.get("tool", "")
        inp = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        failed = payload.get("failed")
        # Read before this call's row lands, as hooks/projects-posttooluse.py
        # does: `source` is the row's taint mark and `marks` answers about the
        # turn the call arrived in. The bridge never sends the result's body, and
        # `marks` reads a None result as a subagent call that read nothing, so a
        # non-None stand-in keeps the call-decided subagent label omp always
        # had. ponytail: a background `task` launch is labelled like a report,
        # because the bridge sends nothing that tells the two apart. A failed
        # call made no effect, so it keeps its own channel and earns no notice.
        own = untrusted_source(tool, inp)
        if failed is True:
            source, label = own, untrusted_label(own)
        else:
            source, label = safe(session_id, marks, tool, inp, session_id,
                                 "") or (None, None)
        record(session_id, classify(tool, inp))
        # failed is tri-state on purpose: None means omp reported no outcome,
        # and the ledger then records a check that ran, never one that passed.
        # `source` is the untrusted channel the result came through, or the one
        # an effect inherits from its turn, and is left out of the row for every
        # other call.
        # `result_len` is the size the bridge measured, never the body, and only
        # an integer counts: a value of any other shape is left unstated so the
        # row cannot claim a size nobody measured.
        size = payload.get("result_len")
        if own == SUBAGENT_CHANNEL:
            # The bridge measures a result by its top-level length, so a
            # delegate's report - a part list - arrives as a part count (1 on
            # 32174 ledger rows), never as a byte length, and the report's own
            # text is not in the payload. The row states no size rather than
            # claiming a 1-byte report; an absent field means unknown.
            size = None
        # `empty_run` is the bridge's own reading of the result's text (its
        # EMPTY_RUN copy), sent as a flag because the body is never sent
        note_tool(session_id, tool, inp,
                  failed=failed if isinstance(failed, bool) else None,
                  out_bytes=size if isinstance(size, int) and size >= 0 else None,
                  source=source, cwd=cwd,
                  empty_run=payload.get("empty_run") is True)
        if str(tool).lower() == "task" and isinstance(inp.get("tasks"), list):
            # omp names a child's ledger by its task name (`<parent>/<name>.jsonl`)
            # and only this call knows which agent that name runs - `task` when
            # none is given. `tezgah-route --report` joins a route to its worker
            # through it; a task without a name cannot be joined, so it is skipped.
            for t in inp["tasks"]:
                if isinstance(t, dict) and t.get("name"):
                    note(session_id, "spawn", "", child=str(t["name"]),
                         agent=str(t.get("agent") or "task"))
        # the call is already paid for, so the status line's used marks are
        # refreshed from the same answer instead of a second subprocess, and
        # from the idx glyph the session already carries instead of a git fork
        out = answered(*status_line(cwd, session_id, payload.get("idx")))
        # The result is the other thing this event carries. A label is not a
        # deny: the bridge puts it in front of the content itself, so the model
        # reads where the text came from - or, on an effect after such a read,
        # the taint notice - while it reads the result.
        if label:
            out["label"] = label
        return out
    if event == "stop":
        if off("verify-off"):
            return {}
        if (1 if payload.get("stop_hook_active") else 0) >= STOP_REASKS:
            # the reply after a block: recorded, never refused a second time,
            # under its own guard so a record that fails still answers empty
            safe(session_id, stop_reason, payload.get("last_assistant_message"),
                 session_id, cwd=cwd, record_only=True)
            return {}
        reason = stop_reason(payload.get("last_assistant_message"), session_id,
                             cwd=cwd)
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
