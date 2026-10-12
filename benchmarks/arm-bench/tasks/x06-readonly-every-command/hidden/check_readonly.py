#!/usr/bin/env python3
"""Every command the shell accepts, run against a read-only store.

The README's rule: a read-only store rejects every command that would change
it with ReadOnlyError before anything changes, and every command that only
reads keeps working. The shell reaches commands two ways - a `do_<verb>` method
(a dashed verb maps to an underscored method) and plugins.HANDLERS - so this
walks both, and asserts the writing commands still work on a writable store.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from notes.commands import Shell  # noqa: E402
from notes.errors import ReadOnlyError  # noqa: E402
from notes.store import Store  # noqa: E402

SEED = {"milk": "buy milk", "call": "call mum"}
failures = []


def main(tmp):
    path = tmp / "notes.json"
    extra = tmp / "extra.json"
    extra.write_text(json.dumps({"bread": "buy bread"}))
    writes = ["add eggs buy eggs", "remove milk", "rename milk dairy",
              "clear-all", "tag milk shop", "import %s" % extra]
    reads = {"show milk": "buy milk", "list": ["call", "milk"], "count": 2,
             "find buy": ["milk"]}

    for line in writes:
        path.write_text(json.dumps(SEED))
        before = path.read_bytes()
        store = Store(path, readonly=True)
        try:
            Shell(store).run(line)
            failures.append("%r ran on a read-only store" % line)
        except ReadOnlyError:
            pass
        except Exception as exc:
            failures.append("%r raised %r, want ReadOnlyError" % (line, exc))
        if store.items != SEED:
            failures.append("%r changed the notes in memory: %r" % (line, store.items))
        if path.read_bytes() != before:
            failures.append("%r changed the file on disk" % line)

        path.write_text(json.dumps(SEED))
        try:
            Shell(Store(path)).run(line)
        except Exception as exc:
            failures.append("%r failed on a writable store: %r" % (line, exc))
        if path.read_bytes() == before:
            failures.append("%r did not save on a writable store" % line)

    for line, want in reads.items():
        path.write_text(json.dumps(SEED))
        try:
            got = Shell(Store(path, readonly=True)).run(line)
        except Exception as exc:
            failures.append("%r raised %r on a read-only store" % (line, exc))
            continue
        if got != want:
            failures.append("%r = %r, want %r" % (line, got, want))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as name:
        main(Path(name))
    for detail in failures:
        print(detail)
    print("read-only contract: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
