import unittest

from src.orders import line_status
from src.report import fillable_now, shortage_rows
from src.stock import available, reserve


class StockTests(unittest.TestCase):
    def test_available_nets_out_reserved(self):
        item = {"sku": "A1", "stock": 10, "reserved": 4}
        self.assertEqual(available(item), 6)

    def test_reserve_reports_what_it_took(self):
        item = {"sku": "A1", "stock": 10, "reserved": 4}
        self.assertEqual(reserve(item, 3), 3)
        self.assertEqual(item["reserved"], 7)

    def test_line_status_reports_a_shortage(self):
        item = {"sku": "A1", "stock": 5, "reserved": 1}
        self.assertEqual(line_status(item, 6), "A1: 2 short")

    def test_line_status_ready(self):
        item = {"sku": "A1", "stock": 5, "reserved": 1}
        self.assertEqual(line_status(item, 3), "A1: ready")

    def test_shortage_rows(self):
        item = {"sku": "B2", "stock": 2, "reserved": 0}
        self.assertEqual(shortage_rows([item], {"B2": 5}), [("B2", 3)])

    def test_fillable_now(self):
        items = [{"sku": "A1", "stock": 10, "reserved": 4},
                 {"sku": "B2", "stock": 2, "reserved": 0}]
        self.assertEqual(fillable_now(items, {"A1": 8, "B2": 5}), 8)


if __name__ == "__main__":
    unittest.main()
