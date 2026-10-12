"""Payment-provider webhooks.

The provider delivers every event at least once. When our endpoint is slow it
delivers the event again, and a redelivery carries a NEW event `id` with the
same `data` - so the event id cannot tell a redelivery from a new event. What
identifies the thing that happened is the object in `data`: its `id` (a charge
id `ch_...`, a refund id `re_...`) is the same on every delivery. Handlers
record those object ids in `Ledger.applied` and skip any they already applied.
"""
from dataclasses import dataclass, field


@dataclass
class Ledger:
    balances: dict = field(default_factory=dict)
    applied: set = field(default_factory=set)

    def credit(self, customer, cents):
        self.balances[customer] = self.balances.get(customer, 0) + cents


def _charge_succeeded(ledger, data):
    key = ("charge", data["id"])
    if key in ledger.applied:
        return "duplicate"
    ledger.credit(data["customer"], -data["amount"])
    ledger.applied.add(key)
    return "applied"


HANDLERS = {
    "charge.succeeded": _charge_succeeded,
}


def handle(ledger, event):
    handler = HANDLERS.get(event["type"])
    if handler is None:
        return "ignored"
    return handler(ledger, event["data"])
