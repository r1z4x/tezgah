# The harness's mechanical half — what is load-bearing, what is not, and what to change

Line: `.tezgah/research/harness-hardening/`. Everything below is measured on this machine
(darwin-arm64, Python 3.10.14) on 2026-09-20; each item names the claim it rests on. The
close-out pass of 2026-09-22 added no measurement of its own — it settled open claims, scoped
one refutation to the tree it was taken on, and copied the probes into the line, all recorded
in the close-out section below.

## The numbers this report is read against

| what | value | claim |
|---|---|---|
| injected text at `session_start` | 9150 B of 12000 (76.2%), core 8081 B | C01 |
| injected text per user prompt | 1134 B of 6000 (18.9%) | C01 |
| `subagent_start` | 4028 B of 4400 (91.5%) | C01 |
| live-state half vs repository size | unchanged under a 5x lessons/plans input | C02 |
| one gated call, wall clock | **61.0 ms p50** | C05 |
| the rule cascade inside it | **0.427 ms p50** | C05 |
| import of the gate alone | 61.4 ms | C05 |
| unused stdlib import inside that | **~12 ms** (sqlite3+shutil+tempfile) | C06 |
| cost vs. corpus size | flat (0.430 ms at 1 and at 20 ledger files) | C07 |
| refusals over 6 days | 556 in 1613 ledgers, 11 labels | C03 |
| rules that never fired | **`explorer`, `order`** | C03 |
| rules living on one day | `task` 168, `race` 8, `lang` 1 | C04 |
| unbounded read on the hot path | whole ledger per effectful call, 2.928 ms then (bounded since, C24) | C10 |
| hosts enforcing the language rule | 6 of 6 — opencode asks the core | C18, C26 |

## What to change, in the order the evidence justifies

**I1 — Stop paying for three stdlib imports the call does not use (C06).**
`hooks/tezgah_paths.py` imports `sqlite3`, `shutil` and `tempfile` at module level; the
gate imports `tezgah_paths` transitively on every tool call, and the three together are
~12 ms of the 61 ms. Deferring them into the functions that need them (the omp `agent.db`
read, the temp-cache fallback, bin resolution) is one file, reversible, and buys ~20% of
every gated call in every host.
*Acceptance:* re-run `python3 experiments/E3-hot-path-cost/probe-process.py` (`/tmp/hh-proc.py`
when this item was written, copied into the line on 2026-09-22) and watch the probe process land
near
49 ms p50 while `python3 -m unittest discover -s tests` stays green. *Falsified if:* the
probe does not move.

**Measured after the change (2026-09-20, this machine):** `import tezgah_gate` alone fell
**61.4 → 50-55 ms p50** across three runs of ten (jittery; the cumulative figure by
`-X importtime` is the stable one at 41.2 → 27.1 ms, −34%), with `tezgah_paths` going
from 12.7 ms to **0.18 ms** and `shutil` deferred out of `tezgah_snapshot` as well. The
end-to-end probe - what a host actually pays per gated call - reads **61.0 → 56.8 ms
p50** on an idle machine, n=40: **−4.2 ms, or 7%.** The "~49 ms process" acceptance
this item was written with was unsupported, and the panel was right to say so: the
import is what moved most, the process what moved least.

**I2 — Bound the one unbounded hot-path read (C10).**
`tezgah_untrusted.turn_channel` reads the whole ledger on every effectful call, where the
gate's own read is tail-bounded at 200 rows. Today that is 2.928 ms; it is linear in
session length with no bound. Give it the same tail the gate uses.
*Acceptance:* a session ledger grown past 900 rows shows a bounded read; the untrusted-label
tests stay green. *Falsified if:* the tail changes what the taint rule decides on a
replayed session.

**I3 — Implement the language rule on opencode, or route its commands through the core (C08).**
The plugin has no `lang` code at all, so on that host a Turkish branch name, commit subject
or PR title is created unchecked — and those are the artifacts that outlive the session.
*Acceptance:* the pattern the plugin suite already uses for the task rule (seed a fixture,
compare against the Python core) is extended to a non-English commit subject and fails
before the fix. *Falsified if:* the delegated path already reaches the rule for every
identifier-creating command.

**I4 — Decide `explorer` and `order`'s fate with a probe, not a guess (C03).**
Neither has ever fired in 556 refusals. The published yardstick says a rule is worth what
its reach covers (C11), and this repository's own audit method says the next step is a
frozen probe that issues each rule's shape deliberately. Three outcomes are all fine —
reachable and useful, reachable and useless, unreachable — but each has a different action,
and "its text is already written" is not one of them.
*Acceptance:* a probe either produces a refusal for each shape or records it as unreachable,
committed before the run.

