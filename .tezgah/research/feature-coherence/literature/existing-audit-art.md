# Existing audits, and what they do not cover (practice note)

Repositories read at source on 2026-09-20, as the user asked: is there already a
skill, prompt or repository that closes this?

| Artifact | What it is | What it covers | What it does not |
|---|---|---|---|
| `EnchStyle/ui-ux-audit-skill` (MIT, read at first hand) | an agent skill: 15 categories, a 0-100 score with a ship verdict, severity weights, a per-finding format (Found / Why / Fix / **Prevent**), a prevention pre-flight, and four product profiles | the surface: typography, layout, states, forms, responsive, a11y, data viz; its stated root cause is that a model "generates a plausible static snapshot of a single state" | the layers behind the surface: no capability, contract, flow-prerequisite or permission check; its remedies are lint rules and tests, not a capability change; the nearest existing art, and the source of the `Prevent` line this repository's skill adopted |
| `github/spec-kit` (MIT, `spec-driven.md` read) | spec-driven development: `/specify`, `/plan`, `/tasks` templates and a constitution | templates that force `[NEEDS CLARIFICATION]` markers, checklists that act as spec "unit tests", phase gates (simplicity, anti-abstraction), test-first file order, traceability from every technical choice to a requirement | it specifies work that is being built; it audits nothing, and an existing feature has no spec to be driven from. Worth copying: the gate shape (a template whose missing section is visible) |
| `bghcore/form-engine` comparison doc (read) | a feature matrix across form libraries (RJSF, TanStack Form, uniforms, SurveyJS, Formio, Form Engine) | what a declarative rules engine with cross-field effects, computed values and built-in wizards gives you | it is a library choice, not an audit: a config-driven form makes the field contract inspectable, which is worth knowing, but nothing there reports a defect |
| `mrmgoynes/schema_shift` (read) | a CI sentinel: DB schema vs OpenAPI, with a chaos module | field-level drift between the database and the declared contract, with a failing build | it checks the contract against the store; it does not compare either against the surface, which is where the feature's defects live |
| `07Kaustubh/driftspec`, `calvinlee326/api-contract-drift-detector` (read as listings) | CLI diffs of OpenAPI specs and live APIs | breaking-change classification for API consumers | same shape: contract-to-contract, no surface |
| The audited repository's own `apps/admin/lib/admin-crud-coverage.ts` + test, and `scripts/verify-api-contract.mjs` + `docs/openapi.json` | a hand-kept CRUD registry (route x operations x delete strategy x terminal state) and a contract verifier | capability coverage for ten tenant routes, and API drift for declared endpoints | `/users` is **not** in the registry (it is platform-disposition), so the very surface this line audited is outside the repository's own capability check; the contract verifier compares spec to generated client, not spec to call sites |

Quality: every row above is a repository or documentation page read in this session,
not a claim from memory. The pattern across all of them: **the tools that automate
this live at one layer boundary each** (spec-to-spec, spec-to-store,
surface-to-rule), and none carries the feature's whole path - which is the gap this
line's skill fills, and why its matrices are tables a person or an agent fills
rather than a tool that runs.
