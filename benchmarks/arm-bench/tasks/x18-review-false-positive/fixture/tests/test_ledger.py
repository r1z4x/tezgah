import datetime
import unittest

from ledger.accounts import Account, transfer
from ledger.dates import month_end
from ledger.errors import LedgerError
from ledger.fx import convert
from ledger.money import percent_of, split
from ledger.parse import parse_amount


class DatesTest(unittest.TestCase):
    def test_month_end(self):
        self.assertEqual(month_end(2024, 2), datetime.date(2024, 2, 29))
        self.assertEqual(month_end(2023, 4), datetime.date(2023, 4, 30))


class MoneyTest(unittest.TestCase):
    def test_percent_rounds_half_up(self):
        self.assertEqual(percent_of(50, 1), 1)

    def test_even_split(self):
        self.assertEqual(split(100, 4), [25, 25, 25, 25])


class FxTest(unittest.TestCase):
    def test_settlement_rounds_half_to_even(self):
        # pinned by the settlement agreement (see the fx module docstring)
        self.assertEqual(convert(5, "0.5"), 2)
        self.assertEqual(convert(15, "0.5"), 8)
        self.assertEqual(convert(100, "1.2345"), 123)


class AccountTest(unittest.TestCase):
    def test_transfer_moves_money(self):
        a, b = Account("a", 100), Account("b")
        transfer(a, b, 40)
        self.assertEqual((a.balance, b.balance), (60, 40))

    def test_withdraw_refuses_overdraft(self):
        with self.assertRaises(LedgerError):
            Account("a", 10).withdraw(11)


class ParseTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_amount("12.50"), 1250)

    def test_garbage(self):
        with self.assertRaises(LedgerError):
            parse_amount("twelve")


if __name__ == "__main__":
    unittest.main()
