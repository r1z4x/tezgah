import unittest

from billing.discount import discount_cents
from billing.invoice import line_total_cents
from billing.money import to_cents


class MoneyTests(unittest.TestCase):
    def test_to_cents_rounds_half_up(self):
        self.assertEqual(to_cents(0.125), 13)
        self.assertEqual(to_cents(4.35), 435)


class InvoiceTests(unittest.TestCase):
    def test_whole_amount(self):
        self.assertEqual(line_total_cents(2.0, 3), 600)

    def test_line_total_is_not_a_cent_short(self):
        # 2 x 4.35 is 8.70; the float product times 100 is 869.999...
        self.assertEqual(line_total_cents(4.35, 2), 870)


class DiscountTests(unittest.TestCase):
    def test_ten_percent(self):
        self.assertEqual(discount_cents(4.35, 10), 44)


if __name__ == "__main__":
    unittest.main()
