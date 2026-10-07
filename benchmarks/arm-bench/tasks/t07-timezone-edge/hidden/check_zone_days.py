#!/usr/bin/env python3
"""Hidden calendar-day checks for t07. Run with the candidate tree as the cwd.

Every row is wrong for a naive UTC answer, for a hard-coded UTC offset, or for
both, so a fix that does not resolve the zone cannot pass.
"""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.getcwd())

from src.calendar_day import calendar_day  # noqa: E402

# (UTC instant, IANA zone, expected local date).
CASES = [
    # UTC+13 and UTC+14: a different day than UTC, just after local midnight.
    ("2026-03-14T11:30:00", "Pacific/Auckland", date(2026, 3, 15)),   # NZDT +13:00
    ("2026-01-01T11:30:00", "Pacific/Kiritimati", date(2026, 1, 2)),  # +14:00, no DST
    # UTC-10: the day behind UTC, across a year boundary.
    ("2026-01-01T05:30:00", "Pacific/Honolulu", date(2025, 12, 31)),
    # Exact local midnight in a +05:30 zone, and one second before it.
    ("2026-06-30T18:29:59", "Asia/Kolkata", date(2026, 6, 30)),
    ("2026-06-30T18:30:00", "Asia/Kolkata", date(2026, 7, 1)),
    # America/New_York switches EST(-05:00) -> EDT(-04:00) at 2026-03-08T07:00:00Z.
    ("2026-03-08T04:30:00", "America/New_York", date(2026, 3, 7)),   # EST, 23:30 the day before
    ("2026-03-08T06:30:00", "America/New_York", date(2026, 3, 8)),   # EST, 01:30
    ("2026-03-08T07:30:00", "America/New_York", date(2026, 3, 8)),   # EDT, 03:30
    ("2026-07-04T04:30:00", "America/New_York", date(2026, 7, 4)),   # EDT, 00:30
    # ... and EDT(-04:00) -> EST(-05:00) at 2026-11-01T06:00:00Z.
    ("2026-11-01T04:30:00", "America/New_York", date(2026, 11, 1)),  # EDT, 00:30
    ("2026-11-01T06:30:00", "America/New_York", date(2026, 11, 1)),  # EST, 01:30
    # A zone whose offset is not a whole hour.
    ("2026-03-31T18:15:00", "Asia/Kathmandu", date(2026, 4, 1)),     # +05:45, local midnight
]

failures = []

for iso, zone, want in CASES:
    epoch = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()
    try:
        got = calendar_day(epoch, zone)
    except Exception as exc:  # noqa: BLE001 - any exception is a failure here
        failures.append(f"calendar_day({iso}Z, {zone!r}) raised {type(exc).__name__}: {exc}")
        continue
    if got != want:
        failures.append(f"calendar_day({iso}Z, {zone!r}) = {got!r}, want {want!r}")

# An integer epoch is as valid as a float one.
got = calendar_day(1767267000, "Pacific/Kiritimati")
if got != date(2026, 1, 2):
    failures.append(f"calendar_day(1767267000, 'Pacific/Kiritimati') = {got!r}, want {date(2026, 1, 2)!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
