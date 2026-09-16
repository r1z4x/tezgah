import unittest

from inventory.core import apply_discount, compute_total, find_item


class CoreTests(unittest.TestCase):
    def test_compute_total(self):
        self.assertEqual(compute_total([{"price": 1.5}, {"price": 2.5}]), 4.0)

    def test_apply_discount_round_numbers(self):
        self.assertEqual(apply_discount(100.0, 10), 90.0)

    def test_find_item(self):
        items = [{"name": "a", "price": 1.0}, {"name": "b", "price": 2.0}]
        self.assertEqual(find_item(items, "b")["price"], 2.0)
        self.assertIsNone(find_item(items, "z"))


if __name__ == "__main__":
    unittest.main()
