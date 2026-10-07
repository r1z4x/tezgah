"""Assigns each event to the calendar day it belongs to."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def calendar_day(epoch_seconds: float, tz_name: str) -> date:
    """Return the calendar date `epoch_seconds` falls on in `tz_name`."""
    instant = datetime.fromtimestamp(epoch_seconds, timezone.utc)
    return instant.astimezone(ZoneInfo(tz_name)).date()
