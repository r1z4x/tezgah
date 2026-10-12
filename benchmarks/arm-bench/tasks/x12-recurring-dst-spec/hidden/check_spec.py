#!/usr/bin/env python3
"""Grade `occurrences` against cal/SPEC.md, one clause per argument.

  window  rules 1-2: start inclusive, end exclusive, an empty window, a window in
          another zone, no day before `first_day`.
  gap     rule 3: a 02:30 meeting on 2026-03-08 in New York is at 03:00 EDT
          (07:00Z); zoneinfo's default fold=0 reading gives 07:30Z. Berlin's
          gap (2026-03-29 02:00 -> 03:00 CET -> CEST) is the second zone.
  fold    rule 4: a 01:30 meeting on 2026-11-01 in New York is at 06:30Z, the
          second instant; the default fold=0 reading gives the first, 05:30Z.
"""
import sys
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, ".")
UTC = timezone.utc
NY = "America/New_York"


def z(*a):
    return datetime(*a, tzinfo=UTC)


CASES = {
    "window": [
        # start inclusive, end exclusive
        ((date(2026, 1, 1), time(9), NY, z(2026, 1, 5, 14), z(2026, 1, 7, 14)),
         [z(2026, 1, 5, 14), z(2026, 1, 6, 14)]),
        ((date(2026, 1, 1), time(9), NY, z(2026, 1, 5, 14), z(2026, 1, 5, 14, 0, 1)),
         [z(2026, 1, 5, 14)]),
        # empty and inverted windows
        ((date(2026, 1, 1), time(9), NY, z(2026, 1, 5, 14), z(2026, 1, 5, 14)), []),
        ((date(2026, 1, 1), time(9), NY, z(2026, 1, 7, 14), z(2026, 1, 5, 14)), []),
        # bounds in another zone: 09:00 New York == 15:00 Berlin in January
        ((date(2026, 1, 1), time(9), NY,
          datetime(2026, 1, 5, 15, tzinfo=timezone(timedelta(hours=1))),
          datetime(2026, 1, 6, 15, tzinfo=timezone(timedelta(hours=1)))),
         [z(2026, 1, 5, 14)]),
        # nothing before first_day
        ((date(2026, 1, 6), time(9), NY, z(2026, 1, 1), z(2026, 1, 8)),
         [z(2026, 1, 6, 14), z(2026, 1, 7, 14)]),
    ],
    "gap": [
        ((date(2026, 3, 1), time(2, 30), NY, z(2026, 3, 7), z(2026, 3, 10)),
         [z(2026, 3, 7, 7, 30), z(2026, 3, 8, 7, 0), z(2026, 3, 9, 6, 30)]),
        ((date(2026, 3, 1), time(2, 0), NY, z(2026, 3, 8), z(2026, 3, 9)),
         [z(2026, 3, 8, 7, 0)]),
        ((date(2026, 3, 1), time(2, 45), "Europe/Berlin", z(2026, 3, 28), z(2026, 3, 31)),
         [z(2026, 3, 28, 1, 45), z(2026, 3, 29, 1, 0), z(2026, 3, 30, 0, 45)]),
    ],
    "fold": [
        ((date(2026, 10, 1), time(1, 30), NY, z(2026, 10, 31), z(2026, 11, 3)),
         [z(2026, 10, 31, 5, 30), z(2026, 11, 1, 6, 30), z(2026, 11, 2, 6, 30)]),
        ((date(2026, 10, 1), time(2, 30), "Europe/Berlin", z(2026, 10, 24), z(2026, 10, 27)),
         [z(2026, 10, 24, 0, 30), z(2026, 10, 25, 1, 30), z(2026, 10, 26, 1, 30)]),
    ],
}


def main(clause):
    try:
        from cal.recur import occurrences
    except Exception as exc:                                  # noqa: BLE001
        print("cannot import occurrences: %r" % exc)
        return 1
    bad = 0
    for args, want in CASES[clause]:
        try:
            got = occurrences(*args)
        except Exception as exc:                              # noqa: BLE001
            print("raise  %r: %r" % (args, exc))
            bad += 1
            continue
        if [t.astimezone(UTC) for t in got] != want or any(t.utcoffset() != timedelta(0) for t in got):
            print("wrong  %r\n   got  %r\n  want  %r" % (args, got, want))
            bad += 1
    print("%s: %d/%d cases" % (clause, len(CASES[clause]) - bad, len(CASES[clause])))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
