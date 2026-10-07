import unittest

import inventory.report as report


class T3Rename(unittest.TestCase):
    def test_report_still_works(self):
        self.assertEqual(report.summary([{"price": 1.0}, {"price": 2.0}]), "items=2 total=3.00")


if __name__ == "__main__":
    unittest.main()
