#!/usr/bin/env python3
"""Amp lifecycle hook: the python half of tezgah's Amp plugin.

Amp's plugin API is TypeScript (ampcode.com/docs plugin-api), so
`hosts/amp/tezgah-plugin.ts.in`, rendered to `$XDG_CONFIG_HOME/amp/plugins/
tezgah.ts`, forwards each event here as one JSON payload on stdin and turns the
answer into Amp's own result. The protocol is omp's (hosts/omp/hook.py); the
session id is Amp's thread id.

    {"event": "session_start", "cwd", "session_id", "subagent", "parent",
     "ignore_guidance", "line"}
        -> {"context": <live state, the core too when AGENTS.md lacks it>,
            "status", "idx"}
    {"event": "status", "cwd", "session_id"} -> {"status", "idx"}
    {"event": "user_prompt", "cwd", "session_id", "prompt", "subagent"}
        -> {"context": <reminder + the rules this prompt arms>}
    {"event": "pre_tool_use", "cwd", "session_id", "tool", "input"} -> {"deny": reason}
    {"event": "post_tool_use", "cwd", "session_id", "tool", "input", "status",
     "exit_code", "result_len", "empty_run", "idx", "line"}
        -> {"label": one line, "status", "idx"}
    {"event": "stop", "cwd", "session_id", "last_assistant_message",
     "stop_hook_active"} -> {"decision": "block", "reason": reason}
    {"event": "subagent_stop", ..., "parent", "agent"} -> {} (record-only)

Session start cannot inject in Amp, so the bridge asks `session_start` on the
thread's next `agent.start` and sends the brief with that turn. The always-on
core is the managed block in `~/.config/amp/AGENTS.md`; the brief repeats it
only while that block is missing or AMP_IGNORE_GUIDANCE_FILES is set. The
status line is plain text: Amp's status item draws no ANSI.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_guard import attest_session, import_failed, safe  # noqa: E402
try:
    from tezgah_context import (  # noqa: E402
        command_text, context_for, health_segments, record, render_tiers, shell_kind,
        skill_read_kind)
    from tezgah_gate import cross_project_note, decision  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        SUBAGENT_CHANNEL, bind_session, note, note_tool, stop_reason, untrusted_label,
        untrusted_source)
    from tezgah_paths import HOST_DIRS, off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Amp's tool names -> the gate's vocabulary. `shell_command` is the other shell
# tool `shellCommandFromToolCall` reads (plugin-api); `Bash`, `edit_file`,
# `create_file`, `apply_patch` and `Task` are already the gate's names, and
# an MCP tool already arrives as `mcp__<server>__<tool>`.
GATE_TOOLS = {"shell_command": "Bash"}
IDX_GLYPHS = ("\u2713", "\u21bb", "\u2717", "?", "\u2013")


def gate_name(name):
    """The tool name the gate denies under and the ledger row records; both
    halves map through here so a call hashes to one id."""
    return GATE_TOOLS.get(name, name)


def gate_input(tool, inp):
    """The input in the gate's fields: the gate reads a shell call's text only
    from `command`, so Amp's `cmd` is copied there when the bridge sent none."""
    inp = dict(inp) if isinstance(inp, dict) else {}
    if tool == "Bash" and "command" not in inp and isinstance(inp.get("cmd"), str):
        inp["command"] = inp["cmd"]
    return inp


def classify(tool, inp):
    """The used-tool kind for a mapped call, or None."""
    if tool.startswith("mcp__") and "codegraph" in tool:
        return "graph"
    kind = skill_read_kind(tool, inp)
    if kind:
        return kind
    if tool.lower() == "task":
        return "orch"
    if tool == "Bash":
        return shell_kind(command_text(inp))
    return None


def call_failed(tool, status, exit_code):
    """`note_tool`'s `failed`, tri-state. An error or cancelled result is a
    failure; a shell result passes or fails only on an integer exit code the
    bridge read off the output object; anything else is None - a call that
    ran, never a pass (a `done` shell result alone proves nothing)."""
    if status in ("error", "cancelled"):
        return True
    if tool == "Bash" and isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return exit_code != 0
    return None


