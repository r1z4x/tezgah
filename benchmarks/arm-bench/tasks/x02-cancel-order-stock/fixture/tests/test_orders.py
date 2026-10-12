import unittest

from src.inventory import Inventory
from src.orders import OrderBook


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.receive("BOLT-M6", 10)
        self.book = OrderBook(self.inv)

    def test_place_and_ship(self):
        self.book.place("o1", "BOLT-M6", 3)
        self.book.ship("o1")
        self.assertEqual(self.inv.stock["BOLT-M6"], 7)
        self.assertEqual(self.book.orders["o1"].status, "shipped")

    def test_cancelled_units_go_back_on_the_shelf(self):
        self.book.place("o1", "BOLT-M6", 3)
        self.book.cancel("o1")
        self.assertEqual(self.book.orders["o1"].status, "cancelled")
        self.assertEqual(self.inv.stock["BOLT-M6"], 10)

    def test_a_shipped_order_cannot_be_cancelled(self):
        self.book.place("o1", "BOLT-M6", 3)
        self.book.ship("o1")
        with self.assertRaises(ValueError):
            self.book.cancel("o1")
