import unittest

from src.feed import write_feed
from src.reader import read_feed
from src.reconcile import archived, differences


class FeedTests(unittest.TestCase):
    def test_line_format(self):
        self.assertEqual(
            write_feed([{"sku": "NUT-M6", "name": "Hex nut M6", "qty": 3, "price_cents": 4}]),
            "NUT-M6|3|4\n")

    def test_reader_undoes_escapes(self):
        self.assertEqual(read_feed("A\\|B|1|2\n")[0]["sku"], "A|B")

    def test_reconcile_an_archived_feed(self):
        self.assertEqual(differences(archived("2026-09-30"), {"BOLT-M6": 1180, "NUT-M6": 2950, "SHELF-1": 40}),
                         {"SHELF-1": -1})
