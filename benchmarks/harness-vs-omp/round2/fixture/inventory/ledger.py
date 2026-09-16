"""A tiny ledger."""


class Ledger:
    entries = []

    def add(self, amount):
        self.entries.append(amount)
        return self

    def total(self):
        return sum(self.entries)
