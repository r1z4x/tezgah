# Judge: the judgement seam, its five callers and its switches

The judgement seam is `hooks/tezgah_judge.py`: one module that asks TypeSafe
(Jev) for a batched structured judgement over a state tezgah would otherwise pay
an agent to read. Read this page when you are about to call one of its four
callers, when you need to say what leaves the machine, or when you have to tell a
user how to switch it off. It is an on-demand capability, not a rule: no paragraph
of it is injected into a session, and a session that never asks pays one clause in
the kill-switch paragraph and nothing else (`CORE`,
`hooks/tezgah_policy.py::CORE`).

## What it is

One seam, five callers, one credential, one egress boundary, one price, one
redirect guard. The module is stdlib only and total - a failure is a `None`, never
an exception, because a hook imports it and a hook that raises takes a session
down (`_request`, `hooks/tezgah_judge.py::_request`). One endpoint and one key path
are module constants (`URL`, `hooks/tezgah_judge.py::URL`; `KEY_FILE`,
`hooks/tezgah_judge.py::KEY_FILE`), one opener is shared by every call (`OPENER`,
`hooks/tezgah_judge.py::OPENER`), and it refuses a redirect that leaves the
endpoint's host, so a `Location` cannot carry the bearer (`guarded_opener`,
`hooks/tezgah_paths.py`, the one copy `bin/consult` and `bin/codegen` use too). A
transient failure - a timeout, a connection error, a 5xx - gets exactly one more
attempt; a 4xx and a malformed reply never do (`_transient`,
`hooks/tezgah_judge.py::_transient`). A hook caller asks for one attempt and a
wall-clock `deadline` instead (`ask`, `hooks/tezgah_judge.py::ask`).
urllib's timeout bounds one socket operation, not the whole call.
`TEZGAH_TYPESAFE_URL` repoints the endpoint and `TEZGAH_OPENROUTER_URL` the
fallback's; both are test seams, not fallbacks.

Every caller reads an answer through the same two accessors rather than reaching
into the raw reply, so a Choice and a Noul are read one way for all five
(`choice`, `hooks/tezgah_judge.py::choice`; `noul`,
`hooks/tezgah_judge.py::noul`). Both are total: a missing or wrongly-typed
answer is a `None`, never an exception.

A judgement is an aid, never the claim. It ranks units or names a page; the agent
still reads the selected refs and owns the finding, and the ledger's step kinds
are untouched, so a model answer can never license a "done" (`STEP_KINDS`,
`hooks/tezgah_integrity.py::STEP_KINDS`).

The state leaves the machine. A judgement sends the state and the questions to
`api.typesafe.ai` - for the triage that is the screen's own text, so a screen
carrying personal data is read by a third party, and for the docs fallback it is
the reader's query. When no TypeSafe key resolves, the same state goes to
`openrouter.ai` instead (`OPENROUTER_URL`, `hooks/tezgah_judge.py::OPENROUTER_URL`), which is
the price of a machine that has no Jev credential still having a judge at all:
the destination changes, not what is sent. Nothing else goes: no session id, no
workspace path, no environment. The seam does not rewrite the state, because
sending it is the point. Two callers rewrite what they send. `bin/tezgah-route`
sends its brief through the ledger's own redactor (`redact`,
`hooks/tezgah_integrity.py::redact`), because a delegation brief can quote an error
message or a token. A brief that matches the router's override vocabulary never
leaves the machine. That vocabulary names stored data, credentials, keys and
certificates, destructive data or history operations, privilege and security.
The prompt-path skill hint sends the user's prompt through the same redactor. It
also cuts the prompt at 2,000 characters (`PROMPT_MAX`,
`hooks/tezgah_skill_pick.py::PROMPT_MAX`), because a prompt can quote a token and
nobody chose to send it. Four of the callers are explicit -
a person runs the tool - and the fifth, `bin/tezgah-route`, is what the
ORCHESTRATE paragraph tells the router to run before every delegation, which is
why its redaction is not optional. The switches below are the off buttons.

## The five callers

