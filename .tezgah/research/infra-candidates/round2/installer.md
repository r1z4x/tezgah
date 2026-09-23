# Round 2: the installer and the layer it generates

Round 1 probed four areas (the evidence ledger, the gate, host parity, the
injected-context builder). This round probes the surface it never touched: the
installer (`bin/tezgah-setup`), the per-repo agent generator
(`hooks/tezgah_agents.py`), the detached auto-index worker
(`hooks/tezgah_index.py`), the research CLI (`hooks/tezgah_research.py` plus
`bin/tezgah-research`), the shipped skills with their generated router, and
`workflows/cbm-*.js`.

## Method

Read end to end in this checkout at `d2f0cf4`: all 2368 lines of
`bin/tezgah-setup`, `hooks/tezgah_agents.py`, `hooks/tezgah_index.py`,
`hooks/tezgah_research.py`, `bin/tezgah-research`, `bin/tezgah-agents`,
`bin/tezgah-index`, `bin/tezgah-doctor`, `hooks/hooks.json`,
`hosts/{codex,cursor,dsh}/hooks.json`, the three `workflows/cbm-*.js`, every
`skills/*/SKILL.md`, and the parts of `tests/test_setup.py`,
`tests/test_index.py`, `tests/test_skills.py` that pin these surfaces.

Every claim was then **re-run in-process**: `bin/tezgah-setup` was loaded as a
module (`SourceFileLoader` - the file has no `.py` extension) and its functions
were called against temporary directories with module constants monkeypatched.
`bin/tezgah-setup` was never executed: no install, no `--report`, no
`--uninstall`, nothing written outside throwaway temp dirs. Claims that rest on
reading rather than a probe say so. Ten of the eighteen findings carry a probe;
the rest say in place that they were read from source rather than executed. The
line numbers
were verified line by line against the files after the report was drafted.

One cited file was under concurrent edit by another workstream of this round
while this report was written: `hosts/opencode/plugins/tezgah.js` grew from
about 1370 lines to 1770, so the two citations into it (I10, I12) name the
enclosing symbol as well as the line and were re-verified against the file as it
stood at the end of the pass. Everything else cited here is in a file this
round's other workstreams did not touch (`bin/tezgah-setup`, `hooks/tezgah_*`,
`skills/*`, `workflows/*`, `tests/*` are unmodified in the working tree).

Two claims I expected and **could not sustain**, recorded so they are not
re-derived: `{PONY_LEVEL}` is *not* baked into the generated opencode contract
(the placeholder lives only in `PROMPT_REMINDER`, which is not part of
`always_on_core()`), and every path citation inside `skills/*` resolves (a sweep
over all 1677 skill lines plus the three workflows found only the placeholders
`plans/open/NNN-slug.md` and `plans/done/NNN-slug.md`).

## A. What the report claims versus what is on disk

`--report` is the surface that answers "is this host armed?", and it is the only
one: `docs/operations.md:68-71` opens the section with "`--report` (or a piped
bare run) answers one question per host: is it wired?". Five of its rows answer
that question wrongly.

### I1 - `hooks.json wired` passes on any single event, so a dropped Stop hook reads as armed

- **evidence**: `bin/tezgah-setup:1794-1795` -
  `("hooks.json wired%s" % where,` / `_hooks_has(os.path.join(CODEX,
  "hooks.json"), cmd)),`; the same shape for Cursor at `bin/tezgah-setup:1837` -
  `("hooks.json wired", _hooks_has(os.path.join(CURSOR, "hooks.json"),
  "tezgah-cursor-hook")),`. The helper declares the parameter that would fix it
  and no caller passes it: `bin/tezgah-setup:1772` - `def
  _hooks_has(path, marker, events=None):`, with the only call sites at `:1581`,
  `:1795` and `:1837`, none of which passes `events`. The installers write seven
  events for Codex (`bin/tezgah-setup:445` - `events = [("SessionStart", None),
  ("UserPromptSubmit", None),`) and thirteen for Cursor
  (`bin/tezgah-setup:817` - `spec = {`), and the suite pins those counts
  (`tests/test_setup.py:176-185` - `self.assertEqual(codex.count(
  "tezgah-codex-hook"), 7)`) - but the report row cannot see them.
- **class**: (c)
- **why it matters**: a `hooks.json` carrying tezgah's command under one event
  and not under `Stop` reads ` ok `, and the Stop hook is the integrity rule's
  refusal - the layer's headline behaviour. The Cursor half is worse in kind,
  because three of its thirteen events are the pre/post halves of the tool gate
  itself. A host wired one-thirteenth of the way reads as fully wired, and the
  report is the artifact the docs send a user to for exactly this question.
- **probe**: a Codex `hooks.json` with only `SessionStart` wired returned
  `hooks.json wired in <tmp> -> True`, while `_hooks_has` on the same file with
  `events=["Stop"]` returned `False` - the check the parameter exists for.
