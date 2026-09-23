# Orchestration and observation surfaces - what the second unprobed area holds

Written 2026-09-19 against `d2f0cf4`, from reading `bin/consult`, `bin/codegen`,
`statusline.py`, `hosts/opencode/tui/tezgah-tui.tsx`,
`hosts/dsh/statusline/lib/{index,client}.js`, `hooks/tezgah_untrusted.py` and the
`tezgah_context`/`tezgah_integrity` code they read. Every claim below carries a
`path:line` that was opened. Where a claim was executed it says **measured** and
gives the observation; where a host had to be assumed it says so.

Method: a local stub chat-completions endpoint under `CONSULT_URL` /
`CODEGEN_URL`, the real CLIs run against it, in-process calls to the pure
predicates (`untrusted_source`, `marks`, `counters_all`, `health_segments`), a
`sys.addaudithook` wrapper to inventory the children one redraw spawns, and a
read of the 1186 ledgers on this machine. No provider was paid, no repo file was
written by a probe, and no host state was touched.

Not verified here, and said so where it matters: how often opencode's event bus
delivers `message.part.updated` (no opencode session was driven), and the dsh route
itself (dsh was not running).

## O1 - the referee's cross-examination is unverified: the five headings are a prompt, not a check

- evidence: `bin/consult:60` - "The headings are fixed so the caller can read
  back named fields"; `bin/consult:295` - `print("## referee (%s)" % judged)`;
  `bin/consult:301` - `print(verdict)`. The verdict is printed verbatim: nothing
  in the file tests that it carries one of the five headings.
- evidence, second: `tests/test_consult_arena.py:122` asserts the headings appear
  in the *prompt* (`test_the_referee_is_asked_for_every_field_the_rule_names`),
  and `:107` asserts `"2. Key disagreements"` in stdout - which passes because the
  fake's default reply is the well-formed `DIGEST` at
  `tests/test_consult_arena.py:24-28`, not because the tool checked anything.
- **measured**: panel `m1,bad` with `bad` answering 429 and the referee returning
  the prose "Both answers are fine. I would go with the first one." -> exit 0, a
  `## referee (m1)` section with zero of the five headings, footer `referee: m1`,
  and nothing distinguishing it from a cross-examination.
- class: (c) - nobody has named it. (The *default* referee being one of the
  panellists it judges is a different matter and is class (a): documented at
  `bin/consult:8`, "referee model (default: first that answered)", `:288`.)
- why it matters: stage two exists so the caller reads back named fields instead
  of a free-form verdict that drops the minority view (`bin/consult:59-61`). A
  truncated, paraphrased or outright unstructured reply is printed as
  `## referee (<model>)` and the footer says `referee: <model>`, exactly like a
  good one, so a decision that was never cross-examined is acted on as if it
  were. The tool already knows how to disclose a degraded arena
  (`bin/consult:310`, "referee: FAILED ... the panel answers stand unjudged") - it
  has no predicate for this degradation.
- measurable: yes, k=20 against a stub. Outcome variable: the share of runs whose
  referee section omits at least one of the five headings while the run still
  reports `referee: <model>` and exits 0. Pass = every such run carries a
  degradation line the way the dead-referee branch does.
- sketch: one predicate in `main()` after `bin/consult:292` - a `REFEREE_FIELDS`
  constant holding the five heading strings, checked against `verdict`; on a miss
  print the panel answers and reuse the existing "no cross-examination" footer.
  About six lines, no new flag, and the existing fake endpoint makes it a
  one-test change.

## O2 - the panel has no global deadline, so the documented timeout is off by up to (N+1)x

- evidence: `bin/consult:260` - `deadline = timeout + 15  # wall-clock cap per
  model`; `bin/consult:264-266` collects the futures in a serial loop, each with
  its own `.result(timeout=deadline)`; `bin/consult:292` gives the referee one
  more `(timeout+15)`, submitted only after that loop ends.
- evidence, second: `bin/consult:12` documents the flag as "per-model timeout
  seconds"; `bin/codegen:18-19` shows the sibling CLI's opposite choice - "caps
  the WHOLE request, not one socket operation".