def rules_carry_core():
    """True when Amp's user AGENTS.md holds tezgah-setup's managed block."""
    try:
        with open(os.path.join(HOST_DIRS["amp"], "AGENTS.md"), encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def status_line(cwd, session_id, idx=None):
    """{status, idx}: the widest plain tier of the checklist. `idx` echoed back
    skips the git probe behind that mark, as on omp."""
    segs = health_segments(cwd, session_id,
                           idx_override=idx if idx in IDX_GLYPHS else None)
    out = {"status": render_tiers(segs, color=False)[0][0]}
    glyph = next((s["glyph"] for s in segs if s["key"] == "idx"), None)
    if glyph:
        out["idx"] = glyph
    return out


def post_tool(payload, cwd, session_id):
    """The ledger row for one finished call; {label} for the model."""
    tool = gate_name(str(payload.get("tool") or ""))
    inp = gate_input(tool, payload.get("input"))
    failed = call_failed(tool, payload.get("status"), payload.get("exit_code"))
    # read before this call's row lands: `source` is the taint's own mark; the
    # body never crosses, so a non-None stand-in keeps the subagent label
    own = untrusted_source(tool, inp)
    if failed is True:
        source, label = own, untrusted_label(own)
    else:
        source, label = safe(session_id, marks, tool, inp, session_id, "") or (None, None)
    record(session_id, classify(tool, inp))
    size = payload.get("result_len")
    if own == SUBAGENT_CHANNEL or not isinstance(size, int) or size < 0:
        size = None
    note_tool(session_id, tool, inp, failed=failed, out_bytes=size, source=source,
              cwd=cwd, empty_run=payload.get("empty_run") is True)
    if failed is not True:
        taste = safe(session_id, write_note, session_id, inp, cwd, tool)
        cross = safe(session_id, cross_project_note, session_id, tool, inp, cwd)
        label = "\n".join(t for t in (label, taste, cross) if t)
    out = status_line(cwd, session_id, payload.get("idx")) if payload.get("line") else {}
    if label:
        out["label"] = label
    return out


def handle(payload):
    event = payload.get("event") or ""
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")
    safe(session_id, bind_session, session_id)  # the switch latch (tezgah_paths.off)
    if event == "status":
        return status_line(cwd, session_id)
    if event == "pre_tool_use":
        tool = gate_name(str(payload.get("tool") or ""))
        reason = decision(tool, gate_input(tool, payload.get("input")), cwd, session_id)
        return {"deny": reason} if reason else {}
    if not root_for(cwd):
        return {}
    if event == "session_start":
        sub = bool(payload.get("subagent"))
        if sub and payload.get("parent"):
            # the child's ledger opens with its parent, as on omp
            note(session_id, "spawned", "", parent=str(payload["parent"]),
                 agent=payload.get("agent"))
        elif not sub:
            safe(session_id, attest_session, "amp", session_id, cwd)
        core = not rules_carry_core() or bool(payload.get("ignore_guidance"))
        context = context_for("subagent_start" if sub else "session_start", cwd,
                              dict(payload, host="amp"), with_core=core)
        out = status_line(cwd, session_id) if payload.get("line") else {}
        if context:
            out["context"] = context
        return out
    if event == "user_prompt":
        context = context_for("user_prompt", cwd, dict(payload, host="amp"))
        return {"context": context} if context else {}
    if event == "post_tool_use":
        return post_tool(payload, cwd, session_id)
    if event == "stop":
        if off("verify-off"):
            return {}
        # `stop_hook_active`: this turn was started by tezgah's own continue, so
        # the core may refuse it once more at most (tezgah_integrity, plan 083)
        reason = safe(session_id, stop_reason, payload.get("last_assistant_message"),
                      session_id, cwd=cwd,
                      after_block=bool(payload.get("stop_hook_active")),
                      mode=payload.get("permission_mode"))
        return {"decision": "block", "reason": reason} if reason else {}
    if event == "subagent_stop":
        # record-only (ADR 011): the row lands in the parent's ledger
        if not off("verify-off") and payload.get("parent"):
            safe(session_id, stop_reason, payload.get("last_assistant_message"),
                 session_id, cwd=cwd, subagent=True, agent=payload.get("agent"),
                 parent=str(payload["parent"]))
        return {}
    return {}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    # one guard around the dispatch: a crash answers "nothing to say", and the
    # plugin lets every call through (hooks/tezgah_guard.safe)
    out = safe(payload.get("session_id"), handle, payload) or {}
    if out:
        print(json.dumps(out))


main()
