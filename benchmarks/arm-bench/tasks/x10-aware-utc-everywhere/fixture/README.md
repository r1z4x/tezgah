# events

Records events and decides when they expire and when the next sweep runs.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test.
- **Every datetime is aware UTC.** Each datetime this package creates or returns
  carries `tzinfo=timezone.utc`; a naive datetime is a bug, because comparing
  one with an aware datetime raises TypeError and a naive local time is off by
  the server's offset. Timestamps in text end in `Z` and are UTC.

## Layout

- `events/log.py` - `stamp()`, the time an action is logged.
- `events/model.py` - an event and when it was created.
- `events/clock.py` - whether an event has expired.
- `events/ingest.py` - events arriving with a Unix timestamp.
- `events/parse.py` - events arriving with an ISO-8601 `...Z` timestamp.
- `events/schedule.py` - when the next sweep runs.
