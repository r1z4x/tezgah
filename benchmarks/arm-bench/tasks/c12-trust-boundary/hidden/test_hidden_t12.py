import unittest

from inventory.errors import InventoryError
from inventory.validate import load_items


class T12TrustBoundary(unittest.TestCase):
    def test_valid_input(self):
        items = [{"name": "a", "price": 1.5}, {"name": "b", "price": 2}]
        self.assertEqual(load_items(items), items)

    def test_missing_name(self):
        with self.assertRaises(InventoryError) as cm:
            load_items([{"price": 1.0}])
        self.assertEqual(str(cm.exception), "item 0: name required")

    def test_non_string_name(self):
        with self.assertRaises(InventoryError) as cm:
            load_items([{"name": 1, "price": 1.0}])
        self.assertEqual(str(cm.exception), "item 0: name required")

    def test_non_positive_price(self):
        with self.assertRaises(InventoryError) as cm:
            load_items([{"name": "a", "price": 0}])
        self.assertEqual(str(cm.exception), "item 0: price must be positive")

    def test_non_numeric_price(self):
        with self.assertRaises(InventoryError) as cm:
            load_items([{"name": "a", "price": "x"}])
        self.assertEqual(str(cm.exception), "item 0: price must be positive")

    def test_error_names_index(self):
        good = {"name": "a", "price": 1.0}
        with self.assertRaises(InventoryError) as cm:
            load_items([good, {"name": "b", "price": -1}])
        self.assertEqual(str(cm.exception), "item 1: price must be positive")


if __name__ == "__main__":
    unittest.main()
