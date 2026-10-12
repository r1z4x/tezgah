import unittest

from league.table import standings

EXAMPLE = [
    ("Ajax", "Benfica", 1, 1),
    ("Ajax", "Celtic", 2, 0),
    ("Benfica", "Celtic", 2, 0),
    ("Celtic", "Dukla", 1, 0),
]


class Standings(unittest.TestCase):
    def test_the_spec_example(self):
        self.assertEqual(standings(EXAMPLE), [
            (1, "Ajax", 2, 4, 2, 3),
            (1, "Benfica", 2, 4, 2, 3),
            (3, "Celtic", 3, 3, -3, 1),
            (4, "Dukla", 1, 0, -1, 0),
        ])


if __name__ == "__main__":
    unittest.main()
