import unittest

from invoice.tax import invoice_tax


def line(amount, rate, kind="goods"):
    return {"amount": amount, "rate": rate, "kind": kind}


class InvoiceTax(unittest.TestCase):
    def test_a_single_line(self):
        self.assertEqual(invoice_tax([line("100.00", "5")]), 500)

    def test_invoice_4471_rounds_per_line(self):
        # 70.35c twice: 70 + 70, not round(140.7)
        self.assertEqual(invoice_tax([line("10.05", "7"), line("10.05", "7")]), 140)


if __name__ == "__main__":
    unittest.main()
