"""Business hours helpers."""


def is_business_hours(moment):
    """Return True when moment is an aware datetime on a weekday 09:00-17:00."""
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError("moment must be timezone-aware")
    return moment.weekday() < 5 and 9 <= moment.hour < 17
