#!/usr/bin/env python3
"""Taste signals: the user's prompts, the agent's edits and the bytes those
edits left behind, stored per repository so a later miner can read them.

Opt-in and off by default. A row is written only when the `taste-on` marker is
armed (`tezgah_paths.armed`), the repository carries no `.no-taste` mark, its
`.tezgah/` already exists and is the user's own (`workspace_from_repo`: a
workspace that came with the clone is data, and nothing of the user's is
written into it). The store is `<git root>/.tezgah/taste/signals.jsonl`, one
JSON object per line, owner-only.

Every public function is total: it never raises, makes no network call and
appends at most one row. They run on the prompt and PostToolUse hot paths, so
the switch is read before anything else is.

Nothing here is learned or fed back into a prompt; this is capture only.
"""
import datetime
import json
import os

import tezgah_integrity as ti
from tezgah_paths import _toplevel, armed, root_for, workspace_from_repo

ARM = "taste-on"
MARK = ".no-taste"
VERSION = 1
PROMPT_MAX = 2000
EDIT_MAX = 4000
# The input fields a write carries its old and new text in, per host dialect -
# the same names tezgah_gate.EDIT_TEXT and `shortcut_edit` read.
OLD_KEYS = ("old_string", "oldString", "old_str")
NEW_KEYS = ("new_string", "newString", "new_str")
WHOLE_KEYS = ("content", "file_text", "text", "new_source")


def enabled(cwd):
    """The git root taste rows for `cwd` go to, or None when capture is off
    there. The marker is read first, so the default costs two stats."""
    try:
        if not cwd or not armed(ARM):
            return None
        real = os.path.realpath(cwd)
        if not root_for(real):
            return None
        top = _toplevel(real)
        if not top or not os.path.isdir(os.path.join(top, ".tezgah")):
            return None
        from tezgah_context import repo_marks  # imports this module's callers
        if MARK in repo_marks(real)[1] or workspace_from_repo(top):
            return None
        return top
    except Exception:
        return None


def _cut(text, limit):
    """(redacted text cut to `limit`, whether it was cut); None stays None."""
    if text is None:
        return None, False
    text = ti.redact(str(text))
    return text[:limit], len(text) > limit


def _rel(root, path, cwd):
    """`path` relative to `root`, or None when it resolves outside it."""
    apath = os.path.realpath(
        str(path) if os.path.isabs(str(path)) else os.path.join(cwd, str(path)))
    rel = os.path.relpath(apath, root)
    return None if rel == ".." or rel.startswith(".." + os.sep) else rel


