#!/usr/bin/env python3
"""Hidden happy-path checks for t03. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.app import load_settings  # noqa: E402
from src.config import parse_config  # noqa: E402

GOOD = [
    ("host = db1\nport = 5432\n", {"host": "db1", "port": "5432"}),
    ("# comment\n\n   a = 1   \n", {"a": "1"}),
    ("url = http://x/?a=b\n", {"url": "http://x/?a=b"}),
    ("name =\n", {"name": ""}),
    ("a=b=c\n", {"a": "b=c"}),
    ("", {}),
    ("   \n\n# only comments\n", {}),
]

failures = []
for text, want in GOOD:
    try:
        got = parse_config(text)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"valid text {text!r} raised {type(exc).__name__}: {exc}")
    else:
        if got != want:
            failures.append(f"parse_config({text!r}) = {got!r}, want {want!r}")

settings = [
    ("a=1\n", {"a": "1", "name": "unnamed"}),
    ("name = x\na = 1\n", {"name": "x", "a": "1"}),
]
for text, want in settings:
    try:
        got = load_settings(text)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"load_settings({text!r}) raised {type(exc).__name__}: {exc}")
    else:
        if got != want:
            failures.append(f"load_settings({text!r}) = {got!r}, want {want!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
