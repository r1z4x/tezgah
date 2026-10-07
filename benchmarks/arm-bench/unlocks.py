#!/usr/bin/env python3
"""The switch-paragraph arm: every injected unlock, found and stripped.

An unlock is text the harness injects that tells the model how to turn a rule
off: an `Off: ...` / `Kill switch: ...` sentence, the `**Kill switches:**`
paragraph, the per-turn "Kill switches under ~/.config/tezgah/." pointer, and a
backticked switch or repo-mark name (`verify-off`, `.no-adhd`). The arm strips
what `UNLOCK` finds in the text the model is actually given, not a fixed list of
sites (plan 062, review notes), so a new `Off:` tag is stripped without an edit.

Two uses:

    strip(text)                 -> the text with every unlock removed
    python3 unlocks.py HOOK...  -> run as TEZGAH_PYTHON: the hook's own answer,
                                   with every string in it stripped

As TEZGAH_PYTHON the omp bridge calls `<this> <hook.py>` with the event on
stdin; anything that is not the omp hook is handed to python3 untouched, so the
bridge file stays the installed byte. Each stripped answer appends one line to
`$HOME/.cache/armbench-unlocks.jsonl` (the per-run HOME), the arm's own proof
that the filter ran and left no residue.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# The switch and mark names come from the harness's own list, so a switch added
# there is an unlock here without an edit.
HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "hooks")


def _names() -> tuple[tuple[str, ...], tuple[str, ...]]:
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    import tezgah_paths
    return tuple(tezgah_paths.SWITCHES), tuple(tezgah_paths.REPO_MARKS)


SWITCHES, MARKS = _names()
_NAME = "|".join(re.escape(n) for n in sorted(SWITCHES + MARKS, key=len, reverse=True))

# What counts as an unlock in injected text. The detector is the arm's
# definition: `strip` must leave no match of it, and the residue check reads it.
UNLOCK = re.compile(
    r"\bOff(?: only)?\s*:|\b(?i:kill switch(?:es)?)\s*:"     # Off: / Kill switch(es):
    r"|\b(?i:kill switches under)\b"                         # the per-turn pointer
    r"|`(?:%s)`" % _NAME +                                   # a backticked switch/mark
    r"|`tezgah-adhd off`|\"stop ponytail\"")
# A sentence that opens with an unlock tag runs to the next sentence end: a
# period followed by whitespace or the end of the text. `~/.config` and
# `.no-adhd` hold periods that are not sentence ends, which is why the end is a
# period *before whitespace*, not any period.
_SENTENCE = re.compile(
    r"[ \t]*(?:\bOff(?: only)?\s*:|\b(?i:kill switch)\s*:|\b(?i:kill switches under)\b)"
    r".*?\.(?=\s|$)", re.S)
_PARAGRAPH = re.compile(r"(?m)^\*\*Kill switches:\*\*.*?(?:\n\s*\n|\Z)", re.S)
# POINTER_LINE (hooks/tezgah_context.py) names the switches as one of the things
# the contract skill holds; the phrase goes, the pointer stays
_POINTER = re.compile(r",?\s+and the exact\s+kill switches", re.I)
_TICKED = re.compile(r"`(?:%s)`|`tezgah-adhd off`|\"stop ponytail\"(?:\s*/\s*\"normal mode\")?"
                     % _NAME)


def _drop_tables(text: str) -> str:
    """A paragraph listing three or more switches is the switch table wherever it
    sits, and goes whole: stripping only the names leaves ", , ,"."""
    parts = re.split(r"(\n\s*\n)", text)
    return "".join(p for p in parts if len(re.findall(r"`(?:%s)`" % _NAME, p)) < 3)


def strip(text: str) -> str:
    """`text` with every unlock removed; idempotent, and a no-op on text with none."""
    if not isinstance(text, str) or not UNLOCK.search(text) and not _POINTER.search(text):
        return text
    out = _drop_tables(_PARAGRAPH.sub("", text))
    out = _SENTENCE.sub("", out)
    out = _POINTER.sub("", out)
    out = _TICKED.sub("", out)
    return out


def residue(text: str) -> list[str]:
    """The unlocks `text` still carries - empty for a stripped text."""
    return [m.group(0) for m in UNLOCK.finditer(text or "")]


def strip_json(node):
    """Every string in a decoded JSON answer, stripped."""
    if isinstance(node, str):
        return strip(node)
    if isinstance(node, list):
        return [strip_json(v) for v in node]
    if isinstance(node, dict):
        return {k: strip_json(v) for k, v in node.items()}
    return node


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)


def wrap(argv: list[str]) -> int:
    """TEZGAH_PYTHON entry: filter the omp hook's answer, forward everything else."""
    python = os.environ.get("ARMBENCH_PYTHON") or "python3"
    if not argv or not argv[0].endswith(os.path.join("hosts", "omp", "hook.py")):
        os.execvp(python, [python, *argv])
    payload = sys.stdin.buffer.read()
    proc = subprocess.run([python, *argv], input=payload, capture_output=True)
    sys.stderr.buffer.write(proc.stderr)
    out = proc.stdout.decode("utf-8", errors="replace")
    if out.strip():
        try:
            answer = json.loads(out)
        except ValueError:
            answer = None
        if answer is not None:
            found = sum(len(residue(s)) for s in _strings(answer))
            answer = strip_json(answer)
            left = sum(len(residue(s)) for s in _strings(answer))
            out = json.dumps(answer, ensure_ascii=False)
            try:
                event = json.loads(payload or b"{}").get("event")
            except ValueError:
                event = None
            log = os.path.join(os.path.expanduser("~"), ".cache", "armbench-unlocks.jsonl")
            try:
                os.makedirs(os.path.dirname(log), exist_ok=True)
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"event": event, "found": found,
                                         "removed": found - left, "residue": left}) + "\n")
            except OSError:
                pass
    sys.stdout.write(out)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(wrap(sys.argv[1:]))
