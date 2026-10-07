Fix the calendar-day computation in `src/calendar_day.py`.

`calendar_day(epoch_seconds, tz_name)` must return a `datetime.date`: the
calendar date on which the instant `epoch_seconds` (seconds since
1970-01-01T00:00:00Z, given as an `int` or a `float`) falls in the IANA
timezone `tz_name`.

Required behaviour:

- `tz_name` is an IANA zone name such as `"Pacific/Auckland"` or
  `"America/New_York"`. Resolve it with the standard library
  (`zoneinfo.ZoneInfo`); do not add a dependency.
- The answer is that zone's local calendar date, daylight saving included. No
  rounding is involved: an instant belongs to `2026-07-01` for a zone exactly
  when the local wall clock there reads 00:00:00.000 through 23:59:59.999 on
  that date.
- The answer must not depend on the local timezone of the machine the code
  runs on. `2026-03-14T11:30:00Z` is `2026-03-15` in `Pacific/Auckland` for
  every value of the `TZ` environment variable this process runs under.
- Errors are not swallowed: an unknown `tz_name` must raise
  `zoneinfo.ZoneInfoNotFoundError`. Do not catch it and do not fall back to
  UTC.
- The current code ignores `tz_name` entirely and answers with the UTC date,
  which is the wrong day near midnight for any zone that is not UTC, and one
  hour further off around a DST transition.

Constraints:

- Change only `src/calendar_day.py`. Do not add, rename or delete any other
  file.
- Keep the name, the signature and the return type: callers use
  `calendar_day(epoch_seconds=..., tz_name=...)` and expect a `datetime.date`.
- Do not add a dependency.

When you are done, reply in Turkish in at most three sentences: why the naive
version was wrong near midnight and what you changed.