- **measured**: 2 models and `--timeout 5` against an endpoint that trickles
  under the socket timeout -> 52.2 s wall clock (m1 gave up at 20 s, m2 answered
  at ~38 s, the referee then spent another 20 s), ~10x what the flag reads as
  promising.
- class: (c) - the comment names the socket-reset half, never the aggregate.
- why it matters: consult is invoked from an agent loop, a hook or a script with
  a wall-clock expectation. With the defaults (2 models, `--timeout 120`) a
  trickling endpoint can hold the caller for ~6.75 min and nothing bounds it;
  with `--models a,b,c,d` it is longer. No flag caps the run.
- measurable: yes, k runs at `--timeout t` for a model count of 1..4 against the
  trickling stub. Outcome variable: wall clock divided by the documented per-model
  value. Pass = one global deadline, or a footer naming the aggregate that fired.
- sketch: compute `deadline_at = time.monotonic() + timeout + 15` once before
  `bin/consult:262` and pass `max(0, deadline_at - time.monotonic())` to every
  `.result()`, the referee's included.

## O3 - codegen's "not valid Python" guard keys on the `.py` suffix, so extension-less Python and every other language are unvouched

- evidence: `bin/codegen:214` - `if path.endswith(".py"):` is the whole guard
  (`:216` is the `ast.parse` call); `bin/codegen:27` names "a draft that is not
  valid Python" as one of the exit-2 reasons; the contract generalises it -
  `skills/tezgah-contract/SKILL.md:175`, "a half-written file that happens to
  parse is the exact failure this guards against".
