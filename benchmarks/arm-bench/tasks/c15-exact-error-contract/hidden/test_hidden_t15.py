import unittest

from inventory.errors import InventoryError, require_positive


class T15ErrorContract(unittest.TestCase):
    def test_accepts_positive(self):
        self.assertEqual(require_positive(3, "qty"), 3)

    def test_raises_domain_error(self):
        with self.assertRaises(InventoryError):
            require_positive(0, "qty")

    def test_exact_message(self):
        try:
            require_positive(-1, "qty")
        except InventoryError as exc:
            self.assertEqual(str(exc), "qty must be positive")
        else:
            self.fail("InventoryError not raised")


if __name__ == "__main__":
    unittest.main()
