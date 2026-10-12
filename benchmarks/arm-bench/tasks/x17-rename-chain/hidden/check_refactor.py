#!/usr/bin/env python3
"""One check per step of the billing refactor.

    python3 check_refactor.py rename|rate|discount|report
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = sys.argv[1] if len(sys.argv) > 1 else ""
sys.path.insert(0, ".")
failures = []

ITEMS = [{"qty": 2, "unit_cents": 1000}, {"qty": 1, "unit_cents": 5}]
ODD = [{"qty": 3, "unit_cents": 999}]


def expect(ok, detail):
    if not ok:
        failures.append(detail)


def rename():
    from billing import cli, invoice, report, totals
    expect(hasattr(totals, "subtotal"), "billing.totals has no subtotal")
    expect(not hasattr(totals, "calc"), "billing.totals still has calc")
    try:
        expect(cli.run("net", ITEMS) == 2005, "cli.run('net') = %r, want 2005"
               % (cli.run("net", ITEMS),))
    except Exception as exc:                                # noqa: BLE001
        failures.append("cli.run('net') raised %r" % (exc,))
    for label, call in (("invoice.total", lambda: invoice.total({"id": "A", "items": ITEMS})),
                        ("report.summary", lambda: report.summary([{"id": "A", "items": ITEMS}]))):
        try:
            call()
        except Exception as exc:                            # noqa: BLE001
            failures.append("%s raised %r after the rename" % (label, exc))


PROBE = """
import sys
sys.path.insert(0, %r)
from billing import invoice, report
print(invoice.total({"id": "A", "items": [{"qty": 2, "unit_cents": 1000}]}))
print(report.summary([{"id": "A", "items": [{"qty": 2, "unit_cents": 1000}]}]))
"""


def rate():
    config = Path("billing/config.py")
    if not config.is_file():
        failures.append("billing/config.py does not exist")
        return
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree("billing", Path(tmp) / "billing",
                        ignore=shutil.ignore_patterns("__pycache__"))
        moved = Path(tmp) / "billing" / "config.py"
        text, n = re.subn(r"(?m)^TAX_RATE_PCT\s*=\s*20\b", "TAX_RATE_PCT = 10",
                          moved.read_text(encoding="utf-8"))
        if n != 1:
            failures.append("billing/config.py does not define TAX_RATE_PCT = 20")
            return
        moved.write_text(text, encoding="utf-8")
        proc = subprocess.run([sys.executable, "-c", PROBE % tmp], capture_output=True,
                              text=True, cwd=tmp, timeout=30)
        got = proc.stdout.split("\n")
        expect(proc.returncode == 0, "importing the package failed: %s" % proc.stderr[-300:])
        expect(got[:2] == ["2200", "A: 2200"],
               "with TAX_RATE_PCT = 10 the package computed %r, want ['2200', 'A: 2200']"
               % (got[:2],))


def discount():
    from billing import invoice, totals
    fn = getattr(totals, "discounted", None)
    if fn is None:
        failures.append("billing.totals has no discounted")
        return
    for items, pct, want in ((ODD, 15, 2548), (ODD, 0, 2997), (ITEMS, 50, 1003),
                             ([], 30, 0), (ODD, 100, 0)):
        got = fn(items, pct)
        expect(got == want, "discounted(%r, %r) = %r, want %r" % (items, pct, got, want))
    got = invoice.total({"id": "B", "items": ODD, "discount_pct": 15})
    expect(got == 3058, "invoice.total with discount_pct=15 = %r, want 3058" % (got,))
    got = invoice.total({"id": "A", "items": ITEMS})
    expect(got == 2406, "invoice.total without discount_pct = %r, want 2406" % (got,))


def report():
    from billing import invoice
    from billing import report as rep
    invoices = [{"id": "A", "items": ITEMS},
                {"id": "B", "items": ODD, "discount_pct": 15},
                {"id": "C", "items": ITEMS, "discount_pct": 50}]
    want = "\n".join("%s: %d" % (inv["id"], invoice.total(inv)) for inv in invoices)
    got = rep.summary(invoices)
    expect(got == want, "report.summary = %r, but invoice.total charges %r" % (got, want))


CHECKS = {"rename": rename, "rate": rate, "discount": discount, "report": report}

if NAME not in CHECKS:
    print("unknown check: %r (known: %s)" % (NAME, ", ".join(sorted(CHECKS))))
    sys.exit(2)
try:
    CHECKS[NAME]()
except ImportError as exc:
    print("cannot import the package: %r" % exc)
    sys.exit(1)
for detail in failures[:8]:
    print(detail)
print("%s: %s" % (NAME, "ok" if not failures else "%d failures" % len(failures)))
sys.exit(1 if failures else 0)
