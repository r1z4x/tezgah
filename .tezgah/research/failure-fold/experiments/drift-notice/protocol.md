# drift-notice — the refusal becomes a notice on the result channel

Written **before** the run, and committed before it. Line:
`.tezgah/research/failure-fold/`. Every number below is a fold of the local
corpus at a named snapshot; no number here is a behavioural measurement of the
harness.

## The change under measurement

The `drift` rule stops refusing. Today the gate's last check, `drift_reason()`
(`hooks/tezgah_gate.py:1508`), writes the `drift` marker row and then returns the
`DRIFT_DENY` text, which `decision()` turns into `_deny(session_id, "drift", …)`
(`hooks/tezgah_gate.py:1760`). The text is the re-statement of the standing
constraints; the refusal exists only because a PreToolUse hook has no other way
to reach the model, which the code says in its own docstring.

The change's own shape, as implemented (uncommitted when this was written): the
constant is renamed `DRIFT_DENY` -> `DRIFT_NOTICE` and its closing clause reads
`nothing was refused, so carry on.`; `drift_reason` keeps its name and its
leading text and now takes `(tool, inp, cwd, session_id)`; `DRIFT_STEPS = 25`,
`DRIFT_TAIL = 200`, the detection, the one-per-turn mark and the marker row's
shape (kind `drift`, `detail` = the turn's step count as a string, `workspace`
set) are unchanged.

Under the change:

- **no refusal**: `decision()` returns nothing for drift, and no `deny` row whose
  `detail` starts `drift:` is written;
- **the same text, on the tool-result channel**: the call proceeds, and the host
  writes the notice with the tool result it belongs to — the channel
  `hooks/projects-posttooluse.py:110` already uses
  (`hookSpecificOutput.additionalContext`), which `hosts/omp/hook.py:164` reads
  back as `out["label"]` and `hosts/opencode/plugins/tezgah.js` mirrors as
  `labelResult`;
- **the marker row stays**: detection and the `drift` marker row move to the
  post-tool path together, so the marker is written exactly when the notice text
  is produced and handed to the host. The mark is still per turn — one
  re-statement in a turn that drifted, none in a short one;
- **no `deny` row** may remain for this rule on any wired host.

The detection condition itself is unchanged: `DRIFT_STEPS = 25` work rows in the
current user turn, read from a `DRIFT_TAIL = 200` window, one marker per turn.

## What it predicts

1. **No `drift` refusal is written any more.** The metric is the `drift` row of
   `bin/tezgah-status --failure-shapes`, i.e. that rule's deny rows. Its value
   **before** was read three times on 2026-09-20 as the corpus grew:
   `177 sessions 225 fires 1.27/session` (the candidate analysis, 1661 ledgers),
   `179 sessions 227 fires 1.27/session` (this line, 1669 ledgers) and
   `180 sessions 228 fires 1.27/session` (1670 ledgers, the last pre-change
   fold). Predicted after: **zero `drift` deny rows written after the change's
   commit**, read on the ledgers dated after it — the round's own arm ledgers
   (`counters().denies["drift"]`, 0 by construction) and the real-work ledgers
   written after the commit. The corpus-wide total is **not** the read: it holds
   the pre-change history and can only decay as old ledgers are removed, so it
   would answer a question about the corpus rather than about the change.
   Nothing else in the report moves on account of this change.
2. **The notice is still produced.** The marker rows are the receipt that the
   notice text was produced and handed to a host. Over real work
   (`/Users/rizax/Projects`), the 2026-09-20 snapshot holds **227 `drift` marker
   rows on 280 turns of >= 25 work rows** (the analysis read ~272 such turns at
   444 real-work ledgers; this line's re-read at 447 ledgers reads 280), and the
   1670-ledger re-read on the same date reads 230 marker rows on 281 such turns.
   The marker count already exceeds the deny count by two: those two turns are
   the change's first live instances in this working tree (2026-09-20 19:35:32
   and 19:37:51, marker written, no deny row), which is the shape prediction 1
   predicts. Predicted after: the count stays above **200** of those turns —
   73.5% of the ~272 the pre-registration was written against.
3. **The counter-metric does not move up.** The counter-metric is the blocked
   claim rate of real work — `claim` rows whose `detail` starts `blocked:` over
   all `claim` rows in ledgers whose workspace set contains
   `/Users/rizax/Projects`. Its value **before**, at the analysis snapshot of
   2026-09-20, is **124 blocked / 232 claims = 0.5345** over 444 ledgers; this
   line's own re-read on the same date reads 124 / 233 = **0.5322** over 447
   ledgers. Predicted after: **not above 0.5345**.
