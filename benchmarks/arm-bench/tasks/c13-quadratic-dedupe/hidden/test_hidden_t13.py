import time
import unittest

from inventory.dedupe import unique


class T13LinearDedupe(unittest.TestCase):
    def test_order_and_uniqueness(self):
        self.assertEqual(unique([3, 1, 3, 2, 1]), [3, 1, 2])
        self.assertEqual(unique(["b", "a", "b"]), ["b", "a"])
        self.assertEqual(unique([]), [])

    def test_large_input_is_linear(self):
        data = list(range(20000)) * 2
        start = time.perf_counter()
        result = unique(data)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(result), 20000)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
