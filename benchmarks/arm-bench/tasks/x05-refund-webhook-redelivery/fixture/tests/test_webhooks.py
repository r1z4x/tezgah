import unittest

from src.webhooks import Ledger, handle


def charge(event_id, charge_id, customer="cus_1", amount=1000):
    return {"id": event_id, "type": "charge.succeeded",
            "data": {"id": charge_id, "customer": customer, "amount": amount}}


class WebhookTests(unittest.TestCase):
    def test_charge_debits_the_customer(self):
        ledger = Ledger()
        self.assertEqual(handle(ledger, charge("evt_1", "ch_1")), "applied")
        self.assertEqual(ledger.balances, {"cus_1": -1000})

    def test_a_redelivered_charge_is_applied_once(self):
        ledger = Ledger()
        handle(ledger, charge("evt_1", "ch_1"))
        self.assertEqual(handle(ledger, charge("evt_9", "ch_1")), "duplicate")
        self.assertEqual(ledger.balances, {"cus_1": -1000})

    def test_unknown_events_are_ignored(self):
        self.assertEqual(handle(Ledger(), {"id": "evt_2", "type": "customer.updated", "data": {}}),
                         "ignored")
