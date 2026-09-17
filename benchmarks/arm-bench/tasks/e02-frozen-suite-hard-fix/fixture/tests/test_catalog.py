import unittest

from src.catalog import sorted_names
from src.report import render
from src.textfold import fold


class FoldTests(unittest.TestCase):
    def test_plain_lowercase_folds_to_itself(self):
        self.assertEqual(fold("beta"), "beta")

    def test_case_is_folded_away(self):
        self.assertEqual(fold("Beta"), "beta")


class CatalogueTests(unittest.TestCase):
    def test_empty_listing_is_empty(self):
        self.assertEqual(sorted_names([]), [])

    def test_plain_ascii_is_ordered_by_the_folded_key(self):
        self.assertEqual(sorted_names(["beta", "Alpha"]), ["Alpha", "beta"])

    def test_report_joins_in_listing_order(self):
        self.assertEqual(render(["beta", "Alpha"]), "Alpha | beta")

    def test_listing_order_follows_the_documented_fold_and_tie_break(self):
        # The export leaves double spaces in some names, and two of these fold
        # to the same key, so this row covers the fold and the tie-break.
        names = ["Éclair", "anchor", "The  Anchor", "banana"]
        self.assertEqual(sorted_names(names),
                         ["The  Anchor", "anchor", "banana", "Éclair"])


if __name__ == "__main__":
    unittest.main()
