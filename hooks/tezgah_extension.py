#!/usr/bin/env python3
"""Statusline extensions: a repository's own metrics, on tezgah's line.

A repository adds chips to the status line without touching tezgah. It drops one
manifest at `<repo>/.tezgah/extension.json`:

    {"statusline": {"command": ["bin/engagement-statusline", "--segments"],
                    "timeout_ms": 300}}

and that command prints structured segments on stdout:

    {"segments": [{"key": "eng", "state": "info", "text": "pentest-001",
                   "glyph": "", "group": 0}]}

The command is handed its own call on stdin as one JSON object -
`{"api": 1, "event": "statusline", "cwd": ..., "repo_root": ...,
"session_id": ...}` (`call_envelope()`) - so it knows which repository and
session asked, rather than guessing from its environment.

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

The same manifest carries four more keys. Each is read here, consumed by one
caller and validated the way `statusline` is, so a broken value costs that key
and never the line or the gate (docs/status-line.md, "The manifest's other
keys"):

    {"checks": ["./bin/run-tool"],                          # repo_checks
     "untrusted": ["nmap", "sqlmap"],                       # untrusted_programs
     "agents": [{"match": "(?i)recon", "agent": "recon"}],  # repo_agent
     "statusline": {"command": [...], "override": true}}    # override
"""
import json
import os
import re
import shlex
import subprocess

EXT_DIR = ".tezgah"
MANIFEST_NAME = "extension.json"
# The variable a domain repository names its engagement root with: a session
# working anywhere under `$TEZGAH_ENGAGEMENTS_ROOT/<slug>` reads that
# engagement's own manifest even when the walk up ran out first.
ENGAGEMENTS_ENV = "TEZGAH_ENGAGEMENTS_ROOT"
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
# The call envelope's version, not this module's: it is what tells an extension
# which keys to expect on its stdin. Adding a key leaves it alone; changing what
# a key means bumps it.
CALL_API = 1
# The other keys' bounds. A list past its cap is cut, not refused, so a long
# manifest still contributes its first entries. A pattern is bounded in length
# and the brief it reads in characters, so a repo's regex cannot hold route() up.
MAX_CHECKS = 32
MAX_UNTRUSTED = 64
MAX_AGENTS = 32
MAX_PATTERN = 512
MAX_BRIEF = 4000
# An agent name lands in a ledger row's `agent=` word and in a spawn call, so it
# is one word of a file-name alphabet; a program name is one basename.
NAME = re.compile(r"^[A-Za-z0-9][\w.+-]{0,63}$")


def call_envelope(repo_root, cwd, session_id=None):
    """The one JSON object every extension call carries on stdin.

    The child is told which repository it was called for, from which directory
    and in which session, instead of inferring that from its own environment. A
    key an extension does not know it ignores; `api` is the key it can gate on,
    so a future envelope reads as a named refusal rather than a wrong chip."""
    return {"api": CALL_API, "event": "statusline",
            "cwd": os.path.realpath(cwd), "repo_root": repo_root,
            "session_id": session_id or None}


def manifest_path(cwd):
    """(repo_root, manifest_path) for the nearest `.tezgah/extension.json` above
    `cwd`, or (None, None) when there is none within MAX_WALK levels.

    The first manifest wins: nesting is a mistake, not a feature, and stopping
    early is what makes the walk cheap. When the walk finds none, a cwd under
    `$TEZGAH_ENGAGEMENTS_ROOT/<slug>` reads that engagement's manifest however
    deep it sits (`_engagement_manifest`)."""
    path = os.path.realpath(cwd)
    for _ in range(MAX_WALK):
        candidate = os.path.join(path, EXT_DIR, MANIFEST_NAME)
        if os.path.isfile(candidate):
            return path, candidate
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return _engagement_manifest(cwd)


def _engagement_manifest(cwd):
    """(engagement_root, manifest_path) for a cwd under
    `$TEZGAH_ENGAGEMENTS_ROOT/<slug>`, or (None, None): no root set, a cwd
    outside it or at the root itself, or no manifest in that engagement. One
    `isfile`, so an unset or unrelated root costs nothing."""
    root = os.environ.get(ENGAGEMENTS_ENV)
    if not root:
        return None, None
    root = os.path.realpath(os.path.expanduser(root))
    rel = os.path.relpath(os.path.realpath(cwd), root)
    slug = rel.split(os.sep, 1)[0]
    if slug in (os.curdir, os.pardir):
        return None, None
    engagement = os.path.join(root, slug)
    candidate = os.path.join(engagement, EXT_DIR, MANIFEST_NAME)
    return (engagement, candidate) if os.path.isfile(candidate) else (None, None)


