import unittest

from money.round import apply_discount


class ApplyDiscount(unittest.TestCase):
    def test_a_plain_percentage(self):
        self.assertEqual(apply_discount(100.0, 10), 90.0)

    def test_a_fractional_cent(self):        # 19.99 * 33.3% = 665.667c
        self.assertEqual(apply_discount(19.99, 33.3), 13.33)

    def test_a_rounding_fractional_cent(self):   # 12.50 * 5.5% = 68.75c
        self.assertEqual(apply_discount(12.50, 5.5), 11.81)


if __name__ == "__main__":
    unittest.main()
