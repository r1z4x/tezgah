# unreallabsai/unreal-agent — an async-first agent harness, and what it decomposes well

https://github.com/unreallabsai/unreal-agent — MIT ("Copyright (c) 2026 Unreal Labs"),
Go 1.27, module `github.com/unreallabsai/unreal-agent`. Read at first hand from a clone
at commit `b7c9bf1` (`Use release environment for Docker Hub publishing (#2)`): 169 Go
files, 61,771 lines under `harness/ internal/ cmd/ benchmarks/`. The repository's own
`CONTRIBUTING.md` states it "contains selected components from a larger internal
codebase" and that pull requests are not reviewed or merged — so what is readable here is
a published slice, not the shipped product.

Launch surface, read on 2026-09-22: launch post `https://unreallabs.ai/blog/unreal-agent/`
(HTTP 200, published that day) and its Hacker News submission, item `49805748` (score 56,
42 comments, submitted by `trollied`, observed through the Hacker News Firebase API at
retrieval time; the score moves). **Nothing was built, installed, imported or executed.**
No Go toolchain was invoked, no test was run, no file in the clone was modified. Every
number below is either read from a source or is a count of files that were opened.

## What it is

An async-first agent harness: a Go library whose deliverable is the loop itself, plus
`cmd/unreal-agent-runner`, which "writes events to stdout as JSONL and exits when the
task finishes". The README's component table names eight components, and the code makes
the decomposition real:

- **One goroutine owns the loop.** `Run` multiplexes inbox, operation updates, tool
  heartbeat, grace deadline and model responses on a bare `select`
  (`harness/coordinator/loop.go:125`). The model call is a goroutine feeding an unbuffered
  channel; the tool-call scheduling path is synchronous on the loop
  (`harness/coordinator/loop.go:763-828`).
- **The translator may not do I/O.** "Tool translator … runs synchronously on the
  coordinator's event loop and must not perform I/O or suspend the loop"
  (`README.md:20`). `Context.Submit(operation.Spec) operation.ID` "allocates an ID and
  records inert data without performing I/O or handing work to another queue"
  (`harness/tool/tool.go:20-24`); the coordinator's implementation only appends to a
  slice with a fresh UUID and `StatusReady` (`harness/coordinator/loop.go:816-828`). A
  translator that cannot resolve its skill returns the text error immediately
  (`harness/tool/skill_use.go:19-38`).
- **Work becomes a versioned, serializable value.** `Spec` and `Operation` both carry
  `MaxOutputLength`, `Type`, `Version`, `State jsontext.Value` and
  `Idempotency jsontext.Value` (`harness/operation/operation.go:29-46`), so the runtime
  can persist, fork or ship an operation without knowing its shape. Decoders refuse a
  version mismatch with one sentinel, `ErrUnsupported`
  (`operation.go:11`, `value.go:42-47`, `shell.go:176-181`, `skill_use.go:87-92`,
  `remote_job.go:73-79`, `image.go:94-97`).
- **An actor runtime executes them, and it is swappable.** `LocalOperationManager` is
  three methods (`Add`, `Cancel`, `Updates`) over one `run()` goroutine and five
  channels; `Add` "starts an operation at most once for each ID during the manager's
  lifetime" and a duplicate ID returns nil (`harness/operation/operation.go:59-64`,
  `harness/operation/local_manager.go:134-137`). The README's own extension example — "a
  proxy operations manager can send serialized operations to a local operations manager
  running in a process inside a remote sandbox" — is implemented by `remote_job`, which
  routes the whole serialized operation to the one registered handler whose plan type
  *and* version match, refusing zero or two matches, and validates every update back
  (output limit, type, version and plan bytes byte-identical, legal transition only)
  (`harness/operation/remote_job_handler.go:36-63`, `:101-152`).
- **Durability is one append-only log.** `Item{Sequence, RecordedAt, Kind, Data}` with
  five kinds — `fork`, `input`, `turn`, `model_response`, `tool_call_status`
  (`harness/sessionstore/sessionstore.go:23-35`) — one file per session, and `Data`
  decoded only after the tag is read (`harness/sessionstore/itemjson.go:21-37`).

## The three invariants worth copying

1. **Commit before dispatch.** A tool call's status and the operation snapshots it
   authorizes are one persisted record: "AppendToolCallStatus appends the status and its
   operation snapshots. The first append also initializes those operations"
   (`sessionstore.go:97-99`). The coordinator commits, and only then hands the executor
   the operations *from that committed value* (`loop.go:780-828`, `:225-254`); a failed
   status commit persists no operation, dispatches nothing and starts no request, and the
   retry dispatches exactly once (`recovery_sequences_test.go:184-243`). The fuzz trace
   asserts it as a system property: "operation dispatched before its status and state
   committed" is fatal (`fault_fuzz_test.go:311`).
