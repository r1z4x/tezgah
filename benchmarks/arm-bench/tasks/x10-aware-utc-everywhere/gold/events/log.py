from datetime import datetime, timezone


def stamp():
    """The time an action is logged."""
    return datetime.now(timezone.utc)
