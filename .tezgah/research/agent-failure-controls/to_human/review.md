# Review of this report's own claims

The six dimensions the research contract requires before a claim leaves the
session, scored on this report, with the findings the two independent review
passes returned. Both passes were read-only and ran in a fresh context that did
not write the sections: `VerifyABC` over A/B/C and `VerifyDEFG` over D/E/F/G.
Between them they checked 39 findings, and every one was applied (three with a
corrected anchor, recorded below).

| dimension | score | basis |
|---|---|---|
| Evidence relevance | pass after correction | no conclusion was overturned; four `major` findings were evidence lines that overreached their own grep. Example, verbatim from the reviewer: "the grep does not reproduce. Re-run over hooks/ + hosts/ it returns 15+ matches". |
| Falsifiability | pass | every claim in `claims.jsonl` carries a falsifier, and each experiment's protocol states its prediction and falsifier before the run. One falsifier fired and is reported as fired (E3's 500-byte allowance). |
| Scope calibration | **weakest dimension** | the dominant defect class: "returns only" over a grep that returns more; "nothing on a hook path calls it" contradicted by `hosts/opencode/plugins/tezgah.js:593-597`; "every host is covered at one place" contradicted by the plugin's own `recordEvidence` (`:215-235`); two E3 figures attributed to `results.jsonl` that live in `results-exploratory.jsonl`. All corrected. |
| Argument coherence | pass | every block runs evidence → gap → control → where → cost, and each group section closes with the modes it could not mechanise and why. |
| Exploration integrity | pass | the failed E3 prediction, the failed `consult`, the late literature fetches, and the one brief-named id that did not exist at write time are all recorded rather than smoothed over. |
| Methodological rigour | pass for the probes, limited for the designs | E1/E2/E3 have pre-registered labels, committed protocols and committed raw output. The six design sections are not measured at all, and the report says so in every synthesis caveat. |

## What the review changed

- **A**: the mode-8 note claiming `[2605.05403]` was absent is false - the note
  now cites it; the any-position placation scan was narrowed so it cannot block a
  reply that owns a mistake, which the contract requires; the Stop envelope
  wording replaced the paper's `continue` (no adapter emits that field).
- **B**: the result-inspection grep restated to the form that reproduces
  (`tool_response|exit_code`), with opencode added to the hosts that already read
  an outcome (`hosts/opencode/plugins/tezgah.js:212-213`, `:223-225`);
  three anchors re-targeted to `hooks/tezgah_integrity.py:391-394` (failure
  block), `:395-396` (pass branch), `:325-327` (ran-not-passed).
- **C**: the contract-drift gap scoped to the five hosts that run their own copy
  (opencode repairs its rendered contract once per session); the E3 figures
  re-attributed; the prefix-walk consequence downgraded from a live mixing risk to
  a latent hazard; five minor enumerations completed.
- **D**: the rollback control no longer presents `.tezgah-bak` as new -
  `bin/tezgah-setup:202-205` already backs up every file it writes.
- **E**: mode 1's signal restated honestly (sink-side argument matching, because
  no hook sees a tool result); the untrusted-read mark bounded to the turn with a
  mechanical clear; mode 4's redaction scoped to include the opencode plugin's
  JavaScript ledger writer.
- **F, G**: two cross-section conflicts resolved by the router rather than
  patched locally - one ledger schema (`P1`) and one attempt counter (`P4`) in the
  synthesis, with F mode 6, G control 6, G control 7, F mode 4 and G control 10
  referencing them instead of each defining their own.

## Three corrections where the reviewer's anchor had gone stale

1. `literature/INDEX.md` grew a four-line paragraph after `VerifyDEFG` read it, so
   the non-fetch record lives at `:55-58`, not `:51-54`; the fixer used the
   current file.
2. The same pass reported `literature/` as "39 report ids" with two named ids
   absent; by then 41 ids existed and both were present, so `F` states the
   observed count.
3. One parenthetical in the untrusted-input grep explanation was corrected against
   the actual line (`hooks/tezgah_policy.py:341` is a provenance mention, not an
   "uncertainty" substring).

## What the review did not test

- It verified citations and re-ran absence greps; it did not test whether any
  proposed control changes what an agent does. No control in sections A-G was
  implemented or run, so every `Control` line is a design, not a result.
- It did not re-derive the E1/E2/E3 numbers independently; it read the raw files
  and compared them with what the sections claim.
- Two OpenAlex reviews (prompt injection in agent systems, MCP tool poisoning)
  remain unfetched; both sections that needed them say so and cite the local
  inventories instead.
