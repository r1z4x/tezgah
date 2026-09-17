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
- [ ] A session start in a git repo under a root leaves `git status --porcelain`
      empty: the generated agent dirs are ignored via `.git/info/exclude`, and
      `.gitignore` is byte-identical before and after. Pinned in
      `tests/test_agents.py` and reproduced live in a scratch repo.
- [ ] `sync_root` returns `None` when nothing changed, so a steady-state session
      brief carries no "Subagents (this repo, generated)" line at all; a write or
      a removal still reports. Pinned in `tests/test_agents.py`.
- [ ] No injected text tells the model to install, upgrade, restart or debug
      tezgah mid-session (NO_CBM, the omp hook-failure notice), and the always-on
      core carries **Session scope** so a missing capability is reported in one
      line instead of investigated. `output-styles/tezgah.md` and the benchmark
      README budget block match the instrument.
- [ ] `bin/codegen --timeout N` bounds the whole request: a server that accepts
      and never answers makes it exit 2 in ~N seconds (test drives a local
      stalling HTTP server; no network).
- [ ] `python3 -m compileall -q hooks hosts bin statusline.py`,
      `python3 -m unittest discover -s tests` and `ruff check .` all pass.

## State
Both behaviours reproduced here before any edit: the scratch-repo run above, and
`/tmp/ctx1.txt` from `bin/tezgah-context session_start`. The second opinion could
not run - the OpenRouter key returns 403 (credit limit) and there is no DeepSeek
key - so the design rests on the observed evidence, not on a consult.

## Next
Implement on `plan/010-repo-footprint-and-session-scope`: move the ignore block
to `.git/info/exclude`, make the agents note change-only, add the Session scope
rule, drop the install directives, give codegen a total deadline, then run the
three checks and re-run both reproductions.
