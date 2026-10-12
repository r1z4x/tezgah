import unittest

from src.catalog import Catalog
from src.quotes import QuoteService


class QuoteTests(unittest.TestCase):
    def test_quote_adds_vat(self):
        self.assertEqual(QuoteService(Catalog()).quote("BOLT-M6"), 144)

    def test_quote_follows_set_price(self):
        catalog = Catalog()
        quotes = QuoteService(catalog)
        self.assertEqual(quotes.quote("NUT-M6"), 48)
        catalog.set_price("NUT-M6", 50)
        self.assertEqual(quotes.quote("NUT-M6"), 60)
