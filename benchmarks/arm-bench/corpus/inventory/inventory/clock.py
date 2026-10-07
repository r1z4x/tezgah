"""Business hours helpers."""


def is_business_hours(moment):
    """Return True when moment is a weekday between 09:00 and 17:00."""
    return moment.weekday() < 5 and 9 <= moment.hour < 17
