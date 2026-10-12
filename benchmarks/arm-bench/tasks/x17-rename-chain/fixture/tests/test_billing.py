import io
import unittest
from contextlib import redirect_stdout

from billing import cli, invoice, report

ITEMS = [{"qty": 2, "unit_cents": 1000}, {"qty": 1, "unit_cents": 5}]


class InvoiceTest(unittest.TestCase):
    def test_total_adds_tax(self):
        self.assertEqual(invoice.total({"id": "A", "items": ITEMS}), 2005 + 401)

    def test_tax_rounds_half_up(self):
        self.assertEqual(invoice.tax(5), 1)
        self.assertEqual(invoice.tax(2), 0)


class ReportTest(unittest.TestCase):
    def test_one_line_per_invoice(self):
        text = report.summary([{"id": "A", "items": ITEMS}, {"id": "B", "items": []}])
        self.assertEqual(text, "A: 2406\nB: 0")


class CliTest(unittest.TestCase):
    def test_count(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(["count", "2x1000", "1x5"]), 0)
        self.assertEqual(out.getvalue(), "3\n")

    def test_unknown_command(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["nope"]), 2)


if __name__ == "__main__":
    unittest.main()
