#!/usr/bin/env python3
"""Statusline extensions: a repository's own metrics, on tezgah's line.

A repository adds chips to the status line without touching tezgah. It drops one
manifest at `<repo>/.tezgah/extension.json`:

    {"statusline": {"command": ["bin/engagement-statusline", "--segments"],
                    "timeout_ms": 300}}

and that command prints structured segments on stdout:

    {"segments": [{"key": "eng", "state": "info", "text": "pentest-001",
                   "glyph": "", "group": 0}]}

tezgah discovers the manifest by walking up from the working directory, runs the
command once per render (bounded, fail-open) and appends what it returns after
its own marks. The core owns rendering: an extension produces data, never a
formatted line, so color, the narrow-surface drop and the group separators stay
identical for every extension, and the extension never has to know tezgah's
gutter.

Why a subprocess and not an import: the extension lives in the user's repo, in
whatever language, and may be slow or broken. Importing it runs its code in the
harness's own process; a bounded child is the seam that keeps a broken extension
costing one chip on one line, never the gate that carries every turn.

The line is drawn on every redraw, so the cost is bounded on purpose: the walk
stops at the first manifest, the child gets a hard timeout, and a repo with no
manifest pays a single `os.path.isfile` per level and nothing else.
"""
import json
import os
import subprocess

EXT_DIR = ".tezgah"
MANIFEST_NAME = "extension.json"
# How far the walk climbs before giving up. A repo root is at most a few levels
# above any working directory an editor or a host opens; a bound keeps a
# manifest-less path from stat-ing every ancestor up to `/`.
MAX_WALK = 12
# A healthy extension costs one interpreter start (~25 ms measured 2026-10-19),
# but a cold start under a loaded machine spiked past 500 ms, so the default
# carries headroom: the budget is a hang detector, not a latency budget, and a
# manifest that knows its own cost lowers it.
DEFAULT_TIMEOUT_MS = 1000
# A chip budget, not a data budget: the status line is one row, and an extension
# that floods it is a bug in the extension. The per-extension cap keeps one
# broken manifest from pushing the built-in marks off the line.
MAX_SEGMENTS = 8
STATES = ("on", "ready", "off", "info")


def manifest_path(cwd):
    """(repo_root, manifest_path) for the nearest `.tezgah/extension.json` above
    `cwd`, or (None, None) when there is none within MAX_WALK levels.

    The first manifest wins: nesting is a mistake, not a feature, and stopping
    early is what makes the walk cheap."""
    path = os.path.realpath(cwd)
    for _ in range(MAX_WALK):
        candidate = os.path.join(path, EXT_DIR, MANIFEST_NAME)
        if os.path.isfile(candidate):
            return path, candidate
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return None, None


def _load_manifest(manifest_file):
    """The manifest dict, or None when it is missing or malformed. A bad manifest
    costs the extension, never the line."""
    try:
        with open(manifest_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _valid_segment(seg, index):
    """One segment dict, normalized, or None when it cannot be rendered.

    `text` and `state` are the only required fields: text is what the reader
    sees, state is what the glyph and the color mean. A missing or unknown state
    is `info` (the state-less mark), never a guess at "on"."""
    if not isinstance(seg, dict):
        return None
    text = seg.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    state = seg.get("state")
    if state not in STATES:
        state = "info"
    key = seg.get("key")
    if not isinstance(key, str) or not key:
        key = "ext-%d" % index
    glyph = seg.get("glyph")
    if not isinstance(glyph, str):
        glyph = ""
    return {"key": key, "state": state, "glyph": glyph, "text": text.strip()}


def run_manifest(repo_root, manifest):
    """The segments a manifest's command returns, or [] on any failure.

    Failure is a closed door, not a raised one: a missing command, a non-zero
    exit, a timeout, malformed JSON, a wrong shape and an over-budget list all
    answer [] - the line loses this extension's chips and keeps its own."""
    spec = manifest.get("statusline")
    if not isinstance(spec, dict):
        return []
    command = spec.get("command")
    if (not isinstance(command, list) or not command
            or not all(isinstance(a, str) for a in command)):
        return []
    timeout_ms = spec.get("timeout_ms", DEFAULT_TIMEOUT_MS)
    if not isinstance(timeout_ms, (int, float)) or timeout_ms <= 0:
        timeout_ms = DEFAULT_TIMEOUT_MS
    argv = list(command)
    # A bare program name resolves on PATH; a path is relative to the repo root,
    # so a manifest travels with its clone instead of naming an absolute path.
    if os.sep in argv[0] and not os.path.isabs(argv[0]):
        argv[0] = os.path.join(repo_root, argv[0])
    if os.sep in argv[0] and not os.path.isfile(argv[0]):
        return []
    try:
        proc = subprocess.run(argv, cwd=repo_root, capture_output=True,
                              text=True, encoding="utf-8",
                              timeout=timeout_ms / 1000.0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout or "")
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    raw = payload.get("segments")
    if not isinstance(raw, list):
        return []
    out = []
    for index, seg in enumerate(raw[:MAX_SEGMENTS]):
        clean = _valid_segment(seg, index)
        if clean is not None:
            out.append(clean)
    return out


def segments(cwd):
    """Every extension segment for a render of `cwd`, in manifest order.

    One manifest today (the first found); the return is a list so a second
    extension is a discovery change, not a caller change."""
    repo_root, manifest_file = manifest_path(cwd)
    if not manifest_file:
        return []
    manifest = _load_manifest(manifest_file)
    if not manifest:
        return []
    return run_manifest(repo_root, manifest)
