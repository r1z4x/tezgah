## google/gemini-2.5-pro:online
I recommend proceeding with the proposed change, but with one modification: adopt and adapt the existing `Geo1230/product-analysis` skill instead of authoring a new one from scratch.

Your specific questions are answered as follows:
1.  A new `product` rule is the correct fix. Widening `research` would conflate two distinct tasks—discovery vs. synthesis—and lead to misaligned agent behavior, defeating the purpose of the change.
2.  The five-class evidence rubric is not over-specified; it is the most critical component of the fix. It forces the agent to ground its analysis in verifiable data, directly addressing the defect of un-evidenced, generic answers.
3.  Vendor the single `Geo1230/product-analysis` skill. It is a high-quality, MIT-licensed, single-file implementation that aligns perfectly with your stated goals. This is strictly better than re-implementing its features, referencing it by URL (which doesn't fix the defect), or vendoring a large, multi-skill library.

### Key Reasons

1.  **The Change Directly Addresses the Defect with Appropriate Structure.** The observed defect is that product-related prompts receive generic, un-scaffolded responses. The proposal to add a dedicated `product` class with a strict evidence requirement moves this class of task from an unstructured chat to a verifiable workflow. This aligns with the core philosophy of `tezgah` as an "agent task workbench" that provides structure and resources for completing tasks ([tezgah.dev](https://tezgah.dev/)).

2.  **Specialization Prevents Mode Collapse.** A separate `product` rule ensures the agent receives a prompt tailored to product analysis, not a generic "research" prompt. The `komunite/tezgah` project is built on a foundation of specialized skills (`saas-database`, `saas-auth`, `saas-payments`) for a reason: specialized tools produce better results than general-purpose ones ([komunite/tezgah](https://github.com/komunite/tezgah)). Merging `product` into `research` would be a step backward from this principle.

3.  **High-Quality Prior Art Exists and Should Be Leveraged.** The `Geo1230/product-analysis` skill is a near-perfect implementation of the proposal's intent ([GitHub.laiyagushi.com](https://github.laiyagushi.com/Geo1230/product-analysis)). It audits across code, UI/UX, and product strategy; demands evidence; produces a prioritized backlog; and even generates a handoff document for the next agent. Adopting and adapting this single MIT-licensed skill would be significantly faster and likely result in a more robust outcome than building a new skill from zero. Its multi-mode analysis (e.g., `full`, `quick`, `just product`) also provides built-in flexibility.

### What Could Make This Wrong

1.  **Skill Adaptation Cost Is Underestimated.** The `Geo1230/product-analysis` skill, while comprehensive, might have subtle dependencies on a different agent's contract or prompting style. The effort to adapt it to `tezgah`'s specific `CORE` contract and `tezgah-research` integration could prove greater than the effort to build a simpler, native skill from scratch.

2.  **The Structure is Overly Rigid.** The strict, evidence-based framework might be too constraining for early-stage, purely generative ideation prompts like "what are some crazy ideas for our next feature?" The system might become good at analysis but poor at creative brainstorming. The `Geo1230` skill's multiple modes may mitigate this, but it remains a risk.

3.  **Context Window Pressure.** Adding another conditional paragraph to the `CORE` prompt consumes valuable context window space for every turn where the `product` rule is armed. If the context is already near its limit, this could degrade the model's performance in other areas during product analysis tasks.

What would change my mind:
A side-by-side comparison showing that a minimal, from-scratch skill consistently produces better, more concise product analysis backlogs for this project's specific domain than the adapted `Geo1230/product-analysis` skill.

## x-ai/grok-4.3:online
**recommendation**  
Add the new `product` class + dedicated skill exactly as proposed. It is the minimal, documented-compliant change that delivers a purpose-built paragraph instead of repurposing the `research` one.

**key disagreements**  
Widening `research` is strictly worse: product prompts need PM/PE axes, HEART (normalized ratios), OST opportunity scores, and the five evidence classes, none of which are native to the ML-experiment paragraph. The five-class rubric is the right invariant because it forces explicit provenance on every claim the model emits; collapsing it would lose the “none” escape hatch and the concrete citation formats that already work for `research`. Vendoring `phuryn/pm-skills` wholesale is unnecessary when the proposed skill already extracts the minimal reusable standards; a URL reference is sufficient for now.

**unchecked assumptions**  
The classifier regexes will be precise enough that “product manager seviyesinde analiz” reliably matches while “kullanıcı deneyimi raporu” does not; the new paragraph will be short enough that the model actually reads and applies it on the first turn; `research-off` will be the only kill-switch needed.

**what would change your mind**  
A head-to-head A/B test (same 8 prompts, 20 runs each) showing the widened-`research` variant produces higher evidence density or fewer hallucinations than the dedicated `product` paragraph.

**requested evidence**  
1. The exact new regex entries planned for `PROMPT_HINTS`.  
2. The full text of the `product` paragraph that will be appended to `CORE`.  
3. Classifier test output for the two negative prompts listed in AC1.

## referee (google/gemini-2.5-pro:online)
### 1. Recommendation
I recommend acting on the answer from Model A (Gemini), which advises proceeding with the proposed change but with a crucial modification: instead of authoring a new `product-analysis` skill from scratch, adapt the existing, high-quality `Geo1230/product-analysis` skill.

This recommendation is superior because:
1.  **It directly addresses the defect with a best-in-class tool.** The core problem is that product questions receive unstructured, un-evidenced answers. The `Geo1230/product-analysis` skill is purpose-built to prevent this, providing a multi-dimensional audit across product, UI/UX, and code, and generating structured artifacts like an execution backlog and an agent handoff document [[GitHub.laiyagushi.com](https://github.laiyagushi.com/Geo1230/product-analysis)]. This aligns perfectly with `tezgah`'s philosophy of being an "agent task workbench" that provides structure to complex tasks [[tezgah.dev](https://tezgah.dev/)].
2.  **It avoids reinventing the wheel.** The `Geo1230` skill has already implemented many features described in the proposal, such as demanding evidence and creating a prioritized task list. Adapting this MIT-licensed skill is likely faster and will result in a more robust and feature-rich solution than building a minimal version from zero.
3.  **It correctly answers the user's specific questions.** It affirms that a new, dedicated `product` rule is correct (Question 1), that the evidence rubric is essential (Question 2), and provides a concrete, superior path for handling prior art by vendoring a single, well-chosen skill (Question 3).

While Model B (Grok) correctly validates the user's proposal, Model A's recommendation to leverage a specific, high-quality open-source component is a more insightful and strategically sound engineering decision.

### 2. Key disagreements
The models agree that a new, dedicated `product` rule is the correct fix and that widening the existing `research` rule would be a mistake. They also agree that the proposed five-class evidence rubric is a critical and well-specified part of the solution.

Their key disagreement is on **how to implement the new `product-analysis` skill and handle prior art**:
*   **Model A (Gemini)** argues for adapting the specific `Geo1230/product-analysis` skill found in the search results. It views this as a superior alternative to both building from scratch and the other options presented in the original question.
*   **Model B (Grok)** argues for creating a new skill from scratch as described in the proposal. It suggests that vendoring a large library like `phuryn/pm-skills` is unnecessary and that a URL reference is sufficient, as the proposed skill already captures the core standards. It does not mention the `Geo1230` skill.

This conflict centers on a "build vs. buy" decision. Model A identifies a specific component to "buy" (adapt), while Model B defaults to "build."

### 3. Unchecked assumptions
Both models accepted the framing of the problem and assumed the following without verification:

*   **Architectural Fitness:** Both assume that injecting a conditional paragraph into the system prompt is the most effective way to guide an agent for a complex task like product analysis. They don't question if this `tezgah` mechanism is sufficient or if a different architecture (e.g., a multi-step agent chain) would be better.
*   **Framework Supremacy:** Both accept the proposed standards (HEART, Opportunity Solution Tree) as the correct ones for the task without considering alternatives or their potential limitations.
*   **LLM Compliance:** Both models implicitly assume that the agent will be able to reliably understand and follow the complex set of instructions in the new skill—from adhering to the five evidence classes to correctly applying the HEART framework and generating a scorecard.
*   **Classifier Efficacy:** Both assume that a few regular expressions will be sufficient to accurately classify a wide range of natural language prompts for "product analysis" while correctly ignoring related-but-distinct prompts like "user experience report." The original defect report shows this is a non-trivial problem.

### 4. What would change my mind
My recommendation is to adapt the `Geo1230/product-analysis` skill based on the assumption that it is a faster and more robust path than building from scratch. I would change my mind if I saw evidence to the contrary.

Specifically, I would reverse my recommendation if a spike or proof-of-concept demonstrated that:
1.  The effort to adapt the `Geo1230/product-analysis` skill to the `tezgah` contract and `tezgah-research` workspace is significantly higher than the effort to build a new, native skill that meets all acceptance criteria.
2.  A minimal, from-scratch skill (as suggested by Model B and the original proposal) consistently produces higher-quality, more relevant analysis for the `tezgah` project's specific context than the more generic, adapted `Geo1230` skill.

### 5. Requested evidence
To resolve the disagreement and de-risk the recommendation, I would request the following evidence, combining the excellent list from Model B with an item to address the recommendation from Model A:

1.  **Classifier Design:** The exact list of `(key, regex)` pairs proposed for `PROMPT_HINTS` to detect product-related prompts, including those in other languages like Turkish.
2.  **Prompt Text:** The full text of the `product` paragraph to be added to the `CORE` contract, as its length and clarity are critical to its effectiveness.
3.  **Comparative Estimate:** A brief technical spike or time-boxed investigation comparing the effort required to (a) adapt the `Geo1230/product-analysis` skill versus (b) build the new skill from scratch.
4.  **Negative Test Cases:** The output of running the proposed classifier against the negative examples from the defect report (`bu ürünü analiz et...`, `kullanıcı deneyimi raporu`, etc.) to prove it doesn't over-fire.

consulted: google/gemini-2.5-pro:online, x-ai/grok-4.3:online | failed: none
referee: google/gemini-2.5-pro:online
