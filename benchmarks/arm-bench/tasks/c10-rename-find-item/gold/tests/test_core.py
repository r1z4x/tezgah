import unittest

from inventory.core import apply_discount, calc_total, lookup_item


class CoreTests(unittest.TestCase):
    def test_calc_total(self):
        self.assertEqual(calc_total([{"price": 1.5}, {"price": 2.5}]), 4.0)

    def test_apply_discount_round_numbers(self):
        self.assertEqual(apply_discount(100.0, 10), 90.0)

    def test_lookup_item(self):
        items = [{"name": "a", "price": 1.0}, {"name": "b", "price": 2.0}]
        self.assertEqual(lookup_item(items, "b")["price"], 2.0)
        self.assertIsNone(lookup_item(items, "z"))


if __name__ == "__main__":
    unittest.main()
