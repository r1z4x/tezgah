import unittest

from src.inventory import Inventory, OutOfStock


class InventoryTests(unittest.TestCase):
    def test_reserve_moves_stock_to_reserved(self):
        inv = Inventory()
        inv.receive("BOLT-M6", 10)
        inv.reserve("BOLT-M6", 4)
        self.assertEqual((inv.stock["BOLT-M6"], inv.reserved["BOLT-M6"]), (6, 4))
        self.assertEqual(inv.audit(), [])

    def test_ship_takes_units_out_of_the_building(self):
        inv = Inventory()
        inv.receive("BOLT-M6", 10)
        inv.reserve("BOLT-M6", 4)
        inv.ship("BOLT-M6", 4)
        self.assertEqual(inv.on_hand["BOLT-M6"], 6)
        self.assertEqual(inv.audit(), [])

    def test_cannot_reserve_more_than_the_shelf_holds(self):
        inv = Inventory()
        inv.receive("BOLT-M6", 2)
        with self.assertRaises(OutOfStock):
            inv.reserve("BOLT-M6", 3)
