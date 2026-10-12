#!/usr/bin/env python3
"""One check per real finding of the ledger review.

    python3 check_review.py dates|split|history|parse|transfer

Finding 4 (fx rounding) is wrong: the fx module's docstring and the visible
suite pin round-half-to-even. Its check is the visible suite itself
(tests/test_ledger.py FxTest), so this script has no fx command.
"""
import datetime
import sys

NAME = sys.argv[1] if len(sys.argv) > 1 else ""
sys.path.insert(0, ".")
failures = []


def expect(ok, detail):
    if not ok:
        failures.append(detail)


def dates():
    from ledger.dates import month_end
    for year, month, want in ((2024, 12, datetime.date(2024, 12, 31)),
                              (2023, 12, datetime.date(2023, 12, 31)),
                              (2024, 11, datetime.date(2024, 11, 30)),
                              (2024, 1, datetime.date(2024, 1, 31))):
        try:
            got = month_end(year, month)
        except Exception as exc:                            # noqa: BLE001
            failures.append("month_end(%r, %r) raised %r" % (year, month, exc))
            continue
        expect(got == want, "month_end(%r, %r) = %r, want %r" % (year, month, got, want))


def split():
    from ledger.money import split as do_split
    for total, parts, want in ((100, 3, [34, 33, 33]), (7, 2, [4, 3]), (5, 5, [1] * 5),
                               (0, 3, [0, 0, 0]), (2, 4, [1, 1, 0, 0]), (100, 4, [25] * 4)):
        got = do_split(total, parts)
        expect(got == want, "split(%r, %r) = %r, want %r" % (total, parts, got, want))


def history():
    from ledger.accounts import Account
    acct = Account("a")
    acct.deposit(10)
    got = acct.history()
    got.append(("deposit", 999))
    expect(acct.history() == [("deposit", 10)],
           "appending to history()'s result changed the account: %r" % (acct.history(),))
    acct.withdraw(4)
    expect(acct.history() == [("deposit", 10), ("withdraw", 4)],
           "history() no longer records entries: %r" % (acct.history(),))


def parse():
    from ledger.errors import LedgerError
    from ledger.parse import parse_amount
    for text, want in (("1,234.50", 123450), ("12,000", 1200000), ("12.50", 1250),
                       ("-3", -300), (" 1,000.05 ", 100005)):
        try:
            got = parse_amount(text)
        except Exception as exc:                            # noqa: BLE001
            failures.append("parse_amount(%r) raised %r" % (text, exc))
            continue
        expect(got == want, "parse_amount(%r) = %r, want %r" % (text, got, want))
    for bad in ("twelve", "", "1.2.3"):
        try:
            got = parse_amount(bad)
            failures.append("parse_amount(%r) = %r, want LedgerError" % (bad, got))
        except LedgerError:
            pass
        except Exception as exc:                            # noqa: BLE001
            failures.append("parse_amount(%r) raised %r, want LedgerError" % (bad, exc))


def transfer():
    from ledger.accounts import Account, transfer as do_transfer
    from ledger.errors import LedgerError
    for amount in (50, 0, -5):
        src, dst = Account("src", 30), Account("dst", 7)
        before = (src.balance, dst.balance, list(src.history()), list(dst.history()))
        try:
            do_transfer(src, dst, amount)
            failures.append("transfer of %r out of 30 was not refused" % (amount,))
        except LedgerError:
            pass
        after = (src.balance, dst.balance, list(src.history()), list(dst.history()))
        expect(after == before, "refused transfer of %r changed the accounts: %r -> %r"
               % (amount, before, after))
    src, dst = Account("src", 30), Account("dst", 7)
    do_transfer(src, dst, 30)
    expect((src.balance, dst.balance) == (0, 37),
           "transfer of 30 left balances %r" % ((src.balance, dst.balance),))


CHECKS = {"dates": dates, "split": split, "history": history, "parse": parse,
          "transfer": transfer}

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
