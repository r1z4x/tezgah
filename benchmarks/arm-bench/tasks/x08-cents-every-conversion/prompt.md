An invoice line for 2 x 4.35 charges 869 cents instead of 870. The suite is red
on it:

    python3 -m unittest discover -s tests

README.md has the rule: every float amount turned into integer cents - charged,
refunded, stored or printed - goes through `billing.money.to_cents` and is
rounded half up. The invoice line is where a customer noticed it; make the
whole package follow the rule, wherever it turns an amount into cents.

Change only `billing/`; `tests/` is frozen.
