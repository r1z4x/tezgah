# Agents hallucinate: the grounding half of the problem

- **Source:** Xixun Lin et al., "LLM-based Agents Suffer from Hallucinations: A Survey
  of Taxonomy, Methods, and Directions", arXiv:2509.18970 (v1 2025-09-23, v2
  2025-11-18).
- **Read:** the arXiv API record for the abstract (fetched 2026-09-19).
- Second, related source: "Cite Before You Speak: Enhancing Context-Response Grounding
  in E-commerce Conversational LLM-Agents", arXiv:2503.04830 (v1 2025-03-05), which
  appeared in the same search and addresses the same failure from the product-factoid
  side. Abstract-level only; not read in full.

## What the source says (verbatim abstract)

> "despite their remarkable potential, LLM-based agents remain vulnerable to
> hallucination issues, which can result in erroneous task execution and undermine the
> reliability of the overall system design"
> "we present the first comprehensive survey of hallucinations in LLM-based agents. By
> carefully analyzing the complete workflow of agents, we propose a new taxonomy that
> identifies different types of agent hallucinations occurring at different stages.
> Furthermore, we conduct an in-depth examination of eighteen triggering causes
> underlying the emergence of agent hallucinations."

## What this settles for the structure

- Hallucination is staged, not uniform: it happens at particular points in an agent's
  workflow. So a mitigation attached to one stage (a citation requirement on the
  claim) leaves the other stages open, and the design should say which stage each rule
  covers rather than claiming to have solved hallucination.
- It is a survey, so it compiles others' results; it is evidence that the failure class
  is real and studied, not a measurement of any particular harness.

## What this source does NOT support

- It measures no harness, no prompt, and no product question. It cannot be used to
  claim that a given routing change reduces hallucination.