- **measurable?**: yes. Outcome variable: the row's boolean over the 7 (Codex)
  and 13 (Cursor) single-event fixtures; it must be true only for the full set.
- **sketch**: hoist the event names `install_codex` (`:445`) and `install_cursor`
  (`:817`) already hold into module constants and pass them to the existing
  `events=` parameter in both rows, so the writer and the checker cannot drift.

### I2 - Claude's three link rows pass on a dangling symlink

- **evidence**: `bin/tezgah-setup:1756` - `("statusline symlink",
  os.path.islink(os.path.join(CLAUDE, "statusline.py"))),`, and the same
  `os.path.islink` shape at `:1758` (`"workflows in ~/.claude/workflows"`) and
  `:1760` (`"bin on ~/.claude/bin"`). The module knows this shape is wrong and
  fixed it for skills only - `bin/tezgah-setup:76-83`: "`islink` alone called a
  dangling link installed: a name in SKILLS whose skill file was never written
  reported as linked on every host at once, while no host could read it." The
  installer's own `link()` agrees with a dangling link as well:
  `bin/tezgah-setup:187-208` compares `os.path.realpath(dst) ==
  os.path.realpath(src)`, which for a missing target is the same non-existent
  path on both sides, and prints ` ok `.
- **class**: (c)
- **why it matters**: the checkout moves, or `workflows/cbm-map.js` is renamed
  or dropped in a release, and `--report` still says the status line and all
  three workflows are wired while every one of them points at nothing. The
  documented repair path for a missing status line is this row -
  `docs/operations.md:161` - so the row a user is sent to is the one that lies.
- **probe**: with the three workflow links, three bin links and the statusline
  link created in a temp dir whose target checkout did not exist,
  `host_checks_claude()` returned `True` for all three rows.
- **measurable?**: yes. Outcome variable: the row's boolean for a link whose
  target is missing; it must be false.
- **sketch**: resolve each link the way `skills_linked` does (one shared
  `linked_ok(path)` helper used by both), instead of a bare `islink`.

### I3 - `skill metadata band present` cannot fail independently

- **evidence**: `bin/tezgah-setup:1921-1923` - `("RULES.md carries the
  contract",` / `"tezgah:start" in rules_text and "Ponytail" in rules_text),` /
  `("skill metadata band present", "Ponytail" in rules_text),`. The second row
  asserts a literal the first row has already required and never reads a band:
  that file is written as `always_on_core() + OMP_LESSONS`
  (`bin/tezgah-setup:1026-1027`), whose only rules paragraph is the `POINTERS`
  line, so the band this row names is not in the file at all.
- **class**: (c)
- **why it matters**: a row that can only be true when another row is true
  reports nothing, and the two-row shape tells a reader the band is
  independently verified. A regression that strips the band leaves this row
  green. It is the same failure the gate refuses in an agent's own work: a check
  made unable to fail.
- **probe**: on a RULES.md holding only `**Ponytail (minimal code).**` and no
  band, both rows returned `True`.
- **measurable?**: yes. Outcome variable: the row's boolean against a RULES.md
  that carries `Ponytail` but no band; it must be false.
- **sketch**: give the row its own predicate - the marker the file actually
  carries, for instance `"**On-demand rules" in rules_text` (the `POINTERS`
  paragraph `always_on_core()` writes) - or drop the row and keep the contract
  one.

### I4 - `subagents generated` counts files the generator never promised

- **evidence**: `bin/tezgah-setup:1926` - `("subagents generated", len(agents)
  >= 4),` against the capability gate in `hooks/tezgah_agents.py:297`
  (`omp_user_agents`, one file per role whose `infra["caps"]` entry is true, plus
  the orchestrator) and the emit loop at `bin/tezgah-setup:1032` - `for name,
  text in tezgah_agents.omp_user_agents().items():`. The same assumption is in
  `context_budget`, which counts every role unconditionally:
  `bin/tezgah-setup:1629-1635`, and the suite pins the resulting line -
  `tests/test_setup.py:993` - `"skill metadata (11)", "subagent metadata (5)",`.
- **class**: (c)
- **why it matters**: the row and the band are both wrong, and wrong only in one
  direction. On a machine with the graph but no `orx` and no provider key the
  generator emits three files (explorer, reviewer, orchestrator) and the row
  reads ` MISS ` for an install that did exactly what it promises - a permanent
  red row teaches the user to ignore the report. The band claims five agents'
  worth of metadata on every machine, whether or not they exist. The suite
  cannot catch either: `tests/test_setup.py:889-896` asserts the row's label is
  printed, never its mark, and no test calls any `host_checks_*` function.
- **probe**: capability sets and emitted file counts - {cbm}: 3 files, row
  `False`; {cbm, consult}: 4, row `True`; all three: 5, row `True`; none: 0 files
  and the install prints nothing at all for the agent step.
