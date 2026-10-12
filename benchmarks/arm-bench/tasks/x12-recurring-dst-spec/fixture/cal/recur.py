"""Daily recurring meetings. The contract is cal/SPEC.md."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def occurrences(first_day, at, tz_name, window_start, window_end):
    """UTC instants of a daily meeting at local time `at`, inside the window."""
    tz = ZoneInfo(tz_name)
    out = []
    day = max(first_day, (window_start - timedelta(days=1)).date())
    while day <= window_end.date() + timedelta(days=1):
        t = datetime.combine(day, at, tzinfo=tz).astimezone(timezone.utc)
        if window_start <= t <= window_end:
            out.append(t)
        day += timedelta(days=1)
    return out
