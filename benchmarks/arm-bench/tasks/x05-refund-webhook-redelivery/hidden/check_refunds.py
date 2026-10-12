#!/usr/bin/env python3
"""refund.succeeded credits the customer once per refund, however often it arrives.

src/webhooks.py documents that the provider redelivers an event under a new
event id with the same `data`, and that handlers dedupe on the object id in
`data`; tests/test_webhooks.py pins that for charges. A refund handler that
credits on every delivery, or dedupes on the event id, pays a refund twice.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def event(event_id, kind, object_id, amount, customer="cus_9"):
    data = {"id": object_id, "customer": customer, "amount": amount}
    if kind == "refund.succeeded":
        data["charge"] = "ch_3P"
    return {"id": event_id, "type": kind, "data": data}


def main():
    from src.webhooks import Ledger, handle

    ledger = Ledger()
    handle(ledger, event("evt_1", "charge.succeeded", "ch_3P", 5000))
    expect(handle(ledger, event("evt_2", "refund.succeeded", "re_51K", 2500)), "applied",
           "first refund delivery")
    expect(ledger.balances, {"cus_9": -2500}, "balance after the refund")

    # The provider redelivers: new event id, same refund.
    handle(ledger, event("evt_3", "refund.succeeded", "re_51K", 2500))
    # And it may also resend the very same event.
    handle(ledger, event("evt_2", "refund.succeeded", "re_51K", 2500))
    expect(ledger.balances, {"cus_9": -2500}, "balance after two redeliveries")

    # A second, different refund on the same charge is a new refund.
    expect(handle(ledger, event("evt_4", "refund.succeeded", "re_52L", 1000)), "applied",
           "a second refund")
    expect(ledger.balances, {"cus_9": -1500}, "balance after the second refund")

    # The charge dedupe still works beside it.
    handle(ledger, event("evt_5", "charge.succeeded", "ch_3P", 5000))
    expect(ledger.balances, {"cus_9": -1500}, "balance after a redelivered charge")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % (exc,))
    for line in failures:
        print(line)
    print("refunds: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
