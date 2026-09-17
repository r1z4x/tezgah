import unittest

from src.report import render


class PlainReportTests(unittest.TestCase):
    def test_every_line_carries_its_total(self):
        self.assertEqual(render(), "A1 x2 2400\nB2 x3 1500\nC3 x4 1000")


class MemberReportTests(unittest.TestCase):
    def test_every_line_carries_the_discounted_total(self):
        self.assertEqual(render(member=True), "A1 x2 2160\nB2 x3 1350\nC3 x4 900")


if __name__ == "__main__":
    unittest.main()
