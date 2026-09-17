---
id: 010
title: Stop touching the user's repo and nagging about tezgah itself
status: open
branch: plan/010-repo-footprint-and-session-scope
pr:
created: 2026-09-17
updated: 2026-09-17
---
## Goal
A session inside a user's project must leave that project's tracked files alone
and must not spend the session on tezgah's own installation. Two reported
behaviours: tezgah wrote into a repo it does not own, and it kept raising its own
files/health inside a project session.

## Findings (all observed in this checkout, rev 87aa2ae)
- `hooks/tezgah_agents.py:421-446` `ensure_gitignore` appends a managed block to
  the repo's **tracked** `.gitignore` on every session start, with no per-repo
  opt-in. Reproduced in a scratch repo: `bin/tezgah-agents <repo>` printed
  `4 agent(s) written` and left ` M .gitignore`. Live residue:
  `/Users/rizax/Projects/AI-Research-SKILLs` carries that uncommitted edit;
  `Ustam` committed it (`5795d1f`). `.git/info/exclude` was never written.
- `hooks/tezgah_agents.py:527-528` returns `"... agent(s) current"` even when
  nothing was written, and `hooks/tezgah_context.py:479-482` injects it into
  every session brief. Observed: `Subagents (this repo, generated): 4 agent(s)
  current` in `/tmp/ctx1.txt:85`, a repo where nothing changed.
- `hooks/tezgah_policy.py:345-353` (NO_CBM) tells the model "Install it and
  restart the session to arm search_graph / trace_path" - an install directive
  inside a user's project session. `hosts/omp/tezgah-hook.ts.in:90-94` tells the
  model to check with `tezgah-setup --report`.
- `bin/codegen:119-120` passes `--timeout` to `urllib.request.urlopen`, which
  bounds each socket operation, not total wall time; a stalled body can outlive
  `--timeout` indefinitely. `bin/consult:145-155` already solves this with a
  wall-clock `future.result(timeout=deadline)`.

## Acceptance
- [x] A session start in a git repo under a root leaves `git status --porcelain`
      empty: the generated agent dirs are ignored via `.git/info/exclude`, and
      `.gitignore` is byte-identical before and after. Pinned in
      `tests/test_agents.py` and reproduced live in a scratch repo.
- [x] `sync_root` returns `None` when nothing changed, so a steady-state session
      brief carries no "Subagents (this repo, generated)" line at all; a write or
      a removal still reports, and `tezgah-setup --agents` still answers its user
      with "current". Pinned in `tests/test_agents.py`.
- [x] No injected text tells the model to install, upgrade, restart or debug
      tezgah mid-session (NO_CBM, the omp hook-failure notice), and the always-on
      core carries **Session scope** so a missing capability is reported in one
      line instead of investigated. `output-styles/tezgah.md` and the benchmark
      README budget block match the instrument (core 5377 -> 5987 chars).
- [x] `bin/codegen --timeout N` bounds the whole request: a server that accepts
      and never answers makes it exit 2 in ~2s. The pre-fix call was still
      running after 12s against the same server.
- [x] `python3 -m compileall -q hooks hosts bin statusline.py`,
      `python3 -m unittest discover -s tests` (436 tests) and `ruff check .` all
      pass on the committed tip, re-run from a detached worktree.

## State
Landed on `plan/010-repo-footprint-and-session-scope`, tip `cbe2bae`:
`801dcfa` exclude instead of .gitignore + silent steady state, `ed11e20` the
Session scope rule and the dropped install directives, `99c1ad8` codegen's
end-to-end deadline, `08b77cc` the re-measured README bands, `cbe2bae` the
independent review's findings. Live verification on the committed tip: first
session start prints `4 agent(s) written`, the second prints nothing,
`tezgah-context session_start` carries 0 lines about tezgah's own files and the
new scope rule, `.gitignore` stays `node_modules/`, `git status` clean.

Two incidents worth recording: the second opinion could not run (OpenRouter key
returns 403, no DeepSeek key), and a concurrent session in this shared checkout
switched branches mid-task and stashed the in-progress half of `cbe2bae` - it was
recovered from `stash@{0}`, and the remaining work was done in a throwaway
worktree so it could not be swept again.

Not done, by decision: no push and no PR (outward-facing, awaiting the user), and
the two upstream items the session report raised are external - the
codebase-memory-mcp daemon lock is an upstream bug (the graph answers fine in
this session), and the `idx✓` mark reports index freshness, not daemon health,
so it stays as documented rather than paying a health probe on every redraw.

## Next
Push the branch and open the PR (or leave it local), then run
`tezgah-setup --install` on this machine: the always-on core changed, so
`~/.omp/agent/RULES.md` and the Claude output-style copy only pick up the
Session scope rule from that install.

