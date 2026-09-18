# Status line: what each mark means and how it is drawn

Every [host](hosts.md) shows one line: what tezgah has armed, what this session
has used, and what this repo adds. Read it when you add a
[mark](glossary.md#mark), when no line is drawn, or when a mark shows a state you
cannot explain. As this repository prints it:

    pony○ exec✓ adhd○  ·  consult○ research○ cbm○ orch○  ·  idx✓  ·  plans 1

## Shape: segments, groups, separator

One mark is one segment — `{"key", "state", "glyph", "text", "group"}` — built
host-neutrally by `health_segments()` (hooks/tezgah_context.py:1150-1215).
`render_line()` joins segments with one space inside a group and `  ·  ` between
groups (hooks/tezgah_context.py:1237-1243). The group is *data on each segment*: a renderer building its
own line from `--json` separates on `seg.group` and matches `render_line()`
without a second copy of the partition (hooks/tezgah_context.py:1159-1162) — opencode and dsh do exactly
that (hosts/opencode/tui/tezgah-tui.tsx:76-79,
hosts/dsh/statusline/lib/client.js:86-90).

| group | members | why together |
|---|---|---|
| 0 | `pony`, `exec`, `adhd` | the always-on switches |
| 1 | `consult`, `research`, `cbm`, `orch` | the on-demand capabilities |
| 2 | `idx` | a per-repo fact: code-graph readiness |
| 3 | `plans` | a per-repo fact, its own group |

Groups 0 and 1 come from `_GROUP` (hooks/tezgah_context.py:1081-1082); `idx` and
`plans` carry 2 and 3 where they are appended (hooks/tezgah_context.py:1209-1214). Outside every
[root](glossary.md#root) the checklist still prints — tezgah loads globally on
opencode, so the indicator must not go silent — and only the per-repo extras are
omitted (hooks/tezgah_context.py:1164-1166, tests/test_statusline.py:11-12,tests/test_statusline.py:45-50).

## States

`LEGEND` (hooks/tezgah_context.py:1090-1105) is the source for this table; run
`tezgah-status --legend` to print it verbatim.

| state | glyph | color | asserts |
|---|---|---|---|
| `on` | `✓` | green | armed and in force this session (or always-on) |
| `ready` | `○` | yellow | armed, on demand — not used yet this session |
| `off` | `✗` | red | turned off by a [kill switch](glossary.md#kill-switch) or a per-repo `.no-*` mark |
| `info` | none | dim | no state: `idx` n/a, no blocked plan, or a measure this surface cannot report |

Glyphs are `GLYPHS`, colors `COLORS` (green 32, yellow 33, red 31, dim 2; 1083-1088).
The whole `text`+`glyph` chip is colored, and the glyph is drawn in every state:
color is additive, never the only carrier of the state — the accessibility rule
(`_seg_text()`, hooks/tezgah_context.py:1225-1234). `idx` is the one exception: its glyph *is* the index's
state, mapped back by `IDX_STATE` (hooks/tezgah_context.py:1123).

## Per mark

Flips come from the flag table (hooks/tezgah_context.py:1150-1159) and the
resolution after it (hooks/tezgah_context.py:1195-1203): `off` is decided first and always wins, then a
measure the surface cannot see, then armed-and-used or armed-not-used.

| mark | goes `on` when | goes `off` when |
|---|---|---|
| `pony` | the full ponytail skill text was read this session | `ponytail-auto.off`, or `.no-ponytail` |
| `exec` | never used-gated: `on` as soon as armed | `exec-mode.off` |
| `adhd` | `skills/i-have-adhd/SKILL.md` was read this session | `adhd-off`, or `.no-adhd` |
| `consult` | a shell command really ran `consult` | `consult-off`, or no OpenRouter/DeepSeek key |
| `research` | a command really ran the research CLI | `research-off`, or `orx` not installed |
| `cbm` | a code-graph tool call (an `mcp__…codebase…` tool) | `.no-cbm` |
| `orch` | a delegate call (`Task`/`Agent`/`spawn_agent`) or a subagent start | `orchestrate-off` |

Read `on` for `consult`/`research` as "installed and usable", not "you must use it":
a missing key or binary reads the same red as a kill switch (`have_consult_key()`,
`orx_bin()`, hooks/tezgah_context.py:1155-1156, hooks/tezgah_paths.py:200-216).
`exec` has no used channel — its `meas` is `None` — so it can never be `ready`
(1153,1166). The per-repo `idx`: ✓ indexed, ↻ indexed but HEAD moved since the
stamp, ✗ not indexed yet, – n/a (outside a root, codebase-memory-mcp absent, or
`.no-cbm`); its probe forks git twice, so it is memoised per `(cwd, base)`
(`index_mark()`, hooks/tezgah_context.py:1021-1033) and `idx_override` lets a redraw send the glyph back
instead of forking (hooks/tezgah_context.py:1179-1181). `plans` is `plans N` plus `(M blk)` when M open
plan files carry `status: blocked` in their first 400 bytes — `ready` with a
blocked plan, else `info` (`plan_mark()`, hooks/tezgah_context.py:1088-1107).

### The two skill-read marks, and `--observable=`

`pony` and `adhd` mean "the full skill text reached the session" — the only signal
separating a real rule read from the always-on summary. They are earned by a read
of `skills/<name>/SKILL.md`, matched on the path suffix, so any other read costs
nothing (`SKILL_MARKS`, `skill_read_kind()`, hooks/tezgah_context.py:hooks/tezgah_context.py:118-141).

A read is not observable at an acceptable price everywhere: it needs Claude's
transcript, opencode's in-process classification, or omp's extension filter before
python is asked (hooks/tezgah_context.py:125-129). A surface that cannot see one must not say "the skill
was never opened", so it declares what it can see and those marks render `info`
(dim, no glyph) instead of `ready` (`observable`, hooks/tezgah_context.py:1172-1177; the set constant
`TOOL_USE_MEASURES`, hooks/tezgah_context.py:1147). The `--observable=` flag carries it on the CLI
(bin/tezgah-status:12-16,37-38,69-72). Two callers pass the tool-use set: Cursor's
status line (statusline.py:109-114) and Codex, which renders the line plain into
`systemMessage` (hosts/codex/hook.py:163-165,177-179); dsh passes the literal flag
string (hosts/dsh/statusline/lib/index.js:18,47-48).

## The used-kinds channel

A used measure is one append to the session store,
`<cache_dir>/sessions/<slug(session_id)>.jsonl`, one `{"kind": …}` per line
(`record()`, hooks/tezgah_context.py:hooks/tezgah_context.py:965-982; `used()` reads it back, hooks/tezgah_context.py:984-999).
`cache_dir()` is `~/.cache/tezgah` with a temp fallback for sandboxed hosts
(hooks/tezgah_paths.py:26,31-32,122-136); a missing kind is not an event, so only
the four kinds are ever written (hooks/tezgah_context.py:hooks/tezgah_context.py:968-971).

Writers: the shared PostToolUse hook `hooks/projects-posttooluse.py` — `cbm` from
an MCP tool name, else the shell tokenizer's answer, which counts a tool only when
the command really ran it (34-38,84) — plus `hooks/projects-auto-init.py:35`
(`orch` on subagent start), hosts/codex/hook.py:130,149,
hosts/cursor/hook.py:207,230,236,251,259, hosts/opencode/plugins/tezgah.js:1160-1167,
hosts/opencode/plugins/tezgah.js:1541-1542, hosts/omp/hook.py:141. Both Claude (hooks/hooks.json) and dsh
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
  `TEZGAH_STATUS_COLOR=0` (`color_default()`, hooks/tezgah_context.py:1218-1222).
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
  (24-56,hosts/opencode/tui/tezgah-tui.tsx:76-79). Its `tezgah: status legend` command opens a dialog running
  `--legend` (109-115).
- **dsh** — hosts/dsh/statusline/lib/index.js serves `GET /api/tezgah.status`
  behind the Web UI's own authenticated fetch fence, so the browser fetches it
  same-origin with no extra token handling (14,34-38); it always passes
  `--observable=consult,research,cbm,orch` (18,47-48) and returns `{segments,
  legend}` for `?format=json`, plain text otherwise (49-56,63). Its client half
  (hosts/dsh/statusline/lib/client.js) renders the marks in the session header in
  fixed light/dark colors, polls every 10 s while the tab is visible, and shows the
  legend on hover, pins it on click (16-19,35,47-52,63-64).
- **Codex** — hosts/codex/hook.py puts the plain line in `systemMessage`
  (163-165,177-179).

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
the used marks cannot light up (18-20). `--color`/`--no-color` force ANSI or plain,
`--observable=` narrows the measures as above, and an unknown flag exits 2 (37-41).

`--counters` is not the marks: it prints `tezgah_integrity.counters(session)` —
`steps`, `tool_error_rate`, `claims`, `false_completion`, `denies`, `nudges`,
`fanout`, `consult`, `codegen`, `codegen_failed` and the `kinds` seen (49-60);
with `--json` as JSON. `tezgah-setup --status <path>` prints the plain line for a
repo (bin/tezgah-setup:2283-2284). A wrong or missing line usually ends in one of
three places: no session id (used marks stay `○`), a surface that passed
`--observable=` and so renders dim where you expected a state, or a store a
sandboxed host could not write (hooks/tezgah_paths.py:27-32).

## A mark must not claim what it cannot see

A mark asserting a state the surface cannot observe is a bug in this layer, so the
honest answer is dim, never a guess. That is why `observable` exists (hooks/tezgah_context.py:1172-1177),
why the skill-read check is documented as unavailable on Codex, Cursor and dsh
(hooks/tezgah_context.py:125-129), why omp ignores any `idx` value that is not one of its four glyphs
(hosts/omp/hook.py:82-95), and why `off` is decided before the visibility one — a
kill switch is observable everywhere (1139-1143,1162-1163). Cursor's pinned plain
line is the regression for it (tests/test_statusline.py:15-16,33-37).

## Source of truth

- `hooks/tezgah_context.py`, `hooks/tezgah_paths.py`, `bin/tezgah-status`
- `statusline.py`, `hooks/projects-posttooluse.py`, `hooks/projects-auto-init.py`
- `hooks/hooks.json`, `hosts/dsh/hooks.json`
- `hosts/omp/tezgah-hook.ts.in`, `hosts/omp/hook.py`, `hosts/codex/hook.py`,
  `hosts/cursor/hook.py`
- `hosts/opencode/tui/tezgah-tui.tsx`, `hosts/opencode/plugins/tezgah.js`
- `hosts/dsh/statusline/lib/index.js`, `hosts/dsh/statusline/lib/client.js`
- `tests/test_statusline.py`
