# The infrastructure-change path (practice note)

Grey sources, read 2026-09-20 in this session by a delegated research pass, except
where marked standard. What this note is for: the proposal section of
`skills/feature-audit/SKILL.md` claims a capability change must carry an artifact a
tool can reject; these are the artifacts.

| Mechanism | Source | Artifact it produces |
|---|---|---|
| OpenAPI 3.1 contract-first | `https://spec.openapis.org/oas/v3.1.0` (standard) | the document, versioned by its own versioning clause |
| `buf breaking` gate | `https://buf.build/docs/reference/cli/buf/breaking/` (grey) | a CI check that fails on a breaking schema change against a reference |
| OpenFeature specification | `https://openfeature.dev/specification/` (standard) | a standard evaluation API; the provider behind it |
| Unleash flag types and lifecycle | `https://docs.getunleash.io/concepts/feature-flags.md` (grey) | a typed flag with an expected lifetime (release 40d, operational 7d, kill switch permanent) and stale-flag detection |
| Parallel change (expand/contract) | `https://martinfowler.com/bliki/ParallelChange.html` (standard) | a three-phase plan, releasable at each phase |
| gh-ost | `https://github.com/github/gh-ost` (grey) | a ghost table, a decoupled cut-over, a test-on-replica run |
| Architecture decision record | `https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions` (standard) | a dated record with Title, Context, Decision, **Status**, Consequences |
| Working backwards PR/FAQ | AWS re:Invent 2019 slides (grey) | a press release plus an internal FAQ that answers "are we stepping through a one-way door" before the UI is designed |
| Shape Up rabbit holes / circuit breaker | `https://basecamp.com/shapeup/1.4-chapter-05` (standard) | a pitch naming the appetite and the out-of-bounds, with no-extension as the default |
| GitHub spec-kit | `https://github.com/github/spec-kit` (grey; `spec-driven.md` read) | per-feature spec, plan, tasks; templates that force `[NEEDS CLARIFICATION]` markers, checklists as spec "unit tests", and phase gates (simplicity, anti-abstraction) |
| OpenSpec | `https://github.com/Fission-AI/OpenSpec` (grey) | a change folder: proposal, specs, design, tasks |

The load-bearing sentence for this line, from the delegated pass: *a capability
proposal is detectable as absent exactly when no artifact exists that a tool other
than its author can reject* - a schema diff under a compatibility checker, a
permission-rule diff, a flag with a type and an expiry, an ADR with a non-empty
status.

Quality: the standards are readable at first hand and stable; the vendor pages
(Unleash, gh-ost, buf, spec-kit, OpenSpec) are the tools' own documentation, quoted
for their artifact shape rather than their claims. The two mechanisms that force the
infrastructure question *before* the UI is designed - PR/FAQ's internal FAQ and
Shape Up's "does this need technical work we have never done" - are the ones worth
copying into an audit's proposal gate.
