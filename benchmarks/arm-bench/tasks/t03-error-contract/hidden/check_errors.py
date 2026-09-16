#!/usr/bin/env python3
"""Hidden error-contract checks for t03. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.config import parse_config  # noqa: E402

# (text, exact message the ValueError must carry)
CASES = [
    ("abc\n", "line 1: expected '=' in 'abc'"),
    ("  abc  \n", "line 1: expected '=' in 'abc'"),
    ("host=1\nabc\n", "line 2: expected '=' in 'abc'"),
    ("a=1\n\n   \n# note\nnope\n", "line 5: expected '=' in 'nope'"),
    ("a\n=1\n", "line 1: expected '=' in 'a'"),
    ("=7\n", "line 1: empty key in '=7'"),
    ("host = 1\n  = 7\n", "line 2: empty key in '= 7'"),
    ("# c\n\n   = 1\n", "line 3: empty key in '= 1'"),
    ("a=1\nb=2\na=3\n", "line 3: duplicate key 'a'"),
    ("host = 1\nother = 2\n   host = 3\n", "line 3: duplicate key 'host'"),
    ("# a=0\nx=1\ny=2\n  x = 3\n", "line 4: duplicate key 'x'"),
]

failures = []
for text, want in CASES:
    try:
        got = parse_config(text)
    except ValueError as exc:
        if str(exc) != want:
            failures.append(
                f"{text!r}: message is {str(exc)!r}, want {want!r}"
            )
    except Exception as exc:  # noqa: BLE001 - any non-ValueError is a failure
        failures.append(
            f"{text!r}: raised {type(exc).__name__}: {exc}, expected ValueError"
        )
    else:
        failures.append(f"{text!r}: returned {got!r}, expected ValueError {want!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
