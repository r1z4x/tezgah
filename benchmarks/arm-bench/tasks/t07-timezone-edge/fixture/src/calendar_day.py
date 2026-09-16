"""Assigns each event to the calendar day it belongs to."""

from datetime import date, datetime, timezone


def calendar_day(epoch_seconds: float, tz_name: str) -> date:
    """Return the calendar date the instant `epoch_seconds` falls on."""
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).date()
