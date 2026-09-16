#!/usr/bin/env python3
"""Hidden behaviour checks for t04. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.formatting import format_row, pad  # noqa: E402
from src.invoices import render_invoice_table  # noqa: E402
from src.orders import render_order_table  # noqa: E402

failures = []


def check(label, call, want):
    try:
        got = call()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{label}: raised {type(exc).__name__}: {exc}")
    else:
        if got != want:
            failures.append(f"{label}: returned {got!r}, want {want!r}")


# `pad` is out of scope: its own keyword name and behaviour must be untouched.
check("pad positional", lambda: pad("ab", 5), "ab   ")
check("pad width=", lambda: pad("ab", width=5), "ab   ")
check("pad fill", lambda: pad("ab", 5, "-"), "ab---")
check("pad text= width=", lambda: pad(text="x", width=4), "x   ")

# The helper keeps its parameter order and its positional call path.
check("format_row positional", lambda: format_row("ab", 8, 7), "ab=7    ")

# Defaults survive the rename: 12 for orders, 16 for invoices.
check(
    "order default",
    lambda: render_order_table([("ab", 7), ("cdef", 12)]),
    ["ab=7".ljust(12), "cdef=12".ljust(12)],
)
check(
    "invoice default",
    lambda: render_invoice_table([("ab", 7), ("cdef", 12)]),
    ["ab=7".ljust(16), "cdef=12".ljust(16)],
)
check("callers, several rows", lambda: render_order_table([("a", 1), ("bb", 22)], columns=6), ["a=1".ljust(6), "bb=22".ljust(6)])
check("empty rows", lambda: render_invoice_table([]), [])

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
