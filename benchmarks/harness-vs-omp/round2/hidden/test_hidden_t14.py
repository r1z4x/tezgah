import unittest

from inventory.ledger import Ledger


class T14SharedState(unittest.TestCase):
    def test_instances_are_independent(self):
        first = Ledger()
        first.add(10)
        second = Ledger()
        self.assertEqual(second.entries, [])
        self.assertEqual(second.total(), 0)

    def test_total_and_chaining(self):
        ledger = Ledger()
        ledger.add(1).add(2)
        self.assertEqual(ledger.total(), 3)


if __name__ == "__main__":
    unittest.main()
