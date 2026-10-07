import unittest

from src.proration import prorated_cents


class ProrationTests(unittest.TestCase):
    def test_a_whole_cycle_is_the_plan_price(self):
        self.assertEqual(prorated_cents(1250, 30), 1250)
        self.assertEqual(prorated_cents(1250, 0), 0)

    def test_a_part_cycle_rounds_up(self):
        # 13/30 of 1250 is 541.66... cents, and the part of a cent goes to the
        # member rather than coming off what they are charged.
        self.assertEqual(prorated_cents(1250, 13), 542)

    def test_another_part_cycle_rounds_up(self):
        # 7/30 of 1250 is 291.66... cents, same rule.
        self.assertEqual(prorated_cents(1250, 7), 292)


if __name__ == "__main__":
    unittest.main()
