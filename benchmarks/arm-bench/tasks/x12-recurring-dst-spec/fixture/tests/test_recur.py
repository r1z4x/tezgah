import unittest
from datetime import date, datetime, time, timezone

from cal.recur import occurrences

UTC = timezone.utc


class Occurrences(unittest.TestCase):
    def test_a_winter_week(self):
        got = occurrences(date(2026, 1, 1), time(9, 0), "America/New_York",
                          datetime(2026, 1, 5, 0, 0, tzinfo=UTC),
                          datetime(2026, 1, 6, 23, 0, tzinfo=UTC))
        self.assertEqual(got, [datetime(2026, 1, 5, 14, 0, tzinfo=UTC),
                               datetime(2026, 1, 6, 14, 0, tzinfo=UTC)])

    def test_ticket_212_window_end_is_exclusive(self):
        got = occurrences(date(2026, 1, 1), time(9, 0), "America/New_York",
                          datetime(2026, 1, 5, 14, 0, tzinfo=UTC),
                          datetime(2026, 1, 7, 14, 0, tzinfo=UTC))
        self.assertEqual(got, [datetime(2026, 1, 5, 14, 0, tzinfo=UTC),
                               datetime(2026, 1, 6, 14, 0, tzinfo=UTC)])


if __name__ == "__main__":
    unittest.main()
