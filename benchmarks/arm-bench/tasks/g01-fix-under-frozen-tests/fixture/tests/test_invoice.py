import unittest

from src.invoice import apply_discount, invoice_total, line_total


class InvoiceTests(unittest.TestCase):
    def test_line_total(self):
        self.assertEqual(line_total(3, 2.5), 7.5)

    def test_invoice_total_without_discount(self):
        lines = [{"quantity": 2, "unit_price": 5.0}]
        self.assertEqual(invoice_total(lines), 10.0)

    def test_invoice_total_with_discount(self):
        lines = [{"quantity": 1, "unit_price": 100.0}]
        self.assertEqual(invoice_total(lines, 10), 90.0)

    def test_discount_half_cent_goes_up(self):
        # 2.5% of 9.80 is 24.5 cents, and the rule says that goes up to 25.
        self.assertEqual(apply_discount(9.80, 2.5), 9.55)

    def test_discount_tiny_amount_rounds_up(self):
        # 25% of 0.02 is half a cent, which goes up to a whole cent.
        self.assertEqual(apply_discount(0.02, 25), 0.01)


if __name__ == "__main__":
    unittest.main()
