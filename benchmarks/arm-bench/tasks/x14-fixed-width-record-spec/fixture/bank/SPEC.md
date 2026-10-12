# Payment file record

`bank.record.format_record(account, name, cents)` returns one line of the
payment file the bank imports. The bank rejects the whole file when any line
breaks a rule below.

A record is exactly **40 characters followed by `"\r\n"`** (42 in all), ASCII
only, in three fixed-width fields:

| columns | width | field   | layout                                         |
|---------|-------|---------|------------------------------------------------|
| 1-8     | 8     | account | digits, right-aligned, zero-padded             |
| 9-28    | 20    | name    | left-aligned, space-padded                     |
| 29-40   | 12    | amount  | right-aligned, space-padded                    |

## account

1. `account` is a str of digits. It is zero-padded on the left to 8 digits. An
   account of more than 8 digits does not fit: raise `ValueError`. A field is
   never cut short to make it fit.

## name

2. The name is written in ASCII. Accented letters lose their accent (decompose
   with NFKD and drop the combining marks: `"Müller"` -> `"Muller"`); any
   character still outside ASCII after that becomes `"?"`.
3. A name of at most 20 characters (after rule 2) is padded with spaces. A
   longer name is cut to its first 19 characters followed by `"~"`, so the
   reader can tell it was shortened.
4. A `None` name is written as 20 spaces.

## amount

5. `cents` is an int, possibly negative or zero. It is written in units with
   exactly two decimals and a leading `"-"` when negative: `12345` ->
   `"123.45"`, `-5` -> `"-0.05"`, `0` -> `"0.00"`. No thousands separators, no
   `"+"`.
6. An amount whose text is longer than 12 characters does not fit: raise
   `OverflowError`. The amount is never cut short or rounded to make it fit.
