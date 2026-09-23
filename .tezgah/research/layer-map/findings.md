# Findings — the layers the word `harness` names

Question: *which layer does tezgah sit in, and how is that boundary drawn against a host, a
framework, an SDK, an IDE plugin, an eval harness, an orchestrator and MCP?*

This line is the research half of plan 005. It is a **literature line**: no experiment ran, and
every claim below cites a note under `literature/` rather than a row this session produced. What
it was asked for is the source base behind the boundary page, not the page.

## What we know

- **The word is assigned to opposite layers by two sources of the same kind.** UHP defines a
  harness as "a complete agent runtime" and names Codex, Claude Code and Hermes; this
  repository's glossary defines `harness` as the wrapper tezgah puts *around* a host. Both
  statements are about the same two layers with the names swapped, which is the ambiguity the
  page exists to end (C01).
- **The definition paper already supplies the inclusion/exclusion list the page has to answer
  to**: agent framework, agent SDK, IDE plugin, eval harness, orchestrator — decided by a
  constitutive definition and applied to six real harnesses plus deliberate edge cases (C02).
  It is a conceptual instrument, not a measurement.
- **A harness gain is structural, not prose.** The agentic-harness-engineering ablation
  localizes its improvement to tools, middleware and long-term memory rather than the system
  prompt, so what transfers between models is the mechanical half of the layer (C03).
- **Two of the six sources are environment-side or model-side, not host-side, and they say so.**
  EnvHarness is a plug-in layer around a *static environment* that keeps the benchmark's
  verifier untouched (C04); Ecdysis's object is a runtime harness trained against failures,
  whose premise is that a failure alone cannot say whether model or harness is at fault (C05).
- **One source is a vendor's own document and carries its own commercial claim.** UHP is
  Apache-2.0, versioned and readable at first hand, but its cost and latency figures are the
  vendor benchmarking its own product on one task across eight harness and model
  configurations, with the README itself noting the winner varies by task (C06).

## Patterns

- **The sense of "harness" tracks where the loop runs, not how big the system is** [C01] [C02]
  [C04] — the definition paper and UHP agree that a harness is the layer that turns
  a model into something that acts, and EnvHarness shows the same word reused for the layer
  that wraps the *world* instead. A boundary statement therefore has to name the loop it talks
  about before it names the layer.
- **Structure transfers, prose does not** [C03]
  [literature/2604.25850-agentic-harness-engineering.md] — the one ablation in the set that
  separates parts of a harness finds the components carrying the gain and the system prompt
  carrying none, which is the same split this repository's own cost measurement sees between
  its rule cascade and its injected bytes.
- **Failure evidence has to be aggregated before it means anything** [C05]
  [literature/2609.11677-ecdysis-failure-driven-collaborative-refinement.md] — a single failure
  is compatible with both a broken harness and a weak model, so the sources that improve a
  harness do it by recurrence across instances rather than by reacting to one instance.
- **A vendor's number and a paper's number are not the same class of evidence** [C06]
  [literature/uhp-spec-2026-09-12.md] — the UHP specification can be read and quoted;
  its benchmark cannot be weighed without the vendor's own methodology page behind it.

## Lessons

- **A definitional source is not a weaker source than a measurement one, it is a different
  artifact**: the page needs a ruler (what counts as a harness) before it can use any of the
  measurements, which is why the one conceptual paper here is the load-bearing one for this
  line (C02).
- **The vendor document has to be cited twice for its two halves** — the specification text is
  openly licensed and read at first hand, the benchmark numbers are the vendor's own and are
  recorded as the vendor's claim. Collapsing them into one "UHP says" would have laundered a
  commercial figure into a specification citation (C06).
- **No protocol was written for this line, and that is the honest state.** The layer's rule is
  that a protocol is the prediction committed before a run; screening sources is not a run, and
  inventing a protocol to make the directory look complete would fabricate a prediction nothing
  tested. The `experiments/` directory is deliberately empty.
- **The notes carry no number this session measured.** Every figure in them is the source's,
  quoted with its source beside it; that is why each claim here is `literature` kind and none
  declares `evidence` (C01–C06).

## Open questions

- **Does the literature's sense ever collapse back onto this repository's?** Both AHE and
  Harness-R1 edit a harness that sits between a model and a task, close to what tezgah calls a
  host; whether a wrapper around a host is a harness under the definition paper's test is a
  question for the page, and this line did not decide it.
- **Where does MCP fall?** None of the six sources decides it. The page's non-goal says the gate
  sees an MCP call and not its contents; the literature here bounds a harness against a
  framework and an orchestrator and is silent on a tool-transport protocol.
- **Is there a source that assigns "harness" to a wrapper around a host, the way this repository
  does?** The five searched are all the other direction. One such source would make the
  glossary's sense citable rather than merely local, and the line has not found it.
- **Would the vendor's benchmark survive an independent run?** Unmeasured here and unmeasurable
  without the vendor's own product; recorded as the vendor's claim for that reason (C06).
