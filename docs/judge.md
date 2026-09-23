# Judge: the judgement seam, its three callers and its switches

The judgement seam is `hooks/tezgah_judge.py`: one module that asks TypeSafe
(Jev) for a batched structured judgement over a state tezgah would otherwise pay
an agent to read. Read this page when you are about to call one of its three
callers, when you need to say what leaves the machine, or when you have to tell a
user how to switch it off. It is an on-demand capability, not a rule: no paragraph
of it is injected into a session, and a session that never asks pays one clause in
the kill-switch paragraph and nothing else (`CORE`,
`hooks/tezgah_policy.py:768-777`).

## What it is

One seam, three callers, one credential, one egress boundary, one price, one
redirect guard. The module is stdlib only and total - a failure is a `None`, never
an exception, because a hook imports it and a hook that raises takes a session
down (`_request`, `hooks/tezgah_judge.py:274-293`). One endpoint and one key path
are module constants (`URL`, `hooks/tezgah_judge.py:51-51`; `KEY_FILE`,
`hooks/tezgah_judge.py:52-52`), one opener is shared by every call (`OPENER`,
`hooks/tezgah_judge.py:95-97`), and it refuses a redirect that leaves the
endpoint's host, so a `Location` cannot carry the bearer
(`_NoCrossHostRedirect`, `hooks/tezgah_judge.py:77-94`). A transient failure - a
timeout, a connection error, a 5xx - gets exactly one more attempt; a 4xx and a
malformed reply never do (`_transient`, `hooks/tezgah_judge.py:262`).
`TEZGAH_TYPESAFE_URL` repoints the endpoint and `TEZGAH_OPENROUTER_URL` the
fallback's; both are test seams, not fallbacks.

Every caller reads an answer through the same two accessors rather than reaching
into the raw reply, so a Choice and a Noul are read one way for all three
(`choice`, `hooks/tezgah_judge.py:232-241`; `noul`,
`hooks/tezgah_judge.py:242-260`). Both are total: a missing or wrongly-typed
answer is a `None`, never an exception.

A judgement is an aid, never the claim. It ranks units or names a page; the agent
still reads the selected refs and owns the finding, and the ledger's step kinds
are untouched, so a model answer can never license a "done" (`STEP_KINDS`,
`hooks/tezgah_integrity.py:855-857`).

The state leaves the machine. A judgement sends the state and the questions to
`api.typesafe.ai` - for the triage that is the screen's own text, so a screen
carrying personal data is read by a third party, and for the docs fallback it is
the reader's query. When no TypeSafe key resolves, the same state goes to
`openrouter.ai` instead (`OPENROUTER_URL`, `hooks/tezgah_judge.py:57`), which is
the price of a machine that has no Jev credential still having a judge at all:
the destination changes, not what is sent. Nothing else goes: no session id, no
workspace path, no environment, and the state is not redacted because sending it
is the point. That is why both shell callers are explicit and the third is
opt-in, and why the switches below are the off buttons.

## The three callers