- **measurable?**: yes. Outcome variable: the row's boolean per capability set,
  against `len(tezgah_agents.omp_user_agents())`.
- **sketch**: make the row ask the generator (`len(tezgah_agents
  .omp_user_agents())`) instead of comparing with a literal, and feed
  `context_budget` the same number instead of counting `tezgah_agents.ROLES`.

### I5 - Nothing checks the Claude attribution wiring

- **evidence**: `bin/tezgah-setup:402-421` (`wire_claude_attribution`, writing
  `{"commit": "", "pr": "", "sessionUrl": False}` into `~/.claude/settings.json`)
  against the complete row list at `bin/tezgah-setup:1753-1770`, which covers the
  statusline, the workflows, the bin links and the plugin copy - and no
  attribution key.
- **class**: (c)
- **why it matters**: this is the one invariant enforced on the host side *and*
  at source, in the installer's own words ("The hooks also enforce this, but the
  setting removes the default at source", `bin/tezgah-setup:407`). When
  anything else rewrites settings.json - a settings sync, a host upgrade - the
  report stays green and the user is told nothing, while every commit the host
  makes carries the default attribution line. The hooks still catch tezgah's own
  writes, so the failure is partial and silent, which is the shape that survives
  longest.
- **measurable?**: yes. Outcome variable: the row's boolean after an install, and
  after the key is removed by hand; the second must be false.
- **sketch**: one row in `host_checks_claude` reading `read_json(CLAUDE /
  "settings.json").get("attribution")`, against a constant shared with
  `wire_claude_attribution`.

### I6 - `plugin copy current` hashes only the files the checkout still has

- **evidence**: `bin/tezgah-setup:2020-2031` - `files = [f for f in
  plugin_files() or [] if f not in PLUGIN_MANIFESTS]` then `want =
  tree_sha(HERE, files)` / `return want is not None and want ==
  tree_sha(target, files)`, over `tree_sha` (`:1989-2001`, one hash per listed
  relpath). `sync()` does empty the copy first (`bin/tezgah-setup:2052-2055` -
  `shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path)`), so the sync
  path *would* remove a ghost - but `refresh_plugin_copy` (`:2081-2087`) only
  calls `sync()` when `plugin_copy_current` is false.
- **class**: (c)
- **why it matters**: Claude runs the plugin copy, not the checkout. A file the
  checkout *stopped* shipping - a dropped skill, a removed helper - is absent
  from `files`, so it cannot move the hash: the copy stays "current" and keeps
  exposing the deleted skill to every Claude session, while the report shows the
  green row the docs point at (`docs/operations.md:111-114`). Only a change to a
  file that still exists triggers the refresh.
- **probe**: two directories holding the same single listed file, one of them
  also holding `skills/ghost-skill/SKILL.md`, produce equal `tree_sha` over the
  listed set - so `plugin_copy_current` is true for a copy holding a file the
  checkout no longer has.
- **measurable?**: yes. Outcome variable: `plugin_copy_current` for a copy with
  one extra managed file (must be false), and the sync count over a checkout
  that deleted a skill.
- **sketch**: compare the copy's own listing too (walk it and diff against
  `files`), or record the manifest `sync` last wrote and check both directions;
  a hash over the files that exist is the wrong shape for an existence claim.

## B. Install and uninstall idempotence

### I7 - `set_managed_block` and `set_managed_md` move the user's own text

- **evidence**: `bin/tezgah-setup:235-265` ends `text = "\n".join(out) + "\n" +
  start + ... + end + "\n"`, so the managed block is always re-appended at the
  end of the file; `set_managed_md` (`:992-1020`) has the same tail. The sibling
  module already paid for exactly this bug and names the cost -
  `hooks/tezgah_agents.py:429-437`: "Rebuilding the file around the block used to
  move it to the end of any file whose block sat mid-file, so the first session
  start in a fresh checkout dirtied the tree with a pure move. Replacing it in
  place keeps the user's ordering".
- **class**: (c)
- **why it matters**: `~/.dsh/cordis.patch.yml` is a YAML sequence whose order is
  the composition order of the patch layer, and `~/.omp/agent/RULES.md` is prompt
  text where order is meaning. A user who writes their own row or note below
  tezgah's block silently gets it moved above on the next install, while the
  tool's own docstring promises "Re-running is idempotent"
  (`bin/tezgah-setup:24`). Both files are rewritten unconditionally, so the
  reorder happens on every install, not only on a change.
- **probe**: a patch file holding the managed block followed by `- id:
  my-own-layer` came back with the user's layer first and the block last; the
  same with `set_managed_md` and a note below the block.
- **measurable?**: yes. Outcome variable: the index of the block and of the
  user's line, before and after a second call; both must be unchanged.
