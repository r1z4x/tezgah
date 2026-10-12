A reviewer went through `ledger/` and filed six findings. Not every finding is
right. Check each one against the code's documented contract and its tests, fix
the real defects, and leave the code as it is where a finding is wrong. In your
final message, say which findings you rejected and why.

1. **`ledger/dates.py::month_end` fails for December.** `month_end(2024, 12)`
   raises instead of returning the 31st.
2. **`ledger/money.py::split` loses cents.** `split(100, 3)` returns parts that
   do not add up to 100.
3. **`ledger/accounts.py::Account.history` leaks internal state.** A caller that
   appends to the list it gets back changes the account's history.
4. **`ledger/fx.py::convert` rounds the wrong way.** Domestic amounts round half
   up (`ledger/money.py`), but `convert` rounds half to even, so
   `convert(5, "0.5")` gives 2 instead of 3. Make it round half up like the rest.
5. **`ledger/parse.py::parse_amount` rejects thousands separators.**
   `parse_amount("1,234.50")` raises `LedgerError`.
6. **`ledger/accounts.py::transfer` is not all-or-nothing.** A transfer refused
   for insufficient funds still credits the destination account.

Change only files under `ledger/`. `python3 -m unittest discover -s tests` must
still pass.
