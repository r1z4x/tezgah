#!/usr/bin/env python3
"""Hidden boundary checks for t02. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.loader import load_amounts  # noqa: E402

GOOD = [
    ('{"amounts": []}', []),
    ('{"amounts": [0, 1, 25]}', [0, 1, 25]),
    ('{"amounts": [7], "note": "ignored"}', [7]),
]

BAD = [
    ("not json at all", "text that is not JSON"),
    ("[1, 2, 3]", "JSON array instead of object"),
    ('{}', "missing 'amounts'"),
    ('{"amounts": 5}', "'amounts' is not a list"),
    ('{"amounts": "12"}', "'amounts' is a string"),
    ('{"amounts": [1, -2]}', "negative element"),
    ('{"amounts": [1, true]}', "bool element"),
    ('{"amounts": [1, 2.0]}', "float element"),
    ('{"amounts": [1, "3"]}', "string element"),
]

failures = []

for text, want in GOOD:
    try:
        got = load_amounts(text)
    except Exception as exc:  # noqa: BLE001 - any exception is a failure here
        failures.append(f"valid payload {text!r} raised {type(exc).__name__}: {exc}")
    else:
        if got != want:
            failures.append(f"valid payload {text!r} returned {got!r}, want {want!r}")

for text, label in BAD:
    try:
        got = load_amounts(text)
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
