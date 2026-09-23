# E4 — the host-parity map (discovery)

## The change under measurement
None. A read-only map of the gate's rules against the hosts that reimplement them.

## What it predicts
1. The opencode JavaScript plugin is the one host that cannot call the core in
   process, so it is where a rule is most likely to be **absent or divergent**;
   at least one shipped rule is not enforced there.
2. The plugin test (`tests/test_opencode_plugin.py`) does **not** cover every rule
   label - it covers the rules whose agreement was pinned at the time.
3. No host other than opencode reimplements a rule at all: the codex, cursor and
   omp adapters call the core.

## What would falsify it
- Every shipped rule is implemented in the plugin and covered by the test.
- Some other host reimplements a rule instead of calling the core.

## Why this is worth a measurement
The architecture's stated invariant is "no cross-host drift", and the changelog
records one already (the opencode gate carried the pre-lease consent model and
let a repeat of an unapproved irreversible command through). Two readings of one
rule drift in both directions; the map says which rule is exposed and whether a
test would catch the drift or only its edit.

## Method
Read the Python gate and the plugin; enumerate every denial label from `_deny` and
the `*_DENY` constants; for each, classify the plugin's behaviour and cite
`path:line`. Report the counts and the labels the plugin test does not compare.

## Reported rows
One row per rule: `rule`, `python`, `js_status`, `js`, `test_covers`, `source`.
Plus a totals row.
