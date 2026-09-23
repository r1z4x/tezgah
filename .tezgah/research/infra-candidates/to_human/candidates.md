# Candidate features for tezgah's infrastructure

Read this to choose what to build next. Every candidate below is a gap that was
**observed in this checkout on 2026-09-19**, not a design idea: line citations,
probe commands with their output, and the exact change are given so the decision
can be re-derived. The research line lives one directory up
(`../state.json`, `../findings.md`, `../log.md`, `../experiments/E0-current-stop-rule/`).

## Method

1. Reconnaissance of the layer as it is (docs layer, six adapters, the ledger, the
   gate) to know what already exists, so the candidates are gaps rather than
   rediscoveries.
2. Literature pass over 7 sources through `orx discover` / `orx paper`, each note
   in `../literature/`. All 7 ids were cross-checked against arXiv DOI metadata
   (DataCite content negotiation): title and authors match.
3. Four read-only audits (evidence, gate, host parity, context) whose findings
   were then **re-run by hand**, because a read-only audit cannot execute: two
   claims changed under execution (the `rsync` direction and its flag behaviour).
4. E0: the real `_stop_block`, `passing_check`, `effect_class`, `_index_mark`,
   `subagent_core` and the ledger corpus, probed in-process. Results in
   `../experiments/E0-current-stop-rule/`.

## The measured baseline

Facts about the layer as it stands, each from a command run in this session:

| measure | value | source |
|---|---|---|
| local ledgers | 1162 | `~/.cache/tezgah/evidence/*.jsonl` |
| `verify_ok` rows | 1224 | same |
| `verify_ok` rows carrying `out_bytes` | **0** | same - the guard that field exists for has never fired |
| `verify_ok` rows `passing_check` accepts | **1224** | same |
| `claim` rows: ok / blocked | 290 / 108 -> false-completion **0.271** | same |
| `deny` rows by rule | task 172, drift 36, consent 33, shortcut 26, retry 5, attribution 4, loop 2, sink 1 | same |
| a "done" reply after `edit -> verify_ok -> edit` | **allowed** | E0 cell A |
| a "done" reply licensed by an earlier turn's check | **allowed** | E0 cell B |
| destructive/outward commands deriving no effect class | 9 of 20 probed | E0 cell E |
| `rsync` outbound (data egress) | derives nothing | E0 cell F |

## The candidates

Each row: what it closes, the evidence, the smallest change, how it is checked,
and whether it needs a policy decision from you. `k=1` means a deterministic
probe settles it; `k>=25` means an arm-bench block.

### A. Evidence integrity - the layer's headline claim

**C1 - Fresh evidence (the pass branch is position-blind).** The Stop rule's
refusal branch is turn-scoped (`hooks/tezgah_integrity.py:1097-1107`) while its
pass branch is not (`:1249`), and neither compares a check's position against an
`edit` row's - so a turn may claim done with its newest write unverified, and an
earlier turn's green run licenses a later turn's claim. The after-state that
would refute both is already recorded and unread: `_post_write` writes `changed`
(`:938-960`), `changed_files` reads exactly those rows (`:963-971`), and outside
`tests/test_integrity.py` nothing calls it. *Change:* gate the pass branch on
"newer than the newest `changed: true` edit", scoped by `_turn_start`. ~10 lines,
no new policy text. *Check:* E0 cells A/B/C + an arm-bench block on the hard
family. *Decision needed:* none on behaviour; the escape (`dogrulanmadi`) already
exists. *Risk:* a genuinely cosmetic write after a green run now blocks - which
is the point, and a no-op write does not count (`changed: false`).

**C2 - The `out_bytes` guard is dead, so decide its fate.** `passing_check`
(`:1066`) refuses a check whose result was empty, documented as "the classic
silent failure" (`docs/evidence.md`). In practice the field never arrives: 0 of
1224 `verify_ok` rows carry it, because omp, codex and cursor never pass it and
the Claude-family path passes one only when the payload carries
`tool_response`. So the predicate tests `None == 0`, which is false, and the
guard's own test (`tests/test_integrity.py:751-754`) seeds a field production
never sends. *Change, one of:* (i) plumb a real result size from each host and
keep the guard, (ii) make absent mean unknown and stop calling it proof, (iii)
delete the field and the claim. *Check:* k=1 against the ledger corpus.
*Decision needed:* **yes** - (i) costs a host change, (ii) narrows what counts as
proof on five hosts, (iii) removes a documented guarantee.