**I5 — Guard the core call, and stop one crash becoming a session-wide disable (C09).**
No entry point guards `decision`/`context_for`/`note_tool`/`stop_reason`. Claude, Codex and
Cursor lose one envelope; omp loses the gate, the ledger and the status line for the rest of
the session; opencode's spawn has no timeout, so a hung core blocks a tool call. The
cheapest version is a guard at each entry point that degrades one feature, plus a timeout on
the opencode spawn.
*Acceptance:* a core call made to raise leaves the session's other mechanisms armed, host by
host. *Falsified if:* the guard changes what a normal turn is told.

**I6 — Before running more arms, pick tasks whose behaviour an arm can move (C13, C11).**
The lab's own corpus is saturated for the harness question (22 of 25 pilot tasks; pooled
40/50 against 40/50 across armed and bare arms). The published form of the fix is an
*attributable-evidence gate*: score a candidate change only on the tasks whose behaviour it
can move. That is a change to how the next round is designed, not to the harness.
*Acceptance:* the next pre-registration names, per task, the behaviour the arm under test
would have to change.

## What happened to the six items (updated 2026-09-20, after the second opinion)

| item | state | evidence |
|---|---|---|
| I5 guard + deadline | **landed** | `9538f56`; `tests/test_guard.py` failed on all seven entry points before it |
| I6 attributable-evidence gate | **landed as a gate** | lab branch `8db165a`: `PREREGISTRATION-E8.md` answers, per task, which behaviour an arm must move; `corpus/attribution.md` |
| I2 turn-scoped taint read | **landed** | `21eaee3`; equivalence over five ledger shapes + a parse-count bound, 20 tests |
| I3 opencode language + visible fail-open | **landed** | `21eaee3`; refusal compared character-for-character with the core's own answer, `delegation` row pinned |
| I4 probe for `explorer`/`order` | **landed, and it answered the open question** | E6: **both rules refused when their shape was issued** (7 cases, 4 refusals) - so E2's zero counts mean the shape was never offered, not that the rule cannot match. The withdrawn "unreachable" verdict stays withdrawn. |
| I1 deferred imports | **landed, last and smallest** | `21eaee3`, `0632ba3`; the gated call moves 61.0 → 56.8 ms p50 (7%) |

## The second opinion, and the correction it forced

A panel was asked to judge the six items against the measurements alone (no conclusion of
mine): `x-ai/grok-4.3` and two DeepSeek models answered, `google/gemini-2.5-pro` returned
empty on both providers, and the referee was `deepseek-chat`. All three answers and the
referee put **I5 first** and **demoted I1**, and the report above is wrong on both counts:

- **I1 is not the first item and probably not an item.** The referee did the arithmetic the
  report did not: `tezgah_paths`' own body is 0.6 ms, so its three stdlib imports are a
  *ceiling* of ~12 ms; `tezgah_integrity` — the larger share of the 41.2 ms import — is
  untouched by the change; and 12 ms is the 0.5-1% of a model turn the report itself calls
  unfelt. "Free to remove" is not a decision axis when the measurement it would move is below
  the noise of the thing the user pays for.
- **I5 is first because its downside is asymmetric**: it is the only item whose failure mode
  is a silent loss of a whole session's enforcement, on two hosts, by two mechanisms. Cost is
  not the tiebreaker; the asymmetry is. The caveat it carries: no ledger row records a hook
  crash, so the damage is read off the code.
- **I6 is a gate on lab spend, not a task** — both DeepSeek answers and the referee read it
  that way, because the lab's remaining arms measure a corpus that is saturated.
- **I2 ships only behind its own replay** (does the 200-row tail preserve the taint decision?).
- **I3's acceptance is wrongly shaped**: the defect is not only the missing `lang` rule, it is
  that *any* delegation failure allows the call; one non-English commit subject tests one
  shape of one rule and not the fail-open path.
- **I4's verdict is withdrawn**: zero rows over six days cannot support "record as
  unreachable". A probe can establish "no shape I enumerated triggers these labels" and
  nothing more, so the item is a bounded spike, not a verdict.

Corrected order: **I5 → I6 (as a gate) → I2 (after its replay) → I3 (rule *and* the fail-open
decision) → I4 (spike only) → I1 (last, if at all).** Counted by the panel's own verdicts:
I5 first 3 of 3, I1 demoted 3 of 3, I4's verdict refused 2 of 2 who addressed it.

The evidence the panel asked for, none of which this line holds: hook-crash instrumentation
that reproduces omp's session-wide disable; an in-situ end-to-end per-call cost (model turn
latency in dollars and seconds, not a microbenchmark) to decide I1's fate; and one test that
drives every identifier-creating command through opencode's delegated path.

## Line close-out (2026-09-22)

The line is terminal as of this date: `phase: concluded`, `direction: conclude`. What this
pass settled, and the row that now carries it:

