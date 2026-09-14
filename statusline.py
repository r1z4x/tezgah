#!/usr/bin/env python3
"""Status line wrapper: Orca's own statusline output, then the Projects
harness checklist (ponytail / exec / consult / orchestrate / cbm) when the
session cwd is under a tezgah root. Reads the same stdin JSON Claude Code feeds
every statusLine command and forwards it verbatim to Orca's script."""
import json
import glob
import os
import subprocess
import sys

# installed as a ~/.claude/statusline.py symlink, so resolve the real file to
# find the plugin it ships with before importing the shared root resolver
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "hooks"))
from tezgah_paths import have_consult_key, root_for  # noqa: E402

HOME = os.path.expanduser("~")
ORCA = os.path.join(HOME, ".orca", "agent-hooks", "claude-statusline.sh")

data = sys.stdin.read()
try:
    payload = json.loads(data or "{}")
except Exception:
    payload = {}

orca_out = ""
if os.access(ORCA, os.X_OK):
    try:
        orca_out = subprocess.run(
            ["/bin/sh", ORCA], input=data, capture_output=True,
            text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        orca_out = ""

cwd = ((payload.get("workspace") or {}).get("current_dir")
       or payload.get("cwd") or "")
seg = ""
try:
    real = os.path.realpath(cwd) if cwd else ""
except OSError:
    real = ""
PROJECTS = root_for(real) if real else None
if PROJECTS:
    def off(name):
        return os.path.exists(os.path.join(HOME, ".claude", name))

    repo_flags = set()
    p = real
    while p.startswith(PROJECTS):
        for f in (".no-ponytail", ".no-cbm"):
            if os.path.exists(os.path.join(p, f)):
                repo_flags.add(f)
        if p == PROJECTS:
            break
        p = os.path.dirname(p)

    key_ok = have_consult_key()

    # Did this session actually USE the measurable tools? Parse tool_use blocks
    # from the transcript — a substring scan would flag the tool NAME appearing in
    # chat text (this very message) as a use, reproducing the false-✓ complaint.
    used = {"consult": False, "cbm": False, "orch": False}
    tp = payload.get("transcript_path")
    # subagent transcripts live next to the main one; a cbm/consult call made
    # inside a delegated agent counts as used (otherwise orch✓ forces cbm○)
    import glob
    files = [tp] if tp and os.path.exists(tp) else []
    if tp:
        files += glob.glob(os.path.splitext(tp)[0] + "/subagents/**/*.jsonl", recursive=True)  # incl. workflows/<run>/agent-*.jsonl
    lines = []
    for fp in files:
        try:
            size = os.path.getsize(fp)
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                if size > 2_000_000:  # ponytail: last 2MB only; a use buried earlier in a huge log is missed
                    fh.seek(size - 2_000_000)
                lines += fh.read().splitlines()
        except OSError:
            pass
    if lines:
        try:
            for line in lines:
                try:
                    content = (json.loads(line).get("message") or {}).get("content")
                except Exception:
                    continue  # partial first line after seek, or non-message row
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    name = b.get("name", "")
                    if name.startswith("mcp__codebase-memory-mcp__"):
                        used["cbm"] = True
                    elif name in ("Task", "Agent"):
                        used["orch"] = True
                    elif name == "Bash" and "consult" in \
                            (b.get("input") or {}).get("command", ""):
                        used["consult"] = True
        except OSError:
            pass

    # Behavioural rules (can't measure from transcript): armed ✓ / off ✗.
    armed = [
        ("pony", not off("ponytail-auto.off") and ".no-ponytail" not in repo_flags),
        ("exec", not off("exec-mode.off")),
    ]
    # Measurable rules: used ✓ / armed-but-unused ○ / off ✗.
    measurable = [
        ("consult", not off("consult-off") and key_ok, used["consult"]),
        ("cbm", ".no-cbm" not in repo_flags, used["cbm"]),
        ("orch", not off("orchestrate-off"), used["orch"]),
    ]
    left = " ".join(n + ("✓" if on else "✗") for n, on in armed)
    right = " ".join(
        n + ("✗" if not on else ("✓" if u else "○")) for n, on, u in measurable)
    seg = left + "  ·  " + right
    # Plans layer: open plan count for the enclosing repo (plans/open/*.md), blocked in brackets.
    p = real
    while p.startswith(PROJECTS):
        plans = glob.glob(os.path.join(p, "plans", "open", "*.md"))
        if plans:
            blocked = 0
            for f in plans:
                try:
                    with open(f) as fh:
                        blocked += "status: blocked" in fh.read(400)
                except OSError:
                    pass
            seg += "  ·  plans %d" % len(plans) + (" (%d blk)" % blocked if blocked else "")
            break
        if p == PROJECTS:
            break
        p = os.path.dirname(p)

parts = [p for p in (orca_out, seg) if p]
print("  |  ".join(parts))
