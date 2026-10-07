import unittest

from money.round import apply_discount


class ApplyDiscount(unittest.TestCase):
    def test_a_plain_percentage(self):
        self.assertEqual(apply_discount(100.0, 10), 90.0)

    def test_a_fractional_cent(self):        # 19.99 * 33.3% = 665.667c
        self.assertEqual(apply_discount(19.99, 33.3), 13.33)


if __name__ == "__main__":
    unittest.main()