2. **A version gate at record zero, with a named refusal.** A `Version` header is stamped
   by the writer (`codec.go:15`, `:55-58`) and read before any item is decoded
   (`codec.go:107-127`): version 1 gets its own message, "legacy session format version 1
   cannot be resumed" (`:114-118`), anything else "unsupported session format version %d"
   (`:119-121`). A control mode the running version no longer models is refused the same
   way — history carrying the removed `"soft"` stop mode fails with `unsupported control
   mode "soft"` (`store_test.go:303-309` over `testdata/soft-stop-session.session.jsonl`).
3. **Input identity from the producer, the seen-set rebuilt from history.** The id is the
   caller's `MessageID` when supplied and a fresh UUID otherwise
   (`cmd/internal/agentrunner/run.go:388-396`); `Inbox.New(ctx, seenIDs)` seeds the dedup
   set from `ResumeState.ExternalInputIDs`, which is rebuilt from the session file
   (`harness/inbox/local.go:19-31`, `sessionstore.go:78-82`,
   `localfile/state.go:286-317`), so a redelivery after a crash is still a duplicate. A
   duplicate is dropped before queueing, silently (`local.go:73-75`).

## Two more mechanisms worth a rule

- **Retryability is decided by a closed list of terminal provider codes and error types
  *before* the HTTP status is read, and the classifier deliberately fails open.** The
  docstring says so: "this classifier intentionally fails open, favoring retries"
  (`harness/llm/responsesapi/retry.go:16-17`); the code checks a terminal-code set and two
  terminal error types (`:22-27`, `:28-32`) and only then falls back to the status
  (`:33-35`). So a 429 or 503 whose body carries `insufficient_quota` is never retried,
  while an unrecognised status is. `retry_policy_test.go:14-46` pins every row, including
  "quota overrides HTTP status" and "policy overrides HTTP status".
- **A server's own backoff hint is obeyed up to a ceiling, and jitter may never shorten
  it.** The wait takes the max of the `Retry-After` header (seconds or an HTTP date, with
  an overflow guard), a regex over the message body, and the local curve, then caps at
  `MaxBackoff`; jitter is applied only as a subtraction of at most a fifth
  (`harness/llm/responsesapi/retry.go:39-54`, `:56-82`). `retry_policy_test.go:120-160`
  fails the test if jitter shortened the server's hint.

## Where the published slice falls short of its own documentation

Three gaps are declared in the code itself, and they are the reason this survey's answer
is "borrow the decomposition, not the engine":

- **The omission record is declared and dead.** `ChangeKind` ∈ {omitted, truncated,
  compacted}, `Change{Kind, Source, Reason}`, `Report{Changes}` and
  `Result{Request, Report}` all exist (`harness/contextbuilder/contextbuilder.go:11-30`),
  and the README promises the context builder will "return the model input together with
  a record of anything omitted, truncated, or compacted" (`README.md:36`). Nothing
  populates it: `Build()` returns `Result{Request: request}` with `Report` zero
  (`builder.go:130-136`), the only `Build()` caller discards it (`loop.go:351`), and the
  one reader in the tree asserts the list is **empty** (`builder_test.go:181-183`).
- **The fork path is declared unsound.** `// FIXME: Forks leave inherited calls without
  results and retain pending-input accounting.` (`harness/coordinator/loop.go:552`), and
  the store side agrees: `// TODO: Preserve status snapshots in forked history without
  making inherited operations dispatchable.` (`localfile/state.go:401`). `fork_test.go`
  only asserts the child starts idle, keeps the parent's turn boundary and never acts on
  an inherited call.
- **Output truncation keeps no file.** `// TODO: Capture the full result in a file before
  truncating and expose its path.` (`harness/operation/remote_job_output.go:4`).

## Why it is not an adoption target for a daemon-less harness

Its architecture class is set by the code, not the README: a single-process,
event-loop-coordinated runtime that owns session state and a durable store. tezgah is
the other slot entirely — hooks invoked by a host CLI, `hooks/hooks.json` wiring eight
host events with 5-10 s timeouts, no scheduler, no session store, no tool execution
engine, no long-lived process. "Adopt the async engine" and "grow the process tezgah
deliberately does not have" are the same sentence in two directions; `2608.28553` is the
published measurement of why the fault-tolerance guarantee that justifies such a process
is bought exactly by moving records out of the failing process.

What survives translation is the *shape*: an intent committed before the effect, a
version gate on durable state, an identity the producer controls, a cancellation that is
its own outcome, and a delegation whose scope the delegate may not widen. Each of those
is a rule, a field or a paragraph in tezgah, and the costs are in
`to_human/report.md`.
