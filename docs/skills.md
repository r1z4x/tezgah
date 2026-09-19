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
`argument-hint` in that frontmatter (`skills/plan-add/SKILL.md:10`,
`skills/ponytail/SKILL.md:16`), and Claude exposes each skill as
`/tezgah:<name>` - a bare `/plan-add` is a command that does not exist
([tests/test_skills.py:124-139]).

Two neighbours are not skills. A **slash command** is a file under `commands/`
wired only through the Claude plugin channel - `commands/ponytail.md` and
`commands/adhd.md` are shells over `tezgah-pony` and `tezgah-adhd`, and no other
host installs them (`commands/` appears nowhere in `bin/tezgah-setup`). Its name
is prefixed with the plugin's, so the command is `/tezgah:plan-sync` and a bare
`/plan-sync` does not exist ([tests/test_skills.py:124-139]). An **always-on
rule** is text injected into every turn by the client hooks, defined in
`hooks/tezgah_policy.py:487` (`CORE`); the model cannot choose not to load it,
and only the on-demand tail of it points at a skill, `tezgah-contract`
(`hooks/tezgah_policy.py:650`, `:669`). A rule is disarmed with a [kill switch](glossary.md#kill-switch); a
skill is simply not read.

## The router

opencode has no prompt-time injection point tezgah can rely on for a skill list,
so the installer writes one: `~/.config/tezgah/opencode-skills.md` always-on and
`opencode-skills.full.md` on demand ([bin/tezgah-setup:106-109]), the first
listed in opencode's `instructions` ([bin/tezgah-setup:793-795]). Its native
skill list and `skill` tool are switched off in the same pass -
`permission.skill = "deny"` ([bin/tezgah-setup:808]) - so the generated file is
the only list that host has.

The router is generated, not written: `skill_groups()` walks the installed skill
directories in precedence order - this checkout's `skills/`, then opencode's,
Claude's and `~/.agents/skills` - takes the first directory that defines a name,
buckets each by `skill_category()` and returns the groups
([bin/tezgah-setup:679-699]). Buckets are `tezgah core`, `code & host tooling`,
`research & papers`, `AI research & engineering`, `marketing & growth`; the first
two are listed always-on and the rest collapse to a count line pointing at the
full file ([bin/tezgah-setup:673-676], `bin/tezgah-setup:751-765`). `ai-research` is the one
exception: it stays named in the always-on file under `research (tezgah's own)`
because a library a session is never told about is one it answers from memory -
measured on a live opencode turn that read nothing and answered anyway
([bin/tezgah-setup:745-750]).

Each line is `name - trigger - path`, and the trigger is one sentence pulled from
the frontmatter `description` by `skill_description()` ([bin/tezgah-setup:629-655],
`bin/tezgah-setup:717-726]). **The sentence carrying the `Use when ...` trigger wins over the
opening one.** A line built from the first sentence is what shipped, and it
stripped `tezgah-contract` and `ponytail` of every word a session matches on -
`tezgah-contract`'s description opens with "The full tezgah working contract." -
leaving both unroutable. The rule is pinned on a synthetic `SKILL.md`, not only on
the two shipped ones ([tests/test_setup.py:395-436]), and the live router's own
lines are asserted to carry their trigger words ([tests/test_setup.py:439-454]).
A line is cut at 140 characters with a trailing `...`; a description with no
trigger sentence keeps its first sentence.

Every other host gets the same idea natively: the skills are linked into the
directory that host reads, and the host lists `name` + `description` itself -
which is why the installer counts that metadata as an always-on cost
([bin/tezgah-setup:1676-1684]).

## How a skill reaches a host

`SKILLS` in `bin/tezgah-setup:76-78` is the shipped list, and it is the single
definition of "a tezgah skill": the router, the per-host linking, the uninstall
and the context budget all read it. Each install function links those
directories into the host's own skill directory - Codex
([bin/tezgah-setup:506-507]), opencode (`bin/tezgah-setup:779-780`), Cursor (`bin/tezgah-setup:869-870`), dsh
(`bin/tezgah-setup:1016-1017`), omp (`bin/tezgah-setup:1078-1080`). Claude is the exception: it installs from a
plugin, so the skills arrive in the COPY at
`~/.claude/plugins/cache/rizacan-local/tezgah/<version>/` that `--sync` refreshes
and `--install` re-refreshes when it is stale ([bin/tezgah-setup:20-23],
`bin/tezgah-setup:2048-2122`, `bin/tezgah-setup:2133-2136`). On Claude the plugin name prefixes the skill name -
`Skill(tezgah:ponytail)` ([hooks/tezgah_policy.py:27-29]).

The install report checks the file, not the link. `skills_linked()` requires
every name in `SKILLS` to resolve to a readable `SKILL.md` under the host
directory ([bin/tezgah-setup:76-82]), and it is used for every host row
([bin/tezgah-setup:1851-1852], `bin/tezgah-setup:1867`, `bin/tezgah-setup:1900`, `bin/tezgah-setup:1932`, `bin/tezgah-setup:1990`). It was
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
| `no-ai-slop` | Edits a draft sharper and more human without losing the voice, or flags slop; fires on a draft review, and before publishing English prose tezgah writes itself. |
| `analyze-app` | Inspects and drives a running web or mobile app from its accessibility / DOM / view tree instead of screenshots; fires when a task must verify behaviour, not just read source. |
| `plan-add` | Creates a plan under `plans/open/`, bootstraps the `plans/` layer if missing, commits it; fires on `/tezgah:plan-add`, "track this as a plan". |
| `plan-status` | Reads every open plan, enriches rows with live PR state from `gh`, rewrites the README table and recommends the next plan; fires on `/tezgah:plan-status` or "what plans are open". |
| `plan-sync` | Closes finished plans whose PR merged or closed, moves them to `plans/done/`, commits one message per plan; fires on `/tezgah:plan-sync`, "sync plans". |
| `research` | Runs an auditable research line - two loops, protocol before run, six-dimension review, provenance; fires when the deliverable is evidence: a lit review, a hypothesis, a benchmark or ablation. |
| `ai-research` | The vendored 98-skill library for AI/ML machinery - training and serving a model, benchmarks, interpretability, retrieval pipelines; read one entry, never the tree. |

## Vendored material

`NOTICE` records every third-party skill and its terms: it opens by saying the
root MIT LICENSE covers tezgah's own files while these copies keep their
original terms ([NOTICE:1-2]), and an adapted entry adds what the adaptation
changed. A test fails if the adapted upstream or its licence stops being named
([tests/test_skills.py:144-146]). `skills/no-ai-slop`, `skills/ponytail`,
`skills/i-have-adhd`, `skills/research` and `skills/ai-research` are MIT.
`i-have-adhd` is adapted (the ten rules kept, two rewritten, the user-invocation
frontmatter dropped so the router can reach it); `research` adapts the
orchestration layer of Orchestra Research's AI-research-SKILLs library and copies
nothing verbatim; `ponytail`'s origin was not recorded at vendoring time. In
every case the entry names the upstream, and an adapted entry says what the
adaptation changed - the same record an added adaptation is expected to carry.

`skills/ai-research` is the one vendored tree: 98 upstream skills in 23
categories, bodies byte-for-byte upstream including frontmatter and `author`
lines, at revision `773a52944ba4747a18bd4ae9ade53fff041adcbc`
([skills/ai-research/SOURCE:1-20]). No machine-scraped reference dumps and no
LaTeX template trees were copied, and every drop is named in that file.
`bin/tezgah-import-ai-research --check` verifies the tree against its manifest.

## Adding a skill

1. Write `skills/<name>/SKILL.md` with frontmatter carrying `name` and a
   `description` whose **later** sentence begins `Use when ...` - that sentence
   is the router line, and it must carry the words a session would match on
   ([bin/tezgah-setup:629-655]).
2. Add the name to `SKILLS` ([bin/tezgah-setup:76-78]). `SKILLS` drives the
   router, the linking, the uninstall and the budget; a name without a
   `SKILL.md`, or a directory without a `SKILLS` entry, is not a shipped skill.
3. Expect `tests/test_skills.py:54-69` to fail if the two disagree, and
   `tests/test_setup.py:455-471` to fail if the generated router line lost its
   trigger words. Re-run `--install` (or opencode's `--refresh`,
   [bin/tezgah-setup:621-625]) so the written routers pick the skill up.
4. Quote examples in a form the tests accept: no floating `@latest` package tag
   and any pinned package spec must match the one tezgah wires
   ([tests/test_skills.py:90-97]); slash commands carry the `tezgah:` prefix
   ([tests/test_skills.py:124-139]); no unrendered placeholder such as
   `<repo slug>` ([tests/test_skills.py:111-117]); every kill switch named in
   `CORE` appears in `tezgah-contract` ([tests/test_skills.py:99-109]); a rule
   added to the contract must also reach the skill
   ([tests/test_setup.py:592-616]).

## Source of truth

- `bin/tezgah-setup` - `SKILLS`, `skills_linked()`, `skill_description()`,
  `skill_category()`, `skill_groups()`, `skill_router_texts()`, the per-host
  `install_*` linking, `--sync`, the report rows
- `skills/*/SKILL.md` - the shipped skills and their frontmatter
- `commands/ponytail.md`, `commands/adhd.md` - the Claude-only slash commands
- `NOTICE`, `skills/ai-research/SOURCE`, `bin/tezgah-import-ai-research`
- `hooks/tezgah_policy.py` - the always-on rule text and the Claude skill name
- `tests/test_setup.py`, `tests/test_skills.py` - the router-line, name
  resolution and skill-standard tests
