#!/usr/bin/env python3
"""Every conversion in fx uses the rate of the transaction's own day.

The prompt makes `on` a required keyword of fetch_rate and asks every caller to
pass the transaction's day. Callers reach fetch_rate by name, through a module
attribute, through an import alias, through the providers.SOURCES table (whose
docstring says every source shares fetch_rate's arguments) and through a
functools.partial; each is driven with transactions from days whose rate is not
the latest one.
"""
import sys
from datetime import date

sys.path.insert(0, ".")

failures = []
MON, TUE, SAT = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 10)


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def attempt(label, call):
    try:
        return call()
    except Exception as exc:
        failures.append("%s raised %r" % (label, exc))


def main():
    from fx import batch, ledger, pricing, providers, rates, report
    from fx.convert import to_eur
    from fx.model import Txn

    try:
        rates.fetch_rate("USD")
        failures.append("fetch_rate without `on` did not raise TypeError")
    except TypeError:
        pass
    expect(attempt("fetch_rate(USD, on=MON)", lambda: rates.fetch_rate("USD", on=MON)),
           0.91, "fetch_rate(USD, on=2026-01-05)")
    expect(attempt("fetch_rate(USD, on=SAT)", lambda: rates.fetch_rate("USD", on=SAT)),
           0.97, "fetch_rate(USD, on=2026-01-10)")

    usd = Txn(100, "USD", MON)
    gbp = Txn(10, "GBP", TUE)
    expect(attempt("to_eur", lambda: to_eur(usd)), 91.0, "to_eur(100 USD on 01-05)")
    expect(attempt("total_eur", lambda: report.total_eur([usd, gbp])), 102.7,
           "total_eur(100 USD on 01-05, 10 GBP on 01-06)")
    expect(attempt("post", lambda: ledger.post(usd)),
           {"day": "2026-01-05", "rate": 0.91, "eur": 91.0}, "post(100 USD on 01-05)")
    expect(attempt("convert_all ecb", lambda: batch.convert_all([usd, gbp])),
           [91.0, 11.7], "convert_all(ecb)")
    expect(attempt("convert_all fixed",
                   lambda: batch.convert_all([Txn(100, "BGN", MON)], "fixed")),
           [51.13], "convert_all(fixed)")
    expect(attempt("fixed_rate", lambda: providers.fixed_rate("BGN", on=MON)),
           0.5113, "fixed_rate(BGN, on=2026-01-05)")
    expect(attempt("invoice_line", lambda: pricing.invoice_line(gbp)),
           "2026-01-06 11.70 EUR @ 1.1700", "invoice_line(10 GBP on 01-06)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % exc)
    for detail in failures:
        print(detail)
    print("rate day: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
