# Findings — the failure-driven refinement's first candidate

Question: *does removing the drift refusal and delivering the same notice on the
tool-result channel drive `drift` deny rows to zero without raising the real-work
blocked-claim rate above its 2026-09-20 value of 0.5345?*

**The state below was written before the round and is left as it stands.** The
round the protocol pre-registered then ran on 2026-09-20 and read as an **untested
factor, not a null**: the arms' `session_rows` of 4-15 per row never reached
`DRIFT_STEPS = 25` work rows in one turn, so no arm could fire the rule; the
mechanism is verified outside the arms (49 `drift` marker rows, 0 deny rows over
the round's 30-ledger window); prediction (b) met its producer floor (248 of 308
turns); and prediction (c) — the falsifier that can end the change — is undecided
at 8/12 = 0.6667 against the 0.5345 floor. The line is now `concluded`, H1 stays
`untested`, and the round's outcome is recorded in `to_human/report.md` and as
claims C06-C07.

## What we know

- **All 227 `drift` refusals land in the user's real work, none in the lab**: 179
  sessions at the 2026-09-20 snapshot of 1669 ledgers, and 0 fires in any
  arm-bench ledger (C01). The candidate analysis on the same date read 177
  sessions / 225 fires — the same shape, a corpus that had not finished growing.
- **The refusal carries no correction to the call it refuses** (C02): 130 of 227
  (57.3%) refused calls were re-issued identically inside the same user turn —
  130 wasted round trips — and 97 (42.7%) were never re-issued, so 97 composed
  calls the session never got back. No fire sat on a turn with no work rows, and
  only 15 had an accepted check earlier in the turn.
- **The counter-metric has to be scoped to real work** (C03): 124 blocked of 232
  claims = 0.5345 over the 444 ledgers whose workspace set contains
  `/Users/rizax/Projects`, against 204/736 = 0.2772 corpus-wide, because 892 of
  the 1670 ledgers are the arm-bench lab's own sessions and their claim rows are
  the lab's instrument, not the user's work.
- **Seven of the eight recurrent shapes are excluded on the ledger** (C04):
  `task` fires 154 times in the lab and 0 times in the real work; `consent`
  re-uses 9 of 97; `sink` 1 of 40; `retry` 0 of 25; `secret` 0 of 18; `shortcut`
  1 of 34 with a quarter of its rows carrying no call id; `loop` sits at 7 fires.
- **The change is already observable, uncommitted**: at the 1670-ledger read of
  2026-09-20 the corpus holds 230 `drift` marker rows against 228 deny rows, and
  the two extra are marker-only turns at 19:35:32 and 19:37:51, both after the
  gate and its host wiring last changed at 19:35:05-19:35:22 — a marker written,
  no deny row (C05). Two turns is not a result; it is the shape prediction 1
  predicts, seen in the working tree the round will be deployed from.
- **The candidate is written down before anything ran**: the change (no refusal;
  the same text on `hookSpecificOutput.additionalContext` / the host's `label`;
  the marker row kept; no `deny` row), its three falsifiers and its two baseline
  numbers are in `experiments/drift-notice/protocol.md`. Nothing has been run:
  the ratio of refusals to re-issued calls is a count of what the corpus holds,
  not an experiment.

## Patterns

- [C02] [C04] — **A refusal is only a correction when the call it refuses is
  wrong, and the ledger can tell the two apart**: the shapes whose model stops
  (`retry` 0 of 25 re-issued, `secret` 0 of 18) are rules doing their job, and
  the shape whose model re-issues unchanged 57.3% of the time while carrying no
  correction is a delivery mechanism wearing a refusal's clothes.
- [C01] [C02] — **Channel choice is part of a rule's cost, not an implementation
  detail**: the same text costs 128 identical round trips a corpus-term because
  the only channel a pre-tool hook had was a refusal, and the repository's own
  post-tool path (`hooks/projects-posttooluse.py`) already carries advisory text
  to the model with no refusal at all.
- [C03] — **A corpus-wide rate is not a behaviour rate when the corpus has a lab
  in it**: 0.2772 and 0.5345 are the same measurement over two populations, and
  the 892 lab ledgers are what make the corpus-wide one unusable as a
  counter-metric.
- [C02] — **A marker row is a receipt of production, not of delivery**: the row
  is written before the result envelope is printed and no host reports back, so a
  marker count can falsify a broken producer and cannot prove the model read the
  notice; the protocol's second falsifier is worded as a floor because of it.

## Lessons

- The `drift` rule fired on this session's own write while the protocol was being
  written: the tool result came back as the re-statement instead of a success
  message and the write had not happened, so the call had to be re-issued
  unchanged — the rule's cost landed on the writer of a long turn exactly as the
  corpus says it does.
- The corpus moves while a line is written (1661 -> 1669 -> 1670 ledgers, 225 ->
  227 drift fires, 232 -> 233 real-work claims): a number folded here is a value
  only with its date and its ledger count beside it.
- The eight shapes' rankings, the exclusions and the two floors are folds of a
  ledger written by the harness the change touches; the fold reads the deny rows
  the change removes, so the same fold cannot be both the instrument and the
  outcome once the change is in — the round's own arm ledgers are what the
  post-change numbers come from.

## Open questions

- Does the tool-result channel reach the model at all? Read in this repository's
  code and docs, never exercised against a live host inside this line — which is
  why the protocol's second falsifier is a production floor rather than a
  delivery proof.
- Which lab family's single prompt crosses 25 work rows in one turn? Unknown
  until the round's own run ledgers are folded; the lab measures bounded tasks
  and its README says it does not measure long-horizon behaviour.
- Does the change move the real-work blocked-claim rate in either direction, and
  if it falls, is that the notice working or the refusal's interruption going
  away? The protocol predicts "not above 0.5345" and claims no more.
- What happens on a host that refuses `drift` today and is not wired into the
  post-tool path by the change? The refusal count would not reach 0 there, which
  is falsifier (a) rather than a separate finding.
