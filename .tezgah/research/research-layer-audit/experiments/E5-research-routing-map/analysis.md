# E5 analysis — the rule reaches every host; the mark does not see the layer's own CLI

Raw: `results.jsonl` (rows carry the `path:line` the delegated map returned).

## Result

- **Routing is complete.** All six hosts arm the `research` rule at prompt time,
  through four mechanisms: `UserPromptSubmit` (claude, codex, dsh),
  `beforeSubmitPrompt` (cursor), the plugin's `chat.message` (opencode) and
  `before_agent_start` (omp). One builder produces the text
  (`hooks/tezgah_context.py:795-804`), so the contract's "every host says the same
  thing" holds for this rule.
- **The manual has a fallback where there is no shim.** dsh and omp install no
  orx skill shim (`bin/tezgah-setup:101-104`), and the rule already documents the
  fallback (`orx skill` on the shell).
- **The mark measures a proxy.** `research` lights when a *shell command* ran
  `orx` (`hooks/tezgah_context.py:1000-1013`, `:1272`, with tests for `orx
  experiment list`, `orx run --project p`, `orx experiment run`).
  `bin/tezgah-research init|check|status|claim` is never classified as such, so
  the auditable-workspace half of the layer is invisible to the one surface that
  reports whether the layer was used.
- **Two doc/code contradictions found in passing.** `bin/tezgah-setup:788` and
  `docs/skills.md:33` state that opencode has no prompt-time injection point;
  `hosts/opencode/plugins/tezgah.js:2169-2190` injects rule text for
  `user_prompt`. The statement is true for a per-prompt *skill list* and false as
  written. And dsh's context delivery is not verifiable in this repository at all
  - only its manifest event list is pinned, while the forwarding happens in the
  third-party bridge that `tests/test_dsh_hooks.py` does not reach.

## Why the mark matters more than it looks

The status line is the only mechanism by which a session or the user can see that
the research rule was *used* rather than *armed*. A layer whose whole claim is
"the evidence is auditable, and here is the command that checks it" reports
nothing when that command runs, and reports a green measure when a bare `orx`
call happens. Fixing it is one classification entry plus the test gap in E6
(item 11).

Rows here are scope: real (this repository's hosts, hooks, installer and status line).
