from datetime import datetime, timezone

from .model import Event


def from_epoch(name, seconds):
    """An event that arrived with a Unix timestamp (seconds since the epoch)."""
    return Event(name, datetime.fromtimestamp(seconds, timezone.utc))
