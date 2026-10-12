from datetime import datetime


def stamp():
    """The time an action is logged."""
    return datetime.utcnow()
