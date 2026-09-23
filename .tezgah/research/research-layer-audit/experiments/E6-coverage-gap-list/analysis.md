# E6 analysis — the write/check half is well pinned; the prose half and the CLI edges are not

Raw: `results.jsonl` (25 rows), `protocol.md` (the brief).

## What is covered

Thirteen behaviour groups are pinned, most of them adversarially:
`tests/test_research.py` drives the module and the CLI end to end against a real
git repository with fixed commit dates, and covers scaffolding and the slug
guard, the six `state.json` refusals, findings sections, the claim field rules,
the whole protocol-order family (same-second commits, a rebase, renames into
place, untracked results, `git=False`), the CLI's exit contract, the claim
append under `flock` including eight concurrent writers and a held lock, and the
session note. The routing/arming half is spread over `test_context.py`,
`test_statusline.py`, `test_cursor_hook.py`, `test_omp_hook.py`, `test_paths.py`;
the generated agent over `test_agents.py`; the vendored library over
`test_ai_research_library.py`.

## What is not

25 rows. They cluster into four kinds, and the kind matters more than the count:

1. **The documented method has no test at all** (rows 20, 21, 23). The skill's
   locked evaluation, its review, its citation rule and its evidence-fidelity
   rules are prose nothing reads, and E1's 0/8 is the same fact measured from the
   other end: the checker does not implement them either.
2. **The CLI's refusal edges** (rows 12-19). `status` with arguments, a non-git
   directory, non-UTF-8 stdin, an unwritable line, `init`'s printed guidance - all
   of them are branches with a documented exit code and no test.
3. **Degradation paths** (rows 2, 5, 6, 19). The no-fcntl refusal, `is_ancestor`
   returning None, a machine without git, the last-byte repair. Each is a design
   decision written in a docstring, each is skipped or unexercised in the suite.
4. **The status surface** (rows 10, 11, 24). Which measure lights, in what order
   the budget drops a rule, and whether the classifier's own audit log is written
   - the surface a user reads to decide whether the layer is working.

## Reading it with E1

E1 says the checker's *reach* stops at structure. E6 says the part of the layer
that a test could hold to account - the checks, the CLI, the marks - is covered
unevenly: strong where a file is written, thin where a decision is documented. The
two together are one finding: this layer's discipline lives in prose, and neither
the checker nor the suite reads the prose.

Rows here are scope: real (this repository's test suite and the code it pins).
