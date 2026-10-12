"""Customer orders. Each order is one SKU line."""
from dataclasses import dataclass


@dataclass
class Order:
    order_id: str
    sku: str
    qty: int
    status: str = "open"


class OrderBook:
    def __init__(self, inventory):
        self.inventory = inventory
        self.orders = {}

    def place(self, order_id, sku, qty):
        self.inventory.reserve(sku, qty)
        self.orders[order_id] = Order(order_id, sku, qty)
        return self.orders[order_id]

    def ship(self, order_id):
        order = self.orders[order_id]
        if order.status != "open":
            raise ValueError("order %s is %s" % (order_id, order.status))
        self.inventory.ship(order.sku, order.qty)
        order.status = "shipped"

    def cancel(self, order_id):
        order = self.orders[order_id]
        if order.status != "open":
            raise ValueError("order %s is %s" % (order_id, order.status))
        self.inventory.release(order.sku, order.qty)
        order.status = "cancelled"
