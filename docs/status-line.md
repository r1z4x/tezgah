# Status line: what each mark means and how it is drawn

Every [host](hosts.md) shows one line: what tezgah has armed, what this session
has used, and what this repo adds. Read it when you add a
[mark](glossary.md#mark), when no line is drawn, or when a mark shows a state you
cannot explain. As this repository prints it:

    tezgah v0.12.1  ·  pony○ exec✓ adhd○  ·  consult○ research○ graph○ orch○ judge○  ·  idx✓  ·  plans 1

## Shape: segments, groups, separator

One mark is one segment — `{"key", "state", "glyph", "text", "group"}` — built
host-neutrally by `health_segments()` (hooks/tezgah_context.py:1250-1318).
`render_line()` joins segments with one space inside a group and `  ·  ` between
groups (hooks/tezgah_context.py:1338-1346). The group is *data on each segment*: a renderer building its
own line from `--json` separates on `seg.group` and matches `render_line()`
without a second copy of the partition (hooks/tezgah_context.py:1259-1262) — opencode and dsh do exactly
that (hosts/opencode/tui/tezgah-tui.tsx:108-111,
hosts/dsh/statusline/lib/client.js:86-90).

| group | members | why together |
|---|---|---|
| -1 | the version prefix | the product itself, before any mark |
| 0 | `pony`, `exec`, `adhd` | the always-on switches |
| 1 | `consult`, `research`, `graph`, `orch`, `judge` | the on-demand capabilities |
| 2 | `idx` | a per-repo fact: code-graph readiness |
| 3 | `plans` | a per-repo fact, its own group |

Groups 0 and 1 come from `_GROUP` (hooks/tezgah_context.py:1237-1238); the prefix
carries -1 and `idx` and `plans` carry 2 and 3 where they are appended (hooks/tezgah_context.py:1320,1335-1339). Outside every
[root](glossary.md#root) the checklist still prints — tezgah loads globally on
opencode, so the indicator must not go silent — and only the per-repo extras are
omitted (hooks/tezgah_context.py:1332-1340, tests/test_statusline.py:12-13,tests/test_statusline.py:45-50).

### The version prefix

The line opens with `tezgah v0.12.1` (`version_segment()`, hooks/tezgah_context.py:1420-1435): not a [mark](glossary.md#mark) — no glyph, and `info`, the state that reports none — with a group of its own, so the marks separate from it the way the groups separate from each other; its segment carries the number as `version` for a program reading `--json`.
The number is the one reader `bin/tezgah-setup --version` also calls (`version()`, hooks/tezgah_context.py:1403-1419, bin/tezgah-setup:213): the local plugin manifest, else the newest `CHANGELOG.md` release, read bounded and never raising; unreadable, the prefix keeps the bare name rather than a placeholder.

## States

`LEGEND` (hooks/tezgah_context.py:1221-1237) is the source for this table; run
`tezgah-status --legend` to print it verbatim.

| state | glyph | color | asserts |
|---|---|---|---|
| `on` | `✓` | green | armed and in force this session (or always-on) |
| `ready` | `○` | yellow | armed, on demand — not used yet this session |
| `off` | `✗` | red | turned off by a [kill switch](glossary.md#kill-switch) or a per-repo `.no-*` mark |
| `info` | none | dim | no state: `idx` n/a or uncomparable, no blocked plan, or a measure this surface cannot report |

Glyphs are `GLYPHS`, colors `COLORS` (green 32, yellow 33, red 31, dim 2; hooks/tezgah_context.py:1214-1217).
The whole `text`+`glyph` chip is colored, and the glyph is drawn in every state:
color is additive, never the only carrier of the state — the accessibility rule
(`_seg_text()`, hooks/tezgah_context.py:1326-1335). `idx` is the one exception: its glyph *is* the index's
state, mapped back by `IDX_STATE` (hooks/tezgah_context.py:1220).

## Per mark

Flips come from the flag table (hooks/tezgah_context.py:1284-1294) and the
resolution after it (hooks/tezgah_context.py:1296-1306): `off` is decided first and always wins, then a
measure the surface cannot see, then armed-and-used or armed-not-used.

| mark | goes `on` when | goes `off` when |
|---|---|---|
| `pony` | the full ponytail skill text was read this session | `ponytail-auto.off`, or `.no-ponytail` |
| `exec` | never used-gated: `on` as soon as armed | `exec-mode.off` |
| `adhd` | `skills/i-have-adhd/SKILL.md` was read this session | `adhd-off`, or `.no-adhd` |
| `consult` | a shell command really ran `consult` | `consult-off`, or no OpenRouter/DeepSeek/Inception key |
| `research` | a command really ran the research CLI | `research-off`, or `orx` not installed |
| `graph` | a code-graph tool call (an `mcp__…codegraph…` tool) | `.no-graph` — a missing binary is `idx`'s report, not this mark's |
| `orch` | a delegate call (`Task`/`Agent`/`spawn_agent`) or a subagent start | `orchestrate-off` |
| `judge` | a shell command really ran `tezgah-triage` or `tezgah-docs` | `judge-off`, or no credential: no `TYPESAFE_API_KEY` and no non-empty `~/.config/typesafe/key`, and neither the fallback's `OPENROUTER_API_KEY` nor its `~/.config/openrouter/key` |

Read `on` for `consult`/`research`/`judge` as "installed and usable", not "you
must use it": a missing key or binary reads the same red as a kill switch
(`have_consult_key()`, `orx_bin()`, `have_judge_key()`, hooks/tezgah_context.py:1291-1293,
hooks/tezgah_paths.py:213-230, hooks/tezgah_paths.py:249-278). `judge` is the seam
behind `bin/tezgah-triage`, `bin/tezgah-docs` and the skill picker
([judge](judge.md)), and its credential is the seam's own two channels, never
omp's login store. `graph` and `orch` are the two switch-only marks: nothing at
arming time asks whether their toolchain is on the machine, because neither rule
leaves the text when it is missing - the graph-first rule ships whether or not
codegraph is installed, and the graph's own absence is `idx`'s report
(`–` from the same check, `_index_mark()`, hooks/tezgah_context.py:1119) beside the
note that names the missing MCP (hooks/tezgah_context.py:870-872). Their `○` says
the rule is armed, never that a graph or a delegate surface answers.
`exec` has no used channel — its `meas` is `None` — so it can never be `ready`
(hooks/tezgah_context.py:1287,1250). The per-repo `idx`: ✓ indexed, ↻ indexed but HEAD moved since the
stamp, ✗ not indexed yet, ? the index cannot be compared to HEAD (no stamp, or
an unreadable HEAD), – n/a (outside a root, codegraph absent, or
`.no-graph`); its probe forks git twice, so it is memoised per `(cwd, base)`
(`index_mark()`, hooks/tezgah_context.py:1103-1115) and `idx_override` lets a redraw send the glyph back
instead of forking (hooks/tezgah_context.py:1308-1309). `plans` is `plans N` plus `(M blk)` when M open
plan files carry `status: blocked` in their first 400 bytes — `ready` with a
blocked plan, else `info` (`plan_mark()`, hooks/tezgah_context.py:1185-1204).

### The two skill-read marks, and `--observable=`

`pony` and `adhd` mean "the full skill text reached the session" — the only signal
separating a real rule read from the always-on summary. They are earned by a read
of `skills/<name>/SKILL.md`, matched on the path suffix, so any other read costs
nothing (`SKILL_MARKS`, `skill_read_kind()`, hooks/tezgah_context.py:140-164).

A read is not observable at an acceptable price everywhere: it needs Claude's
transcript, opencode's in-process classification, or omp's extension filter before
python is asked (hooks/tezgah_context.py:147-151). A surface that cannot see one must not say "the skill
was never opened", so it declares what it can see and those marks render `info`
(dim, no glyph) instead of `ready` (`observable`, hooks/tezgah_context.py:1272-1277; the set constant
`TOOL_USE_MEASURES`, hooks/tezgah_context.py:1247). The `--observable=` flag carries it on the CLI
(bin/tezgah-status:26-30,52-53,120-123). Two callers pass the tool-use set: Cursor's
status line (statusline.py:109-114) and Codex, which renders the line plain into
`systemMessage` (hosts/codex/hook.py:182-184,195-198); dsh passes the literal flag
string (hosts/dsh/statusline/lib/index.js:18,47-48), which names the five marks its
own hook can record - `judge` included, since dsh wires the same PostToolUse hook
every other host does. The set is what a host can write, not what it happens to
have written: a mark the literal omits reads `info` there rather than a claim.

## The used-kinds channel

A used measure is one append to the session store,
`<cache_dir>/sessions/<slug(session_id)>.jsonl`, one `{"kind": …}` per line
(`record()`, hooks/tezgah_context.py:1047-1063; `used()` reads it back, hooks/tezgah_context.py:1066-1080).
`cache_dir()` is `~/.cache/tezgah` with a temp fallback for sandboxed hosts
(hooks/tezgah_paths.py:24,31-32,123-143); a missing kind is not an event, so only
the five kinds are ever written (hooks/tezgah_context.py:1050-1053).

Writers: the shared PostToolUse hook `hooks/projects-posttooluse.py` — `graph` from
an MCP tool name, else the shell tokenizer's answer, which counts a tool only when
the command really ran it (34-38,84) and is the one writer that can earn `judge`
(a run of `bin/tezgah-triage` or `bin/tezgah-docs`, `shell_kind`, hooks/tezgah_context.py:1010-1025)
— plus `hooks/projects-auto-init.py:35`
(`orch` on subagent start), hosts/codex/hook.py:148,168,
hosts/cursor/hook.py:224,250,256,272,280,295, hosts/opencode/plugins/tezgah.js:1863-1870,
hosts/opencode/plugins/tezgah.js:2276, hosts/omp/hook.py:141. Both Claude (hooks/hooks.json) and dsh
(hosts/dsh/hooks.json) wire PostToolUse to that one shared hook, which is how dsh
gets any used mark at all: with no local transcript, the store is the only channel
its line has (hooks/projects-posttooluse.py:26-30).

Claude's line never reads the store: it parses `tool_use` blocks out of
`payload["transcript_path"]` plus the subagent transcripts under it, which is how
it sees the skill reads the store cannot carry (statusline.py:58-107).
Every other surface reads the store.

## Surfaces

- **Claude / Cursor** — `statusline.py` reads the host's session JSON on stdin,
  picks the host from `--cursor` or `TEZGAH_STATUS_HOST`, renders
  `render_line(segs, color=color_default())`, and joins Orca's own status line to
  the tezgah segment with `  |  `; `TEZGAH_STATUS_LEGEND=1` appends the legend
  (31-34,40-48,116-122). ANSI is dropped under `NO_COLOR` or
  `TEZGAH_STATUS_COLOR=0` (`color_default()`, hooks/tezgah_context.py:1319-1323).
- **omp** — hosts/omp/tezgah-hook.ts.in: `draw()` prefers
  `ctx.ui.setWidget("tezgah", [line], {placement: "belowEditor"})`, which renders
  the colored string as-is; `setStatus` is the fallback for a build without
  `setWidget`, and it is plain because omp strips ANSI (12-29). `status_line()`
  builds the line and carries `idx_override`, so a per-tool redraw forks no git
  (hosts/omp/hook.py:85-97); it redraws on session start, session switch, turn end
  and each watched tool result (hosts/omp/tezgah-hook.ts.in:198-199,245-249).
- **opencode** — hosts/opencode/tui/tezgah-tui.tsx: a local TUI plugin
  (`tui.json`'s `plugin` array, not the server plugin) registering an `app_bottom`
  slot, shelling out to `tezgah-status <dir> --json <sessionID>`, coloring each
  segment from the active theme and rebuilding the separator from `seg.group`
  (56-88,hosts/opencode/tui/tezgah-tui.tsx:108-111). Its `tezgah: status legend` command opens a dialog running
  `--legend` (141-147).
- **dsh** — hosts/dsh/statusline/lib/index.js serves `GET /api/tezgah.status`
  behind the Web UI's own authenticated fetch fence, so the browser fetches it
  same-origin with no extra token handling (14,34-38); it always passes
  `--observable=consult,research,graph,orch,judge` (18,47-48) and returns `{segments,
  legend}` for `?format=json`, plain text otherwise (49-56,63). Its client half
  (hosts/dsh/statusline/lib/client.js) renders the marks in the session header in
  fixed light/dark colors, polls every 10 s while the tab is visible, and shows the
  legend on hover, pins it on click (16-19,35,47-52,63-64).
- **Codex** — hosts/codex/hook.py puts the plain line in `systemMessage`
  (182-184,195-198).

## Seeing and debugging the line

`bin/tezgah-status` is the CLI every surface above shells out to, and the way to
see a line by hand:

```sh
tezgah-status /path/to/repo <session-id>     # the line for one repo and session
tezgah-status /path/to/repo <id> --json      # segments: key/state/glyph/text/group
tezgah-status /path/to/repo <id> --counters  # the evidence ledger's counters
tezgah-status --legend                       # what each mark means
```

The session id is the second positional argument or `TEZGAH_SESSION`; without it
the used marks cannot light up (bin/tezgah-status:119). `--color`/`--no-color` force ANSI or plain,
`--observable=` narrows the measures as above, and an unknown flag exits 2 (bin/tezgah-status:49-54,120-127).

`--counters` is not the marks: it prints `tezgah_integrity.counters(session)` —
`steps`, `tool_error_rate`, `claims`, `false_completion`, `denies`, `nudges`,
`fanout`, `consult`, `codegen`, `codegen_failed`, `judge`, `shape` and the `kinds`
seen (bin/tezgah-status:68-90); with `--json` as JSON. `shape` counts the reply
shapes the Stop path flags - `table-open`, `recap-close` - one row per flagged
reply and never a refusal, because the output contract's own carve-outs make a
refusal wrong before the rate is known
(hooks/tezgah_integrity.py:1458-1490). `judge` is the seam's spend,
counted on the row's **kind** and never on a `detail` substring like `consult` and
`codegen` are, because a judgement's detail carries the caller and the model and a
substring would also count a commit message that says "judge"
(hooks/tezgah_integrity.py:743-749). It is in neither `STEP_KINDS` nor the check
set: a judgement is a cost, and a model answer must never license a "done" claim
(`STEP_KINDS`, hooks/tezgah_integrity.py:673). `tezgah-setup --status <path>` prints the plain line for a
repo (bin/tezgah-setup:4117-4119). A wrong or missing line usually ends in one of
three places: no session id (used marks stay `○`), a surface that passed
`--observable=` and so renders dim where you expected a state, or a store a
sandboxed host could not write (hooks/tezgah_paths.py:120-133).

## A mark must not claim what it cannot see

A mark asserting a state the surface cannot observe is a bug in this layer, so the
honest answer is dim, never a guess. `idx` has the same rule inside its own glyph
set: `?` means the comparison could not be made - no stamp file, or a HEAD that
could not be read - so the mark refuses to say either fresh or stale, and
`index_notice()` says on the turn that the graph's age is unknown. On a host that
sandboxes hook writes (dsh) the stamp is never written, and before that state
existed the mark read green there for good. That is why `observable` exists (hooks/tezgah_context.py:1272-1277),
why the skill-read check is documented as unavailable on Codex, Cursor and dsh
(hooks/tezgah_context.py:147-151), why omp ignores any `idx` value that is not one of
its five glyphs (hosts/omp/hook.py:82-95) - a value outside that set re-probes
instead of being reused, one fork and never a wrong mark - and
why `off` is decided before the visibility one - a
kill switch is observable everywhere (hooks/tezgah_context.py:1272-1277,1297-1300). Cursor's pinned plain
line is the regression for it (tests/test_statusline.py:14-17,33-37). `judge` is
the live case of both halves: its used-kind is written by the hosts' own hooks, so
where that store cannot be written the mark states nothing instead of claiming
"armed, not used yet" forever, and where the kill switch is armed `off` wins over
that carve-out (tests/test_statusline.py:167-177).

## Source of truth

- `hooks/tezgah_context.py`, `hooks/tezgah_paths.py`, `bin/tezgah-status`
- `statusline.py`, `hooks/projects-posttooluse.py`, `hooks/projects-auto-init.py`
- `hooks/hooks.json`, `hosts/dsh/hooks.json`
- `hosts/omp/tezgah-hook.ts.in`, `hosts/omp/hook.py`, `hosts/codex/hook.py`,
  `hosts/cursor/hook.py`
- `hosts/opencode/tui/tezgah-tui.tsx`, `hosts/opencode/plugins/tezgah.js`
- `hosts/dsh/statusline/lib/index.js`, `hosts/dsh/statusline/lib/client.js`
- `tests/test_statusline.py`
