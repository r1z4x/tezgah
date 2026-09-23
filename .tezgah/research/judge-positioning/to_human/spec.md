# Spec: position the judgement seam (checkable)

**Status on 2026-09-22 (HEAD `ddf72b4`), added when the line was closed.** J1-J6
are built: `judge-off` and the per-caller switches are in the kill-switch
paragraph, the contract table and its two mirrors (J1, J5); `choice()` and
`noul()` exist and all three callers read through them (J2); the `judge` mark
renders with its `observable` carve-out (J3); the ledger carries a `judge` key
counted on the row kind, one row per judgement from each caller (J4); and
`docs/judge.md` is written and indexed (J6). J7 is **refuted**, not built: the
pre-registered round in `experiments/E2-citation-adjudication` returned 0.56
agreement against a 0.9 floor and precision 0.29, which `C5-R` records. The
passages below are the specification as written before the build, and
`to_human/report.md` says what the tree does today.

Standard this spec is held to: every item names the observable it changes, the
command whose output proves it, and the test that fails without it. Line numbers
are the working tree's at 2026-09-20 02:40 (HEAD `4bf25e8`, eight files carrying
an uncommitted `skill-suggest-*` change). Items are ordered cheapest-high-value
first. `README.md:86-115`-style claims are not accepted as proof anywhere: each
acceptance criterion is a command and its expected output.

Standard for the *rules-text* items below: in this layer the injected text is the
only observable a session has, which is why the existing suite already asserts on
it (`tests/test_context.py:1290`, `tests/test_setup.py:804`,
`tests/test_skills.py:106-109`). Asserting that `judge-off` reaches the session's
text is therefore a behaviour assertion, not a source-text one.

---

## J1. Name the off button where the session can see it

**Change.** Add `judge-off` to the `**Kill switches:**` paragraph
(`hooks/tezgah_policy.py:743-749`) as one clause in the existing list - no new
paragraph. Add a row to the kill-switch table (`docs/contract.md:133-146`). Mirror
the paragraph into `skills/tezgah-contract/SKILL.md` and regenerate
`output-styles/tezgah.md` from a fresh interpreter (a warm one serves a stale
`CORE`).

**Acceptance.**
1. `bin/tezgah-context session_start .` prints a line containing `judge-off`.
2. `bin/tezgah-docs --citations` reports 0 flagged rows for the three touched
   files (`bin/tezgah-docs --citations` exits 1 when any row is flagged).
3. The paragraph still names every switch `core_split()` honours and every
   per-repo mark, i.e. the switch pin is unchanged in its other rows.

**Test that fails without it.** `OutputStyleMirrorsCore.test_body_is_the_always_on_core`
(`tests/test_context.py:1290`) and `ContractParity` (`tests/test_setup.py:804`)
both compare `CORE` against its two copies, so changing `CORE` alone fails them.
Add one assertion to the switch pin (`tests/test_skills.py:106-109`) that the
paragraph names `judge-off`: without it the clause can be reverted by a later edit
and nothing notices, which is exactly how the switch reached this state.

**Cost.** ~40 bytes per session, no new paragraph.

---

## J2. One answer reader, so the fourth caller cannot re-invent it

**Change.** Add two accessors to the seam: `choice(result, id)` -> the option
taken or `None`, and `noul(result, id)` -> the probability or `None`. Route all
three callers through them: `bin/tezgah-triage:147-157` (`prob`),
`bin/tezgah-docs:195-197`, `hooks/tezgah_skill_pick.py:157-161`.

