import unittest

from inventory.textnorm import normalize_name


class T16UnicodeNormalization(unittest.TestCase):
    def test_composed_and_decomposed_match(self):
        composed = "Caf\u00e9"
        decomposed = "Cafe\u0301"
        self.assertEqual(normalize_name(decomposed), normalize_name(composed))
        self.assertEqual(normalize_name(decomposed), "caf\u00e9")

    def test_inner_whitespace_collapsed(self):
        self.assertEqual(normalize_name("  a   b  "), "a b")

    def test_lowercased(self):
        self.assertEqual(normalize_name("EMLAK"), "emlak")


if __name__ == "__main__":
    unittest.main()
