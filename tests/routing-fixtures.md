# Routing fixtures

A situation a session actually gets handed, the skill it should reach, and the
words the generated router line has to keep for that to happen. The router is
generated from the descriptions, so a reworded description can drop the one term
a situation matches on and nothing else in the suite notices: this table is the
regression net. It is checked by `tests/test_setup.py::RoutingFixtures`, against
the routers the installer writes (`opencode-skills.md` and its on-demand
`opencode-skills.full.md`).

Two rules for a row:

- the skill is a name in `bin/tezgah-setup`'s `SKILLS`, and every name there has
  at least one row here - a skill with no fixture is one nothing proves reachable;
- the phrase in the last column has to sit inside the router line's 140-character
  cut, because a trigger past the cut names a skill a session cannot match.

| situation | skill | the router line must keep |
|---|---|---|
| an audit, "every call site", "what breaks if", a task too wide for one context | `harness` | every call site |
| the deep detail behind the compact core: the code graph, a subagent fan-out, codegen, a second opinion | `tezgah-contract` | subagent fan-out |
| any coding task - writing, fixing, refactoring, choosing a dependency | `ponytail` | refactoring |
| a fix, a plan, a report or a status update the reader has to act on | `i-have-adhd` | act on |
| a draft that must read less AI-sounding, or a question whether writing does | `no-ai-slop` | AI-sounding |
| verify a running app - walk a flow, read the UI or the console | `analyze-app` | walk a flow |
| "track this as a plan", work that spans sessions | `plan-add` | track this as a |
| "what plans are open", plan status at the start of a session | `plan-status` | what plans are open |
| "sync plans", close finished plans whose PR merged | `plan-sync` | sync plans |
| a deliverable that is evidence: a literature or reference review, a hypothesis | `research` | literature or reference review |
| product analysis, UX audit, competitor teardown, retention or churn | `product-analysis` | retention |
| one existing feature - an admin panel, a CRUD screen, a wizard, a data table | `feature-audit` | admin panel |
| a UI turn that needs a design floor, tokens or a named state set | `design-contract` | design floor |
| a UI or product turn that needs a cognitive-load or visual-critique method | `design-library` | cognitive-load |
| a product question that needs the method, not the framework name: opportunity solution trees | `pm-frameworks` | opportunity solution trees |
| AI or ML machinery: training, fine-tuning, serving, evaluating a model | `ai-research` | fine-tuning |