4. **The completion cost is not paid by the user.** The change removes one
   refusal per long turn and adds no call, so the turn's own shape does not get
   more expensive; the paid round checks that this does not show up as a drop in
   the arm's pass rate.

## What would falsify it

Any one of these ends the line: record the null, and abandon the change.

- **(a) A `drift` deny row is still written after the change.** Read on the
  ledgers written after the commit — the round's own arm ledgers by
  `counters().denies["drift"]`, and the real-work ledgers dated after it. The
  corpus-wide fold's `drift` row is deliberately not this metric: it holds the
  pre-change history (228 fires at the 1670-ledger fold) and can only decay, so a
  reader taking it for the outcome would be reading the past.
- **(b) The notice stops being produced.** Marker rows over real-work turns of
  >= 25 work rows fall below **200** of ~272. The marker is written before the
  result envelope is printed, so a host that drops the field still leaves one — a
  collapse therefore means the notice is not produced at all (an unwired host, a
  detection that no longer runs, a marker lost with the move), never that it was
  produced and ignored.
- **(c) The real-work blocked-claim rate rises above 0.5345.** The refusal was
  doing work the notice does not do: without it, long turns end in more blocked
  claims than before.

## Why `drift` and not the other seven shapes

The fold's eight shapes, ranked by distinct sessions, each read against the same
question: does removing the rule's refusal cost more than it buys, and is the
refusal carrying a correction the notice could not? One line each, from the
analysis (2026-09-20; counts are its snapshot, this line's re-read in brackets):

- **`drift` — chosen.** 225 fires (re-read: 227), 177 sessions (re-read: 179),
  **every fire in the user's real work and none in the lab**, and it is the only
  shape whose refusal carries **no correction to the call**: the pre-change text
  says re-issue it unchanged, and the change's own clause says `nothing was
  refused, so carry on` — either way the notice tells the caller of nothing it
  got wrong. Measured on the fires: 0 repeated an already-refused
  call id in the same turn, 0 sat on a turn with no work rows, only 15 had a
  passing check earlier in the turn (re-read: 130 of 227 = 57.3% were re-issued
  identically in the same turn, 97 = 42.7% were never re-issued, 15 had a passing
  check earlier). Cost, measured: 128 of 225 (56.9%) refused calls were re-issued
  identically inside the same turn — 128 wasted round trips — and 97 of 225
  (43.1%) were never re-issued — 97 composed calls the session did not get back.
- **`task` — excluded.** 168 fires, of which 148 are the arm-bench lab's own
  traffic (re-read: 154 in arm-bench, 14 in the lab's temp task dirs, **0** in
  `/Users/rizax/Projects`), so the rule's cost lands where the user is not; and
  the correction it carries is real (a phase or an allowlist the user set).
- **`consent` — excluded.** 95 fires with only 9 re-uses (re-read: 97 fires, 9),
  of which 3 were designed re-uses; the refusal is the ask the rule exists to
  make, and removing it removes the ask.
- **`sink` — excluded.** 37 real fires with **0** repeats (re-read: 40 fires, 1):
  the model does not re-issue, so a notice would change nothing and the refusal
  is the untrusted-content control's only teeth.
- **`shortcut` — excluded.** A 33% repeat rate looked attractive (re-read: 23.1%
  by session, 2.9% by turn) but 18 fires is a thin floor (re-read: 34), and a
  quarter of its rows carry **no call id**, so the repeat rate cannot be read off
  the ledger at all.
- **`retry` — excluded.** 23 of 25 refusals stood (re-read: 25 fires, 0
  re-issued): the model stops, so there is nothing for a notice to recover.
- **`secret` — excluded.** 0 repeats (re-read: 18 fires, 0): same as `retry`,
  and the shape is a credential about to be written, where the refusal is the
  protection rather than the correction.
- **`loop` — excluded.** At the floor (7 fires, 6 sessions; re-read: 7 fires):
  below any threshold at which a change could be read, and its refusal already
  names the failure rather than restating the contract.

## The design that reads it

An **arm pair**, not a single arm: `omp-drift-notice` (the change, its commit)
against `omp-drift-notice-pre` (the parent commit), deployed the way E2b's round
deployed its pair — a copy of the arm directory with the one `const HOOK` line
re-pinned at each checkout, so the two members differ in the gate and its host
wiring and in nothing else. The round's own free pre-flight is the arming proof
and this change's first acceptance: the pre-tool path must **still refuse** in the
parent member and **no longer refuse** in the change member, before the first
model call. A pair whose two halves load the same python half is inert, which is
the trap F2 of the lab's E8 pre-registration names.

**The primary metric is free.** `fold_ledgers.py` already reads each run's own
evidence ledger with the predicates resolved from that arm's own bridge, so the
`drift` deny rows of prediction 1 and the `blocked_any` claims of prediction 3
come out of the round's own ledgers at no extra cost. Whether any lab turn crosses
25 work rows is itself read from those ledgers rather than assumed: the lab's
fixtures are single bounded tasks and its README states it does not measure
long-horizon behaviour, so a round in which the notice never fires is possible and
would be reported as an untested factor, not as a null.

**The families that can see a mechanical factor** are the ones whose one prompt
forces many calls — the exhaustive-audit family (`h01-exhaustive-callsite-audit`,
`h05-review-sweep`), the multi-requirement tasks (`e03-three-item-request`,
`c14-shared-ledger-state`) — because the rule's trigger is the length of the turn
rather than the content of any one call. Tasks that saturate in every arm (`s01`,
`s03`, 25/25 in both arms) or sit at the floor (`s02`, 0/25) cannot see it, and the
lab's gate excludes them by name.

**The paid round guards the completion cost**, and only that: prediction 4 is read
as the arm's pass rate with a Wilson interval beside its parent, one model family,
at the lab's own accounting rules. The spend is the user's decision, not the
session's.

Read after the change has been in use, not from the round: predictions 2 and 3 are
folds of the user's real-work corpus, because that is where `drift` fires and
where the counter-metric lives.

## What is assumed and not verified

- **The result channel reaches the model.** The claim that a host shows the model
  `hookSpecificOutput.additionalContext` / `label` is read in this repository's
  code and docs (`docs/evidence.md`, `docs/hosts.md`'s observability rule) and
  **never exercised against a live host inside this line**. Falsifier (b) exists
  because of this: it is the only check that the notice is still produced and
  handed over, and it is a bound, not a delivery proof — no host reports back
  that the model read the field.
- **The host wiring is complete.** That every host which refuses drift today
  gains the post-tool path in the same change is read in the diff, not measured
  per host. A host left only in the pre-tool path would show as prediction 1's
  falsifier.
- **The population is comparable.** Predictions 2 and 3 compare a fold taken
  after the change against the numbers above, on a corpus that grows and whose
  mix shifts between folds; the 0.5345 floor and the 200-of-272 floor are
  therefore pre-registered rather than recomputed, and the corpus size is reported
  with every fold so a reader can see the drift.

## What this does not claim

- **No effect size.** The line's stated expectation is that a refusal disappears
  and that a notice is still produced; it claims nothing about the model behaving
  better with the notice than with the refusal, and a moved counter-metric would be
  an observation, not a demonstration of cause.
- **No transfer to another model family.** The lab's own result is a null pooled
  over two families and a sign flip between them, so a cell on one family is not
  evidence for the other.
- **No claim about the seven shapes this line did not choose.** They are excluded
  with reasons; the reasons are folds of the ledger, not experiments.
- **No claim that the corpus-wide blocked-claim rate (0.2772 at the 2026-09-20
  snapshot, 736 claims / 204 blocked over 1670 ledgers) is the right
  counter-metric for anything.** It is not usable here: 892 of those ledgers are
  the arm-bench lab's own sessions, whose claim rows are the lab's instrument
  rather than the user's work, which is why the counter-metric is scoped to
  `/Users/rizax/Projects`.

## Method, and what the round records

- Fold the corpus for the three numbers above, each row naming the fold command,
  the corpus size and the date: `bin/tezgah-status --failure-shapes` for prediction
  1, the marker/long-turn fold for prediction 2, the claim fold for prediction 3.
- Deploy the pair, run the free pre-flight, and score the admitted families at the
  lab's own `k`, one model family, recording `pass`, `stop_classes`, `session_rows`
  and the ledger fold per row.
- File each run's receipt with `bin/tezgah-research source failure-fold drift-notice
  --run <orxRunId> --scope real`, and the fold rows in `results.jsonl` with a
  `source` and a `scope`.

## Reported rows

One object per fold and per scored cell: `metric`, `value`, `n`, `corpus` (ledgers
and date), `arm` (for a scored cell), `k`, `model`, `source`, `scope`.
