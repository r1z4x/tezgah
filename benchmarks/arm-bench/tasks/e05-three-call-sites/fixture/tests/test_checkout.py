import unittest

from src.checkout import billable_cases


class BillableCasesTests(unittest.TestCase):
    def test_a_count_that_fills_its_cases_exactly(self):
        self.assertEqual(billable_cases(24), 2)

    def test_a_count_that_does_not_fill_a_case_is_billed_for_it(self):
        # 18 units do not fit in one case, so the customer is billed for two.
        self.assertEqual(billable_cases(18), 2)

    def test_no_units_is_no_cases(self):
        self.assertEqual(billable_cases(0), 0)


if __name__ == "__main__":
    unittest.main()
