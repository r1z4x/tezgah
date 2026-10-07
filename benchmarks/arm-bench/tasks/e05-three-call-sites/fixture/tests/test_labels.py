import unittest

from src.labels import case_labels, shipping_weight_kg


class LabelsTests(unittest.TestCase):
    def test_labels_for_a_whole_number_of_cases(self):
        self.assertEqual(case_labels(24), 2)

    def test_weight_of_a_whole_number_of_cases(self):
        self.assertEqual(shipping_weight_kg(24), 16)

    def test_no_units_needs_no_labels(self):
        self.assertEqual(case_labels(0), 0)


if __name__ == "__main__":
    unittest.main()
