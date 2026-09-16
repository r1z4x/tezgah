import unittest
from datetime import datetime, timezone

from src.clock import is_open


class ClockTests(unittest.TestCase):
    def test_midday_weekday_is_open(self):
        moment = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(is_open(moment))

    def test_late_evening_is_closed(self):
        moment = datetime(2026, 9, 16, 22, 0, tzinfo=timezone.utc)
        self.assertFalse(is_open(moment))

    def test_weekend_is_closed(self):
        moment = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
        self.assertFalse(is_open(moment))

    def test_window_is_read_in_the_moments_own_timezone(self):
        # 14:00 UTC is inside the window where the moment says it is, whatever
        # clock the machine running this test keeps.
        moment = datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc)
        self.assertTrue(is_open(moment))


if __name__ == "__main__":
    unittest.main()
