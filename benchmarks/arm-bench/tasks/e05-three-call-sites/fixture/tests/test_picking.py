import unittest

from src.picking import cases_to_pick


class CasesToPickTests(unittest.TestCase):
    def test_one_full_case(self):
        self.assertEqual(cases_to_pick(12), 1)

    def test_a_whole_number_of_cases(self):
        self.assertEqual(cases_to_pick(36), 3)

    def test_nothing_to_pick(self):
        self.assertEqual(cases_to_pick(0), 0)


if __name__ == "__main__":
    unittest.main()
