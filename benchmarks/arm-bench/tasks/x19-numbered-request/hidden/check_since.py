#!/usr/bin/env python3
"""One check per item of the --since request.

    python3 check_since.py filter|list|search|invalid|export|empty
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = sys.argv[1] if len(sys.argv) > 1 else ""
sys.path.insert(0, ".")
failures = []

NOTES = [
    {"id": 1, "title": "Kickoff", "body": "Agenda and owners.", "created": "2024-01-15"},
    {"id": 2, "title": "Budget", "body": "Q1 numbers, draft.", "created": "2024-02-29"},
    {"id": 3, "title": "Retro", "body": "What went well; budget overrun.", "created": "2024-03-01"},
    {"id": 4, "title": "Hiring", "body": "Two roles open.", "created": "2024-03-20"},
    {"id": 5, "title": "Old budget", "body": "Last year.", "created": "2023-12-31"},
]


def expect(ok, detail):
    if not ok:
        failures.append(detail)


def cli(*argv, notes=NOTES):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "n.json"
        path.write_text(json.dumps(notes), encoding="utf-8")
        proc = subprocess.run([sys.executable, "-m", "notes.cli", str(path), *argv],
                              capture_output=True, text=True, timeout=30, cwd=os.getcwd())
    return proc.returncode, proc.stdout, proc.stderr


def filter():
    from notes import store
    fn = getattr(store, "since", None)
    if fn is None:
        failures.append("notes.store has no since")
        return
    got = [n["id"] for n in fn(NOTES, datetime.date(2024, 3, 1))]
    expect(got == [3, 4], "since(2024-03-01) kept ids %r, want [3, 4]" % (got,))
    got = [n["id"] for n in fn(NOTES, datetime.date(2024, 2, 29))]
    expect(got == [2, 3, 4], "since(2024-02-29) kept ids %r, want [2, 3, 4]" % (got,))
    got = [n["id"] for n in fn(NOTES, datetime.date(2023, 1, 1))]
    expect(got == [1, 2, 3, 4, 5], "since(2023-01-01) kept ids %r" % (got,))


def list_():
    code, out, err = cli("list", "--since", "2024-03-01")
    want = "  3 2024-03-01 Retro\n  4 2024-03-20 Hiring\n"
    expect(code == 0 and out == want, "list --since 2024-03-01: exit %r, out %r, err %r"
           % (code, out, err[-200:]))


def search():
    code, out, err = cli("search", "budget", "--since", "2024-01-01")
    want = "  2 2024-02-29 Budget\n  3 2024-03-01 Retro\n"
    expect(code == 0 and out == want, "search budget --since 2024-01-01: exit %r, out %r, err %r"
           % (code, out, err[-200:]))


def invalid():
    for argv in (("list",), ("search", "budget"), ("export",)):
        for bad in ("2024-13-01", "yesterday", "2024-02-30"):
            code, out, err = cli(*argv, "--since", bad)
            expect(code == 2 and "usage:" in err and "Traceback" not in err,
                   "%s --since %s: exit %r, stderr %r" % (" ".join(argv), bad, code, err[-200:]))


def export():
    code, out, err = cli("export", "--since", "2024-03-01")
    want = ("# 2 notes\n\n## Retro (2024-03-01)\n\nWhat went well; budget overrun.\n\n"
            "## Hiring (2024-03-20)\n\nTwo roles open.\n")
    expect(code == 0 and out == want, "export --since 2024-03-01: exit %r, out %r, err %r"
           % (code, out, err[-200:]))


def empty():
    for argv, notes in ((("list",), []), (("search", "zebra"), NOTES)):
        code, out, err = cli(*argv, notes=notes)
        expect(code == 0 and out == "(no notes)\n",
               "%s with nothing to list: exit %r, out %r, err %r"
               % (" ".join(argv), code, out, err[-200:]))
    code, out, err = cli("list")
    expect(out.count("\n") == 5, "list of five notes printed %r" % (out,))


CHECKS = {"filter": filter, "list": list_, "search": search, "invalid": invalid,
          "export": export, "empty": empty}

if NAME not in CHECKS:
    print("unknown check: %r (known: %s)" % (NAME, ", ".join(sorted(CHECKS))))
    sys.exit(2)
try:
    CHECKS[NAME]()
except ImportError as exc:
    print("cannot import the package: %r" % exc)
    sys.exit(1)
for detail in failures[:8]:
    print(detail)
print("%s: %s" % (NAME, "ok" if not failures else "%d failures" % len(failures)))
sys.exit(1 if failures else 0)
