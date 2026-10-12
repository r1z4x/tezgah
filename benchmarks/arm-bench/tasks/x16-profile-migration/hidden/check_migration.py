#!/usr/bin/env python3
"""One check per step of the format-2 migration.

    python3 check_migration.py save|load|version|readers|export|migrate
"""
import json
import os
import sys
import tempfile
from pathlib import Path

NAME = sys.argv[1] if len(sys.argv) > 1 else ""
sys.path.insert(0, ".")
failures = []


def expect(ok, detail):
    if not ok:
        failures.append(detail)


ADA = {"name": "Ada", "email": "ada@example.org", "tags": ["admin", "ops"]}
BOB = {"name": "Bob", "email": "bob@Example.ORG", "tags": []}


def save():
    from profiles.store import save as do_save
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ada.json"
        do_save(dict(ADA), path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        want = {"version": 2, "name": "Ada", "email": "ada@example.org", "tags": ["admin", "ops"]}
        expect(raw == want, "save wrote %r, want %r" % (raw, want))


def load():
    from profiles.store import load as do_load
    cases = [
        ({"mail": "ada@example.org", "name": "Ada", "tags": "admin,ops"}, ADA),
        ({"mail": "bob@Example.ORG", "name": "Bob", "tags": ""}, BOB),
        ({"version": 1, "mail": "cy@example.org", "name": "Cy", "tags": "ops"},
         {"name": "Cy", "email": "cy@example.org", "tags": ["ops"]}),
        ({"version": 2, "name": "Di", "email": "di@example.org", "tags": ["a", "b"]},
         {"name": "Di", "email": "di@example.org", "tags": ["a", "b"]}),
        ({"version": 2, "name": "Ed", "email": "ed@example.org", "tags": []},
         {"name": "Ed", "email": "ed@example.org", "tags": []}),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (raw, want) in enumerate(cases):
            path = Path(tmp) / ("p%d.json" % i)
            path.write_text(json.dumps(raw), encoding="utf-8")
            try:
                got = do_load(path)
            except Exception as exc:                        # noqa: BLE001
                failures.append("load(%r) raised %r" % (raw, exc))
                continue
            expect(got == want, "load(%r) = %r, want %r" % (raw, got, want))


def version():
    from profiles.errors import ProfileError
    from profiles.store import load as do_load
    with tempfile.TemporaryDirectory() as tmp:
        for v in (3, 0):
            raw = {"version": v, "name": "X", "email": "x@example.org", "tags": []}
            path = Path(tmp) / "x.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            try:
                got = do_load(path)
                failures.append("load of version %r returned %r, want ProfileError" % (v, got))
            except ProfileError:
                pass
            except Exception as exc:                        # noqa: BLE001
                failures.append("load of version %r raised %r, want ProfileError" % (v, exc))


def readers():
    from profiles.search import by_domain, by_tag
    people = [dict(ADA), dict(BOB), {"name": "Ops", "email": "o@x.io", "tags": ["opsx"]}]
    try:
        expect([p["name"] for p in by_tag(people, "ops")] == ["Ada"],
               "by_tag(..., 'ops') = %r" % (by_tag(people, "ops"),))
        expect(by_tag(people, "") == [], "by_tag(..., '') matched %r" % (by_tag(people, ""),))
        expect([p["name"] for p in by_domain(people, "example.org")] == ["Ada", "Bob"],
               "by_domain(..., 'example.org') = %r" % (by_domain(people, "example.org"),))
    except Exception as exc:                                # noqa: BLE001
        failures.append("search on the new shape raised %r" % (exc,))


def export():
    from profiles.export import to_csv
    want = "name,email,tags\nAda,ada@example.org,admin;ops\nBob,bob@Example.ORG,\n"
    try:
        got = to_csv([dict(ADA), dict(BOB)])
    except Exception as exc:                                # noqa: BLE001
        failures.append("to_csv on the new shape raised %r" % (exc,))
        return
    expect(got == want, "to_csv = %r, want %r" % (got, want))


def migrate():
    from profiles.migrate import migrate_dir
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ada.json").write_text(
            '{"mail": "ada@example.org", "name": "Ada", "tags": "admin,ops"}\n', encoding="utf-8")
        (root / "bob.json").write_text(
            '{"mail": "bob@Example.ORG", "name": "Bob", "tags": ""}\n', encoding="utf-8")
        current = root / "di.json"
        current_text = '{"version": 2, "tags": ["a"], "name": "Di", "email": "di@example.org"}'
        current.write_text(current_text, encoding="utf-8")
        os.utime(current, ns=(1_000_000_000, 1_000_000_000))
        (root / "notes.txt").write_text("not a profile", encoding="utf-8")
        try:
            first = migrate_dir(root)
            second = migrate_dir(root)
        except Exception as exc:                            # noqa: BLE001
            failures.append("migrate_dir raised %r" % (exc,))
            return
        expect(first == 2, "first migrate_dir returned %r, want 2" % (first,))
        expect(second == 0, "second migrate_dir returned %r, want 0" % (second,))
        expect(current.read_text(encoding="utf-8") == current_text
               and current.stat().st_mtime_ns == 1_000_000_000,
               "migrate_dir rewrote a file already at version 2")
        for name, want in (("ada.json", {"version": 2, "name": "Ada", "email": "ada@example.org",
                                         "tags": ["admin", "ops"]}),
                           ("bob.json", {"version": 2, "name": "Bob", "email": "bob@Example.ORG",
                                         "tags": []})):
            raw = json.loads((root / name).read_text(encoding="utf-8"))
            expect(raw == want, "%s after migration = %r, want %r" % (name, raw, want))


CHECKS = {"save": save, "load": load, "version": version, "readers": readers,
          "export": export, "migrate": migrate}

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
