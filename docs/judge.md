# Judge: the judgement seam, its five callers and its switches

The judgement seam is `hooks/tezgah_judge.py`. It asks the session's own model,
through the host's CLI, for a batched structured judgement over a state tezgah
would otherwise pay an agent to read. Read this page when you are about to call one of its four
callers, when you need to say what leaves the machine, or when you have to tell a
user how to switch it off. It is an on-demand capability, not a rule: no paragraph
of it is injected into a session, and a session that never asks pays one clause in
the kill-switch paragraph and nothing else (`CORE`,
`hooks/tezgah_policy.py::CORE`).

## What it is

One seam, five callers, one provider order, one egress boundary, one price, one
redirect guard. The module is stdlib only and total - a failure is a `None`, never
an exception, because a hook imports it and a hook that raises takes a session
down (`_request`, `hooks/tezgah_judge.py::_request`). The carriers' endpoints are
module constants: `URL` (`hooks/tezgah_judge.py::URL`), `JEV_OPENROUTER_URL`
(`hooks/tezgah_judge.py::JEV_OPENROUTER_URL`) and `CLOUDFLARE_URL`
(`hooks/tezgah_judge.py::CLOUDFLARE_URL`). One opener serves every call (`OPENER`,
`hooks/tezgah_judge.py::OPENER`), and it refuses a redirect that leaves the
endpoint's host, so a `Location` cannot carry the bearer (`guarded_opener`,
`hooks/tezgah_paths.py`, the one copy `bin/consult` and `bin/codegen` use too). A
transient failure - a timeout, a connection error, a 5xx - gets exactly one more
attempt. A 4xx, a session CLI's non-zero exit and a malformed reply never do
(`_transient`, `hooks/tezgah_judge.py::_transient`). A hook caller asks for one
attempt and a wall-clock `deadline` instead (`ask`, `hooks/tezgah_judge.py::ask`).
A session CLI answers in 4-10 s (measured 2026-10-07), so the skill hint's
4 s deadline usually ends first. `TEZGAH_TYPESAFE_URL`, `TEZGAH_JEV_OPENROUTER_URL`,
`TEZGAH_CLOUDFLARE_URL`, `TEZGAH_OPENROUTER_URL` and
`TEZGAH_OMP_BIN`/`TEZGAH_CLAUDE_BIN` are the test seams. Each URL override goes
through `override` (`hooks/tezgah_judge.py::override`), which refuses plain http
off this machine.

Every caller reads an answer through the same accessors rather than reaching
into the raw reply, so a Choice and a Noul are read one way for all five
(`choice`, `hooks/tezgah_judge.py::choice`; `noul`,
`hooks/tezgah_judge.py::noul`). A `text` question is the one shape that asks
for prose. `bin/tezgah-taste` asks it for a learning's readable line, and only
a generative provider answers one. No Jev carrier is sent one (`text`,
`hooks/tezgah_judge.py::text`). All three are total: a missing or
wrongly-typed answer is a `None`, never an exception.

A judgement is an aid, never the claim. It ranks units or names a page; the agent
still reads the selected refs and owns the finding, and the ledger's step kinds
are untouched, so a model answer can never license a "done" (`STEP_KINDS`,
`hooks/tezgah_integrity.py::STEP_KINDS`).

The state leaves the machine. By default it goes to the session's own vendor,
through the session's own CLI and credential ([below](#the-providers-and-their-order)).
A third party reads it only as the `fallback` setting allows. The third parties
are the Jev carriers' hosts - `api.typesafe.ai`, `openrouter.ai`,
`api.cloudflare.com` or a user's `JEV_API_BASE_URL` - and the chat endpoint
(`OPENROUTER_URL`, `hooks/tezgah_judge.py::OPENROUTER_URL`).
For the triage the state is the screen's own text, so whoever
answers reads any personal data on it. For the docs fallback it is the query.
Nothing else goes: no session id, no
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
nobody chose to send it. Three of the callers are explicit - a person runs
the tool. `bin/tezgah-route` is what the ORCHESTRATE paragraph tells the router
to run before every delegation, which is why its redaction is not optional.
`bin/tezgah-taste learn` also starts by itself at session start once the user
armed `taste-on`. It then sends redacted signal text to TypeSafe only, and only
when a TypeSafe key resolves (`learn_later`, `hooks/tezgah_taste.py::learn_later`).
The switches below are the off buttons.

