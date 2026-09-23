# Scoring addendum - runtime rows join the scoring set

Committed before any rater output was read (E2's three raters are still running).
The E2 protocol froze the corpus for the raters' blindness; it did not freeze the
scoring set against evidence produced afterwards by a different experiment.

E1b's observed rows R01-R06 join the scoring set:

| Row | Effect on scoring |
|---|---|
| R01 (= D03), R02 (= D04), R03 (= D06), R06 (= D09) | no change: they settle corpus rows that were already in the set |
| R04 (table overflows at 320/768/1280) | **new row in the set**: a rater reporting it is a detection, not a false positive |
| R05 (wizard URL state vs rendered state) | **new row in the set**: same |

The asymmetry this creates is named rather than hidden: E2's raters ran without the
runtime rows in their environment, and E3's raters will run in an environment where
the app is live. Both arms are scored on the same set, so if the treatment's
advantage comes only from R04/R05 being findable, that is visible in the per-row
breakdown and is reported as such.

Rows R01-R06 carry `scope: real` and their own `source`, so a reader can weigh
them without reading this file.
