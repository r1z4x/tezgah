import unittest

from src.charge import invoice_total_cents, partial_charge_cents


class PartialChargeTests(unittest.TestCase):
    def test_thirteen_days_of_a_twelve_fifty_plan(self):
        self.assertEqual(partial_charge_cents(1250, 13), 542)

    def test_a_whole_cycle_is_the_plan_price(self):
        self.assertEqual(partial_charge_cents(1250, 30), 1250)


class InvoiceTotalTests(unittest.TestCase):
    def test_the_invoice_adds_the_tax_to_the_charge(self):
        self.assertEqual(invoice_total_cents(1250, 13, tax_cents=87), 629)


if __name__ == "__main__":
    unittest.main()
