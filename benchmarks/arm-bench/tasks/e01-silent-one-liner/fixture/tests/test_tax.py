import unittest

from src.tax import tax_cents


class TaxTests(unittest.TestCase):
    def test_seven_percent_of_a_round_cart(self):
        self.assertEqual(tax_cents(1000), 70)

    def test_tax_rounds_down(self):
        # 7% of 1250 is 87.5 cents, and the odd half cent is not charged.
        self.assertEqual(tax_cents(1250), 87)

    def test_tax_rounds_down_on_another_cart(self):
        # 7% of 1150 is 80.5 cents, same rule.
        self.assertEqual(tax_cents(1150), 80)

    def test_empty_cart_has_no_tax(self):
        self.assertEqual(tax_cents(0), 0)


if __name__ == "__main__":
    unittest.main()
