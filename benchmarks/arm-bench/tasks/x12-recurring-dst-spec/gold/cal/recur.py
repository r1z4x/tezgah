"""Daily recurring meetings. The contract is cal/SPEC.md."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
MINUTE = timedelta(minutes=1)


def _exists(local):
    """Whether this naive-wall-clock, tz-aware datetime names a real instant."""
    back = local.astimezone(UTC).astimezone(local.tzinfo)
    return back.replace(tzinfo=None) == local.replace(tzinfo=None)


def _instant(day, at, tz):
    local = datetime.combine(day, at, tzinfo=tz)
    if not _exists(local):
        # spring forward: walk back to the start of the gap; its fold=0 reading
        # uses the pre-jump offset, which is exactly the instant of the jump
        start = local
        while not _exists(start - MINUTE):
            start -= MINUTE
        return start.astimezone(UTC)
    later = local.replace(fold=1)
    if later.utcoffset() != local.utcoffset():
        return later.astimezone(UTC)            # fall back: the second instant
    return local.astimezone(UTC)


def occurrences(first_day, at, tz_name, window_start, window_end):
    """UTC instants of a daily meeting at local time `at`, inside the window."""
    tz = ZoneInfo(tz_name)
    out = []
    if window_end <= window_start:
        return out
    day = max(first_day, (window_start - timedelta(days=1)).date())
    while day <= window_end.date() + timedelta(days=1):
        t = _instant(day, at, tz)
        if window_start <= t < window_end:
            out.append(t)
        day += timedelta(days=1)
    return out
