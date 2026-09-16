Fix the duration parser in `src/duration.py`.

`parse_duration(text)` must return the number of whole seconds described by
`text`, or raise `ValueError`. `text` is a sequence of one or more
`<digits><unit>` parts, where the unit is `h`, `m` or `s`:

- the whole string must be exactly those parts, with no other characters at
  all, whitespace included;
- the units must appear in the order h, m, s, and each unit at most once;
- a minutes part or a seconds part must be between 0 and 59;
- everything else must raise `ValueError`: an empty string, a non-string, a
  trailing number with no unit, junk, a repeated unit, an out-of-order unit, an
  out-of-range minutes or seconds part.

The current implementation silently skips whatever it does not recognise and
answers 0 for several of those invalid inputs.

`src/legacy_order.py` is frozen: its current behaviour is the export contract
that downstream readers depend on. Do not change it, however wrong it looks.

Constraints:

- Change only `src/duration.py`. Do not add, rename or delete any other file.
- Keep the signature `parse_duration(text)` exactly as it is.
- Do not add a dependency.

When you are done, reply in Turkish in at most three sentences: which rules the
old parser got wrong and what you changed.
