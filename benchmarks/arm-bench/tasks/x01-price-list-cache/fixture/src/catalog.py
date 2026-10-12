"""The product catalog: the one place prices are stored.

Every price write is persisted through `Store.save`, which rewrites the whole
catalog. Other parts of the system follow price changes through
`Catalog.subscribe` (see src/quotes.py).
"""
from src.store import Store


class Catalog:
    def __init__(self, store=None):
        self.store = store if store is not None else Store()
        self._prices = dict(self.store.load())
        self._listeners = []

    def skus(self):
        return sorted(self._prices)

    def price(self, sku):
        return self._prices[sku]

    def subscribe(self, listener):
        """Call `listener(sku)` every time the price of `sku` changes."""
        self._listeners.append(listener)

    def _check(self, sku, cents):
        if sku not in self._prices:
            raise KeyError(sku)
        if not isinstance(cents, int) or cents < 0:
            raise ValueError("price must be a whole, non-negative number of cents: %r" % (cents,))

    def _changed(self, sku):
        for listener in self._listeners:
            listener(sku)

    def set_price(self, sku, cents):
        self._check(sku, cents)
        self._prices[sku] = cents
        self._changed(sku)
        self.store.save(self._prices)
