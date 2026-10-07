import unittest

from src.formatter import discounted


class FormatterTests(unittest.TestCase):
    def test_whole_percent(self):
        self.assertEqual(discounted(100.0, 10), 90.0)

    def test_discount_truncates(self):
        # The reviewer who wrote this expects the discount to be truncated.
        # 2.5% of 9.80 is 24.5 cents, so truncating leaves 9.80 - 0.24 = 9.56.
        self.assertEqual(discounted(9.80, 2.5), 9.56)


if __name__ == "__main__":
    unittest.main()