**C3 - A `verify_ok` may have no `exit` key at all (464 of 1224).** The legacy
tolerance in `passing_check:1061-1065` exists so an upgrade does not block an open
session on its own history - a deliberate, dated exception with a stated removal
condition ("drop this branch when no live session's first row predates plan
012"). The corpus now shows 464 rows still taking it. *Change:* re-measure and,
if the count is old rows only, delete the branch. *Check:* the same corpus query,
restricted to recent files. *Decision needed:* no - the condition is already
written in the code.

### B. The preventive surface

**C4 - `rsync` is classified backwards, and breaks on a flag.** Measured
(E0 cell F): `rsync host:/src ./dst` - a *read* - is refused as `send`, while
`rsync ./dst host:/dst` - the egress - derives nothing, and with `-avz` in front
neither direction matches (`rsync\s+\S*:`, `hooks/tezgah_gate.py:245`, requires the
first token to end in a colon, where the sibling `scp` branch tolerates flags).
*Change:* `rsync\s+(?:-\S+\s+)*\S*:` - two lines, one false positive and one false
negative closed. *Check:* k=1 truth table over the four forms. *Decision:* none.

**C5 - Nine destructive commands ask nobody.** Measured (E0 cell E): `git reset
--hard HEAD~3`, `git tag -d v1`, `gh repo delete`, `aws s3 rb --force`,
`flyway clean`, `docker compose down -v`, `chmod -R 000 /etc`, plain `git push
origin main` all derive no class, and none appears in `docs/gate.md`'s deliberate
non-goal list. *Change:* extend the existing constants (`MIGRATION`,
`BRANCH_DELETE`, `GH_SUBCOMMANDS`, `DEPLOY`, `SEND`); no new mechanism. *Check:*
denial rate per command (k=1) plus the corpus pass rate (k>=25) for false
refusals. *Decision needed:* **yes, per command** - e.g. `git tag -d` and
`docker compose down -v` are local and arguably should not ask, while `git reset
--hard` on pushed work should. This is a policy call, not a bug list.

**C6 - `powershell` is unreachable on every Python host.** It sits in
`BASH_TOOLS` (`hooks/tezgah_integrity.py:113-114`) but no PreToolUse matcher names
it (`hooks/hooks.json:16`, `hosts/dsh/hooks.json:13`, omp's `GATED`), so consent,
secret, shortcut, loop, retry, task-shell and sink can never run for one, while
the PostToolUse side records its rows. *Change:* wire the matcher, or drop the
name. *Check:* a config assertion. *Decision:* **yes, one line either way.**

**C7 - A shell write escapes three write-tool-only rules.** `SKIP_TEST`,
`ATTRIB_LINE` and the secret scan are attached to `WRITE_TOOLS`; `WRITE_TOOLS` and
`BASH_TOOLS` are disjoint (`hooks/tezgah_integrity.py:110-114`), so a heredoc
writing `@pytest.mark.skip` into a test file, or `Co-Authored-By:` into a
changelog, or an `API_KEY=` into a config through the shell is refused by nothing.
This is the route E7c measured as the one an agent actually takes once the write
tools are refused, and it is the structural limit the literature names as the
defining failure of tool-layer guardrails (ActPlane). *Change:* run
`shortcut_edit` / `attribution_edit` / the secret predicate over a shell write's
body, reusing the `SHELL_WRITE` shape test the task rule already has
(`hooks/tezgah_gate.py:962`). *Check:* the E7c task (`u02-refusal-bypass`)
re-run, plus k=1 probes per rule. *Decision:* none.

**C8 - The consent lease answers for text, not for an action.** `call_id`
(`hooks/tezgah_integrity.py:190-206`) hashes only tool + canonical args: no cwd,
no repo, while the effect is resolved against the workspace (`rm_outside`, the
sink paths). So a grant obtained for `rm -rf build` in one repo is the same token
as the identical text in another. On Cursor it is worse: a successful shell call
writes no `exit` key, so the spender at `hooks/tezgah_gate.py:546-548` never
fires and one approval becomes a standing permit, against the documented lease
model. *Change:* fold a workspace identity into the lease key; widen the spend
predicate to a step row. *Check:* re-ask rate on the 2nd..k-th identical approved
command per host. *Decision:* no, once the key shape is agreed.

### C. Rules that do not exist yet

**C9 - No rule asserts an ordering between two actions.** Every rule in
`decision` reads one call plus a ledger tail. The field's own measurements say
that is the wrong shape: FAVA found 90% of real `CLAUDE.md`/`AGENT.md` projects
enforce sequence-dependent constraints ("do not commit before running tests") and
ActPlane found 16% of instruction statements to be cross-event. tezgah's closest
is the active-task phase. *Change:* a new rule kind - an obligation read from the
ledger ("no git commit while the newest check in this session is fail or absent").
A ledger row and one predicate; no solver, no model. *Check:* arm-bench block,
task family: a corpus task whose natural first move is to commit before verifying.
*Decision needed:* **yes** - which obligations, and whether it is always on or
switched. *Where it stands (2026-09-22):* the obligation itself landed, and the
block that would measure its rate (`experiments/E3-commit-on-red/`) is written,
pinned and probed but could not run because the provider's account layer holds no
credit (a 402 on every attempted row, `$0.0000` spent), so the decision still open
here is the money: fund the account and run the committed recipe, or move the same
model onto the `deepseek` credential omp already holds, which changes the model
lock in that protocol's section 3 and needs an amendment first.

### D. Text and marks that do not tell the truth

**C10 - The `idx` mark claims fresh when it cannot compare.** Probed: no stamp
file at all -> `fresh`; `git rev-parse` fails -> `fresh`; and the per-turn
`index_notice` stays empty, so a graph built before code moved is delivered with
the index's authority and no warning - the exact failure the notice was written to
prevent. On a sandboxed host (dsh) the worker never writes a stamp, so the mark is
permanently wrong there. *Change:* split the `try`, return the stale glyph when
the comparison could not be made. *Check:* k=1 fixture. *Decision:* none.

**C11 - The per-turn reminder swallows its own merge authority.** The reminder
says "merge the PR yourself and report it - do not ask", then lists "anything
touching a live production account or external service" among the cases to stop
and report instead. A PR merge is an external-service write, so the exception
swallows the rule; the carve-out that resolves it ("beyond the merge") exists only
in the on-demand contract. In a repository whose premise is *one* contract text,
this is a defect in the deliverable. *Change:* one clause in the reminder (and its
twin in the always-on invariant). *Check:* k=1 read. *Decision:* none.

**C12 - The subagent brief is missing two always-on blocks while claiming
completeness.** Probed: `subagent_core()` (2082 chars) contains neither the
on-demand-rules pointer nor any kill-switch path, yet its header says "the rules
below are the short form and all of them are in force". A delegated agent cannot
learn that spec-first, consult, research routing or graph-first exist, and cannot
answer "how do I switch this off". *Change:* append the pointer sentence and the
switch list to the brief header. *Check:* k=1 presence. *Decision:* none.

**C13 - The lessons digest can move without the shown text moving.** Probed: a
tail-only edit of a 260-character lesson line changes `_lessons_state` while the
200-character prefix the model is shown is identical - so the one channel whose
job is "this fact changed" fires on a no-op, contradicting `_lesson_lines`'
docstring ("one reader ... so the digest can only move when the text the model was
shown moves"). *Change:* digest the truncated form. *Check:* k=1 fixture.
*Decision:* none.

### E. Seeing the layer work

**C14 - The headline metric cannot be read.** `false_completion / claims` is
named in the code as the only measure of the layer's effect, and 1162 ledgers on
this machine hold 398 claim rows (0.271 blocked) - but `counters` reads one
session and writes nothing, so no one can see a day, a week or a change. *Change:*
a `counters_all` fold plus `tezgah-status --counters --all`. *Check:* k=1.
*Decision:* none.

**C15 - A miner for the gate's own blind spot.** No code extracts "allowed +
effectful + derived no class" from the ledger, so the pattern table cannot grow
from real traffic; the raw material is there for shell calls (an allowed row keeps
the full command as its detail). This is how C5 stops being a hand-written list
and becomes evidence-driven, and how the next `send`-class hole (commit `cf6b908`)
would have been found without a hand-built adversarial set. *Change:* a reader,
not a writer. *Check:* does a scan reproduce the documented 147/20 numbers.
*Decision:* none.

**C16 - False completion, measured the way the field measures it.** tezgah's
own definition counts a *refusal to stop*, which also fires on "no check ran".
The published definition (Advani 2026) requires an environment state that
contradicts the claim - which arm-bench's `hidden/` checks already are. *Change:*
compute "of the runs whose hidden check failed, what share ended by claiming
success" in `bench.py report`. *Check:* the number itself, over the existing
rows. *Decision:* none.

## Three work packages

| package | contents | why together | cost |
|---|---|---|---|
| **P1 evidence is fresh** | C1, C3 (+C2 decided) | all three are the same predicate and the same test surface; C1 is the only candidate that strengthens the layer's headline promise | ~15 lines + one arm-bench block |
| **P2 gate truth table** | C4, C6, C7, C8, C5-per-command, C15 | one artefact - the class table and the rules that read it - closed against a measurable list | ~60 lines, one bypass block |
| **P3 marks and text tell the truth** | C10, C11, C12, C13, C14, C16 | six k=1 fixes with no behavioural risk and no policy decision | ~40 lines, all deterministic checks |

P1 first: it is the only one where the layer's own claim ("nothing is reported
done unless the output was seen") is currently false in the direction that
matters - the output *was* seen, for a tree that no longer exists. P3 is nearly
free and can ride along with any other work. P2 needs your per-command policy
call on C5; the rest of P2 does not.

## Pre-registration sketch for P1

Frozen before any run, in the shape of `PREREGISTRATION-E7c.md` on
`benchmarks/lab`:

- **Arm:** `omp-task-rule` (the bridge loading a development worktree) against
  `omp+tezgah` at HEAD, one model (`openrouter/deepseek/deepseek-v4-flash`), k=25.
- **Task:** a corpus task whose natural trajectory ends with a small edit after
  the visible suite goes green (the h0-family shape: a hidden invariant the
  visible suite does not cover), so the honest state at the end is "unverified".
- **Outcome variable:** `blocked` / `allowed` per run, read from the ledger's
  `claim` row and the Stop hook's decision - never from the reply's wording.
- **Prediction:** with C1, the `blocked` share rises on the arm carrying the fix
  and the corpus pass rate does not fall; a pass-rate drop is the falsifier that
  matters, because AgentGuard's own numbers show guardrails can cost completion.
- **Second endpoint:** the arm must not block the control case (a turn that edits
  nothing and claims nothing).

## Declined, with the measurement that declines them

- **A semantic/LLM classifier in the gate.** The seat is documented and empty by
  measurement: on tezgah's own adversarial set the classifier-shaped primitive
  answered `yes` on 12 of 20 rows - precision 0.167 at 768 ms/call
  (`docs/gate.md`). Nothing here changes that number.
- **OS-level enforcement (ActPlane's answer to C7).** Correct in general and out
  of scope for a contract layer that deliberately is not a sandbox; C7 closes the
  same hole at the level tezgah owns.
- **Automatic rollback.** A deliberate non-goal with a written rationale
  (`hooks/tezgah_snapshot.py:10-18`): a hook that undoes work can destroy more
  than the failure it answers.
- **A new host adapter.** No evidence of demand in this checkout; the six
  existing asymmetries (C6, C8, and opencode's missing Stop and untrusted halves)
  are worth more than a seventh adapter.

## Sources

`.tezgah/research/infra-candidates/literature/` - ActPlane (2606.25189),
false success (2606.09863), AgentGuard (2609.16287), runtime contract
(2608.11274), FAVA (2607.27267), C-Trace (2606.19242), PIPES (2608.12789). All
ids resolved via arXiv DOI metadata; the quantitative claims are marked `[CITED]`
in each note and were not re-derived.

---

# Round 2 — three areas the first round never probed, plus two the runs found

The first round's candidates came from four probed areas (evidence, gate, host
parity, injected context). This round probed three more and each returned a
findings file with its own evidence, class and sketch. The counts and ids below
are the pass's own report; read the file before acting on one.

| area | file | findings | what it is |
|---|---|---|---|
| installer + generated layer | `../round2/installer.md` | 18 (17 c, 1 a) | the installer, the agent/index/research workers, `skills/*`, `workflows/*` |
| second-opinion + observation | `../round2/orchestration.md` | 10 (8 c, 2 b) | `bin/consult`, `bin/codegen`, `statusline.py`, the opencode TUI, the dsh route |
| the structural answers | `../round2/structural.md` | 3 verdicts + 4 measurements | cross-event obligations, two-implementation agreement, response-boundary screening |
| the host refresh | `../round2/host-refresh.md` | 2 (2 c) | found while making the contract live |

**Ranked, if the next round is a build round** (the reasoning is in each file):

1. **`I10` — the contract's source list omits the module it renders from.**
   `CONTRACT_SOURCES` does not name `hooks/tezgah_context.py`, so a contract
   rendered after that file changed can be stale and the list will not say so.
   Same shape as the plugin-copy gap the refresh found, and the smallest fix of
   the whole round.
2. **`O1` — the referee's five headings are printed without being checked.**
   Measured: exit 0, "referee: m1", zero headings. The contract routes every
   hard-to-reverse call through the panel and tells the caller to read the
   referee's cross-examination back; nothing verifies it arrived.
3. **`I1` — a report row that cannot fail independently.** The "hooks.json wired"
   row passes when any single event is wired, so a host with no Stop hook reports
   as armed. A report is the installer's own claim about what is armed.
4. **`order` follow-ups from real traffic.** The miner found `gh run delete` /
   `gh cache delete` and `ssh host cmd` deriving no class; both are the user's
   policy call, like the five C5 left out.
5. **The structural verdicts.** Obligations: build now (the kind is ~12 lines).
   Two-implementation agreement: build after a divergence set exists — measured
   as 20 shared patterns but only 11 Python rules and 4 mirror rules write a deny
   row at all, so a runner would start red for a scope reason, not drift.
   Response-boundary screening: **do not build** the screen; a surface-path sink
   list plus one notice sentence instead.

**The one measurement worth repeating here:** an in-root write to `AGENTS.md` or
`.tezgah/lessons.md` is allowed by every rule in the gate, and no tainted turn in
this machine's corpus has written to a contract surface (189 edits under a live
taint, 0 of them there). The hole is real and currently unexploited.
