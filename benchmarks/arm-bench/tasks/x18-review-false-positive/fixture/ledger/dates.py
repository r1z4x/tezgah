"""Calendar helpers for statement periods."""
import datetime


def month_end(year, month):
    """The last calendar day of `month` (1-12) in `year`, as a datetime.date."""
    first_of_next = datetime.date(year, month + 1, 1)
    return first_of_next - datetime.timedelta(days=1)