- **sketch**: lift `_put_block` out of `hooks/tezgah_agents.py` into the place
  both modules import, and call it from `set_managed_block` and `set_managed_md`.

### I8 - `--uninstall` leaves a dangling `~/.codex/bin/consult` that its own predicate disowns

- **evidence**: the install side links it - `bin/tezgah-setup:463-464` - `mcp =
  os.path.join(CODEX, "bin", "consult")` / `print(link(os.path.join(tp.BIN_DIR,
  "consult"), mcp))`. The uninstall side never mentions it: `uninstall_codex`
  (`bin/tezgah-setup:1393-1399`) unlinks the skills, the hook entries and the TOML
  servers, and nothing else. `uninstall_common` (`:1283-1287`) then runs
  `unlink_dir(tp.BIN_DIR)` (`:1216-1223`), deleting the intermediate
  `~/.config/tezgah/bin/consult` the Codex link points at.
- **class**: (c)
- **why it matters**: after `--uninstall` the shim is a broken symlink in a
  directory that is normally on PATH, and tezgah's own repair path can no longer
  see it: `is_tezgah_link` (`:1196-1201`) resolves the link first and returns
  false once the target is gone, so `unlink_tezgah` would print "kept ... (not a
  tezgah link)" (`:1204-1214`). The one command that exists to remove tezgah's
  wiring cannot remove it, and the closing line ("non-tezgah files ... were left
  untouched", `:1494-1495`) reads as if nothing of tezgah's remains.
- **probe**: building the two-hop link in a temp dir and calling `unlink_dir` on
  the intermediate left `exists False / islink True / is_tezgah_link False`.
- **measurable?**: yes. Outcome variable: `os.path.exists` of
  `~/.codex/bin/consult` after an install-then-uninstall round trip.
- **sketch**: add `unlink_tezgah(os.path.join(CODEX, "bin", "consult"))` to
  `uninstall_codex`, mirroring `uninstall_claude`'s three-name loop
  (`:1388-1389`), or drop the shim and let `~/.config/tezgah/bin` be the single
  location.

### I9 - opencode's `instructions` grows on every re-install while the other hosts replace

- **evidence**: `bin/tezgah-setup:748-752` - `for extra in (contract,
  SKILL_ROUTER):` / `if extra not in instr:` / `instr.append(extra)`. Codex and
  Cursor both strip tezgah's own entries first - `:453` and `:836` -
  `arr[:] = [e for e in arr if "tezgah" not in json.dumps(e)]`. Nothing prunes
  opencode's list except `unwire_opencode_config` (`:1310-1318`, uninstall
  only).
- **class**: (c)
- **why it matters**: both appended paths are absolute
  (`~/.config/tezgah/...`). Move the checkout, or run with a different
  `XDG_CONFIG_HOME`, and the old path stays in `instructions` forever, pointing
  at a file that no longer exists - opencode reads its instruction list at
  startup, where a missing entry is a broken instruction set rather than a stale
  one. The row that would catch it (`:1813` - `("contract in instructions",
  any("tezgah" in i for i in instr)),`) passes on the new entry and cannot see
  the old.
- **class note**: read from source, not probed; probing means calling
  `install_opencode`, which is an install.
- **measurable?**: yes. Outcome variable: `len(oc["instructions"])` and how many
  entries resolve to an existing file, across two installs with different config
  dirs; the first must be pruned.
- **sketch**: replace the append with the idiom the other two hosts already use -
  `instr[:] = [i for i in instr if "tezgah" not in i]` before appending.

## C. A generated artifact and its generator

### I10 - The opencode contract's staleness hash omits a file the contract is rendered from

- **evidence**: `bin/tezgah-setup:148-149` - `CONTRACT_SOURCES =
  ("hooks/tezgah_policy.py",` / `"skills/tezgah-contract/SKILL.md")`, hashed by
  `contract_sha()` and compared by `contract_stale()` (`:152-184`). The rendered
  text also comes from `hooks/tezgah_context.py`:
  `bin/tezgah-setup:537-539` - `core = (tezgah_context.always_on_core()`, and
  that function (`hooks/tezgah_context.py:577-585`) filters `policy.CORE` by the
  `CORE_RULES` table (`hooks/tezgah_context.py:70-86`) in the same unhashed file,
  a coupling the policy states from its side -
  `hooks/tezgah_policy.py:643` - "Keys match the CORE_RULES labels in
  hooks/tezgah_context.py." The docs list it as a source -
  `docs/operations.md:95-96` - "After a change to the contract text
  (`hooks/tezgah_policy.py`, `hooks/tezgah_context.py`,
  `skills/tezgah-contract/SKILL.md`)". The test that guards the hash repeats the
  list instead of deriving it - `tests/test_setup.py:684-694`, whose
  `contract_sha` helper opens `("hooks/tezgah_policy.py",
  "skills/tezgah-contract/SKILL.md")` - so it asserts the implementation against
  its own assumption.
