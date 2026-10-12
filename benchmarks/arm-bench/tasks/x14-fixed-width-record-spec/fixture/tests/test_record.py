import unittest

from bank.record import format_record


class FormatRecord(unittest.TestCase):
    def test_a_plain_payment(self):
        line = format_record("4711", "Ada Lovelace", 12345)
        self.assertEqual(line, "00004711Ada Lovelace              123.45\r\n")

    def test_line_17_a_long_name_keeps_the_width(self):
        line = format_record("90210", "Bartholomew Featherstonehaugh", 500)
        self.assertEqual(len(line.rstrip("\r\n")), 40)


if __name__ == "__main__":
    unittest.main()