## The five callers

| Caller | What it asks, and what it is for | On failure |
|---|---|---|
| `bin/tezgah-triage` | the analyze-app snapshot triage. `--select FILE --task T` asks one question per repeating unit of the screen in one request and prints the line ids under the selected units with their refs (`select_request`, `bin/tezgah-triage::select_request`; the units are the tree's own repeating pieces, `units`, `bin/tezgah-triage::units`). `--states` asks one judgement per state over a component's subtree (`states`, `bin/tezgah-triage::states`) | exit 1 with one reason (`no_judgement`, `bin/tezgah-triage::no_judgement`), and the loop reads the tree directly |
| `bin/tezgah-docs` | the docs page fallback: only when the keyword index placed nothing, one Choice over the pages with `none` offered (`judge_pick`, `bin/tezgah-docs::judge_pick`; the question wording is `ASK`, `bin/tezgah-docs::ASK`) | reads as no judgement; with none (no credential, `judge-off`, `docs-judge-off`, or a call that failed or came back without one of its options) the pages are ranked by shared words instead (`ranked`, BM25 in `hooks/tezgah_rank.py` over each page's title and answers and their Turkish phrasings) and the top three printed; a query sharing no word with any page, or a judged `none`, exits 1. With the opt-in embedding feature on, the ranking is fused with a static embedding (`hooks/tezgah_embed.py`), which places every page, so only a judged `none` exits 1 |
| `hooks/tezgah_skill_pick.py` | the prompt-path skill hint: a Choice over the roster skills plus one Noul (`judge`, `hooks/tezgah_skill_pick.py::judge`, with the criteria cut from each skill's own clauses, `clause`, `hooks/tezgah_skill_pick.py::clause`), behind a threshold (`GATE`, `hooks/tezgah_skill_pick.py::GATE`), one attempt and a 4 s wall-clock deadline (`ASK_DEADLINE`, `hooks/tezgah_skill_pick.py::ASK_DEADLINE`), the prompt redacted and cut at 2,000 characters | returns `""`; the turn loses the hint |
| `bin/tezgah-route` | the tier router: after the deterministic overrides, one Choice over the three tiers for a delegation brief (`route`, `hooks/tezgah_models.py::route`; `TIER_QUESTION`, `hooks/tezgah_models.py::TIER_QUESTION`) - see [models](models.md) | the static phase table, else the middle tier |
| `bin/tezgah-taste` | the coding-taste measurement and learning: `measure` and `rate` label the prompts a user sent after a writing turn, one Choice per prompt batched into one request, each prompt redacted first (`classify`, `bin/tezgah-taste::classify`). `learn` asks one typed decision per signal and requires TypeSafe (`decide`, `bin/tezgah-taste::decide`). For a learning that turns active it asks one `text` question of a generative provider (`write_line`, `bin/tezgah-taste::write_line`) | with no credential or `judge-off` it exits 2 before any request. A failed call leaves its prompts unlabelled. A decision another provider gave is recorded `unverified` and never applied. A missing line keeps the user's own words |

The third caller is the one no shell row can see: it runs on the prompt path,
caches one answer per `(session, prompt)` (`_remember`,
`hooks/tezgah_skill_pick.py::_remember`; `suggest`,
`hooks/tezgah_skill_pick.py::suggest`), and asks at all only when its own marker is
armed. `bin/tezgah-triage`, `bin/tezgah-docs` and `bin/tezgah-route` are bin
tools a session runs by name, and so is `bin/tezgah-taste`, except for the
background `learn` that armed taste starts.

## The providers and their order

`providers()` (`hooks/tezgah_judge.py::providers`) is the order `ask()` tries.
The next one is asked only when the previous failed. First comes the session's own
CLI (`tp.session_cli`, `hooks/tezgah_paths.py::session_cli`). The host's marker
names it, in this order:

| CLI | Marker | Set by |
|---|---|---|
| `omp` | `OMPCODE` | omp, which sets `CLAUDECODE` too |
| `claude` | `CLAUDECODE` | Claude Code |
| `opencode` | `OPENCODE` | opencode, in its own process |
| `cursor` (runs `cursor-agent`) | `CURSOR_AGENT`, `CURSOR_VERSION` | Cursor: the first in its shell tool, the second in its hooks |
| `codex` | `CODEX_THREAD_ID` | Codex in its shell tool; tezgah's Codex hook sets it from the session id |

A marked host whose binary is missing has no session CLI. No other CLI stands
in. `TEZGAH_JUDGE_CLI`, else `judge_cli` in `~/.config/tezgah/config.json`,
names one of the five instead. `auto`, the default, reads the marker. A named CLI
that is not installed is no session CLI either.

The CLI runs headless in an empty temp dir. Its flags are `SESSION_ARGV`
(`hooks/tezgah_judge.py::SESSION_ARGV`). The omp and claude runs drop tools,
rules, skills, extensions, MCP servers and settings. The other three have no flag
that drops their tools or takes a system prompt. They run with the least their
`--help` offers: opencode `--pure`, cursor-agent `--mode ask`, codex
`-s read-only --ephemeral`. Their prompt starts with the system prompt.
`opencode run` ran a shell command its prompt asked for in a probe on
2026-10-09. So it also gets an inline config that denies every tool
(`SESSION_ENV`, `hooks/tezgah_judge.py::SESSION_ENV`). With it, the same probe
wrote nothing. cursor-agent in ask mode refused the same shell call.
Measured 2026-10-07, a call cost $0.007 on claude and $0.015 on omp. Measured
2026-10-09 on one choice question, opencode read 28,646 input tokens ($0.004 by
its own report), cursor-agent 17,095 and codex 20,919. The session's own
credential pays, OAuth subscription included. The answer and usage come from the
CLI's JSON output (`_session_request`, `hooks/tezgah_judge.py::_session_request`).
`_cli_answer` (`hooks/tezgah_judge.py::_cli_answer`) reads the last three. Only
omp and claude name the model. Then come the
third parties: first the chosen Jev carriers, each a real System One transport
(`_jev_call`, `hooks/tezgah_judge.py::_jev_call`), then the OpenRouter chat
fallback. `JEV_CARRIERS` (`hooks/tezgah_judge.py::JEV_CARRIERS`) names the four.

| Carrier | Endpoint | Credential (env, else file, stripped) | Body |
|---|---|---|---|
| `typesafe` | `https://api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY`, else `~/.config/typesafe/key`, else the active omp login (`~/.omp/agent/agent.db`, read-only; `typesafe_key`, `hooks/tezgah_paths.py::typesafe_key`) | `{state, model, questions}` |
| `jev-openrouter` | `https://openrouter.ai/api/v1/systemone` | `OPENROUTER_API_KEY`, else `~/.config/openrouter/key` | the same, a bare `jev-*` id sent as `typesafe/<id>` |
| `jev-cloudflare` | `https://api.cloudflare.com/client/v4/accounts/<id>/ai/run` | `JEV_CLOUDFLARE_API_TOKEN`, else `CLOUDFLARE_API_TOKEN`, else `~/.config/cloudflare/token`; the account id from `CLOUDFLARE_ACCOUNT_ID`, else `~/.config/cloudflare/account_id` | `{model: "typesafe/jev", input: {state, questions}}`; the reply is read bare or inside `result` |
| `jev-compatible` | `JEV_API_BASE_URL`, used verbatim | `JEV_API_KEY` | TypeSafe's, the model from `TEZGAH_JEV_MODEL` if set |

`JEV_API_BASE_URL` and `JEV_API_KEY` are the names the public jev-mcp server
reads, so one export serves both. `TEZGAH_JEV_PROVIDER` chooses the carrier,
else `JEV_PROVIDER`, else `jev` in `~/.config/tezgah/config.json`, else `auto`
(`jev_choice`, `hooks/tezgah_paths.py::jev_choice`). The values are `auto`,
`typesafe`, `openrouter`, `cloudflare` and `compatible`, and `tezgah-setup --jev
<value>` writes the config key (`set_jev`, `bin/tezgah-setup::set_jev`). `auto`
asks every carrier that resolves, in the table's order (`jev_carriers`,
`hooks/tezgah_paths.py::jev_carriers`). The seam asks a named carrier without
its credential nothing, and nothing stands in for it: the call records
`no credential (jev=<value>)` as a failure. `tezgah-status --judge` prints the
choice and the carriers it resolves to (`jev_summary`,
`hooks/tezgah_judge.py::jev_summary`).

OpenRouter's chat fallback reads the OpenRouter key (`openrouter_key`,
`hooks/tezgah_judge.py::openrouter_key`).
It asks the table's cheap row unless `TEZGAH_JUDGE_MODEL` names another
(`fallback_model`, `hooks/tezgah_judge.py::fallback_model`). The key files are
read because a hook runs where `~/.zshenv` never did. A chat answer is asked for in prose
(`CHAT_SYSTEM`, `hooks/tezgah_judge.py::CHAT_SYSTEM`) and filtered to the ids
asked, a wrongly typed answer dropped (`_chat_answers`,
`hooks/tezgah_judge.py::_chat_answers`).

`fallback` in `~/.config/tezgah/config.json` (`fallback_policy`,
`hooks/tezgah_paths.py::fallback_policy`) decides who may stand in:

| `fallback` | Session CLI present | No session CLI |
|---|---|---|
| `vendor` (default) | the session CLI only; when it fails, no judgement | the Jev carriers, then the chat fallback |
| `any` | the session CLI, then the Jev carriers, then the chat fallback | the Jev carriers, then the chat fallback |
| `none` | the session CLI only | nobody: `available()` is false |

Nothing that stands in is silent. A result carries `provider`, the `model`
the reply named and `fallback` - None when the session answered, else why it did
not. That answer, and a refusal with its failures, is said on stderr as one
`tezgah-judge:` line. It is also kept as the last-use record (`_record`,
`hooks/tezgah_judge.py::_record`), which `tezgah-status --judge` prints. The skill
hint's cost row and the router's `route` row also carry `judge=<provider>/<model>`.

A caller that needs one provider in particular passes `only` (`named`,
`hooks/tezgah_judge.py::named`). `learn`'s decision has to come from a typed
model, so it passes `only=("jev",)`, every Jev carrier that resolves. It gets `None` rather than another
provider's answer. The caller named the provider, so the `vendor` order does not
apply. `none` still keeps every third party out.

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
   one would make two runs of the same command disagree. Beside the last-use
   record, the seam keeps a failure marker (`DOWN_FOR`, 300 s, in `hooks/tezgah_judge.py`). A
   401, 402, 403, 5xx or a session CLI's non-zero exit marks that
   provider, endpoint and credential down for five minutes. A 403 is OpenRouter's
   answer to a key past its limit. Until the marker
   expires, that provider is skipped and sent no request. A dead key or an empty account then costs
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

- `hooks/tezgah_judge.py` — the seam: the carriers' endpoints and bodies,
  `available()`, `ask()`, the answer accessors, the retry class and the
  provider-down marker.
- `hooks/tezgah_paths.py` — the key channels (`typesafe_key`, `jev_carriers`)
  and the carrier choice (`jev_choice`).
- `bin/tezgah-triage` — the snapshot triage and the per-state matrix; prints the
  unit it selected, the characters it saved and the cost it paid.
- `bin/tezgah-docs` — the page router; its index match, then its one fallback
  Choice, then the word ranking (`hooks/tezgah_rank.py`, fused with
  `hooks/tezgah_embed.py` when that opt-in feature is on) when the judge gives
  no judgement.
- `hooks/tezgah_skill_pick.py` — the prompt-path skill hint, its threshold, its
  per-prompt cache and its `skill-suggest-on` marker.
- `hooks/tezgah_policy.py` — the `**Kill switches:**` paragraph the session
  receives; `hooks/tezgah_paths.py` — where a switch file is read, the session CLI
  and the `fallback` setting, and the redirect guard (`guarded_opener`) the seam,
  consult and codegen share; `bin/tezgah-status --judge` — the last-use record.
- `hooks/tezgah_integrity.py` — the ledger and the `judge` counter;
  `hooks/tezgah_context.py` — the status mark and the class carve-out.
- `tests/test_judge.py`, `tests/test_triage.py`, `tests/test_docs_router.py` —
  the wire, the callers and the index criteria.
