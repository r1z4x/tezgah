# Layers

This page answers one question: which layer is tezgah, and where does each
neighbouring layer end. It is written for anyone about to write a claim of the
form "apply X to the harness", and for a reader who has met that word in three
different senses here. [architecture](architecture.md) says what tezgah
contains, [glossary](glossary.md) says what a word means; this page draws the
border around the layer and names what is on the other side of it.

The four layers are listed bottom-up. Each one gets what it owns, what it must
not own, and where this repository touches it.

## Model and MCP transport

Owns the wire: what the model is asked, and how a tool call reaches a server and
its result comes back. MCP is a transport in that sense - it carries a call and
a result and holds no rule.

Must not own policy, provenance or evidence. A transport cannot refuse a call,
and it writes no ledger [row](glossary.md#row).

Here tezgah only *configures* servers and classifies a call by its name: the
app-analysis servers are rendered into each host's own config from one spec
(`hooks/tezgah_apps.py:1-5`), Codex's rows are appended by `ensure_toml_mcp`
(`bin/tezgah-setup:641-673`), and a tool name starting `mcp__` is classified
`mcp` rather than trusted (`MCP_TOOL` `hooks/tezgah_integrity.py:1137`).

## Agent framework

Owns the building blocks a runtime is composed from: the chat pipeline, context
providers, middleware and tool approval, compaction, bounded looping, telemetry.
Microsoft's Agent Framework describes a `HarnessAgent` as composed of exactly
those and notes that it remains a normal framework agent (Microsoft Agent
Framework, `concepts/harness`).

Must not own the user's rules or the record of the turn. A framework supplies
the extension points; what a session is held to is not its subject.

Here tezgah plugs into those points and never supplies one: omp's extension is
"only the bridge" (`hosts/omp/tezgah-hook.ts.in:3-6`), opencode's plugin adds
what its generated `instructions` files cannot carry
(`hosts/opencode/plugins/tezgah.js:3-12`), and Codex's hook maps the host's
events and tool names onto the shared vocabulary (`hosts/codex/hook.py:36-49`).

## Agent host runtime

Owns the loop: plan, call a tool, read the result, edit a file, report back -
one job per session, with its own transcript, tool set and context window. The
UHP spec states it the same way - "a harness is a complete agent runtime ...
Codex, Claude Code and Hermes are harnesses" - with a task or job as the unit of
exchange and a harness-to-application interface shaped like OpenAI Responses
(the UHP spec, `github.com/HarnessRouter/harnessrouter`, file
`protocol/README.md`).

Must not own the user's rules, the evidence of the turn or the refusal. A
runtime runs what the model asks; nothing inside it stops the model, which is
the whole reason tezgah exists ([architecture](architecture.md)).

Here the six hosts are the runtimes, one config dir per host
(`hooks/tezgah_paths.py:49`) with one presence test (`host_installed`
`hooks/tezgah_paths.py:67-77`), and the adapter under `hosts/<name>/` holds the
host's envelope and nothing else ([hosts](hosts.md)). The README's own host list
calls dsh a harness (`README.md:42-43`) - the literature's sense, applied to a
host.

## tezgah's policy and evidence layer

Owns the rule text (`CORE` `hooks/tezgah_policy.py:621-831`), the per-turn reminder
(`PROMPT_REMINDER` `hooks/tezgah_policy.py:847-867`), the refusal before a call
(`decision()` `hooks/tezgah_gate.py:1608-1848`), the record after one (`note()`
`hooks/tezgah_integrity.py:512`), the end-of-turn verdict (`stop_reason()`
`hooks/tezgah_integrity.py:1694`), the pre-write snapshots (`capture()`
`hooks/tezgah_snapshot.py:191`), the status marks, and the per-repo plans,
lessons and research lines.

Must not own the loop, the model, the tools or the network. tezgah never runs
the work and never rolls back on its own - rollback is the explicit
`bin/tezgah-rollback` - and the subagents it defines are rendered into a host's
own agent surface for that host to run (`hooks/tezgah_agents.py:2-21`).

## The boundary, one term at a time

The test in each row is the one arXiv 2606.10106, "What makes a harness a
harness", uses: the paper states necessary and sufficient conditions for a
system to be an agent harness and operates them as an inclusion/exclusion test,
bounding the term against agent framework, SDK, IDE plugin, eval harness and
orchestrator. It also records why the word is ambiguous: it is used polysemously
for a whole product, for an eval scaffold, and for things that are really
frameworks.

| Term | The test it must pass to be this layer | Where this repository touches it |
|---|---|---|
| host | does it run the loop for one session, with its own transcript and tool set? Then it is the runtime the literature calls a harness | six adapters under `hosts/<name>/`, no loop ([hosts](hosts.md)) |
| agent framework | is it composed *from* elsewhere, or does it compose? A framework is composed from building blocks and stays a framework agent | tezgah plugs into its extension points, supplies none |
| SDK | does it leave the iteration to its caller? A client library gives a call and stops | tezgah ships no client; it reads a host's event JSON on stdin (`hosts/codex/hook.py:1-2`) |
| IDE plugin | is it a guest inside another program's surface? It draws and forwards and owns no task runtime | `hosts/opencode/plugins/tezgah.js:1-12` is one, and is a plugin |
| eval harness | does it produce a score over a task set? It measures and enforces nothing | an eval scaffold is vendored as the `lm-evaluation-harness` skill body (`skills/ai-research/11-evaluation/lm-evaluation-harness/SKILL.md:11`), and this project's measurements live apart from the layer (`README.md:411-412`) |
| orchestrator | does it split one request across many runs and merge them? A harness runs one job to a report | the `harness` skill's route table (`skills/harness/SKILL.md:2-8`) and the graph workflows (`hooks/tezgah_policy.py:586`) |
| MCP | does it only carry a call and its result? Then it is transport, not a layer with policy or evidence | the section below |

## Why tezgah is not an agent harness

Under that test tezgah is not one: it holds no loop. It subscribes to a host's
events (`hooks/hooks.json:2-26`), is handed the injected text at the host's
session-start and prompt points (`context_for` `hooks/tezgah_context.py:802-978`),
refuses a call before the host runs it (`hooks/projects-pretooluse.py:24`) and
answers in the host's own output envelope. It has no model, no tool set and no
context window of its own.

What it is: the policy and evidence layer a host loads. The rules travel as text
into the host's context, the gate stands in front of the host's tool calls, and
the ledger records what the host ran - one text, one gate, one ledger, which is
[architecture](architecture.md)'s whole idea. None of this is a claim about
quality: a policy layer is judged by what it refuses and what it can prove, not
by solving the task.

## Three senses of one word

| Sense | What it names | Where it is defined |
|---|---|---|
| tezgah's own | the wrapper around a host - the injected contract, the per-turn text still travelling in the `<harness-reminder>` envelope (`hooks/tezgah_policy.py:806-807`), the gate and the ledger | [glossary](glossary.md#harness) |
| the literature's | the host itself: a "complete agent runtime", which the README's host list also calls a harness for dsh (`README.md:42-43`) | [hosts](hosts.md) |
| the skill's | multi-agent harness selection: which graph workflow or subagent set runs a task too wide for one window (`skills/harness/SKILL.md:2-8`, [skills](skills.md)) | [glossary](glossary.md#harness-skill) |

A claim that says "apply X to the harness" is therefore unreadable until it says
which. Write **host** for the runtime, **the harness skill** for multi-agent
selection, and **tezgah's layer** (or "the policy and evidence layer") for this
one.

## MCP: the gate sees the call, not its contents

This is the checkable consequence of the transport layer here. A hook is handed
the call, so that is all the classification can use (`untrusted_source`
`hooks/tezgah_integrity.py:1192-1195`): an MCP answer enters the ledger as an
untrusted channel, the channel being `mcp` (`untrusted_source`
`hooks/tezgah_integrity.py:1200-1202`), and an answer that is no step of work
of its own earns a row of kind `external` (`note_tool`
`hooks/tezgah_integrity.py:1364-1370`). The compensating control is the sink
rule: an effect in a turn that has read an untrusted channel is refused until
the user approves it afterwards (`UNTRUSTED_DENY` `hooks/tezgah_gate.py:1004-1014`,
`sink_check` `hooks/tezgah_gate.py:1037-1070`, [gate](gate.md)).

The structural limit is that the write tools and the shell tools are disjoint
tuples (`WRITE_TOOLS` `hooks/tezgah_integrity.py:172-174`, `BASH_TOOLS`
`hooks/tezgah_integrity.py:175-176`), so a rule that guards one does not guard
the other - the class named C26 in
`.tezgah/research/infra-candidates/findings.md` (local, untracked). No content
of an MCP answer is inspected, and nothing beyond this is built for MCP.

## What this page does not change

Documentation only: no rule label, no `CORE` paragraph and no injected byte
changes, so the cost table in `README.md` stays true. Definitions stay in the
[glossary](glossary.md) - this page draws the boundary and adds no term of its
own.

## Source of truth

- `hooks/tezgah_policy.py`, `hooks/tezgah_context.py`, `hooks/tezgah_gate.py`,
  `hooks/tezgah_integrity.py`, `hooks/tezgah_snapshot.py`, `hooks/tezgah_paths.py`
- `hooks/hooks.json`, `hooks/projects-pretooluse.py`, `hooks/tezgah_apps.py`,
  `hooks/tezgah_agents.py`, `bin/tezgah-setup`
- `hosts/<name>/`, `skills/harness/SKILL.md`
- `docs/glossary.md`, `docs/hosts.md`, `README.md` (the host list, the cost
  section)
