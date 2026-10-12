#!/usr/bin/env python3
"""Every datetime the events package makes is aware UTC, and comparisons hold.

README.md: each datetime created or returned carries tzinfo=timezone.utc. Runs
under a non-UTC local zone, so a naive local time - or a local time merely
labelled UTC - shows up as a wrong value, not only as a missing tzinfo.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

os.environ["TZ"] = "Asia/Tokyo"
time.tzset()
sys.path.insert(0, ".")

failures = []
UTC = timezone.utc


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def aware(value, label):
    if not isinstance(value, datetime) or value.tzinfo is not UTC:
        failures.append("%s = %r, want an aware UTC datetime" % (label, value))
        return False
    return True


def near(value, label):
    if aware(value, label) and abs(value - datetime.now(UTC)) > timedelta(seconds=5):
        failures.append("%s = %r is not the current UTC time" % (label, value))


def attempt(label, call):
    try:
        return call()
    except Exception as exc:
        failures.append("%s raised %r" % (label, exc))


def main():
    from events import clock, ingest, log, parse, schedule
    from events.model import Event

    near(attempt("stamp()", log.stamp), "stamp()")
    near(attempt("Event().created", lambda: Event("x").created), "Event(x).created")
    sweep = attempt("next_sweep()", schedule.next_sweep)
    if aware(sweep, "next_sweep()") and not timedelta(0) < sweep - datetime.now(UTC) <= timedelta(minutes=15):
        failures.append("next_sweep() = %r is not the next UTC quarter hour" % sweep)

    epoch = attempt("from_epoch", lambda: ingest.from_epoch("x", 0))
    if epoch is not None and aware(epoch.created, "from_epoch(x, 0).created"):
        expect(epoch.created, datetime(1970, 1, 1, tzinfo=UTC), "from_epoch(x, 0).created")
    parsed = attempt("from_text", lambda: parse.from_text("x", "2026-01-05T09:30:00Z"))
    if parsed is not None and aware(parsed.created, "from_text(...Z).created"):
        expect(parsed.created, datetime(2026, 1, 5, 9, 30, tzinfo=UTC), "from_text(...Z).created")

    expect(attempt("expired(new)", lambda: clock.expired(Event("x"))), False,
           "expired(a new event)")
    old = Event("x", datetime.now(UTC) - timedelta(hours=2))
    expect(attempt("expired(old)", lambda: clock.expired(old)), True,
           "expired(an event two hours old)")
    if epoch is not None:
        expect(attempt("expired(epoch)", lambda: clock.expired(epoch)), True,
               "expired(an event from 1970)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % exc)
    for detail in failures:
        print(detail)
    print("aware utc: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