- **measured**, one broken body (unbalanced braces or a bad `def`, closed fence)
  per path kind: `hosts/opencode/tui/tezgah-tui.tsx` -> exit **0**, diff printed;
  `bin/codegen` (a Python file with no `.py` suffix, this repo's own house style)
  -> exit **0**, diff printed; `statusline.py` -> exit 2, "statusline.py: the
  draft is not valid Python". A pure truncation with no closing fence *is*
  caught, at `bin/codegen:189` ("no file block in the reply") - measured exit 2.
- class: (c).
- why it matters: exit 0 is the contract's "usable drafts, diff printed"
  (`bin/codegen:23`) and the only signal the router waits for before applying a
  draft. The check works where it is wired (the `statusline.py` control proves
  it), so what is broken is the coverage - and the repo hands codegen exactly
  these paths: `hosts/*/**.tsx`, `hosts/*/**.js`, and every `bin/*` script.
- measurable: yes, k=1 per path kind: feed one malformed draft per kind and read
  the exit code. Outcome variable: the exit code. Pass = non-zero (or an explicit
  "not checked" line) for every path the tool accepts in `--files`.
- sketch: the honest smallest change is not a TSX parser. Make the unvouched case
  loud: a `CHECKED_SUFFIXES` constant (today `(".py",)`) plus one line in the diff
  footer - `codegen: NOTE <path> was not parsed (no checker for this type)` - so
  the router knows which drafts nothing examined. A second parser can follow if
  the tier is used on `.tsx` in practice.

## O4 - the tier counters count a substring of a command, not a call of the tier

- evidence: `hooks/tezgah_integrity.py:681` - `if "consult" in detail:` and
  `:683` - `if "codegen" in detail:`, over the row's free-text `detail`, which
  for a shell call is the command line (`:1038`, `detail = (cmd or ...)`).
- **measured**: `counters_all()` over this machine's 1186 ledgers right now:
  `consult=112`, `codegen=26`, `codegen_failed=0`. Among the counted rows:
  `sed -n '26,38p' bin/codegen`, `wc -l bin/consult bin/codegen`,
  `grep -n "orchestration\|consult\|codegen\|statusline" ...`, `ls -l bin/consult
  bin/codegen` - reads and greps of the tools' own source, counted as uses of the
  tier.
- class: (c).
- why it matters: `tezgah-status --counters --all` is the only machine-readable
  record of whether the cheap tier was used, and the contract's fallback rule
  (`skills/tezgah-contract/SKILL.md:167-171`, "FALLBACK IS AUTOMATIC AND NOT
  OPTIONAL") makes the tier's failure the interesting event. As counted, a session
  that never ran the tier but read its file inflates `codegen`, and nothing
  separates a real draft from a mention.
- measurable: yes, k=1 over the corpus: recompute the counters with a
  program-position match and diff. Outcome variable: rows counted by substring
  minus rows counted by program position, per tier.
- sketch: in `counters`, replace the `in detail` test with the
  `tezgah_context.shell_programs` membership test `shell_kind` already uses
  (`hooks/tezgah_context.py:967-973`) - one function, both keys.

## O5 - the tier's failure is invisible on the host that reports no outcome

- evidence: `hooks/tezgah_integrity.py:1039` - `if failed:` is the only place
  `FAILED_MARK` (`:607`, `"[exit!=0]"`) is appended, and `:685` is the only place
  `codegen_failed` is counted (`detail.endswith(FAILED_MARK)`).
  `hosts/cursor/hook.py:238` passes `failed=None, source=source` on the
  post-tool event and `:263` says why: "# failed=None because the event carries
  no outcome."
- **measured**: `codegen_failed` is 0 across 1186 ledgers (O4), and 58 of the 112
  consult rows carry `exit: None` - the rows where a failure could not be
  recorded at all.
- class: (b) - the host-level hole is acknowledged (round-1 C8 and the comment
  above); what is not named is the consequence for this rule: on Cursor a
  `bin/codegen` that exits 2 is not distinguishable from one that exited 0, so
  the fallback the contract makes mandatory leaves no trace anywhere.
- why it matters: the fallback is a promise the layer makes ("the router writes
  that code itself ... and says in the report that it fell back and why",
  `skills/tezgah-contract/SKILL.md:171-172`) and the report is prose the router
  writes about itself. With
  `codegen_failed` structurally 0 on one host, a maintainer reading the counters
  cannot tell a healthy tier from a dead one.
- measurable: yes, k=2 (one host that reports the outcome, one that does not), the
  same failing `bin/codegen` invocation on each. Outcome variable: `codegen_failed`
  per host. Pass = a row written by the tier itself in both.
- sketch: the tier's own report is the honest source and it is one call: in
  `bin/codegen`'s `Insufficient` handler, or in the router's fallback, write one
  ledger row (`note(session_id, "codegen_failed", reason)`), instead of inferring
  from a mark a host may be unable to set.

## O6 - a surface with no session id renders "not used yet" as a fact

- evidence: `hooks/tezgah_context.py:1007-1009` - `def used(session_id): if not
  session_id: return set()`; `:1240-1241` maps "not in `seen`" to `state = "on"`
  else `ready`; the legend defines that state as a fact - `:1166` -
  `name\u25cb  yellow  armed, on demand - not used yet this session`. An id whose
  recorder file is unreadable takes the same path (`:1019`, `except OSError:
  pass`).
- evidence, second, three real call sites pass no id: `hosts/dsh/statusline/lib/index.js:47`
  - `const where = sessionId === undefined ? [dir, OBSERVABLE]`, reached whenever
  the client has no id yet (`hosts/dsh/statusline/lib/client.js:36` drops the
  query parameter when `sessionId` is falsy); `hosts/opencode/tui/tezgah-tui.tsx:51`
  - `run([dir, "--json", ...sessionParams(props.api)])`, where `sessionParams`
  returns `[]` when the route carries no `sessionID`; `statusline.py:109` -
  `used_kinds(payload.get("session_id"))` on the Cursor path.
- **measured**: `tezgah-status <repo> --json` with and without a session id
  returns byte-identical segments - all four tool-use marks and both skill marks
  at `ready`.
- class: (b) - `bin/tezgah-status:33` already acknowledges the mechanism ("without
  it the 'used' marks cannot light up"); what nobody has named is that the same
  condition renders `ready`, which the legend turns into "this session did not use
  it".
- why it matters: this is the *other half* of the guard the module already
  documents at `hooks/tezgah_context.py:1212-1217` ("'armed, not used yet' is a
  claim a host cannot make about a mark it cannot observe"). The truthful state
  when the recorder was never read is `info` - dim, no glyph, "cannot report" - and
  the surface cannot reach it for a missing id.
- measurable: yes, k=1 per surface: read the JSON segments with and without the
  id. Outcome variable: the state of the six measure-bearing marks. Pass = `info`
  when no id resolved, `ready` only when the recorder was read and found empty.
- sketch: one condition beside `hooks/tezgah_context.py:1238` - when
  `observable is not None` and no id resolved, render `info`; the host surfaces
  already pass `observable`.

## O7 - the status line silently reports a different checkout when the payload carries no cwd

- evidence: `statusline.py:113` - `segs = health_segments(real or os.getcwd(),
  payload.get("session_id"),` with `real` empty whenever the payload has no
  `workspace.current_dir`/`cwd`; `statusline.py:36` - `payload = json.loads(data
  or "{}")`, so an empty or unparseable payload is exactly that case.
- **measured**: the same payload `{}` run from three directories: from the
  checkout the line ends `idx(check)`; from `/tmp` and from `$HOME` there is no
  `idx` segment at all. With `{"cwd": <repo>}` the line is identical from every
  directory.
- class: (c).
- why it matters: what the line reports is a *repo* - the `idx` glyph, `plans N`
  and the per-repo `.no-*` opt-outs all come from the resolved cwd. When the
  fallback fires, another directory's marks are shown with the same confidence as
  the session's own and the reader has no cue that the line answers about
  somewhere else.
- measurable: yes, k=1: feed `{}` from two directories and diff the segments.
- sketch: keep `real` as `None` when the payload carried no cwd and pass it
  through, so `health_segments` omits the per-repo extras instead of inventing
  them - the same shape the `idx` stale-stamp fix needs.

## O8 - per-redraw cost, and the no-fork path that no host CLI can reach

- evidence: `hosts/opencode/tui/tezgah-tui.tsx:24` - `Bun.spawnSync({ cmd:
  ["python3", STATUS, ...args], ...})`, called from `update()` at `:58`, bound to
  five bus events at `:59-61` of which `message.part.updated` and
  `message.updated` are per-part and per-message-info updates, with only a 30 s
  safety timer (`:18`) and no coalescing; `hosts/dsh/statusline/lib/index.js:50` -
  `const [raw, legend] = await Promise.all([...])`, two `execFile` spawns per poll
  against `hosts/dsh/statusline/lib/client.js:16` `REFRESH_MS = 10000`;
  `statusline.py:43` spawns `/bin/sh`
  on the Orca passthrough and `:66-77` re-reads the transcript tail
  (`fh.seek(size - 2_000_000)`) on every invocation.
- evidence, second: `hooks/tezgah_context.py:1219-1221` - "for a redraw that must
  not fork git for a cosmetic line - omp re-renders on every turn_end and
  tool_result" - and the only caller of `idx_override` in the tree is
  `hosts/omp/hook.py:95`. `bin/tezgah-status` exposes no flag for it, so the three
  surfaces that re-render most cannot use the path built for them.
- **measured**: one `statusline.py` redraw = 138-142 ms wall clock (`python3 -c
  pass` 21 ms, `import tezgah_context` alone 51 ms, the transcript tail 7 ms,
  `health_segments` in-process 27 ms); child inventory over one redraw, taken with
  an audit hook: `git` x2, `/bin/sh` x1. One `tezgah-status <dir> <sid> --json` =
  79 ms, `--legend` = 52 ms - the second is constant per checkout and the dsh
  route fetches it on every poll.
- class: (c) for the TUI and the dsh route. The status line's Orca spawn is
  deliberate (it wraps Orca's own line, `statusline.py:41-49`) and is not counted
  as the defect.
- why it matters: `spawnSync` blocks the TUI's JS thread for the whole spawn, so a
  cosmetic bar can stall rendering during a streaming turn; the dsh route pays two
  interpreter startups every 10 s per visible tab. Not verified here: the
  invocation *count* per turn in opencode (no session was driven) - verified is
  the cost per invocation and that nothing coalesces.
- measurable: yes. For the TUI, instrument `update()` and count calls per streamed
  assistant turn over k runs; outcome variable: invocations per turn, pass = not
  more than one per turn boundary plus one per tool call. For the others, k=1 wall
  clock and child count as above.
- sketch: a timestamp guard in `tezgah-tui.tsx`'s `update()` (drop a call within
  ~250 ms of the last) plus a module-level resolved promise for `--legend` in
  `hosts/dsh/statusline/lib/index.js`; and, if the per-redraw cost is to come
  down, a `--idx=<glyph>` flag on `bin/tezgah-status` forwarding to the
  `idx_override` parameter the core already has.

## O9 - the dsh route answers for the server's own workspace, and the session id rides in argv and in a URL

- evidence: `hosts/dsh/statusline/lib/index.js:45` - `const session = sessionId
  === undefined ? undefined : ctx.sessions.get(sessionId);` and `:46` - `const dir
  = session?.header?.cwd ?? process.cwd();`. An id that resolves to nothing and an
  id that was never sent take the same branch as a real session, so the marks
  served are the dsh server's own cwd.
- evidence, second: `hosts/opencode/tui/tezgah-tui.tsx:24` puts the id on the
  child's command line and `hosts/dsh/statusline/lib/client.js:36` puts it in the
  request URL, while `bin/tezgah-status:32-33` documents `TEZGAH_SESSION` as the
  argv-free alternative.
- **measured**: a process started with the TUI's argv shape (`python3 ... <dir>
  --json <session-id>`) is printed in full by `ps -o command=` - workspace path
  and id included. The dsh route itself was not exercised (dsh was not running).
- class: (c) for both halves.
- why it matters: the cwd fallback shows a session the marks of a checkout it is
  not in - the same defect as O7, one host further out, on a Web UI where the
  reader has less context. The id exposure is low: the id is not a credential (it
  opens nothing; `used()` only reads a file in the user's cache), but on a shared
  machine `ps` is world-readable and the id plus the workspace path name another
  user's session.
- measurable: yes, k=1 each: request the route with an unknown `sessionId` and
  compare the segments against both the session's workspace and the server's; and
  print `ps` for a running child. Outcome variable: which workspace the segments
  describe, and whether the id is visible outside the process.
- sketch: distinguish "no id" and "unknown id" from "resolved" in
  `hosts/dsh/statusline/lib/index.js:45-48` (serve `info`-only segments, or
  nothing, instead of `process.cwd()`); pass the id as `TEZGAH_SESSION` in the
  TUI's `run()` instead of appending it to `cmd`.

## O10 - the tier's own network read is not a channel: a consult answer arrives unlabelled while `curl` to the same URL is labelled

- evidence: `hooks/tezgah_integrity.py:874` - `NETWORK_READ =
  re.compile(r"(?:^|[|;&(])\s*(?:curl|wget|gh\s+api)\b",` and `:895` - `if name in
  BASH_TOOLS and NETWORK_READ.search(mask(cmd)):` are the whole shell arm of
  `untrusted_source`; the channel table is `:876-877` and the label is `:900`;
  `hooks/tezgah_untrusted.py:81` - `def marks(tool, inp, session_id)` is where the
  row's `source` and the model-facing line come from.
- **measured**, in process: `untrusted_source("bash", {"command": "python3
  bin/consult 'q'"})` -> `None`; `bin/codegen 'add a debounce' --files
  hosts/opencode/tui/tezgah-tui.tsx` -> `None`; `python3 bin/consult --online
  'what changed today?'` -> `None`; `curl https://example.com/page.html` ->
  `'network'`. `marks("bash", <consult command>, <fresh session>)` -> `(None,
  None)`, so no row carries a `source` and `turn_channel` can never set the taint
  for the turn that read one.
- class: (c) - the adjacent misses are acknowledged at
  `hooks/tezgah_integrity.py:872-873` ("`sudo curl` and a program reached through
  a variable are missed rather than matched by accident"); a program reached by
  name, which is how tezgah's own tiers are run, is not.
- why it matters: the module's premise is that third-party text needs a provenance
  line (`:861-865`, "nothing else on tezgah's surfaces says so"). A panel answer is
  third-party text by construction, `--online` folds live web results into it
  (`bin/consult:11`), and it is the one such channel that arrives through a tool
  the contract tells the router to run before hard-to-reverse calls. A turn that
  consults and then writes gets no taint notice, so the sink-side reading this
  module was written for has nothing to read.
- measurable: yes, k=1: the four commands above. Outcome variable:
  `untrusted_source` per form. Pass = a `consult`/`codegen` invocation derives a
  channel (a new `UNTRUSTED_CHANNEL` entry, e.g. `"tier": "a paid model answer"`).
- sketch: one more alternative in the shell arm, reusing `shell_programs` the way
  `shell_kind` does (`hooks/tezgah_context.py:967-973`) - a program position
  matching `(?:bin/|config/tezgah/bin/)(?:consult|codegen)$` returns `"tier"`, and
  `UNTRUSTED_CHANNEL` gains the one line the label prints.

## Named and left alone (class (a) - documented deliberate choices)

- The stage-two design: one sequential referee call instead of a multi-round
  debate, with the cost argument written down (`bin/consult:281-285`).
- The referee defaulting to the first panellist that answered (`bin/consult:8`,
  `:288`) - a cost choice, disclosed in the usage text.
- The status line wrapping Orca's own line (`statusline.py:41-49`) and reading the
  Claude transcript for the marks Claude's recorder cannot supply
  (`statusline.py:57-63`).
- `tezgah_untrusted`'s shell net being deliberately loose
  (`hooks/tezgah_integrity.py:872-873`). O10 is the neighbouring case that
  sentence does not cover.

## Probes that came back clean

- A truncated reply with no closing fence is refused: `bin/codegen:189`, exit 2,
  measured - the fence regex is doing real work.
- The dead-referee path is disclosed rather than silent: `bin/consult:310`,
  measured (`referee: FAILED (timeout) -- no cross-examination, the panel answers
  stand unjudged`, exit 0 with the panel intact).
- The failure classes and the one retry variable are real: a 429 produced
  `failed: bad (http-429)` and `retry: ... a 401/403 means the key, not the
  question`.
- `--help` and a trailing flag spend no call (`bin/consult:199`, `:206-211`).
- The dsh route's `--observable=consult,research,cbm,orch` is the right set for its
  host (`hosts/dsh/statusline/lib/index.js:18`), and opencode is *not* in that
  group - its plugin classifies skill reads in process
  (`hosts/opencode/plugins/tezgah.js:1405-1412`), so its TUI passing no
  `--observable` is correct, not a defect.
- No repo file was modified by this slice, so no docs citation in `docs/`,
  `HANDBOOK.md` or `README.md` moved.

## Summary

| id | title | class | measurable |
|---|---|---|---|
| O1 | the referee's verdict is printed without checking the five headings it is asked for | (c) | yes - k=20, share of unstructured verdicts printed as valid |
| O2 | no global deadline: the run is up to (N+1) x (timeout+15) while the flag reads per-model | (c) | yes - k runs, wall clock / documented timeout |
| O3 | codegen's parse guard is keyed to the `.py` suffix, so `.tsx`/`.js`/`bin/*` drafts are unvouched | (c) | yes - k=1 per path kind, exit code |
| O4 | the tier counters match a substring, so reading about the tier counts as using it | (c) | yes - k=1, substring rows vs program-position rows |
| O5 | the tier's failure leaves no trace on a host that reports no outcome | (b) | yes - k=2, `codegen_failed` per host |
| O6 | a surface with no session id renders "not used yet" as a fact | (b) | yes - k=1 per surface, mark state with and without an id |
| O7 | the status line reports the process cwd when the payload carries none | (c) | yes - k=1, segments from two directories |
| O8 | per-redraw spawn and transcript cost; the no-fork path has no CLI to reach it | (c) | yes - invocations per turn; ms and child count per redraw |
| O9 | the dsh route serves the server's cwd for an unknown id; the id rides in argv and in a URL | (c) | yes - k=1, which workspace the segments describe |
| O10 | a consult/codegen answer is not an untrusted channel while `curl` to the same URL is | (c) | yes - k=1, `untrusted_source` per command form |
