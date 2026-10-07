"""Business-hours helpers."""

from datetime import datetime


def is_open(moment: datetime) -> bool:
    """Return True when `moment` is a weekday between 09:00 and 17:00.

    The window is in the moment's own timezone: a moment that carries a
    timezone is read as the wall clock it describes, not as the clock of
    whatever machine happens to run this.
    """
    return moment.weekday() < 5 and 9 <= moment.astimezone().hour < 17
