# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-20 init: opened this line on the user's report that tezgah still allows
  "uy durma veriyle demo yapmak / uydurma veriyle demo yapıp gerçekmiş gibi sunmak"
  (a fabricated demo presented as progress). Question fixed before any run:
  which classes can be refused mechanically, which only named as limits.
- 2026-09-20 protocol E1-scope-audit and E2-number-containment written and
  committed (83fc406) before either run, each with predictions and falsifiers.
- 2026-09-20 E1 run: 520 rows across 8 lines classified by their path text -
  438 unknown, 79 fixture, 3 real. Prediction 3 missed; the finding is that the
  classifier itself is the problem, so the field must be declared, not inferred.
- 2026-09-20 E2 run (first pass): a containment probe that walked whole directories
  and used a loose tokenizer - 63 of 76 (83 percent). It hung on its first run
  (an unbounded directory walk) and was bounded before it produced anything.
- 2026-09-20 dead end: the lone fixture-presented-as-real flag turned out to come
  from the directory name `E6-rule-reach-probe` containing "probe". Reported as the
  method's failure rather than as a finding about a line.
- 2026-09-20 literature: three formal sources via orx discover and orx paper -
  capped evaluation (2606.07379), hack-verifiable environments (2605.20744), and a
  swarm study whose prompt-only integrity rule did not bind (2609.04170).
- 2026-09-20 pivot: the deliverable is not a longer prose rule but a field. E1 says
  the fact cannot be recovered, the swarm study says prose does not bind, and
  2605.20744 says a planted expectation is what makes the mismatch decidable.
- 2026-09-20 implemented control A (`scope`, with the widening claim refused and the
  write path agreeing), control B (containment as a warning), and the visibility
  half (`status`, the report rule, `source --run --scope`). 10 tests added; the
  checker's 195 research tests pass.
- 2026-09-20 E2 re-run, second pass, because the first measured a rule the layer
  does not ship: the shipped tokenizer and the cited-file reader give 53 of 71
  (75 percent). Recorded as a second `pass` in results.jsonl and superseded in C07
  rather than editing the first pass's numbers.
- 2026-09-20 the new rule caught its own line: C07 first asserted a number
  (58 of 78) that no recorded artifact held, and the containment warning named it,
  so the measurement was recorded instead of the sentence rewritten.
- 2026-09-20 declared the scopes of this line's own rows and of `harness-hardening`
  E1's fixture rows, and declared C01/C02 of that line `fixture`; `status` now
  prints them. What stays undeclared on other lines is the debt the warn names.
- 2026-09-20 closure pass, six slices in parallel: the four line slices declared the
  scope of 510 of 813 rows across four other lines (harness-hardening 82,
  infra-candidates 268, research-layer-audit 142, judge-positioning 18) and named the
  stand-in on every fixture row, reading each experiment's protocol, probe and
  `command` field and leaving a basis line in its `analysis.md`; two slices built the
  stand-in controls (the `fixture` description and the scratch-path reminder). One
  slice superseded a claim whose figure no artifact held rather than widening a proof
  list for it, which is the class this line exists to refuse.
- 2026-09-20 E2 third pass and E3 census: the shipped containment rule leaves 80 of 82
  claims contained, and the census reads 0 of 822 rows undeclared. This session's own
  probe first reported 81 because it omitted `_comparable` on the statement side - a
  copy of the rule drifting from the rule, corrected before anything was committed.
- 2026-09-20 citations: the hooks' line numbers moved under this session's edits, so
  every `file:line` reference in docs/ was re-anchored; a script keyed on adjacency
  reported success while three bare references still pointed at the wrong line, and
  `bin/tezgah-docs --citations` was the thing that caught them (now 0 outside).
- 2026-09-22 closure pass over this line's own record, no run and no model call: the eight
  review findings now carry a `status` and a `reason` (five closed, three open as named limits)
  instead of a severity alone, so a reader can tell which of them still needs work and which is
  a limit nothing here can close; the report's limits section now names the three open questions
  of `findings.md` - the honesty of the declaration, whether control C can be built without
  changing what is measured, and whether a stand-in registry would stay cheap - as unmeasured
  rather than leaving them only in the findings file; and the by-design warning bullet no longer
  quotes counts (seven protocols, five supersede relations), because those classes are read from
  `check` over a tree other lines are still changing and the numbers it carried had already
  drifted.
