import unittest

from inventory.money import format_money


class T9FormatSpec(unittest.TestCase):
    def test_default_currency(self):
        self.assertEqual(format_money(12.34), "12.34 TL")

    def test_explicit_currency(self):
        self.assertEqual(format_money(5.0, "USD"), "5.00 USD")

    def test_negative(self):
        self.assertEqual(format_money(-3.5), "-3.50 TL")

    def test_rounding(self):
        self.assertEqual(format_money(1.005, "EUR"), "1.00 EUR")


if __name__ == "__main__":
    unittest.main()