| Caller | What it asks, and what it is for | On failure |
|---|---|---|
| `bin/tezgah-triage` | the analyze-app snapshot triage. `--select FILE --task T` asks one question per repeating unit of the screen in one request and prints the line ids under the selected units with their refs (`select_request`, `bin/tezgah-triage:230-248`; the units are the tree's own repeating pieces, `units`, `bin/tezgah-triage:204-229`). `--states` asks one judgement per state over a component's subtree (`states`, `bin/tezgah-triage:308-431`) | exit 1 with one reason (`no_judgement`, `bin/tezgah-triage:107-113`), and the loop reads the tree directly |
| `bin/tezgah-docs` | the docs page fallback: only when the keyword index placed nothing, one Choice over the pages with `none` offered (`judge_pick`, `bin/tezgah-docs:195-228`; the question wording is `ASK`, `bin/tezgah-docs:162-169`) | returns `None`; the command prints what it always printed and exits 1 |
| `hooks/tezgah_skill_pick.py` | the prompt-path skill hint: a Choice over the roster skills plus one Noul (`judge`, `hooks/tezgah_skill_pick.py:144-176`, with the criteria cut from each skill's own clauses, `clause`, `hooks/tezgah_skill_pick.py:81-109`), behind a threshold (`GATE`, `hooks/tezgah_skill_pick.py:46-48`) and an 8 s timeout (`ASK_TIMEOUT`, `hooks/tezgah_skill_pick.py:49-54`) | returns `""`; the turn loses the hint |

The third caller is the one no shell row can see: it runs on the prompt path,
caches one answer per `(session, prompt)` (`_remember`,
`hooks/tezgah_skill_pick.py:191-206`; `suggest`,
`hooks/tezgah_skill_pick.py:207-222`), and asks at all only when its own marker is
armed. The other two are bin tools a session runs by name.

## The credential's channels

The credential resolves from `TYPESAFE_API_KEY`, else from the key file the module
names (`KEY_FILE`, `hooks/tezgah_judge.py:52`). The environment variable is the
channel an interactive shell has; the file is the channel that matters, because a
hook or a bin tool a host starts runs in a non-interactive shell where a
`~/.zshenv` export never ran, so the variable is absent exactly where a judgement
runs. That is why the file is read rather than the environment trusted. The
install report's health row reads its own pair of channels ([hosts](hosts.md)),
which is a different question from the one the seam asks.

When neither channel resolves, the same two channels are read again for the
fallback provider - `OPENROUTER_API_KEY`, then `~/.config/openrouter/key`
(`openrouter_key()`, `hooks/tezgah_judge.py:124`) - and the request goes to an
OpenAI-compatible chat endpoint instead (`OPENROUTER_URL`,
`hooks/tezgah_judge.py:57`). TypeSafe wins whenever it resolves, so the fallback
cannot move a machine that already judges with Jev (`credential()`,
`hooks/tezgah_judge.py:150`). The chat model is asked for the same shapes in prose
(`CHAT_SYSTEM`, `hooks/tezgah_judge.py:66`), at temperature 0
(`_chat_body()`, `hooks/tezgah_judge.py:295`), and its reply is filtered to the ids
that were asked for, dropping any answer whose type does not match its question
(`_chat_answers()`, `hooks/tezgah_judge.py:337`; `_clean_answer()`,
`hooks/tezgah_judge.py:357`) - so a dropped answer reads the same as no answer at
all, which is what the callers already handled. The model is
`deepseek/deepseek-v4-flash` unless `TEZGAH_JUDGE_MODEL` names another
(`fallback_model()`, `hooks/tezgah_judge.py:141`), and whichever model answered
rides back on the result, which is what the callers' cost rows print.

## The switches

`judge-off` is the master: with it armed `available()` is false and no caller
makes a request at all, so the triage loop reads the tree and the docs fallback
prints what it always printed. Each caller also names its own switch, so one
capability can be disarmed without the others - `triage-off` for
`bin/tezgah-triage` and `docs-judge-off` for `bin/tezgah-docs`. The third caller's
channel is an opt-in marker rather than a kill switch: it is off until
`skill-suggest-on` is armed (`ARM`, `hooks/tezgah_skill_pick.py:41-45`). Every
switch is listed in the `**Kill switches:**` paragraph every session receives
(`CORE`, `hooks/tezgah_policy.py:768-777`), mirrored into `tezgah-contract`, and
pinned by `tests/test_skills.py`.

## What a judgement costs

Input tokens are billed per million and output at zero, and `bin/tezgah-triage`
computes and prints the arithmetic it paid on every run (`PRICE_PER_MILLION`,
`bin/tezgah-triage:56-62`; `judge_line`, `bin/tezgah-triage:196-203`). The
unit-selection shape it ships was measured on two reproduced screens: 100% of the
control lines at a 94% read on a 356-line table, and 100% at a 74% read on a
31-line screen, against 73.5% at a 26% read for the per-line shape it replaced.
The threshold those numbers were taken at is `SELECTED_AT`, and the tool prints
the measurement with every run (`MEASURED`, `bin/tezgah-triage:88-90`;
`SELECTED_AT`, `bin/tezgah-triage:63-65`). The retry covers a rate that was
measured rather than assumed - 0 of 184 live calls returned `None` - so the second
attempt costs a healthy call nothing (`_transient`,
`hooks/tezgah_judge.py:261-273`); `docs/operations.md` records the run. Each
caller also records one `judge` row of cost on the ledger when a session id is
known (`note`, `hooks/tezgah_integrity.py:512-524`), counted by the row's kind
(`counters`, `hooks/tezgah_integrity.py:858-877`).

## What the seam never does

1. **No always-on rule paragraph.** It is on-demand, and the conditional keys
   exist exactly so a session that never asks does not carry the text
   (`CONDITIONAL_KEYS`, `hooks/tezgah_policy.py:836-840`). Naming it buys discovery
   for one clause; a paragraph would cost the always-on block.
2. **Nothing in the gate, the Stop rule, the shortcut parser, the consent path or
   the PreToolUse hot path.** Refusal reproducibility is an invariant with tests
   behind it, and a probabilistic answer on a denial path is a policy bug.
3. **No seam-level cache, and no caller cache beyond the prompt-keyed one that
   exists** (`_remember`, `hooks/tezgah_skill_pick.py:191-206`). A judgement costs
   a fraction of a cent, so a cache is not worth its state file, and a naive one
   would make two runs of the same command disagree.
4. **No SDK, no `requests`, no async, no local model.** Each would trade one of
   the seam's three load-bearing properties - total, stdlib-only,
   dependency-free - for a saving nobody measured.
5. **No `criteria` on the triage's `--select` question.** The task sits in the
   shared state on purpose so the per-unit question does not repeat it dozens of
   times (`select_request`, `bin/tezgah-triage:230-248`).
6. **No rename of the module and no new tool.** It is cited across the docs and
   the tools' own docstrings, and the user-facing surface is already the two tool
   names.
7. **A judgement never counts as a check or a step.** The step kinds stay as they
   are (`STEP_KINDS`, `hooks/tezgah_integrity.py:855-857`); the cost row is a
   counter, not evidence.

## Source of truth

- `hooks/tezgah_judge.py` — the seam: the endpoint and key path, the redirect
  guard, `available()`, `ask()`, the `choice`/`noul` answer accessors, the retry
  class.
- `bin/tezgah-triage` — the snapshot triage and the per-state matrix; prints the
  unit it selected, the characters it saved and the cost it paid.
- `bin/tezgah-docs` — the page router; its index match, then its one fallback
  Choice.
- `hooks/tezgah_skill_pick.py` — the prompt-path skill hint, its threshold, its
  per-prompt cache and its `skill-suggest-on` marker.
- `hooks/tezgah_policy.py` — the `**Kill switches:**` paragraph the session
  receives; `hooks/tezgah_paths.py` — where a switch file is read.
- `hooks/tezgah_integrity.py` — the ledger and the `judge` counter;
  `hooks/tezgah_context.py` — the status mark and the class carve-out.
- `tests/test_judge.py`, `tests/test_triage.py`, `tests/test_docs_router.py` —
  the wire, the callers and the index criteria.
