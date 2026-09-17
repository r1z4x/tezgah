#!/usr/bin/env python3
"""The hold ops puts on a card when a member changes plan mid-cycle.

Run from the repository root:

    python3 -m scripts.hold_budget

The hold covers the days the member still uses before the next cycle starts,
and it is released when the charge is captured.
"""

from src.proration import prorated_cents


def hold_cents(monthly_cents, days):
    """Return the hold for `days` of a cycle, in whole cents.

    A hold must not cover more than the exact share, so this asks the shared
    helper for the dropped part of a cent rather than the rounded-up charge.
    """
    return prorated_cents(monthly_cents, days, round_up=False)


if __name__ == "__main__":
    for days in (7, 13, 29, 30):
        print("%2d days: hold %d" % (days, hold_cents(1250, days)))
