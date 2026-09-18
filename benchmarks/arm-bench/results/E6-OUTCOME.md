# E6 outcome

The block ran at `k=25` per arm (amendment 2 of `../PREREGISTRATION-E6.md`). Every row is re-derived here from the
run's own session transcript (or, for the `--no-session` bare arm, from the row's
`final_message`), because the route check was corrected after the block: it had two
false positives in 100 runs.

| arm | n | asked (as stored) | asked (corrected) |
|---|---|---|---|
| `omp+tezgah` | 25 | 0 | **0** |
| `omp-bare` | 25 | 1 | **1** |
| `orx-gate-off` | 25 | 1 | **0** |
| `orx-verify-off` | 25 | 1 | **0** |

The two changed rows are ``orx-verify-off` r24, `orx-gate-off` r7`.

Both were false positives of the old check: a Turkish question particle matched inside
`tanımı` and `tamamı`, and the word `durum` matched `hata durumları` and `Son durum:`
in done reports that asked nothing. The check now requires the question and the
dimension in one message and matches the fixture's own vocabulary. Re-validated on the two
recovered streams (both now not-asked), on the one genuine positive (still asks), and by
`bench.py selftest` (3/3).

**The conclusion is unchanged and stronger**: only the harness-free arm ever surfaced the
open dimension, once in 25 runs; the armed arm and both mechanical-off arms asked in none.
