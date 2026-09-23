# H4 - a keep-or-translate rail against free translation

**What ran.** `harness/run.py --track h4`, transport `host`. Arm A was told to translate
English terms into Turkish where an equivalent exists; arm B was handed the rail
(`harness/rail.json`: thirteen keep entries and seven translate entries, plus the
register override that keeps `deadline` in the corporate register). Scoring is by script, not
by a judge: a keep form present in the source and missing from the edit scores its severity
(100, 10 or 1), a calque that survives scores its severity, and the total is reported as
points per 1,000 words. A judge scored clarity and information preserved, which is the cost
half of the falsifier.

**What the rows say.** Severity-weighted error points per 1,000 words: arm A **266.4**, arm B
**0.00**. Arm A lost keep terms in the corporate-register item - it translated `Deadline` into
`Teslim tarihinde`, the exact failure the plaza-dili evidence predicts for that register - and
left calques in place; arm B committed neither class of error, and its clarity score did not
fall (**4.58 -> 4.67**), so the reduction was not bought with a comprehension cost. Arm B's
output additionally kept `retry_queue`, `handle_timeout`, `deploy_prod.sh`, `src/db/pool.py`,
the version strings and no revision of `v2.1.2`, and unit symbols unchanged.

**Which claim it moves.** C02, supported, and C07's design consequence: the term axis is the
one place where an explicit rail changed behaviour by an order of magnitude rather than by a
judge's margin.

**What it does not show.** The rail is my own composition from the sources in `literature/`,
so this measures what an explicit, sourced keep list does - not whether my particular list is
the right one, and not the real professional pipeline (a TBX termbase read by a checker such
as Okapi CheckMate). The scoring script rewards the literal form: an arm that legitimately
restructured a sentence away would be scored for a lost keep term, which did not happen here
but is the script's known ceiling. One pair of eyes wrote the rail and the items, so the
items are seeded with the rail's own terms.
