import unittest

from inventory.format import labeled_row, tag


class T11SignatureChange(unittest.TestCase):
    def test_tag_default(self):
        self.assertEqual(tag("x"), "[x]")

    def test_tag_upper(self):
        self.assertEqual(tag("x", upper=True), "[X]")

    def test_labeled_row_uses_new_name(self):
        self.assertEqual(labeled_row("x", 2.5), "[x] 2.50")


if __name__ == "__main__":
    unittest.main()
