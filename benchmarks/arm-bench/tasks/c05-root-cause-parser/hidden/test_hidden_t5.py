import unittest

from inventory.parsing import parse_quantity


class T5RootCause(unittest.TestCase):
    def test_zero_width_space(self):
        self.assertEqual(parse_quantity("12\u200b"), 12)

    def test_leading_bom(self):
        self.assertEqual(parse_quantity("\ufeff7"), 7)


if __name__ == "__main__":
    unittest.main()
