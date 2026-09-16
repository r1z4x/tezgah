import unittest

from inventory.paginate import page_bounds, page_count


class T8OffByOne(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(page_bounds(25, 10, 1), (0, 10))

    def test_second_page(self):
        self.assertEqual(page_bounds(25, 10, 2), (10, 20))

    def test_last_page_clamped(self):
        self.assertEqual(page_bounds(25, 10, 3), (20, 25))

    def test_page_count(self):
        self.assertEqual(page_count(25, 10), 3)
        self.assertEqual(page_count(30, 10), 3)


if __name__ == "__main__":
    unittest.main()