def given_manifest(manifest_file):
    """(repo_root, manifest_path) for a manifest named outright (the renderer's
    `--manifest`): the repo root is the directory holding its `.tezgah`, else
    the directory holding the file. (None, None) when it is no file."""
    path = os.path.realpath(os.path.expanduser(manifest_file))
    if not os.path.isfile(path):
        return None, None
    folder = os.path.dirname(path)
    return (os.path.dirname(folder) if os.path.basename(folder) == EXT_DIR
            else folder), path


def _load_manifest(manifest_file):
    """The manifest dict, or None when it is missing or malformed. A bad manifest
    costs the extension, never the line."""
    try:
        with open(manifest_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load(cwd, manifest_file=None):
    """(repo_root, manifest dict) for `cwd` - or for `manifest_file` when one
    is named - else (None, None). Never raises: every key reader below goes
    through it, and a reader that raised would cost its caller the call."""
    try:
        repo_root, found = (given_manifest(manifest_file) if manifest_file
                            else manifest_path(cwd))
    except (OSError, ValueError, TypeError):
        return None, None
    manifest = _load_manifest(found) if found else None
    return (repo_root, manifest) if manifest else (None, None)


def repo_checks(cwd):
    """[argv prefix] the manifest's `checks` declares, each a list of words.

    An entry is a string split the shell's way (`"bin/audit --check"` is two
    words) or a list of strings; anything else - a number, an empty string, a
    line shlex rejects - is dropped alone. The first word is normalised
    (`./bin/x` and `bin/x` are one prefix), the way a command word is read."""
    _root, manifest = load(cwd)
    raw = (manifest or {}).get("checks")
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw[:MAX_CHECKS]:
        try:
            words = (shlex.split(entry) if isinstance(entry, str)
                     else list(entry) if isinstance(entry, list) else [])
        except ValueError:
            continue
        if words and all(isinstance(w, str) and w for w in words):
            out.append([os.path.normpath(words[0])] + words[1:])
    return out


def untrusted_programs(cwd):
    """frozenset of the program names the manifest's `untrusted` declares: one
    basename each, case kept (a shell's program word is case-sensitive). A
    non-list, or an entry that is no name, is dropped."""
    _root, manifest = load(cwd)
    raw = (manifest or {}).get("untrusted")
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(os.path.basename(p) for p in raw[:MAX_UNTRUSTED]
                     if isinstance(p, str) and NAME.match(os.path.basename(p)))


def repo_agent(brief, cwd):
    """(agent, pattern) of the first `agents` entry whose `match` regex finds
    the brief, or None. An entry with no string pattern, a pattern longer than
    MAX_PATTERN or one `re` rejects, or an agent that is no one-word name, is
    dropped alone; the brief is read on its first MAX_BRIEF characters."""
    _root, manifest = load(cwd)
    raw = (manifest or {}).get("agents")
    if not isinstance(raw, list):
        return None
    text = str(brief or "")[:MAX_BRIEF]
    for entry in raw[:MAX_AGENTS]:
        if not isinstance(entry, dict):
            continue
        pattern, agent = entry.get("match"), entry.get("agent")
        if not (isinstance(pattern, str) and pattern and len(pattern) <= MAX_PATTERN
                and isinstance(agent, str) and NAME.match(agent)):
            continue
        try:
            if re.search(pattern, text):
                return agent, pattern
        except re.error:
            continue
    return None


def override(cwd, manifest_file=None):
    """True when the manifest's `statusline.override` is literally `true`: the
    project owns its status line and points it at tezgah's renderer, so that
    renderer is the only line. Any other value is False."""
    _root, manifest = load(cwd, manifest_file)
    spec = (manifest or {}).get("statusline")
    return isinstance(spec, dict) and spec.get("override") is True


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


def run_manifest(repo_root, manifest, envelope=None):
    """The segments a manifest's command returns, or [] on any failure.

    Failure is a closed door, not a raised one: a missing command, a non-zero
    exit, a timeout, malformed JSON, a wrong shape and an over-budget list all
    answer [] - the line loses this extension's chips and keeps its own.

    `envelope` reaches the child as one JSON object on stdin. A command that
    never reads its stdin sees the same closed, empty input it always did."""
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
                              input=(json.dumps(envelope) if envelope is not None
                                     else ""),
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


def segments(cwd, session_id=None, manifest_file=None):
    """Every extension segment for a render of `cwd`, in manifest order.
    `manifest_file` names the manifest outright (the renderer's `--manifest`)
    instead of discovering it from `cwd`.

    One manifest today (the first found); the return is a list so a second
    extension is a discovery change, not a caller change."""
    repo_root, manifest = load(cwd, manifest_file)
    if not manifest:
        return []
    return run_manifest(repo_root, manifest,
                        call_envelope(repo_root, cwd, session_id))
