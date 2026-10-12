"""Persistence for the catalog.

`save()` serialises and rewrites the whole catalog, so it is slow on a large
catalog; `saves` counts the calls.
"""
import copy

DEFAULT_PRICES = {"BOLT-M6": 120, "NUT-M6": 40, "WASHER-M6": 15, "DRILL-8": 990}


class Store:
    def __init__(self, prices=None):
        self._data = copy.deepcopy(prices if prices is not None else DEFAULT_PRICES)
        self.saves = 0

    def load(self):
        return copy.deepcopy(self._data)

    def save(self, prices):
        self._data = copy.deepcopy(prices)
        self.saves += 1
