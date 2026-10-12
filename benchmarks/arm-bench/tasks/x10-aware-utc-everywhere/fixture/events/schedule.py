from datetime import datetime, timedelta

SWEEP_EVERY = timedelta(minutes=15)


def next_sweep(now=None):
    """The next quarter hour after `now` (default: the current time)."""
    now = now or datetime.now()
    base = now.replace(minute=now.minute - now.minute % 15, second=0, microsecond=0)
    return base + SWEEP_EVERY
