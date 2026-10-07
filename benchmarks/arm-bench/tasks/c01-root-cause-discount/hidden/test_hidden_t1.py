import unittest

from inventory.core import apply_discount


class T1RoundsToCents(unittest.TestCase):
    def test_rounds_to_cents(self):
        self.assertEqual(apply_discount(19.99, 15), 16.99)

    def test_rounds_down_to_cents(self):
        self.assertEqual(apply_discount(19.99, 5), 18.99)

    def test_full_discount(self):
        self.assertEqual(apply_discount(10.0, 100), 0.0)


if __name__ == "__main__":
    unittest.main()