| what was open | how it is settled |
|---|---|
| C11 sat at status `hypothesis` | **C21** supersedes it at status `untested`: the two literature readings stand, the local test they need has not been run and the row says which test it is. |
| C12, superseded by C13 but still reading `supported` | **C22** restates the live truth in one sentence, so a reader who opens C12 finds the current one. |
| C16, superseded by C19, same defect | **C23**. |
| C17, superseded by C20, same defect | **C24**. |
| C09, `supported` and no longer true of the tree | **C25**: the guard landed at seven entry points, so the E5 reading describes the pre-fix tree. |
| C08, `supported` and half no longer true | **C26**: opencode asks the core for the language rule now; the fail-open half stands. |
| H5, refuted against a tree that then changed | **re-taken by E5b (C27)**: the `guarded` half holds, and the `bounded` half failed only at the Stop path, which was then bounded through `turn_rows` with a test that fails on the pre-fix file. |
| the probes lived in `/tmp` | copied into the line with content unchanged: `experiments/E1-injection-budget/probe.py`, `experiments/E2-rule-fire-coverage/probe.py`, `experiments/E3-hot-path-cost/probe.py`, `experiments/E3-hot-path-cost/probe-process.py`. |

Two rows settled things this report did not list as open (C09 and C08) — both were found by
reading the claims against the tree, not by the checker, which can only see the `supersedes`
links a writer recorded. Nothing in `claims.jsonl` was edited in place: the six rows above are
appends, and the superseded rows stay visible with their stale text.

## What the evidence does not show

- **Nothing here says the harness improves or harms the model's work.** The mechanical half
  (cost, coverage, parity, guards) is what was measured; the behavioural half belongs to the
  arm-bench lab, whose pooled result is a null. No item above claims a task-success effect.
- **H5's re-take closes the `guarded` half and leaves two unbounded reads standing.** The E5
  map read the entry points before the guard landed; E5b re-read them on today's tree and
  found `hooks/tezgah_guard.safe` at all seven entry points and a deadline on every core ask
  in the opencode plugin, so the `guarded` half now holds. The `bounded` half failed at the
  Stop path — `stop_reason` and `changed_files` parsed the whole ledger, 2.638 ms against
  0.185 ms for the turn's rows at the largest ledger on this machine (1112 rows) — and was
  bounded afterwards through `turn_rows`, with the test failing at 4002 parsed lines on the
  pre-fix file. H5 therefore still reads `refuted` for today's tree, on the narrower ground
  that `used()` and `_hash_file` remain unbounded by construction. **The bound is a parse
  bound**: `turn_rows` still reads every line (0.164 ms there) and scans it for markers.
- **The re-take moved line citations but not the docs.** `hooks/tezgah_integrity.py` grew by
  29 lines around `turn_rows` and `stop_reason`, so 59 citations in `docs/*.md` now name a
  line outside the symbol beside them (0 before, and the repo-wide figure was already 225).
  They were left as they are — `docs/` is outside the experiment's write scope — and the
  count is in `experiments/E5b-h5-retake/analysis.md`.
- **C11 is untested here, not answered (C21).** The repository holds no measurement of the
  literature's conditional: E1 measures the pressure side (76.2% of a 12000 B budget at
  `session_start`) and the lab's pooled null (C22) was taken at one window over a corpus its
  own README calls saturated (22 of 25 pilot tasks). Settling it needs the arm-bench lab
  re-run with the harness's context policy toggled at two window sizes over a corpus that can
  be moved, which is model spend on the `benchmarks/lab` branch — not available to this line.
- **Two hot-path reads the map named were never timed at all**: `used()` (a kinds-only store)
  and `_hash_file` (a file hashed to EOF by design). Their cost is read off the code, not
  measured, and `stop_reason`'s read — untimed when this report was first written — is now
  priced by E5b (C27) and bounded.
- **The probes' receipts point at `/tmp`.** The four scripts are in the line now, but the
  frozen `results.jsonl` rows still read `source: python3 /tmp/hh-*.py`: results are
  append-only evidence, so the mapping is in `log.md` line 28 and in this section rather than
  in the rows themselves.
- **No cost number was compared against a user-visible budget.** 12 ms or 61 ms per call is
  0.5-1% of a model turn; the case for I1 is that it is free to remove, not that it is felt.
- **The guard audit is static.** No ledger row records a hook crash, so I5's blast radius is
  read off the code, not off an incident — and the fix's own effect is read the same way.
- **The parity map is static.** C26 says opencode now routes the language rule to the core; no
  run drove a non-English identifier through that host's delegated path.
- **`explorer`/`order` zero counts come from one machine and six days** (1613 ledgers), which
  is this repository's own traffic, not a sample of anything else.
- **The literature is read as conditional, not as a prescription.** The papers' wins appear
  under context pressure (C21) and this repository sits at 76% of its budget at session start;
  nothing here tests the elision policies they recommend.
- **One checker warning is left standing on purpose**: C17 still asserts a `4400` its cited
  test does not hold. Its correction is C20/C24, and the file is append-only, so the row stays
  as the visible record of the defect rather than being repaired.
- **Not looked at**: the status line, dsh/omp surface rendering, `bin/tezgah-setup`'s install
  path, `tezgah_research`'s own checker (no subprocess timeout, off the hot path), the
  snapshot store's growth, and the arm-bench corpus itself beyond its README.
