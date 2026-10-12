from collections import namedtuple

# amount: float in `currency`; day: the datetime.date the transaction happened.
Txn = namedtuple("Txn", "amount currency day")