**Acceptance.** No caller reads `.get("choice")` or `.get("noul")` directly
(`grep -n 'get("choice")\|get("noul")' bin/tezgah-triage bin/tezgah-docs hooks/tezgah_skill_pick.py`
returns only the two accessors' own definitions), and the three suites
(`tests/test_triage.py`, `tests/test_judge.py`, `tests/test_skill_pick.py`) are
green with no fixture change.

**Test that fails without it.** None, and that is deliberate: a pure refactor
changes no observable behaviour, so per the contract it earns no new test - the
three existing suites are the acceptance, and they fail if the reader stops
matching the shipped behaviour (the `none` option, the missing-answer case, the
`float` coercion).

---

## J3. A `judge` mark in group 1, decided from the switch and a real used-kind

**Change.** Add `judge` to `_GROUP` group 1 (`hooks/tezgah_context.py:1186-1187`),
a flag row to the table (`:1257-1266`) with `meas="judge"`, `judge` to
`TOOL_USE_MEASURES` (`:1220`), and `judge` to `shell_kind` (`:1000-1006`) for a
shell command that really ran `tezgah-triage` or `tezgah-docs`. States: `on` when
a judgement really ran this session, `ready` when armed and unused, `off` under
`judge-off` or a missing credential, `info` where `observable` excludes the mark.

**Acceptance.**
`tezgah-status <repo> <session> --json` shows `{"key":"judge","state":"ready"}`
with a credential and no switch; after one real judgement, `on`; with
`~/.config/tezgah/judge-off` present, `off`; with
`--observable=consult,research,cbm,orch`, `info` (dim, no glyph) and the plain
line unchanged from the pinned cursor regression.

**Test that fails without it.** `tests/test_statusline.py` pins the plain line, so
the mark cannot be added silently - the pin has to move in the same change, which
is the point. Add one case for the precedence `off` beats `info` on `judge`: a
plausible bug (adding the flag row without the `observable` carve-out) makes a
surface that cannot write the used-kinds store claim `ready` forever, which
`docs/status-line.md` calls out as a bug in the layer rather than a cosmetic one.

---

## J4. Count the spend, on the ledger, from the callers

**Change.** Each caller records one `judge` ledger row after a successful
judgement, when a session id is known (`TEZGAH_SESSION` for the two bin tools, the
host's session id for the prompt-path hook - the same two routes `bin/tezgah-status`
already uses), with `detail = "<caller> <model> in=<n> out=<n> ms=<n>"`.
`counters()` (`hooks/tezgah_integrity.py:692-699`) grows a `judge` key counted on
the row's **kind**, not on a `detail` substring, and `bin/tezgah-status:82` prints
it. The row is never a step and never a check: `STEP_KINDS`
(`hooks/tezgah_integrity.py:626-628`) is untouched.

**Acceptance.** After one judgement from each of the three callers in one session,
`tezgah-status --counters <cwd> <session>` prints a non-zero `judge` count of 3 and
`--counters --all` sums the corpus consistently (both fold through `_counts`, so
they cannot disagree); `tezgah-status --counters` on a session with no judgement
prints `judge: 0`; the prompt-path caller is counted too, which is the half no
shell row can carry.

**Test that fails without it.** A new case in `tests/test_integrity.py` for the
counter and its fold. A plausible bug it catches: counting by `detail` substring -
the pattern `consult`/`codegen` use (`hooks/tezgah_integrity.py:694-699`) - which
would count a command that merely mentions the tool.

**Not in this item:** putting the session's spend on the session-start live-state
line. It is the natural next step and it is deliberately separate: it is a new
surface with its own trim order.

---

## J5. A switch per caller, with `judge-off` as the master

**Change.** `hooks/tezgah_judge.py:86-88` keeps `judge-off` as the master. Each
caller names its own: `bin/tezgah-triage` -> `triage-off`, `bin/tezgah-docs` ->
`docs-judge-off`, `hooks/tezgah_skill_pick.py` -> its existing
`skill-suggest-*` marker (in-flight). All four names appear in J1's paragraph.

**Acceptance.** With only `triage-off` armed, `tezgah-triage --select FILE --task T`
exits 1 with the reason and makes **no request** (the fake endpoint sees zero
calls), while `bin/tezgah-docs <unmatched query>` still answers from its fallback;
with only `docs-judge-off`, the reverse; with `judge-off`, neither makes a
request and `tezgah_judge.available()` is `False`.

**Test that fails without it.** Extend the existing kill-switch cases
(`tests/test_triage.py` `test_the_kill_switch_exits_1`, plus `tests/test_judge.py`
`Availability` and `DocsFallback`): each new assertion pairs the caller that is
off with the caller that must still work. That is exactly the bug a per-caller
switch introduces - a caller that honours the global switch and forgets its own,
or one whose switch silently disables the other.

---

## J6. A docs page and an index entry for the seam

**Change.** Add `docs/judge.md` (the page ceiling is 200 lines, `docs/README.md:58`),
an entry to `docs/index.json` carrying its `title`, `answers` and `sources`, and a
source-of-truth line so `tezgah-docs judge` routes from the keyword index instead
of paying for a Choice.

**Acceptance.** `bin/tezgah-docs judge` prints the new page and **no call is made**
(the fake endpoint sees zero requests for that query); `bin/tezgah-docs --citations`
flags nothing in the new page; `bin/tezgah-docs --citations`' "not judgeable" count
does not rise because of the new page's citations.

**Test that fails without it.** `tests/test_docs_router.py` asserts, per indexed
page, that the Choice's criteria carry the page's `title` and every one of its
`answers` (`:57-65`), so a page added to the index without that material fails the
subTest; `tests/test_docs.py` checks that every citation in the new page resolves
to a file and a line inside it.

---

## J7. The citation audit's unjudgeable half - the new caller, gated on its own round

**Change.** A new mode (its own switch, e.g. `citations-judge-off`) that takes the
citations `bin/tezgah-docs --citations` cannot judge - **734** on this tree, from
the run recorded in `findings.md` - and sends ONE batched Noul per citation:
state = the sentence plus the cited range's lines; question = "does this range
still show the thing the sentence names?"; prints only the rows the judgement
calls drifted, with the call's own cost.

**Acceptance.**
1. The deterministic half is byte-identical with the switch on and off.
2. **Seeded drift:** shift one citation in one docs page by N lines, run the mode,
   and it prints exactly that citation and no other. Revert: it prints none.
3. On the current tree it prints a bounded row count and names its cost.
4. Precision on a hand-labelled sample is at or above the number fixed in the
   experiment's protocol **before** the run - the number is not written here,
   because a threshold chosen after seeing the result is not a criterion.

**Test that fails without it.** (2) is the regression: it fails pre-fix (nothing
printable exists) and passes post-fix. It also catches the failure that matters -
a judgement that flags everything the sentences say differently rather than the
citations that drifted.

**Why it is last despite ranking first on evidence.** It needs its own protocol and
labelled sample before it can be built honestly, which is this repo's own rule
(`.tezgah/research/*/experiments/*/protocol.md`). J1-J6 are decidable today.

---

## What I would not do, and why

1. **No always-on rule paragraph for the judge.** It is an on-demand capability;
   `CONDITIONAL_KEYS` exists so a session that never asks does not carry the text.
   J1 buys discovery for ~40 bytes; a paragraph would cost the always-on block and
   would have to be re-earned by every measurement.
2. **Nothing in the gate, the Stop rule, the shortcut parser, the consent path or
   the PreToolUse hot path.** Refusal reproducibility is an invariant with tests
   behind it, and `docs/gate.md:256-260` already refused a model call on the Stop
   path for the same reason. A probabilistic answer there is a policy bug.
3. **No seam-level cache, and no caller cache beyond the prompt-keyed one that
   exists** (`hooks/tezgah_skill_pick.py:175-198`). The measured price of a
   judgement is $0.000155 (98 options) to $0.000294 (the shipped unit selection on
   a 356-line screen, 7,008 input tokens; the per-line shape cost $0.000569); a
   cache is not worth its state file, and a naive one would make a judgement
   non-reproducible between two runs of the same command.
4. **No SDK, no `requests`, no async, no local model.** Those trade the seam's
   three load-bearing properties - total (`ask` never raises, because a hook
   imports it), stdlib-only (it is the first and only network path in `hooks/`),
   dependency-free (no client library, retry ceiling of one) - for savings this
   round did not measure.
5. **No `criteria` on the triage's `--select` noul.** The task sits in the shared
   state on purpose so the per-unit question does not repeat it 67 times
   (`bin/tezgah-triage:199-213`); filling it in would raise the token bill for no
   accuracy this round measured.
6. **No rename of the module and no new tool.** `hooks/tezgah_judge.py` is cited
   across `docs/operations.md` and the tools' own docstrings, and the user-facing
   surface is already the two tool names.
7. **The judgement never counts as a check or a step.** `STEP_KINDS`
   (`hooks/tezgah_integrity.py:626-628`) stays as it is: a model answer must never
   be able to license a "done" claim, and J4 adds a cost row, not evidence.
