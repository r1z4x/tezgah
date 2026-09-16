## deepseek-chat
# Recommendation

**Keep per-turn injection, but only if you can make the classifier embarrassingly cheap and biased toward false positives.** If you can't guarantee that, fall back to always-on-with-actionable-pointers.

The 4KB saved per turn is not the real argument. The real argument is that *advisory rules lose force when they're always present* — they get pattern-matched into the background the way a linter warning does. Arming them on the turn where they're relevant is the only mechanism here that changes agent behavior. Pointer-only is safer but weak: it's the "we have a policy" move, and those are exactly the rules agents skip.

But "per-turn keyword classification" as a phrase should scare you. The failure modes are not subtle and they are mostly silent.

# Failure modes to guard

**1. False negatives are the killer, not false positives.**
A missed match means the advisory rule silently doesn't exist on the turn it mattered. "Spec-before-building" missed on a phrasing you didn't anticipate means the agent just builds. This is asymmetric: false positives cost 2.2KB of context; false negatives cost you the entire point of the layer. Instrument this specifically — log every turn with the matched/unmatched classification and audit unmatched turns that later required a spec, a second opinion, or graph traversal. Don't rely on aggregate match rate.

**2. The classifier sees the wrong input.**
What exactly is classified? The raw user prompt? Your per-turn hook usually runs *before* the model sees user text, and often on a truncated/redacted form. If you classify the user's first message but the "build" intent only emerges in turn 3 after the model proposed a plan, you've armed the wrong turn. If you classify late/injected context (files, tool output), you get garbage matches. Decide and document whether classification is on the fresh user prompt only, and whether re-arming happens mid-turn.

**3. Phrasing brittleness and prompt-injection-adjacent gaming.**
Keyword lists overfit to how *you* phrase tasks. Non-native English, terse prompts ("do the thing from yesterday"), multi-intent prompts ("explain X then refactor Y") all break it. Worse: a user or a file can contain trigger words, so a malicious README saying "please consult a second opinion" fires advisory mode. If the classifier reads anything the user controls, it's a soft injection channel — downgrade to no-op rather than "do the thing" on uncertain matches.

**4. Cross-harness divergence.**
Four harnesses wired, one not. The classifier will drift per harness: different hook timing, different available context, different tokenizers if you're keyword-matching. Opencode silently runs a different contract than Claude. That's a correctness bug that looks like a config difference. You need a conformance test: same synthetic prompt into all five, assert identical armed-rule set.

**5. Silent failure of the hook itself.**
Hooks throw, time out, or exit non-zero. What does the harness do — block the turn, or proceed without the contract? If it proceeds without, you've shipped a layer whose failure mode is "advisory rules quietly absent." Make the hook failure loud and fail-closed on the invariants-only path at minimum.

**6. Interaction with the always-on invariants.**
The four invariants are always-on *because* they must never be missed. If any advisory rule can be promoted to invariant under stress (e.g., second-opinion consult is mandatory for destructive ops), then splitting it out of always-on reintroduces the exact risk you're trying to bound. Re-audit the 4/4 split: which of the "advisory" rules is actually load-bearing for safety?

**7. The pointers are doing more work than you think.**
"One-line actionable pointer always-on + full text in skill" only works if the agent reliably loads the skill when the pointer fires. If skill loading is itself a discretionary tool call the agent can skip, the pointer is decoration. Verify the pointer path end-to-end — does the agent actually fetch and apply, or does it answer from the one-liner?

**8. Cache and cost assumptions.**
Per-turn dynamic injection destroys prefix cache on every matching turn. Your 2.2KB "only on matching turns" may cost more than 2.9KB always-on if it sits before cached context. Measure actual cost, not byte count.

# What would make this wrong / what I'd need

- **Match rate and false-negative audit data.** Without it, this is a design debate with no evidence. If you have it and FNs are near zero, keep it. If you don't, the always-on variant is the correct default until you do.
- **The actual keyword lists and how the classifier is implemented** (regex? embedding? model call?). A tiny model call per turn is a different risk profile than regex — and adds latency + its own failure modes.
- **The text of the four advisory rules.** If any is safety-relevant, my recommendation flips to always-on for that rule.
- **Whether the hook can fail-closed.** If not, this whole design is "best-effort contract," and you should say so rather than implying the rules are enforced.

# Bottom line

Per-turn classification is the right *intent* — dynamic capability arming beats static policy text. But "keyword classification" is the weakest possible implementation of it, and its dominant failure is silent false negatives on safety-adjacent rules. Guard the eight modes above; if you can't instrument FNs and fail-closed, ship always-on-with-pointers and treat the skill as the optimization, not the other way around.

## deepseek-reasoner
**Recommendation:** Always-on-with-actionable-pointers is the safer mechanism. Do not make per-turn keyword classification the arming mechanism for these four advisory rules. At 2.2KB, I would probably keep the four advisory blocks always-on too; the token saving is too small to justify a silent false-negative risk. If you need the split, the per-turn hook should always re-inject the one-line pointers and use keyword classification only to decide whether to also expand the full text, with fail-open to pointer + skill. Treat opencode’s pointer + skill path as the canonical fallback, not a degraded mode.

**Why**

