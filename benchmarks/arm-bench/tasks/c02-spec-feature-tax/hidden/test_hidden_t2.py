import unittest

from inventory.pricing import total_with_tax


class T2TotalWithTax(unittest.TestCase):
    def test_basic(self):
        items = [{"price": 10.0}, {"price": 5.5}]
        self.assertEqual(total_with_tax(items, 0.20), 18.6)

    def test_zero_rate(self):
        self.assertEqual(total_with_tax([{"price": 3.0}], 0.0), 3.0)

    def test_negative_rate_rejected(self):
        with self.assertRaises(ValueError):
            total_with_tax([{"price": 1.0}], -0.1)


if __name__ == "__main__":
    unittest.main()
