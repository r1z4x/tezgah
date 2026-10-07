import unittest

import inventory.report as report


class T10RenameMultiFile(unittest.TestCase):
    def test_describe_still_works(self):
        items = [{"name": "a", "price": 1.0}]
        self.assertEqual(report.describe(items, "a"), "a: 1.00")
        self.assertEqual(report.describe(items, "z"), "z: not found")


if __name__ == "__main__":
    unittest.main()
