"""A tiny ledger."""


class Ledger:
    def __init__(self, entries=()):
        self.entries = list(entries)

    def add(self, amount):
        if amount <= 0:
            raise ValueError(f"amount must be positive: {amount}")
        self.entries.append(amount)
        return self

    def total(self):
        return sum(self.entries)
