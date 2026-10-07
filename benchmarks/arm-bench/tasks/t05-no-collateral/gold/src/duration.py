"""Duration parsing."""

import re

_UNITS = {"h": 3600, "m": 60, "s": 1}
_ORDER = "hms"
_PART = re.compile(r"\d+[hms]")


def parse_duration(text: str) -> int:
    """Return the number of seconds described by `text`."""
    if not isinstance(text, str) or not text:
        raise ValueError("duration must be a non-empty string")

    parts = _PART.findall(text)
    if not parts or "".join(parts) != text:
        raise ValueError(f"not a duration: {text!r}")

    total = 0
    previous = -1
    for part in parts:
        number, unit = int(part[:-1]), part[-1]
        rank = _ORDER.index(unit)
        if rank <= previous:
            raise ValueError("units must appear in h, m, s order, at most once")
        previous = rank
        if unit != "h" and number > 59:
            raise ValueError(f"{unit} part out of range: {number}")
        total += number * _UNITS[unit]
    return total
