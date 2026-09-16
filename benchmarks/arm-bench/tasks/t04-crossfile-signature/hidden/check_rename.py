#!/usr/bin/env python3
"""Hidden rename checks for t04. Run with the candidate tree as the cwd."""
import os
import sys

sys.path.insert(0, os.getcwd())

from src.formatting import format_row  # noqa: E402
from src.invoices import render_invoice_table  # noqa: E402
from src.orders import render_order_table  # noqa: E402

failures = []

# The new keyword name must be accepted across the whole chain, and the value
# must reach the helper, so the width actually takes effect.
NEW_KEYWORD = [
    ("format_row directly", lambda: format_row(label="ab", columns=5, value=7), "ab=7 "),
    ("order caller", lambda: render_order_table([("ab", 7)], columns=5), ["ab=7 "]),
    ("invoice caller", lambda: render_invoice_table([("ab", 7)], columns=8), ["ab=7    "]),
]
for name, call, want in NEW_KEYWORD:
    try:
        got = call()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: columns= raised {type(exc).__name__}: {exc}")
    else:
        if got != want:
            failures.append(f"{name}: returned {got!r}, want {want!r}")

# The old keyword name must be gone, not aliased back into existence.
OLD_KEYWORD = [
    ("format_row directly", lambda: format_row(label="ab", width=5, value=7)),
    ("order caller", lambda: render_order_table([("ab", 7)], width=5)),
    ("invoice caller", lambda: render_invoice_table([("ab", 7)], width=5)),
]
for name, call in OLD_KEYWORD:
    try:
        got = call()
    except TypeError:
        pass
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: width= raised {type(exc).__name__}, expected TypeError")
    else:
        failures.append(f"{name}: width= still accepted, returned {got!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
