#!/usr/bin/env python3
"""Hidden contract checks for t07. Run with the candidate tree as the cwd.

Checks the public signature, the return type, that the answer does not depend
on the host timezone, and that an unknown zone raises instead of falling back.
"""
import inspect
import json
import os
import subprocess
import sys
from datetime import date, datetime

sys.path.insert(0, os.getcwd())

from src.calendar_day import calendar_day  # noqa: E402

ROWS = [
    (1773487800.0, "Pacific/Auckland", "2026-03-15"),
    (1782844200.0, "Asia/Kolkata", "2026-07-01"),
    (1767245400.0, "Pacific/Honolulu", "2025-12-31"),
]

if "--sweep" in sys.argv:
    # Child mode: report what this process answers under the TZ it inherited.
    print(json.dumps([[str(calendar_day(e, z)) for e, z, _ in ROWS], os.environ.get("TZ")]))
    raise SystemExit(0)

failures = []

params = list(inspect.signature(calendar_day).parameters)
if params != ["epoch_seconds", "tz_name"]:
    failures.append(f"signature is {params}, expected ['epoch_seconds', 'tz_name']")

try:
    got = calendar_day(epoch_seconds=1773487800.0, tz_name="Pacific/Auckland")
except TypeError as exc:
    failures.append(f"keyword call raised {exc!r}")
else:
    if got != date(2026, 3, 15):
        failures.append(f"keyword call returned {got!r}, want {date(2026, 3, 15)!r}")

got = calendar_day(1773487800.0, "Pacific/Auckland")
if isinstance(got, datetime):
    failures.append(f"return type is {type(got).__name__}, want date")
elif not isinstance(got, date):
    failures.append(f"return type is {type(got).__name__}, want date")

# The host timezone must not leak into the answer: same call, different TZ.
want = [row[2] for row in ROWS]
for tz in ("America/Los_Angeles", "Asia/Kolkata", "Pacific/Kiritimati"):
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--sweep"],
        cwd=os.getcwd(),
        env=dict(os.environ, TZ=tz),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        failures.append(f"TZ={tz}: probe exited {proc.returncode}: {proc.stderr.strip()[-200:]!r}")
        continue
    try:
        days = json.loads(proc.stdout.strip().splitlines()[-1])[0]
    except Exception:  # noqa: BLE001 - unreadable probe output is a failure
        failures.append(f"TZ={tz}: unreadable probe output {proc.stdout.strip()[-200:]!r}")
        continue
    if days != want:
        failures.append(f"TZ={tz}: days {days} differ from {want}")

# An unknown zone is an error, never a silently guessed day.
try:
    got = calendar_day(0.0, "Mars/Olympus")
except Exception as exc:  # noqa: BLE001 - the type is what matters here
    if type(exc).__name__ != "ZoneInfoNotFoundError":
        failures.append(f"unknown zone raised {type(exc).__name__}, want ZoneInfoNotFoundError")
else:
    failures.append(f"unknown zone returned {got!r}, want ZoneInfoNotFoundError")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