| Caller | What it asks, and what it is for | On failure |
|---|---|---|
| `bin/tezgah-triage` | the analyze-app snapshot triage. `--select FILE --task T` asks one question per repeating unit of the screen in one request and prints the line ids under the selected units with their refs (`select_request`, `bin/tezgah-triage::select_request`; the units are the tree's own repeating pieces, `units`, `bin/tezgah-triage::units`). `--states` asks one judgement per state over a component's subtree (`states`, `bin/tezgah-triage::states`) | exit 1 with one reason (`no_judgement`, `bin/tezgah-triage::no_judgement`), and the loop reads the tree directly |
| `bin/tezgah-docs` | the docs page fallback: only when the keyword index placed nothing, one Choice over the pages with `none` offered (`judge_pick`, `bin/tezgah-docs::judge_pick`; the question wording is `ASK`, `bin/tezgah-docs::ASK`) | reads as no judgement; with none (no credential, `judge-off`, `docs-judge-off`, or a call that failed or came back without one of its options) the pages are ranked by shared words instead (`ranked`, BM25 in `hooks/tezgah_rank.py` over each page's title and answers and their Turkish phrasings) and the top three printed; a query sharing no word with any page, or a judged `none`, exits 1. With the opt-in embedding feature on, the ranking is fused with a static embedding (`hooks/tezgah_embed.py`), which places every page, so only a judged `none` exits 1 |
| `hooks/tezgah_skill_pick.py` | the prompt-path skill hint: a Choice over the roster skills plus one Noul (`judge`, `hooks/tezgah_skill_pick.py::judge`, with the criteria cut from each skill's own clauses, `clause`, `hooks/tezgah_skill_pick.py::clause`), behind a threshold (`GATE`, `hooks/tezgah_skill_pick.py::GATE`), one attempt and a 4 s wall-clock deadline (`ASK_DEADLINE`, `hooks/tezgah_skill_pick.py::ASK_DEADLINE`), the prompt redacted and cut at 2,000 characters | returns `""`; the turn loses the hint |
| `bin/tezgah-route` | the tier router: after the deterministic overrides, one Choice over the three tiers for a delegation brief (`route`, `hooks/tezgah_models.py::route`; `TIER_QUESTION`, `hooks/tezgah_models.py::TIER_QUESTION`) - see [models](models.md) | the static phase table, else the middle tier |
| `bin/tezgah-taste` | the coding-taste measurement: `measure` and `rate` label the prompts a user sent after a writing turn, one Choice per prompt batched into one request, each prompt redacted first (`classify`, `bin/tezgah-taste::classify`) | with no credential or `judge-off` it exits 2 before any request; a failed call leaves its prompts unlabelled |

The third caller is the one no shell row can see: it runs on the prompt path,
caches one answer per `(session, prompt)` (`_remember`,
`hooks/tezgah_skill_pick.py::_remember`; `suggest`,
`hooks/tezgah_skill_pick.py::suggest`), and asks at all only when its own marker is
armed. The other four are bin tools a session runs by name.

## The credential's channels

The credential resolves from `TYPESAFE_API_KEY`, else from the key file the module
names (`KEY_FILE`, `hooks/tezgah_judge.py::KEY_FILE`). The environment variable is the
channel an interactive shell has; the file is the channel that matters, because a
hook or a bin tool a host starts runs in a non-interactive shell where a
`~/.zshenv` export never ran, so the variable is absent exactly where a judgement
runs. That is why the file is read rather than the environment trusted. The
install report's health row reads its own pair of channels ([hosts](hosts.md)),
which is a different question from the one the seam asks.

When neither channel resolves, the same two channels are read again for the
fallback provider - `OPENROUTER_API_KEY`, then `~/.config/openrouter/key`
(`openrouter_key()`, `hooks/tezgah_judge.py::openrouter_key`) - and the request goes to an
OpenAI-compatible chat endpoint instead (`OPENROUTER_URL`,
`hooks/tezgah_judge.py::OPENROUTER_URL`). TypeSafe wins whenever it resolves, so the fallback
cannot move a machine that already judges with Jev (`credential()`,
`hooks/tezgah_judge.py::credential`). The chat model is asked for the same shapes in prose
(`CHAT_SYSTEM`, `hooks/tezgah_judge.py::CHAT_SYSTEM`), at temperature 0
(`_chat_body()`, `hooks/tezgah_judge.py::_chat_body`), and its reply is filtered to the ids
that were asked for, dropping any answer whose type does not match its question
(`_chat_answers()`, `hooks/tezgah_judge.py::_chat_answers`; `_clean_answer()`,
`hooks/tezgah_judge.py::_clean_answer`) - so a dropped answer reads the same as no answer at
all, which is what the callers already handled. The model is the table's cheap row
(`cheap_model`, `hooks/tezgah_models.py`) unless `TEZGAH_JUDGE_MODEL` names
another, and a table that cannot be read falls back to its own literal
(`fallback_model()`, `hooks/tezgah_judge.py::fallback_model`). The result carries the provider
that answered and the model the reply names. The requested model stands only
when the reply names none, so a silent upgrade behind `jev-latest` shows. The
skill hint's cost row and the router's `route` row print both as one
`judge=<provider>/<model>` word.

## The switches

`judge-off` is the master: with it armed `available()` is false and no caller
makes a request at all, so the triage loop reads the tree and the docs fallback
ranks the pages by shared words instead. Each caller also names its own switch, so one
capability can be disarmed without the others - `triage-off` for
`bin/tezgah-triage` and `docs-judge-off` for `bin/tezgah-docs`. The third caller's
channel is an opt-in marker rather than a kill switch: it is off until
`skill-suggest-on` is armed (`ARM`, `hooks/tezgah_skill_pick.py::ARM`). Every
switch is listed in the `**Kill switches:**` paragraph every session receives
(`CORE`, `hooks/tezgah_policy.py::CORE`), mirrored into `tezgah-contract`, and
pinned by `tests/test_skills.py`.

## What a judgement costs

Input tokens are billed per million and output at zero, and `bin/tezgah-triage`
computes and prints the arithmetic it paid on every run (`PRICE_PER_MILLION`,
`bin/tezgah-triage::PRICE_PER_MILLION`; `judge_line`, `bin/tezgah-triage::judge_line`). The
unit-selection shape it ships was measured on two reproduced screens: 100% of the
control lines at a 94% read on a 356-line table, and 100% at a 74% read on a
31-line screen, against 73.5% at a 26% read for the per-line shape it replaced.
The threshold those numbers were taken at is `SELECTED_AT`, and the tool prints
the measurement with every run (`MEASURED`, `bin/tezgah-triage::MEASURED`;
`SELECTED_AT`, `bin/tezgah-triage::SELECTED_AT`). The retry covers a rate that was
measured rather than assumed - 0 of 184 live calls returned `None` - so the second
attempt costs a healthy call nothing (`_transient`,
`hooks/tezgah_judge.py::_transient`); `docs/operations.md` records the run. Each
caller also records one `judge` row of cost on the ledger when a session id is
known (`note`, `hooks/tezgah_integrity.py::note`), counted by the row's kind
(`counters`, `hooks/tezgah_integrity.py::counters`).

## What the seam never does

1. **No always-on rule paragraph.** It is on-demand, and the conditional keys
   exist exactly so a session that never asks does not carry the text
   (`CONDITIONAL_KEYS`, `hooks/tezgah_policy.py::CONDITIONAL_KEYS`). Naming it buys discovery
   for one clause; a paragraph would cost the always-on block.
2. **Nothing in the gate, the Stop rule, the shortcut parser or
   the PreToolUse hot path.** Refusal reproducibility is an invariant with tests
   behind it, and a probabilistic answer on a denial path is a policy bug.
3. **No seam-level answer cache, and no caller cache beyond the prompt-keyed one
   that exists** (`_remember`, `hooks/tezgah_skill_pick.py::_remember`). A judgement
   costs a fraction of a cent, so a cache is not worth its state file, and a naive
   one would make two runs of the same command disagree. The one state the seam
   keeps is a failure marker (`DOWN_FOR`, 300 s, in `hooks/tezgah_judge.py`). A
   call that ends on a 401, 402 or 5xx marks that provider, endpoint and
   credential down for five minutes. Until the marker expires, every call returns
   no judgement and sends no request. A dead key or an empty account then costs
   one refusal per five minutes, not one per prompt. A rotated key gets a new
   marker, so the seam asks it at once.
4. **No SDK, no `requests`, no async, no local model.** Each would trade one of
   the seam's three load-bearing properties - total, stdlib-only,
   dependency-free - for a saving nobody measured.
5. **No `criteria` on the triage's `--select` question.** The task sits in the
   shared state on purpose so the per-unit question does not repeat it dozens of
   times (`select_request`, `bin/tezgah-triage::select_request`).
6. **No rename of the module and no new tool.** It is cited across the docs and
   the tools' own docstrings, and the user-facing surface is already the two tool
   names.
7. **A judgement never counts as a check or a step.** The step kinds stay as they
   are (`STEP_KINDS`, `hooks/tezgah_integrity.py::STEP_KINDS`); the cost row is a
   counter, not evidence.

## Source of truth

- `hooks/tezgah_judge.py` — the seam: endpoint, key path, `available()`, `ask()`,
  the answer accessors, the retry class and the provider-down marker.
- `bin/tezgah-triage` — the snapshot triage and the per-state matrix; prints the
  unit it selected, the characters it saved and the cost it paid.
- `bin/tezgah-docs` — the page router; its index match, then its one fallback
  Choice, then the word ranking (`hooks/tezgah_rank.py`, fused with
  `hooks/tezgah_embed.py` when that opt-in feature is on) when the judge gives
  no judgement.
- `hooks/tezgah_skill_pick.py` — the prompt-path skill hint, its threshold, its
  per-prompt cache and its `skill-suggest-on` marker.
- `hooks/tezgah_policy.py` — the `**Kill switches:**` paragraph the session
  receives; `hooks/tezgah_paths.py` — where a switch file is read, and the
  redirect guard (`guarded_opener`) the seam, consult and codegen share.
- `hooks/tezgah_integrity.py` — the ledger and the `judge` counter;
  `hooks/tezgah_context.py` — the status mark and the class carve-out.
- `tests/test_judge.py`, `tests/test_triage.py`, `tests/test_docs_router.py` —
  the wire, the callers and the index criteria.
