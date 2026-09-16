import unittest

from inventory.pricing import line_total
from inventory.report import summary


class ReportTests(unittest.TestCase):
    def test_line_total(self):
        self.assertEqual(line_total({"quantity": 2, "unit_price": 3.0}), 6.0)

    def test_summary(self):
        self.assertTrue(
            summary([{"price": 1.0}, {"price": 2.0}]).startswith("items=2 total=3.00")
        )


if __name__ == "__main__":
    unittest.main()
