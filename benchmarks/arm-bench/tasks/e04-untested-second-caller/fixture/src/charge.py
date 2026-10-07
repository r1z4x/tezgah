"""What a member is charged for the part of a cycle they use."""

from src.proration import prorated_cents


def partial_charge_cents(monthly_cents, days):
    """Return what the member pays for `days` of a cycle, in whole cents.

    A part of a cent goes to the member.
    """
    return prorated_cents(monthly_cents, days)


def invoice_total_cents(monthly_cents, days, tax_cents=0):
    """Return the invoiced amount: the part-cycle charge plus any tax on it."""
    return partial_charge_cents(monthly_cents, days) + tax_cents
