"""Customer quotes: the shelf price plus VAT, rounded half up to the cent.

A quote is computed once per SKU and memoised. A memoised quote is only right
while the price it was computed from stands, so the service drops a SKU's
entry whenever the catalog reports that its price changed (`Catalog.subscribe`).
"""
VAT_PERCENT = 20


class QuoteService:
    def __init__(self, catalog):
        self.catalog = catalog
        self._memo = {}
        catalog.subscribe(self._forget)

    def _forget(self, sku):
        self._memo.pop(sku, None)

    def quote(self, sku):
        if sku not in self._memo:
            cents = self.catalog.price(sku)
            self._memo[sku] = (cents * (100 + VAT_PERCENT) + 50) // 100
        return self._memo[sku]
