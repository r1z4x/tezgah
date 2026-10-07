`money/round.py::apply_discount` does not honour the discount contract: it
truncates instead of rounding half up in exact cents. Bring the code to the
contract in `money/SPEC.md`, including its examples table: the spec is the
contract of record and the rule it states is fixed, so the code is the side that
changes. `python3 -m unittest discover -s tests` must pass.
