import unittest

from inventory.search import find_by_prefix


class T17CaseInsensitiveSearch(unittest.TestCase):
    def test_case_insensitive(self):
        items = [{"name": "Apple"}, {"name": "apricot"}, {"name": "Banana"}]
        self.assertEqual(find_by_prefix(items, "ap"), ["Apple", "apricot"])

    def test_prefix_is_normalized_too(self):
        items = [{"name": "Apple"}]
        self.assertEqual(find_by_prefix(items, "AP"), ["Apple"])

    def test_no_match(self):
        self.assertEqual(find_by_prefix([{"name": "a"}], "z"), [])


if __name__ == "__main__":
    unittest.main()
