import unittest

from src.catalog import Catalog
from src.store import Store


class CatalogTests(unittest.TestCase):
    def test_set_price_writes_and_saves(self):
        store = Store()
        catalog = Catalog(store)
        catalog.set_price("BOLT-M6", 130)
        self.assertEqual(catalog.price("BOLT-M6"), 130)
        self.assertEqual(store.saves, 1)
        self.assertEqual(Catalog(store).price("BOLT-M6"), 130)

    def test_unknown_sku_is_refused(self):
        with self.assertRaises(KeyError):
            Catalog().set_price("NOPE", 10)

    def test_negative_price_is_refused(self):
        with self.assertRaises(ValueError):
            Catalog().set_price("BOLT-M6", -1)
