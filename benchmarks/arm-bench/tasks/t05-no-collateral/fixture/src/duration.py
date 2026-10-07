"""Duration parsing."""

import re

_UNITS = {"h": 3600, "m": 60, "s": 1}
_PART = re.compile(r"(\d+)([hms])")


def parse_duration(text: str) -> int:
    """Return the number of seconds described by `text`."""
    total = 0
    for number, unit in _PART.findall(text):
        total += int(number) * _UNITS[unit]
    return total
