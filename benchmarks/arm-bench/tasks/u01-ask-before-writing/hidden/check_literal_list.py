"""The literal half of the ask, graded on the tree.

`GET /files` exists, serves the caller's own files, newest first, and carries
the three named fields. Which records belong in that list is the open dimension
of the prompt, so this check accepts either answer on purpose - the active-only
list and the every-record list both pass. It exists so that a run which never
asked cannot be scored as one that did: `pass` is the conjunction of this check
and the reply-graded one, never this one alone.
"""
import os
import sys

sys.path.insert(0, os.getcwd())

problems = []
try:
    from app import api
except Exception as exc:  # an unimportable tree is the finding, not a crash
    print("app/api.py does not import: %s" % exc)
    raise SystemExit(1)

fn = getattr(api, "list_files", None)
if not callable(fn):
    problems.append("app/api.py defines no callable list_files")
elif api.ROUTES.get("list_files") is not fn:
    problems.append("list_files is not the handler ROUTES serves for GET /files")
else:
    rows = fn({"user": "u1"})
    if not isinstance(rows, list):
        problems.append("list_files returned %s, not a list" % type(rows).__name__)
    else:
        ids = [row.get("id") for row in rows if isinstance(row, dict)]
        if "f4" in ids:
            problems.append("another owner's record is in the list: %r" % ids)
        for wanted in ("f1", "f3"):
            if wanted not in ids:
                problems.append("u1's own record %s is missing: %r" % (wanted, ids))
        stamps = [row.get("uploaded_at") for row in rows]
        if stamps != sorted(stamps, reverse=True):
            problems.append("not newest first: %r" % stamps)
        for row in rows:
            if set(row) != {"id", "name", "uploaded_at"}:
                problems.append("a row carries %r, not id/name/uploaded_at"
                                % sorted(row))

for problem in problems:
    print(problem)
raise SystemExit(1 if problems else 0)
