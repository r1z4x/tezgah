import unittest

from inventory.report import summary


class T6ScopedSummary(unittest.TestCase):
    def test_summary_with_tax(self):
        self.assertEqual(
            summary([{"price": 1.0}, {"price": 2.0}]),
            "items=2 total=3.00 tax=3.60",
        )


if __name__ == "__main__":
    unittest.main()
