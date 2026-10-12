"""Invoice tax in integer cents. The contract is invoice/SPEC.md."""


def invoice_tax(lines):
    """The tax of one invoice, in cents."""
    total = 0.0
    for line in lines:
        total += float(line["amount"]) * float(line["rate"]) / 100
    return int(round(total * 100))