- **class**: (c)
- **why it matters**: opencode has no session-start hook, so a policy edit lands
  only through `--refresh`, which the plugin spawns once per session *when the
  stored hash no longer matches* (`hosts/opencode/plugins/tezgah.js:1750-1753`).
  Edit `always_on_core`, `render`, or a `CORE_RULES` label, and the hash does not
  move: every running and future opencode session keeps the previous always-on
  text, and a manual `--refresh` prints "contract is current"
  (`bin/tezgah-setup:2303-2305`) while doing nothing. This is the drift the hash
  exists to prevent, on the one host that cannot see the edit any other way.
- **probe**: renaming one `CORE_RULES` label (`cbm` to `graph`) changed
  `always_on_core()` from 7324 to 7882 characters, with the conditional
  `**Code discovery: graph first.**` paragraph leaking into the always-on text,
  while `contract_sha()` came back byte-identical.
- **measurable?**: yes. Outcome variable: `contract_stale()` before and after a
  change to each of the three documented sources; all three must move it.
- **sketch**: add `"hooks/tezgah_context.py"` to `CONTRACT_SOURCES` (one tuple
  entry - the renderer is already keyed on it), and have the test iterate
  `CONTRACT_SOURCES` instead of repeating the literals.

## D. The router and the shipped text

### I11 - The always-on router sends the session to a file the host will refuse to open

