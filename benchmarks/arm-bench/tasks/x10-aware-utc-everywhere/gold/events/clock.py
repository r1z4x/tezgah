from datetime import datetime, timedelta, timezone
from functools import partial

TTL = timedelta(hours=1)
NOW = partial(datetime.now, timezone.utc)


def expired(event):
    """True once an event is older than TTL."""
    return NOW() - event.created > TTL
