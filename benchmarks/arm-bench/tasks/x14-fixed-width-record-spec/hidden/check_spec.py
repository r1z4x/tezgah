#!/usr/bin/env python3
"""Grade `format_record` against bank/SPEC.md, one clause per argument.

  layout   the record frame: 40 characters, CRLF, the three columns, ASCII.
  name     rules 2-4: accents dropped, other non-ASCII as "?", a long name cut
           to 19 characters plus "~", None as spaces.
  amount   rule 5: sign, two decimals, zero and sub-unit amounts.
  overflow rules 1 and 6: a 9-digit account raises ValueError and a 13-character
           amount raises OverflowError; the widest amounts that fit are written.
"""
import sys

sys.path.insert(0, ".")

ROWS = {
    "layout": [
        (("4711", "Ada Lovelace", 12345), "00004711Ada Lovelace              123.45\r\n"),
        (("12345678", "X", 1), "12345678X                           0.01\r\n"),
        (("0", "", 0), "00000000                            0.00\r\n"),
    ],
    "name": [
        (("1", "Bartholomew Featherstonehaugh", 500),
         "00000001Bartholomew Feather~        5.00\r\n"),
        (("1", "Exactly Twenty Chars", 500),
         "00000001Exactly Twenty Chars        5.00\r\n"),
        (("1", "Müller Çağlar", 500), "00000001Muller Caglar               5.00\r\n"),
        (("1", "Łukasz Straße", 500), "00000001?ukasz Stra?e               5.00\r\n"),
        (("1", "Zoë Ångström-Bérénice Ü", 500),
         "00000001Zoe Angstrom-Bereni~        5.00\r\n"),
        (("1", None, 500), "00000001                            5.00\r\n"),
    ],
    "amount": [
        (("1", "A", -5), "00000001A                          -0.05\r\n"),
        (("1", "A", -12345), "00000001A                        -123.45\r\n"),
        (("1", "A", 100), "00000001A                           1.00\r\n"),
        (("1", "A", 0), "00000001A                           0.00\r\n"),
        (("1", "A", 123456789), "00000001A                     1234567.89\r\n"),
    ],
    "overflow": [
        (("1", "A", 99999999999), "00000001A                   999999999.99\r\n"),
        (("1", "A", -9999999999), "00000001A                   -99999999.99\r\n"),
        (("1", "A", 100000000000), OverflowError),
        (("1", "A", -10000000000), OverflowError),
        (("123456789", "A", 1), ValueError),
    ],
}


def main(clause):
    try:
        from bank.record import format_record
    except Exception as exc:                                  # noqa: BLE001
        print("cannot import format_record: %r" % exc)
        return 1
    bad = 0
    for args, want in ROWS[clause]:
        try:
            got = format_record(*args)
        except Exception as exc:                              # noqa: BLE001
            if isinstance(want, type) and isinstance(exc, want):
                continue
            print("raise  format_record%r: %r, want %r" % (args, exc, want))
            bad += 1
            continue
        if got != want:
            print("wrong  format_record%r\n   got %r\n  want %r" % (args, got, want))
            bad += 1
    print("%s: %d/%d rows" % (clause, len(ROWS[clause]) - bad, len(ROWS[clause])))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
