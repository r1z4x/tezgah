# E2 analysis — the pack is cheaper always-on than tezgah's own 14, and the prediction was wrong

Raw: `results.jsonl` (4 rows).

## Outcome — one prediction REFUTED, one CONFIRMED

| quantity | bytes | scope |
|---|---|---|
| tezgah's 14 shipped skills, installer formula | **9000** | real |
| upstream 38 skills, same formula | **6180** | fixture |
| upstream 16 model-invoked, same formula | 3422 | fixture |
| CORE (always-on text) | 13483 | real |
| CONTRACT (on-demand, shipped as a skill) | 35860 | real |
| `writing-for-agents` + `SKILL-MECHANICS.md` | 13515 | fixture |

**Prediction 1 (upstream ≥ 2× tezgah) is refuted.** The pack's 38 descriptions
cost 6180 B against tezgah's 9000 B for 14 — the pack is **0.69×**, not 2×.

The reason is measurable and not a quirk of the formula. Per-description length:

| corpus | n | mean | median | max |
|---|---|---|---|---|
| tezgah shipped | 14 | 624.1 | 538.0 | 961 (`feature-audit`) |
| upstream all | 38 | 142.0 | 130.5 | 421 (`code-review`) |
| upstream model-invoked | 16 | 192.5 | 173.5 | 421 |
| upstream user-invoked | 22 | 105.3 | 87.0 | 247 |

tezgah writes one long paragraph per skill and then selects a sentence out of it;
the pack writes one short sentence per skill. The router's 140-character cap
(`bin/tezgah-setup:719`) applies to the *rendered line*, not to the metadata
row the report budgets, and it is the row that is measured here.

**Prediction 2 is confirmed**: the craft reference is 13515 B, **0.38× CONTRACT**
— adopting `writing-for-agents` costs less always-on text than the contract
already spends, and most of it (10886 B) is the reference itself, read only when
pointed at.

## What this changes

The cost argument against adoption is not always-on bytes. For this pack the
budget argument is the *opposite* of what the earlier analysis assumed: a
38-skill pack would add less metadata than tezgah's own 14 already carry, while
the router-yield cost (E1: 22 of 38 lines without a trigger) is where the pack
actually loses.

## What this does not show

- The formula is the installer's, and it counts description bytes as if they were
  all always-on. They are not: only opencode gets a generated always-on router,
  and every other host lists `name` + `description` itself. The number is the
  repository's own cost model, used here so the two corpora are compared by one
  rule; it is not a measurement of any host's live window.
- No host's real token cost was measured; bytes are the unit tezgah itself budgets
  in (`bin/tezgah-setup:1754-1762`), and tokens would need a tokenizer and one.
