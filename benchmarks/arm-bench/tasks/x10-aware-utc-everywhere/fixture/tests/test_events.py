import unittest
from datetime import datetime, timedelta, timezone

from events.log import stamp
from events.schedule import next_sweep


class StampTests(unittest.TestCase):
    def test_stamp_is_aware_utc(self):
        self.assertIs(stamp().tzinfo, timezone.utc)

    def test_stamp_is_now(self):
        delta = abs(stamp() - datetime.now(timezone.utc))
        self.assertLess(delta, timedelta(seconds=5))


class ScheduleTests(unittest.TestCase):
    def test_next_quarter_hour(self):
        now = datetime(2026, 1, 5, 9, 37, 12, tzinfo=timezone.utc)
        self.assertEqual(next_sweep(now), datetime(2026, 1, 5, 9, 45, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
