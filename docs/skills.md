# Skills: what ships, and how one reaches a host

Read this when you are asking what a skill is in tezgah, how one reaches a [host](glossary.md#host),
or how to add one without breaking the router or the install report. It owns the
skill layer: the files under `skills/`, the router that lists them, and the
install step that links them. The always-on rule text a session is told is
[contract](contract.md)'s subject; each host's surfaces are [hosts](hosts.md)'s.

## What a skill is

A skill is `skills/<name>/SKILL.md`: YAML frontmatter carrying `name` and
`description`, then a markdown body. The body is instructions for the model - the
read tool opens it, nothing executes it. `plan-add` and `ponytail` also declare
`argument-hint` in that frontmatter (`skills/plan-add/SKILL.md:11`,
`skills/ponytail/SKILL.md:16`), and Claude exposes each skill as
`/tezgah:<name>` - a bare `/plan-add` is a command that does not exist
([tests/test_skills.py:130-145]).

Two neighbours are not skills. A **slash command** is a file under `commands/`
wired only through the Claude plugin channel - `commands/ponytail.md` and
`commands/adhd.md` are shells over `tezgah-pony` and `tezgah-adhd`, and no other
host installs them (`commands/` appears nowhere in `bin/tezgah-setup`). Its name
is prefixed with the plugin's, so the command is `/tezgah:plan-sync` and a bare
`/plan-sync` does not exist ([tests/test_skills.py:130-145]). An **always-on
rule** is text injected into every turn by the client hooks, defined in
`hooks/tezgah_policy.py:595` (`CORE`); the model cannot choose not to load it,
and only the on-demand tail of it points at a skill, `tezgah-contract`
(`hooks/tezgah_policy.py:822`). A rule is disarmed with a [kill switch](glossary.md#kill-switch); a
skill is simply not read.

## The router

opencode's plugin does inject prompt-time text - the builder's per-turn block,
the conditional rules included
([hosts/opencode/plugins/tezgah.js:2283-2303]) - but that text names at most one
skill (the hint), never the roster, so the installer writes one:
`~/.config/tezgah/opencode-skills.md` always-on and
`opencode-skills.full.md` on demand ([bin/tezgah-setup:106-109]), the first
listed in opencode's `instructions` ([bin/tezgah-setup:998-1002]). Its native
skill list and `skill` tool are switched off in the same pass -
`permission.skill = "deny"` ([bin/tezgah-setup:1022]) - so the generated file is
the only list that host has.

The router is generated, not written: `skill_groups()` walks the installed skill
directories in precedence order - this checkout's `skills/`, then opencode's,
Claude's and `~/.agents/skills` - takes the first directory that defines a name,
buckets each by `skill_category()` and returns the groups
([bin/tezgah-setup:881-902]). Buckets are `tezgah core`, `code & host tooling`,
`research & papers`, `AI research & engineering`, `marketing & growth`; the first
two are listed always-on and the rest collapse to a count line pointing at the
full file ([bin/tezgah-setup:875-878], `bin/tezgah-setup:957-972`). `ai-research` is the one
exception: it stays named in the always-on file under `research (tezgah's own)`
because a library a session is never told about is one it answers from memory -
measured on a live opencode turn that read nothing and answered anyway
([bin/tezgah-setup:951-956]).

Each line is `name - trigger - path`, and the trigger is one sentence pulled from
the frontmatter `description` by `skill_description()` ([bin/tezgah-setup:814-840],
`bin/tezgah-setup:921-930`). **The sentence carrying the `Use when ...` trigger wins over the
opening one.** A line built from the first sentence is what shipped, and it
stripped `tezgah-contract` and `ponytail` of every word a session matches on -
`tezgah-contract`'s description opens with "The full tezgah working contract." -
leaving both unroutable. The rule is pinned on a synthetic `SKILL.md`, not only on
the two shipped ones ([tests/test_setup.py:539-542]), and the live router's own
lines are asserted to carry their trigger words ([tests/test_setup.py:589-609]).
A line is cut at 140 characters with a trailing `...`; a description with no
trigger sentence keeps its first sentence.

The on-demand file also carries a **collision table**: the pairs among tezgah's
own skills whose descriptions share three or more subject words, computed from
the router lines themselves (`skill_collisions()`, [bin/tezgah-setup:1225-1243]).
It rides `opencode-skills.full.md` and never the always-on file, because it is
read when a session is about to choose, not every turn. It is a view, not a
rename: it names `plan-add` / `plan-status` / `plan-sync` and
`design-contract` / `design-library` side by side, and leaves the choice to the
session. `tests/routing-fixtures.md` is the other half - situation to skill, with
the word the router line has to keep - and
`tests/test_setup.py::RoutingFixtures` fails when a reworded description drops
one, or when a shipped skill has no fixture at all.

Every other host gets the same idea natively: the skills are linked into the
directory that host reads, and the host lists `name` + `description` itself -
which is why the installer counts that metadata as an always-on cost
([bin/tezgah-setup:2080-2088]).

## How a skill reaches a host

`SKILLS` in `bin/tezgah-setup:123-125` is the shipped list, and it is the single
definition of "a tezgah skill": the router, the per-host linking, the uninstall
and the context budget all read it. Each install function links those
directories into the host's own skill directory - Codex
([bin/tezgah-setup:601-631]), opencode (`bin/tezgah-setup:987-988`), Cursor (`bin/tezgah-setup:1083-1084`), dsh
(`bin/tezgah-setup:1239-1240`), omp (`bin/tezgah-setup:1303-1305`). Claude is the exception: it installs from a
plugin, so the skills arrive in the COPY at
`~/.claude/plugins/cache/<marketplace>/tezgah/<version>/` that `--sync` refreshes
and `--install` re-refreshes when it is stale ([bin/tezgah-setup:20-23],
`bin/tezgah-setup:3701-3759`, `bin/tezgah-setup:3761-3767`). On Claude the plugin name prefixes the skill name -
`Skill(tezgah:ponytail)` ([hooks/tezgah_policy.py:32-35]).

The install report checks the file, not the link. `skills_linked()` requires
every name in `SKILLS` to resolve to a readable `SKILL.md` under the host
directory (`skills_linked()`, [bin/tezgah-setup:129-136]), and it is used for every host row
([bin/tezgah-setup:3294-3295], `bin/tezgah-setup:3314`, `bin/tezgah-setup:3348`, `bin/tezgah-setup:3384`, `bin/tezgah-setup:3442`). It was
`islink()` once, and a link to nothing is a link: a name whose `SKILL.md` was
never written reported as linked on every host at once while no host could read
it ([tests/test_skills.py:54-69]).

## The shipped skills

| Skill | What it is for, and when it fires |
|---|---|
| `harness` | Picks and runs the right multi-agent harness on top of the code graph; fires on an audit, "every call site", "what breaks if", or a task too wide for one context window. |
| `tezgah-contract` | The full contract behind the always-on core - graph rule, harnesses, orchestration, codegen, consult, kill switches; loads when the core points here or a task needs that detail. |
| `ponytail` | Forces the laziest solution that works, in levels lite/full/ultra; fires on any coding task, or "be lazy", "yagni", "shortest path". |
| `i-have-adhd` | Shapes output for a reader who acts on it - action first, numbered steps, errors as location/cause/fix; fires on any answer the reader must act on, not on code, commits or docs. |
| `no-ai-slop` | Edits a draft sharper and more human without losing the voice, or flags slop; fires on a draft review, on a draft in a language other than English, on text that must keep terms, identifiers or unit symbols verbatim, and before publishing English prose tezgah writes itself. |
| `analyze-app` | Inspects and drives a running web or mobile app from its accessibility / DOM / view tree, its rendered screen (screenshots, blur and grayscale tests, breakpoints) and measurements taken in the page; fires when a task must verify behaviour or read the UI, not just read source. |
| `plan-add` | Creates a plan under `.tezgah/plans/open/` with its own `allowed_paths:` scope, bootstraps the `.tezgah/plans/` layer if missing, commits it in the private `.tezgah` repository (`git -C .tezgah`, never the project's git); fires on `/tezgah:plan-add`, "track this as a plan". |
| `plan-status` | Reads every open plan, enriches rows with live PR state from `gh`, rewrites the README table (committed in the private `.tezgah` repository) and recommends the next plan; fires on `/tezgah:plan-status` or "what plans are open". |
| `plan-sync` | Closes finished plans whose PR merged or closed through `tezgah-task close`, which moves a plan to `.tezgah/plans/done/` as done only when it records an approving `review:`; commits one message per plan in the private `.tezgah` repository; fires on `/tezgah:plan-sync`, "sync plans". |
| `research` | Runs an auditable research line - two loops, protocol before run, six-dimension review, provenance; fires when the deliverable is evidence: a lit review, a hypothesis, a benchmark or ablation. |
| `product-analysis` | Runs a product analysis across five axes - value (HEART), usability (heuristics, the cognitive walkthrough, WCAG 2.2, axe-core, the running app read through `analyze-app` down to component x state, tree and image both), feasibility (a cited `path:line`), competition (a dated teardown) and triage (keep/fix/cut/bet) - with one named evidence class per finding, executed as a research line; fires on a product, feature, retention or roadmap question rather than a code change. |
| `pm-frameworks` | The two vendored product methods the analysis skill defers to - intended-vs-implemented and the Opportunity Solution Tree - kept offline so an offline session reads the method instead of citing its name. |
| `feature-audit` | Audits ONE feature across every layer it is spread over - the surfaces a person uses (a control, a list or table, a detail view, a filter, a picker, a step flow, a notification), the route, the authorization, the service and the data - by filling the capability, field-contract, flow/step and interaction-dependency matrices, where a disagreement between layers is a finding and a fix needing an absent capability becomes a capability-change proposal; fires on an admin screen, CRUD, form, wizard, data table, filter or permission question about an existing feature. |
| `design-contract` | The artifact shape of the per-repo `.tezgah/design-contract.md` - colour roles, type scale, spacing unit and rhythm, the component inventory, the state set every interactive control and data view owes - the derivation rule that reads it out of the repository's own tokens, and the rules `bin/tezgah-design check` fails on; fires on a UI or component turn that needs a floor, a token, a state set, or the design check itself. |
| `design-library` | The vendored MC Dean design/UX subset - 39 skills in the `cognitive-accessibility`, `adaptive-interfaces`, `inclusive-interaction`, `visual-critique` and `design-research` plugins - read one entry at a time through its own `INDEX.md`, never the tree; fires when a UI or product turn needs a cognitive-load, inclusive-interaction or visual-critique method tezgah has no counterpart for. |
| `ai-research` | The vendored 98-skill library for AI/ML machinery - training and serving a model, benchmarks, interpretability, retrieval pipelines; read one entry, never the tree. |
| `rl-env` | The vendored FineEnvs skill set for authoring an RL environment from a description - OpenEnv, OpenReward/ORS, Verifiers and NeMo Gym, plus the orchestrator that ports one description across all four; read one entry, never the tree. |

## Vendored material

`NOTICE` records every third-party skill and its terms: it opens by saying the
root MIT LICENSE covers tezgah's own files while these copies keep their
original terms ([NOTICE:1-2]), and an adapted entry adds what the adaptation
changed. A test fails if the adapted upstream or its licence stops being named
([tests/test_skills.py:150-152]). `skills/no-ai-slop`, `skills/ponytail`,
`skills/i-have-adhd`, `skills/research`, `skills/product-analysis`,
`skills/pm-frameworks` and `skills/ai-research` are MIT; `skills/rl-env` is
Apache-2.0 and keeps that repository's terms.
`i-have-adhd` is adapted (the ten rules kept, two rewritten, the user-invocation
frontmatter dropped so the router can reach it); `research` adapts the
orchestration layer of Orchestra Research's AI-research-SKILLs library and copies
nothing verbatim; `ponytail`'s origin was not recorded at vendoring time. In
every case the entry names the upstream, and an adapted entry says what the
adaptation changed - the same record an added adaptation is expected to carry.

`skills/ai-research` is the large vendored tree: 98 upstream skills in 23
categories, bodies byte-for-byte upstream including frontmatter and `author`
lines, at revision `773a52944ba4747a18bd4ae9ade53fff041adcbc`
([skills/ai-research/SOURCE:1-20]). No machine-scraped reference dumps and no
LaTeX template trees were copied, and every drop is named in that file.
`bin/tezgah-import-ai-research --check` verifies the tree against its manifest.

`skills/rl-env` is the Apache-2.0 one: the five FineEnvs environment-authoring
skills - `rl-env-from-description` plus the four framework ports - and every
reference file they ship, 14 bodies byte-for-byte from
`adithya-s-k/FineEnvs` at revision `26ab9c6` ([skills/rl-env/SOURCE:1-6]),
under `skills/rl-env/<skill>/` at their upstream path. Nothing is adapted.
Upstream's own install route is not used here: `npx skills add
adithya-s-k/FineEnvs` writes into a host's skill directory, which the router
does not read, the install report does not list and `SOURCE` cannot vouch for -
the vendored copy is what the router reaches. The entry point
`skills/rl-env/SKILL.md` is tezgah's own and is not in the manifest, and it is
the file that says what the vendored bodies cannot: this repository runs no
trainer, so an environment they build needs a machine that does.

`skills/pm-frameworks` is the small one: two product-management methods -
`intended-vs-implemented` and `opportunity-solution-tree` - byte-for-byte from
`phuryn/pm-skills` at revision `8607e3b077817f89bf4a9b623246219734ac3be0`
([skills/pm-frameworks/SOURCE:1-5]). Its manifest is the table in `SOURCE`, and
`tests/test_skills.py` hashes each listed body and fails on an unlisted directory
beside them; the entry point `SKILL.md` is tezgah's own and is not in it.

`skills/design-library` is the adapted one: 39 skills from two Owl-Listener
repositories - `inclusive-design-skills` at `6e0740f` (the whole
cognitive-accessibility, adaptive-interfaces and inclusive-interaction plugins)
and `designer-skills` at `9a6930c` (visual-critique, and two design-research
skills) - both MIT, vendored at the upstream path under those five plugin
directories, with `INDEX.md` as the routing surface and `EVALS.md` as the three
trap cases the library is scored against. Two bodies depart from upstream, and
`skills/design-library/SOURCE` and `NOTICE` name both: the touch-target entry
paired `44x44 CSS pixels` with `WCAG 2.2 Level AA`, where SC 2.5.8 is Level AA at
24x24 and SC 2.5.5 is Level AAA at 44x44 - 24 is the floor `bin/tezgah-design`
enforces - and `adaptive-personalisation/SKILL.md` carried the sibling
`contextual-help-design` skill's `name`, which a host that loads a skill from its
directory skips. `tests/test_skills.py` hashes every listed body, fails on an
unlisted directory, and fails on a body that pairs 44x44 with Level AA again.

## Adding a skill

1. Write `skills/<name>/SKILL.md` with frontmatter carrying `name` and a
   `description` whose **later** sentence begins `Use when ...` - that sentence
   is the router line, and it must carry the words a session would match on
   ([bin/tezgah-setup:814-840]).
2. Add the name to `SKILLS` ([bin/tezgah-setup:123-126]). `SKILLS` drives the
   router, the linking, the uninstall and the budget; a name without a
   `SKILL.md`, or a directory without a `SKILLS` entry, is not a shipped skill.
3. Expect `tests/test_skills.py:54-69` to fail if the two disagree, and
   `tests/test_setup.py:589-609` to fail if the generated router line lost its
   trigger words. Re-run `--install` (or opencode's `--refresh`,
   [bin/tezgah-setup:806-810]) so the written routers pick the skill up.
4. Add a row to `tests/routing-fixtures.md`: situation, the skill, and the word
   the router line has to keep. `RoutingFixtures` fails on a shipped skill with
   no row, and on a row whose word a reworded description dropped. The
   frontmatter lint in `tests/test_skills.py::Frontmatter` then holds the entry
   point itself: name equals directory, kebab-case, a `Use when` sentence, a
   description under the metadata cap, every backticked cross-reference
   resolving. Vendored trees are exempt there - their frontmatter is upstream's
   bytes, pinned by that library's own hash test.
5. Quote examples in a form the tests accept: no floating `@latest` package tag
   and any pinned package spec must match the one tezgah wires
   ([tests/test_skills.py:90-97]); slash commands carry the `tezgah:` prefix
   ([tests/test_skills.py:130-145]); no unrendered placeholder such as
   `<repo slug>` ([tests/test_skills.py:117-123]); every kill switch named in
   `CORE` appears in `tezgah-contract` ([tests/test_skills.py:99-109]); a rule
   added to the contract must also reach the skill
   ([tests/test_setup.py:858-905]).

## Source of truth

- `bin/tezgah-setup` - `SKILLS`, `skills_linked()`, `skill_description()`,
  `skill_category()`, `skill_groups()`, `skill_router_texts()`, the collision
  table (`skill_collisions()`), the per-host `install_*` linking, `--sync`, the
  report rows
- `skills/*/SKILL.md` - the shipped skills and their frontmatter
- `commands/ponytail.md`, `commands/adhd.md` - the Claude-only slash commands
- `NOTICE`, `skills/ai-research/SOURCE`, `bin/tezgah-import-ai-research`
- `skills/design-library/SOURCE`, `INDEX.md`, `EVALS.md` - the adapted library,
  its index and its three trap cases
- `skills/rl-env/SOURCE` - the vendored FineEnvs environment-authoring set, its
  upstream revision and the per-file sha256
- `hooks/tezgah_policy.py` - the always-on rule text and the Claude skill name
- `tests/test_setup.py`, `tests/test_skills.py` - the router-line, name
  resolution, frontmatter, collision and skill-standard tests
- `tests/routing-fixtures.md` - situation to skill, with the word the router line
  has to keep
