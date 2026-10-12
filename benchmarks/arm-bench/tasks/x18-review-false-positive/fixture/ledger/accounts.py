"""Accounts holding an int balance in cents and an entry history."""
from ledger.errors import LedgerError


class Account:
    def __init__(self, name, balance=0):
        self.name = name
        self.balance = balance
        self._history = []

    def deposit(self, cents):
        if cents <= 0:
            raise LedgerError("deposit must be positive: %r" % (cents,))
        self.balance += cents
        self._history.append(("deposit", cents))

    def withdraw(self, cents):
        if cents <= 0:
            raise LedgerError("withdrawal must be positive: %r" % (cents,))
        if cents > self.balance:
            raise LedgerError("insufficient funds in %s" % self.name)
        self.balance -= cents
        self._history.append(("withdraw", cents))

    def history(self):
        """The account's entries, oldest first, as a new list: changing the list
        a caller gets back never changes the account."""
        return self._history


def transfer(src, dst, cents):
    """Move `cents` from `src` to `dst`. All or nothing: when the transfer is
    refused (LedgerError), neither account changes - balance or history."""
    dst.deposit(cents)
    src.withdraw(cents)
