import unittest
from datetime import date

from fx.convert import to_eur
from fx.model import Txn


class ConvertTests(unittest.TestCase):
    def test_euro_is_unchanged(self):
        self.assertEqual(to_eur(Txn(12.5, "EUR", date(2026, 1, 5))), 12.5)

    def test_uses_the_rate_of_the_transaction_day(self):
        # Published 2026-01-05: 0.91. A later rate must not be used.
        self.assertEqual(to_eur(Txn(100, "USD", date(2026, 1, 5))), 91.0)


if __name__ == "__main__":
    unittest.main()