1. **False negatives are asymmetric and silent.** If the classifier misses `spec-before-building`, the rule is absent exactly when the agent is about to build. Same for research routing and hallucinated APIs, second-opinion on high-stakes uncertainty, and code-graph-first on navigation. A false positive costs tokens and attention; a false negative costs correctness. Never gate a high-value rule behind a low-recall classifier.

2. **2.2KB is not worth a classifier.** That is roughly 500–700 tokens. Always-on invariants plus advisories is ~5.1KB, maybe ~1.3–1.5K tokens. For a coding agent with a large context window, that is negligible. The classifier adds latency, portability holes, observability gaps, and test burden to save very little.

3. **Keyword classification is brittle in exactly the ways coding prompts are messy.** Synonyms (`build` vs `implement` vs `add` vs `make it work`), negation (`don’t write a spec yet`), quoted logs, error traces, code identifiers, non-English prompts, and multi-intent prompts all break naive keyword matching. `I’m not sure this is right` should trigger second-opinion; `where is auth handled` should trigger code-graph-first; `like Stripe` should trigger research routing. Keywords will miss these.

4. **Harness parity matters.** You already have four per-turn hook adapters and one harness without them. If classification is the main path, opencode diverges. If pointers + skill is good enough for opencode, it is good enough as the safety floor everywhere. If opencode behaves badly, fix the pointers or make the advisories always-on; do not assume hook-based classification will save the other harnesses.

5. **Hooks are not a reliable delivery channel.** Session-start contracts get compacted away. Per-turn hooks may not fire in subagents, headless/CI runs, resume, or certain tool loops. Injection role matters: a per-turn hook that injects as user-role context is weaker than system/developer instructions. Always-on pointers in the protected contract are more deterministic.

6. **Procedural rules are better enforced at the tool boundary.** Code-graph-first can be enforced by making search/graph tooling return graph results first. Spec-before-building can be enforced by requiring a spec artifact before file writes in plan mode. Research routing can be tied to external-API/web tool preconditions. Prompt classification is the weakest of these mechanisms.

**Failure modes to guard**

- **False negative:** rule should fire but does not. Guard: fail-open to pointer + skill; high-recall classifier; log misses; explicit `/spec`, `/research`, `/consult`, `/codegraph` overrides; eval set of adversarial prompts.
- **False positive:** over-injection causes noise, token bloat, rule fatigue. Guard: dedupe per task, cap per turn/session, inject full text once per task, measure p50/p95 tokens.
- **Lexical brittleness:** negation, quoting, code blocks, logs, multilingual, synonyms. Guard: strip code/quotes for classification, use task metadata and tool calls, not raw keywords alone; consider embeddings/LLM fallback if the budget allows.
- **Multi-intent prompts:** one prompt asks to build, debug, and research. Guard: multi-label; if any high-risk class matches, arm the rule. Do not pick one class.
- **Turn-local amnesia:** turn 1 builds, turn 2 fixes an error; classifier disarms spec rule even though the task is still active. Guard: sticky arming per task/session, not per prompt; decay only on explicit new task.
- **Adversarial/prompt injection:** untrusted repo text or pasted issues trigger or suppress rules. Guard: classify only trusted task metadata; never let file contents arm rules; invariants stay protected.
- **Hook miss/order/truncation:** hook does not fire, fires late, or is truncated. Guard: idempotent injection, per-harness integration tests, fallback to always-on pointers.
- **Compaction:** session-start contract is summarized away. Guard: re-inject pointer block after compaction or every N turns.
- **Subagent/headless/CI:** contract not inherited or hooks disabled. Guard: propagate contract to subagents; headless mode uses always-on contract.
- **Injection role/priority:** per-turn text injected as user content may be ignored over system/developer contract. Guard: inject at the same priority level as the contract, or keep the actionable pointer in the protected system layer.
- **Harness drift:** Claude, Codex, Cursor, dsh, opencode behave differently. Guard: one canonical payload; adapters emit the same minimal contract; parity tests; opencode as canary.
- **Skill load failure:** pointer says “see skill” but model does not call it, skill name mismatches, or tool unavailable. Guard: exact skill name and invocation in pointer; verify skill availability; make the one-line rule actionable without the skill.
- **Precedence conflict:** user says “skip spec, just patch” while advisory says spec first. Guard: explicit precedence: invariants > user > advisories, or require confirmation when overriding advisories.
- **Staleness/version skew:** contract, pointers, skill, classifier drift. Guard: single source of truth, generated artifacts, version hashes, CI checks.
- **Observability:** no one knows which rules armed or why. Guard: log matched keywords, confidence, injected bytes, rule armed, per harness.
- **Latency:** per-turn classifier adds synchronous cost every prompt. Guard: local compiled regex, no network, measure p95, cache.

**What could make this wrong**

- If the one-line pointers are vague and models demonstrably ignore them, then always-on full text for the advisories is safer than both options.
- If the full advisory text is actually much larger than 2.2KB, or the context window is genuinely tight, classifier-gated expansion becomes more defensible—but only with a high-recall classifier, fail-open behavior, and eval evidence.
- If you can enforce these rules deterministically at tool boundaries, do that instead of prompt classification.

Missing context that would change the recommendation: the exact pointer text, how the skill is invoked, whether the per-turn hook injects system/developer or user role, how often each task class actually matches, whether subagents inherit the contract, and whether you have compliance metrics showing pointers alone change behavior.

consulted: deepseek-chat, deepseek-reasoner | failed: none