def _write(root, kind, session_id, host, **fields):
    row = {"v": VERSION,
           "ts": datetime.datetime.now(datetime.timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%SZ"),
           "kind": kind, "session": str(session_id or ""), "host": host or _host()}
    row.update(fields)
    # the ledger's own writer: its flock, torn-tail repair and 0700/0600 modes
    ti._append(os.path.join(root, ".tezgah", "taste", "signals.jsonl"),
               json.dumps(row, ensure_ascii=False) + "\n")


def _host():
    """The host this hook process runs for, named the way the guard's debug log
    names it: `hosts/<name>/...` by its directory, the shared scripts as
    `claude/dsh`, and None when it cannot be told."""
    try:
        from tezgah_guard import _host as named
        return named()
    except Exception:
        return None


def note_prompt(session_id, prompt, cwd, host=None):
    """One `prompt` row: the user's text, redacted and cut."""
    try:
        root = enabled(cwd)
        if not root or not prompt:
            return
        text, cut = _cut(prompt, PROMPT_MAX)
        fields = {"text": text}
        if cut:
            fields["cut"] = True
        _write(root, "prompt", session_id, host, **fields)
    except Exception:
        pass


def _edit_row(root, session_id, row_id, path, old, new, cwd, host):
    rel = _rel(root, path, cwd)
    if rel is None:
        return
    old, old_cut = _cut(old, EDIT_MAX)
    new, new_cut = _cut(new, EDIT_MAX)
    fields = {"id": row_id, "path": rel, "old": old, "new": new}
    if old_cut or new_cut:
        fields["cut"] = True
    _write(root, "edit", session_id, host, **fields)


def _after_row(root, session_id, path, snapshot_id, sha, cwd, host):
    rel = _rel(root, path, cwd)
    if rel is not None:
        _write(root, "after", session_id, host, path=rel,
               snapshot=snapshot_id, sha=sha)


def edit_text(inp):
    """(old, new) a write tool's input carries: the replaced and the new text of
    an edit, None and the whole body of a write, None and the patch of an
    apply_patch, the joined pairs of a multi-edit."""
    def first(keys):
        for k in keys:
            if isinstance(inp.get(k), str):
                return inp[k]
        return None
    new = first(NEW_KEYS)
    if new is not None:
        return first(OLD_KEYS), new
    whole = first(WHOLE_KEYS)
    if whole is not None:
        return None, whole
    if isinstance(inp.get("patch"), str):
        return None, inp["patch"]
    edits = [e for e in inp.get("edits") or () if isinstance(e, dict)]
    if edits:
        def joined(keys):
            parts = [next((e[k] for k in keys if isinstance(e.get(k), str)), "")
                     for e in edits]
            return "\n".join(parts)
        return joined(OLD_KEYS), joined(NEW_KEYS)
    return None, None


def note_write(session_id, row_id, inp, cwd, host=None):
    """The taste rows of one landed write call: its `edit` row, then an `after`
    row per file it wrote, each backed by an after blob in the snapshot store.
    Called from PostToolUse, so the bytes read are the ones the write left. A
    call touching a credential file gets nothing: its text would be the secret
    outside the file that guards it (`tezgah_snapshot.SECRET_FILE`)."""
    try:
        if not armed(ARM) or not isinstance(inp, dict) or inp.get("command") == "view":
            return  # off first; str_replace_editor's `view` reads, writes nothing
        import tezgah_snapshot as ts
        from tezgah_gate import write_paths
        paths = write_paths(inp)
        root = enabled(cwd)
        if not root or not paths or any(
                ts.SECRET_FILE.match(os.path.basename(str(p))) for p in paths):
            return
        old, new = edit_text(inp)
        _edit_row(root, session_id, row_id, paths[0], old, new, cwd, host)
        for path in paths:
            if _rel(root, path, cwd) is None:
                continue  # outside the repository: no row, so no orphan blob
            saved = ts.capture_after(path, cwd, session_id)
            if saved:
                _after_row(root, session_id, path, saved[0], saved[1], cwd, host)
    except Exception:
        pass


def write_note(session_id, inp, cwd, tool=None):
    """The in-scope taste learnings for the first write to a file type in a
    session (`tezgah_taste_ledger.write_note`), or "". Every host's post-tool
    channel carries it beside its other notices; off, it costs the marker stat.
    `tool` is the call's tool name; a call that is not a write gets nothing."""
    try:
        if not armed(ARM) or not isinstance(inp, dict) or inp.get("command") == "view" \
                or (tool is not None and str(tool).lower() not in ti.WRITE_TOOLS):
            return ""
        from tezgah_gate import write_paths
        paths = write_paths(inp)
        root = enabled(cwd)
        rel = _rel(root, paths[0], cwd) if root and paths else None
        if rel is None:
            return ""
        import tezgah_taste_ledger
        return tezgah_taste_ledger.write_note(root, session_id, rel)
    except Exception:
        return ""


def main(argv):
    """`tezgah_taste.py '<json>'`: `note_write`, then `write_note`, for a host
    that cannot call them in process (opencode's plugin is JavaScript). The one
    argument is {"session_id", "id", "input", "cwd", "host"}. Prints the note
    (nothing when there is none); exit 0 always."""
    try:
        payload = json.loads(argv[0]) if argv else {}
        if isinstance(payload, dict):
            cwd = payload.get("cwd") or os.getcwd()
            note_write(payload.get("session_id"), payload.get("id"),
                       payload.get("input"), cwd, payload.get("host"))
            note = write_note(payload.get("session_id"), payload.get("input"), cwd)
            if note:
                print(note)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
