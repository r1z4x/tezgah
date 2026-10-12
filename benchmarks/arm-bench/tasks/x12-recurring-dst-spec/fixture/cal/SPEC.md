# Daily recurrence

`cal.recur.occurrences(first_day, at, tz_name, window_start, window_end)` lists
the occurrences of a meeting that happens every day at the local wall-clock time
`at` (a `datetime.time`) in the IANA time zone `tz_name`, starting on the date
`first_day`.

1. The result is a list of timezone-aware datetimes in UTC, ascending, one per
   day at most. No occurrence falls on a day before `first_day`.
2. The window is half open: an occurrence `t` is listed when
   `window_start <= t < window_end`. Both bounds are timezone-aware datetimes, in
   any zone. An occurrence exactly at `window_start` is listed; one exactly at
   `window_end` is not. When `window_end <= window_start` the result is empty.
3. **Clocks spring forward.** When `at` does not exist on a day because the
   clocks jump over it, that day's occurrence happens at the instant of the
   jump, i.e. at the first wall-clock time after the gap. In America/New_York on
   2026-03-08 the clocks go from 02:00 EST to 03:00 EDT, so a 02:30 meeting
   happens at 03:00 EDT (07:00 UTC).
4. **Clocks fall back.** When `at` happens twice on a day, the meeting happens
   once, at the **second** (later) of the two instants. In America/New_York on
   2026-11-01 01:30 happens first in EDT and again in EST; the meeting is at
   01:30 EST (06:30 UTC).

## Examples (America/New_York, `at` = 09:00)

| window                                   | occurrences (UTC)                     |
|------------------------------------------|---------------------------------------|
| 2026-01-05 14:00Z .. 2026-01-07 14:00Z   | 2026-01-05 14:00, 2026-01-06 14:00    |
| 2026-07-01 00:00Z .. 2026-07-02 00:00Z   | 2026-07-01 13:00                      |
