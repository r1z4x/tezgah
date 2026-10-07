#!/usr/bin/env python3
"""Hidden duration checks for t05. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.duration import parse_duration  # noqa: E402

GOOD = [
    ("0s", 0),
    ("45s", 45),
    ("2m", 120),
    ("1h", 3600),
    ("1h30m", 5400),
    ("1h30m45s", 5445),
    ("0h0m0s", 0),
    ("59m59s", 3599),
    ("12h0m1s", 43201),
]

BAD = [
    ("", "empty string"),
    ("   ", "whitespace only"),
    ("1h30", "trailing number without a unit"),
    ("30m1h", "units out of order"),
    ("1h1h", "repeated unit"),
    ("1s2m", "units out of order"),
    ("5x", "unknown unit"),
    ("abc", "no digits at all"),
    ("90m", "minutes out of range"),
    ("1h90s", "seconds out of range"),
    ("1H30M", "uppercase units"),
    ("1h 30m", "inner whitespace"),
    ("1.5h", "fractional part"),
    (None, "not a string"),
    (123, "an int instead of a string"),
]

failures = []

for text, want in GOOD:
    try:
        got = parse_duration(text)
    except Exception as exc:  # noqa: BLE001 - any exception is a failure here
        failures.append(f"valid duration {text!r} raised {type(exc).__name__}: {exc}")
    else:
        if got != want or not isinstance(got, int) or isinstance(got, bool):
            failures.append(f"parse_duration({text!r}) returned {got!r}, want {want!r}")

for text, label in BAD:
    try:
        got = parse_duration(text)
    except ValueError:
        pass
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{label}: raised {type(exc).__name__}, expected ValueError")
    else:
        failures.append(f"{label}: returned {got!r}, expected ValueError")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
