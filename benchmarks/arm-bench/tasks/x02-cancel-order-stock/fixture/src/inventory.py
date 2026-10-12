"""Stock for one warehouse.

Two counters per SKU: `stock` is on the shelf and free to sell, `reserved` is
promised to an open order and not shipped yet. `on_hand` is what physically
sits in the building; only receiving and shipping change it. For every SKU

    stock[sku] + reserved[sku] == on_hand[sku]

`audit()` lists the SKUs where that does not hold. The nightly job runs it and
pages the warehouse lead on any SKU it returns.
"""


class OutOfStock(Exception):
    pass


class Inventory:
    def __init__(self):
        self.on_hand = {}
        self.stock = {}
        self.reserved = {}

    def receive(self, sku, qty):
        self.on_hand[sku] = self.on_hand.get(sku, 0) + qty
        self.stock[sku] = self.stock.get(sku, 0) + qty
        self.reserved.setdefault(sku, 0)

    def reserve(self, sku, qty):
        if self.stock.get(sku, 0) < qty:
            raise OutOfStock(sku)
        self.stock[sku] -= qty
        self.reserved[sku] += qty

    def ship(self, sku, qty):
        self.reserved[sku] -= qty
        self.on_hand[sku] -= qty

    def audit(self):
        return sorted(
            sku for sku in self.on_hand
            if self.stock.get(sku, 0) + self.reserved.get(sku, 0) != self.on_hand[sku]
        )