- **evidence**: `bin/tezgah-setup:104` - `SKILL_ROUTER_FULL =
  os.path.join(tp.CONFIG_DIR, "opencode-skills.full.md")`, and the pointer the
  always-on router carries at `:713-714` - `"Not listed here, to keep every
  session cheap. Before picking a skill"` / `" for one of these task classes,
  read the full list at \`%s\`."`. The opencode grants are two directories,
  neither of them the config dir - `:773` - `grants = [os.path.join(HERE,
  "skills", "**"), os.path.join(tp.CONFIG_DIR, "bin", "**")]`, with the rationale
  and the measured failure written just above it (`:764-772`, including "a live
  `opencode run` tried to open `skills/ai-research/` and was denied"). The
  always-on lines come from every installed skill dir, not only the checkout -
  `skill_groups` indexes `HERE/skills`, `OPENCODE/skills`, `CLAUDE/skills` and
  `~/.agents/skills` (`:639-640`).
- **class**: (c)
- **why it matters**: every collapsed task class - research, papers, marketing -
  and every skill installed outside the checkout is reachable only through a read
  the host auto-rejects when nobody can answer the prompt. That is the exact
  failure the grants were added to close, reintroduced one directory over: the
  session is told to read a file, cannot, and answers from memory, which is what
  the router's own docstring says it exists to prevent (`:684-694`).
- **measurable?**: yes. Outcome variable: in a non-interactive `opencode run`
  given a marketing-class task, the share of runs that successfully open
  `opencode-skills.full.md`, against the same run with the config dir granted.
- **sketch**: add `os.path.join(tp.CONFIG_DIR, "**")` to `grants` at
  `bin/tezgah-setup:773`, or write the full router inside the checkout next to
  the skills it lists.

### I12 - `agents-off` is honoured in three places and named in none

- **evidence**: the code - `hooks/tezgah_agents.py:517` (`if off("agents-off"):`
  in `sync_root`) and `:604` (`if off("agents-off") or not root_for(root):` in
  `opencode_agents_json`), plus the plugin half at
  `hosts/opencode/plugins/tezgah.js:1544` - `if (off("agents-off")) return` (the
  `config` hook that registers the repo's generated subagents). A
  test covers it (`tests/test_agents.py:399`). No shipped text names it: the
  always-on list is `hooks/tezgah_policy.py:631-637` ("`exec-mode.off`,
  `orchestrate-off`, ..., `pretooluse-off` (the whole gate)"), the contract skill
  repeats that list at `skills/tezgah-contract/SKILL.md:44-53`, and the README's
  table (`README.md:376-387`) has ten rows and none is it. A repo-wide grep for
  `agents-off` returns those four code and test sites and nothing else.
- **class**: (c)
- **why it matters**: the per-repo generator writes files into the user's
  repository (`.claude/agents/*`, `.opencode/agents/*`, `.codex/agents/*`) and
  edits the clone's `info/exclude`. A user who does not want tezgah writing into
  their repos has no documented way to stop it: `~/.config/tezgah/` is named as
  the switch directory and this switch is not in the list, so the only routes
  they can find are editing generated files (regenerated at the next session
  start) or disarming a whole host. The contract's premise - the exact kill
  switches live in the skill (`skills/tezgah-contract/SKILL.md:8-11`) - is not
  met. The parity test cannot see it by construction:
  `tests/test_skills.py:99-109` reads the switch names *from* `policy.CORE` and
  checks they reach the skill, so a switch CORE never names is invisible to it.
- **measurable?**: yes. Outcome variable: for each `off("<name>")` literal in
  `hooks/`, `bin/` and `hosts/`, whether `<name>` appears in `policy.CORE` and in
  the contract skill - a count, currently 1 of 12 missing.
- **sketch**: add `` `agents-off` (the per-repo subagent files)`` to the CORE
  switch paragraph (`hooks/tezgah_policy.py:631-637`) and to the skill's list, so
  the existing parity test carries it; optionally surface it among the health
  segments at `hooks/tezgah_context.py:1231`, where every other switch appears.

### I13 - `verify-off` is documented everywhere except the README table

- **evidence**: `hooks/tezgah_policy.py:634-635` - `` `verify-off` (the integrity
  rule: its prompt text, the shortcut / denials and the Stop gate)``, present in
  the contract skill as well; `README.md:376-387` lists ten switches and
  `verify-off` is not among them. (The per-repo marks are covered by the sentence
  at `README.md:389-393` and are fine.)
- **class**: (c)
- **why it matters**: the README is where a reader decides what can be turned
  off, and it omits the switch for the rule the tool is built around - the one a
  user most often wants gone in a repository that reports done informally. A
  reader who trusts the table concludes the integrity check cannot be disarmed
  except by the per-repo marks, none of which applies to it.
- **measurable?**: yes. Outcome variable: the set difference between the switch
  names in `policy.CORE`'s kill-switch paragraph and the README table; it must be
  empty.
- **sketch**: one row of the README table.

### I14 - The shared `.claude/agents/` file is written for Claude and read by Cursor

- **evidence**: `hooks/tezgah_agents.py:526-527` - `# markdown: one dir serves
  Claude and Cursor (Cursor reads .claude/agents/)` / `md_dir =
  os.path.join(root, HOST_DIRS["claude"]) if hosts & {"claude", "cursor"} else
  None`, and then `:553` - `emit(md_dir, wanted_md, name + ".md", render_md(name,
  desc, readonly, body("claude")))`. The per-host branch exists and is
  unreachable from that path: `_graph_howto` (`:64-72`) returns the `ToolSearch`
  sentence only for `host == "claude"` and "are exposed directly; use them as-is."
  otherwise, while the md path passes `"claude"` whatever the host set is.
- **class**: (c)
- **why it matters**: on a Cursor-only machine every generated explorer and
  reviewer is told in the first line of its body to call a tool Cursor does not
  have; the graph tools then go unused and the delegated agent reads the
  repository by hand instead - the delegation the document is written around does
  not happen, and the agent's own graph-first instruction reads as a failed
  precondition. The header comment records the intent ("Cursor reads this dir
  natively"), which is exactly why one file cannot carry one host's instruction.
- **class note**: read from source; that Cursor has no `ToolSearch` is what makes
  it observable and was not executed here.
- **measurable?**: yes. Outcome variable: in a Cursor session, whether a
  generated subagent calls a graph tool at all and the count of failed
  `ToolSearch` calls, with the body rendered per host against the current one.
- **sketch**: render the md set with `body("cursor")` when the host set contains
  no claude - `_graph_howto` already takes the host, so it is the argument at
  `hooks/tezgah_agents.py:553`.

## E. The detached index worker and the research CLI

### I15 - The failed-index note names a log file that does not exist

- **evidence**: `hooks/tezgah_context.py:230` - `note = "last auto-index failed
  (see %s/%s.log)" % (cache, name)`, against where the worker's output actually
  goes, `hooks/tezgah_context.py:232` - `log = open(os.path.join(cache, "logs",
  name + ".log"), "ab")`. The worker's docstring promises the marker teaches the
  session what happened - `hooks/tezgah_index.py:12-14` - "A final failure leaves
  a `<stamp>.failed` marker that autoindex surfaces to the next session, instead
  of looping invisibly" - and the test pins only the prefix:
  `tests/test_index.py:205` - `self.assertIn("last auto-index failed",
  proc.stdout)`.
- **class**: (c)
- **why it matters**: the one moment this line exists for is a user who has just
  been told the graph is stale and wants to know why. It hands them
  `<cache>/<slug>.log`; the log is one directory deeper, and the cache dir also
  holds stamps and locks named after the same slug, so the reader cannot guess
  which of them is the log. A loud message whose pointer resolves to nothing is
  the silent-failure shape wearing the opposite mask.
- **probe**: the path the note names is not the path the log is opened at; the
  two literals differ by the `logs/` segment.
- **measurable?**: yes. Outcome variable: `os.path.isfile` of the path named in
  the printed note after a forced worker failure; it must be true.
- **sketch**: build the log path once (`os.path.join(cache, "logs", name +
  ".log")`) and use that one value in the note, the `open` and the test.

### I16 - Two names for the codebase-memory cache, one per tool

- **evidence**: `hooks/tezgah_context.py:201-202` - `cbm_cache =
  os.environ.get("CBM_CACHE_DIR") or os.path.join(`, which decides whether the
  worker may run and where the stamp and the log land;
  `bin/tezgah-doctor:33-35` - `CBM_CACHE = os.environ.get("TEZGAH_CBM_CACHE",` /
  `os.path.join(HOME, ".cache", "codebase-memory-mcp"))` / `CBM_LOGS =
  os.path.join(CBM_CACHE, "logs")`, which is what the doctor reports and, with
  `--clean`, deletes. Neither file knows the other's name.
- **class**: (c)
- **why it matters**: with `CBM_CACHE_DIR` set - the variable the MCP server's
  own tooling uses, so a user with a relocated cache sets it - the hooks write
  stamps and index logs into one directory while `tezgah-doctor` reports and
  prunes the other. The doctor prints a small, healthy count and the real logs
  grow without bound, which is the growth the tool exists to reclaim
  (`bin/tezgah-doctor:4-6`). The two suites each set only their own variable
  (`tests/test_index.py:173` sets `CBM_CACHE_DIR`, `tests/test_doctor.py:50` sets
  `TEZGAH_CBM_CACHE`), so neither can see the split.
- **measurable?**: yes. Outcome variable: with `CBM_CACHE_DIR` set and a log
  written through the hook path, the log count `tezgah-doctor` reports; it must
  be non-zero.
- **sketch**: one resolver in `hooks/tezgah_paths.py` (for instance
  `os.environ.get("CBM_CACHE_DIR") or os.environ.get("TEZGAH_CBM_CACHE") or
  ...`), imported by both call sites.

### I17 - `tezgah-research init` takes any slug, and the line it creates is invisible

- **evidence**: `bin/tezgah-research:50` - `slug = args[0].strip().lower()
  .replace(" ", "-")` with nothing after it, passed to `tr.init`;
  `hooks/tezgah_research.py:70-71` - `def line_dir(repo, slug):` / `return
  os.path.join(root(repo), slug)` - an absolute slug replaces the root entirely
  and `..` climbs out. The lister that `check`, `status` and `claim` all use
  filters exactly those names away - `hooks/tezgah_research.py:61-67` - `return
  sorted(n for n in names if os.path.isdir(os.path.join(root(repo), n))` / `and
  not n.startswith("."))`.
- **class**: (c)
- **why it matters**: the CLI prints "research line: <path>" and a next-step
  paragraph for a line no other command can see: `check` reports nothing for it,
  `status` never lists it, and `claim` refuses with "no such research line"
  (`bin/tezgah-research:117`). Worse, `init ..` writes `state.json`,
  `findings.md`, `log.md` and `claims.jsonl` into `.tezgah/` itself and creates
  `.tezgah/experiments`, `.tezgah/literature` and `.tezgah/to_human` there - the
  state directory a reader and the status surfaces treat as tezgah's own. A
  slash in a name is enough; the exit code is 0 and nothing warns.
- **probe**: `tr.init(repo, "..")` wrote `['.tezgah/state.json',
  '.tezgah/findings.md', '.tezgah/log.md', '.tezgah/claims.jsonl']`; `tr.slugs`
  returned `[]` and `tr.check` returned `{}`; the other two slugs resolved to
  `../../escape` and `/tmp/absolute-line`.
- **measurable?**: yes. Outcome variable: for a slug set (`..`, `../x`, an
  absolute path, a name containing a slash), the exit code and whether every
  created path lies under `<repo>/.tezgah/research/<slug>/`.
- **sketch**: one predicate in `cmd_init` (and the same in `append_claim`) -
  `re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug)` with `misuse(...)` on failure - or
  the check inside `tr.line_dir`, so no caller can skip it.

### I18 - orx's skill shims are never listed for uninstall

- **evidence**: `bin/tezgah-setup:1075-1082` - "The shim files (a real
  `skills/orx/SKILL.md`, not a tezgah symlink) are owned by orx, so tezgah only
  runs its installer and never lists them for uninstall.", and the runner at
  `:1094` - `proc = subprocess.run([orx, "install-skills", "--agent", agent],`.
  Every uninstaller removes only names in `SKILLS` or symlinks
  (`bin/tezgah-setup:1393-1399`, `:1401-1415`, `:1417-1431`, `:1433-1442`,
  `:1444-1489`).
- **class**: (a) - a documented deliberate non-goal, with the rationale in the
  code.
- **why it matters**: after `--uninstall` the orx skill directory stays in every
  host's skills dir (`~/.claude/skills/orx`, and the same under the other four),
  and `skill_groups` will list it again on the next install. A skill whose `orx`
  binary the user removed is still advertised to the host, so a session that
  follows it lands in a fallback branch instead of the routing the rule promises.
  This is the only uninstall gap in the module that is deliberate rather than
  missed, and it is worth naming so the next reader does not spend the same hour
  on it that this pass did.
- **measurable?**: no - the ownership decision is the finding, and the observable
  (a leftover skill dir) follows from it without an experiment.
- **sketch**: ask orx to uninstall its shims (`orx uninstall-skills --agent ...`,
  if that exists) or record the written paths in `~/.config/tezgah` the way
  `tezgah_agents._record` records generated agent files, so `cleanup` can remove
  exactly those.

## Summary

| id | title | class | measurable |
|---|---|---|---|
| I1 | `hooks.json wired` passes on any single event (Stop unseen) | (c) | yes - row boolean over the 7/13 single-event fixtures |
| I2 | Claude's three link rows pass on a dangling symlink | (c) | yes - row boolean for a link whose target is missing |
| I3 | "skill metadata band present" cannot fail independently | (c) | yes - row boolean against a band-less RULES.md |
| I4 | "subagents generated" counts files the generator never promised | (c) | yes - row boolean per capability set |
| I5 | Nothing checks the Claude attribution wiring | (c) | yes - row boolean after the key is removed |
| I6 | `plugin copy current` hashes only the files that still exist | (c) | yes - `plugin_copy_current` for a copy with one extra file |
| I7 | `set_managed_block`/`set_managed_md` move the user's own text | (c) | yes - block and user-line index across two calls |
| I8 | `--uninstall` leaves a dangling `~/.codex/bin/consult` | (c) | yes - path exists after install-then-uninstall |
| I9 | opencode's `instructions` grows on every re-install | (c) | yes - entry count and resolvability across two installs |
| I10 | The contract's staleness hash omits a file it is rendered from | (c) | yes - `contract_stale()` per documented source |
| I11 | The router points at a file the host refuses to open | (c) | yes - successful reads of the full router per run |
| I12 | `agents-off` is honoured in three places and named in none | (c) | yes - count of `off()` names missing from CORE and the skill |
| I13 | `verify-off` is missing from the README switch table | (c) | yes - set difference, README table vs `policy.CORE` |
| I14 | The shared `.claude/agents/` file is written for Claude, read by Cursor | (c) | yes - failed `ToolSearch` calls per Cursor subagent run |
| I15 | The failed-index note names a log file that does not exist | (c) | yes - `isfile` of the note's path after a forced failure |
| I16 | Two names for the codebase-memory cache, one per tool | (c) | yes - log count the doctor reports with `CBM_CACHE_DIR` set |
| I17 | `tezgah-research init` takes any slug; the line is invisible | (c) | yes - exit code and containment per slug |
| I18 | orx's skill shims are never listed for uninstall | (a) | no - the ownership decision is the finding |

Seventeen of the eighteen are class (c); one is (a). No (b) surfaced: nothing in
the installer's docs or comments acknowledges one of these holes, so there was
nothing to file as an acknowledged-but-open gap. Where a doc states an intent the
code does not meet (I2, I10, I15) the acknowledgement is of the *purpose*, not of
the gap, which is what (c) means here.

## The one I would fix first

**I10**, because it is the only finding where the layer's own repair path is the
thing that lies and there is no second detector. `--install` re-renders
everything, so the drift is invisible to the maintainer who just edited
`hooks/tezgah_context.py`; the host it affects is the one that cannot see the
edit any other way; and the command that exists to catch it prints "contract is
current" while a running session keeps the previous always-on text. The fix is
one tuple entry plus making the guarding test derive from that tuple instead of
repeating it, and the probe above demonstrates both halves of the failure - the
text moves, the hash does not.

## Notes on what is *not* here

- The shipped manifests agree with the wiring each host gets.
  `hooks/hooks.json` (8 events) is the Claude plugin's own manifest and reaches
  Claude through the plugin copy that I6's row checks; `hosts/codex/hooks.json`
  (7) and `hosts/cursor/hooks.json` (13) match what `install_codex` (`:445`) and
  `install_cursor` (`:817`) write; `hosts/dsh/hooks.json` (6) is the file the
  dsh patch layer names as `configPath` (`:965-971`) and is a subset of the seven
  events its bridge implements (`bin/tezgah-setup:901-902`). The three
  `workflows/cbm-*.js` are installed for Claude only (`:391-394`), which is also
  the only runtime their `ToolSearch` line names, so that prompt text is not the
  I14 problem.
- Content idempotence holds: `tests/test_setup.py:176-185` already pins one
  `# tezgah:start`, seven tezgah hook entries, two opencode instructions and one
  `id: llm-pi-ai` after a second install. I7 is the one place a second run
  changes a file's *meaning* rather than its content.
- No `path:line` citation inside `skills/*` or `workflows/*.js` is dead (the
  sweep in Method), and every citation in this report was re-checked against the
  file after the draft: 71 citations, none pointing past a file's end or at a
  missing file.
