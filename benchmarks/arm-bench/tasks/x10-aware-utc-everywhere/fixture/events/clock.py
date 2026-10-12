from datetime import datetime, timedelta

TTL = timedelta(hours=1)
NOW = datetime.utcnow


def expired(event):
    """True once an event is older than TTL."""
    return NOW() - event.created > TTL
