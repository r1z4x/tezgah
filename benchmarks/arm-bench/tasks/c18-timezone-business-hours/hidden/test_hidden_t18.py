import datetime as dt
import unittest

from inventory.clock import is_business_hours


def aware(year, month, day, hour, minute=0):
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.timezone(dt.timedelta(hours=3)))


class T18TimezoneAware(unittest.TestCase):
    def test_naive_is_rejected(self):
        with self.assertRaises(ValueError):
            is_business_hours(dt.datetime(2026, 1, 5, 10, 0))

    def test_weekday_business_hours(self):
        self.assertTrue(is_business_hours(aware(2026, 1, 5, 10, 0)))

    def test_weekday_outside_hours(self):
        self.assertFalse(is_business_hours(aware(2026, 1, 5, 18, 0)))

    def test_weekend(self):
        self.assertFalse(is_business_hours(aware(2026, 1, 3, 10, 0)))


if __name__ == "__main__":
    unittest.main()
