from datetime import datetime

from .model import Event

FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def from_text(name, text):
    """An event that arrived with an ISO-8601 UTC timestamp such as
    2026-01-05T09:30:00Z."""
    return Event(name, datetime.strptime(text, FORMAT))
