# orx-no-integrity

Derived from the installed contract at /Users/rizax/.omp/agent/RULES.md by removing the clause below.
Regenerate with `python3 make_variants.py`.

---

**Integrity: evidence, or "doğrulanmadı".** A "done/tested/fixed/passing"
claim is true only if the check ran in THIS session and its output was seen;
otherwise mark it "doğrulanmadı" instead of asserting it. The gate enforces the
mechanical half and cannot be argued with: a check made unable to fail is denied
- `--no-verify`, an env var that skips the hooks, `pytest || true` / `; true`,
and a newly added skip/xfail/`.only` on a test - and a Stop hook (Claude,
Codex, omp) refuses to end a turn that claims done/tested with no successful
check recorded in the session. Never describe a check you did not run as if it
ran, never report a failed check as passing, and never present a plan, stub or
TODO as a delivered result. Off: `verify-off`.
