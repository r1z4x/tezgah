#!/usr/bin/env python3
"""Derive the clause-ablation arms from the installed agent dir.

    python3 make_variants.py            # (re)deploy arms/orx-*/

Each variant is the installed omp agent dir with exactly one clause removed from
its `RULES.md`, so an arm that loads it runs the same harness minus that clause:
the arm sets `PI_CODING_AGENT_DIR` to the directory, omp reads `RULES.md`,
`hooks/`, `agents/` and the rest of the contract from there, and `omp+tezgah`
reads the installed dir. The copied bridge is the installed byte and pins the
same checkout, so the one file that differs from `omp+tezgah` is the contract.

A variant is not a `RULES.md` on its own: an agent dir holding the contract and
no bridge loads no harness, so the row measures an inert host - `bench.py`'s
pre-flight refuses it before any spend, and `session_rows` would be 0 on every
row. Per-run state (sessions, SQLite DBs, caches) is dropped here because omp
recreates it on first run.

The positive control is `orx-no-reporting`: clause 1 is the reply-language rule,
and `c04-turkish-explain-readonly` grades it, so if that ablation does not break
c04 the variant mechanism itself is broken and no other reading is admissible.
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path.home() / ".omp" / "agent"

# per-run state, not arm configuration: omp recreates every one of these
RUN_STATE = ("sessions", "blobs", "cache", "terminal-sessions", "custom-session-files",
             "agent.db*", "models.db*", "history.db*", "config.yml.lock")

# variant name -> the clause lead to strip
CLAUSES = {
    "orx-no-reporting": "**Turkish, BLUF.**",
    "orx-no-ponytail": "**Ponytail (minimal code).**",
    "orx-no-whole-ask": "**Deliver the whole ask; never the shortcut.**",
    "orx-no-integrity": '**Integrity: evidence, or "doğrulanmadı".**',
}


def deploy(out: pathlib.Path) -> None:
    """The installed agent dir without its per-run state, symlinks preserved."""
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(SOURCE, out, symlinks=True, ignore=shutil.ignore_patterns(*RUN_STATE))


def main() -> int:
    contract = SOURCE / "RULES.md"
    if not contract.exists():
        raise SystemExit("no installed contract at %s - run tezgah-setup first" % contract)
    text = contract.read_text(encoding="utf-8")
    paragraphs = text.split("\n\n")
    for name, lead in CLAUSES.items():
        kept = [p for p in paragraphs if not p.lstrip().startswith(lead)]
        if len(kept) == len(paragraphs):
            raise SystemExit("%s: no paragraph starts with %r" % (name, lead))
        removed = [p for p in paragraphs if p.lstrip().startswith(lead)][0]
        ablated = "\n\n".join(kept)
        out = ROOT / "arms" / name
        deploy(out)
        (out / "RULES.md").write_text(ablated, encoding="utf-8")
        # a header naming what this arm is missing, so a run log identifies the arm
        (out / "PROVENANCE.md").write_text(
            "# %s\n\n"
            "The installed omp agent dir `%s` with one clause removed from `RULES.md`,\n"
            "so the arm differs from `omp+tezgah` in the contract alone: the copied\n"
            "`hooks/pre/tezgah-hook.ts` is the installed byte and pins the same checkout,\n"
            "and every other copied file is the installed byte too. Regenerate with\n"
            "`python3 make_variants.py` in this directory, which re-copies the installed\n"
            "dir and rewrites this file - the two committed files here are the contract\n"
            "and this header, and the rest of the arm is the deployment.\n\n"
            "Copied: everything that dir holds except per-run state (`sessions/`, `blobs/`,\n"
            "`cache/`, `terminal-sessions/`, `custom-session-files/`, `*.db*`,\n"
            "`config.yml.lock`), which omp recreates on first run. `skills/` is copied as\n"
            "symlinks and still resolves into the primary checkout. `arms.json` gives the\n"
            "arm the same `TEZGAH_ROOTS` as `omp+tezgah`: without it `tezgah_paths.root_for`\n"
            "answers None for a run directory under the bench root, every hook returns\n"
            "early, and the arm is inert however complete this directory is.\n\n"
            "The ablated `RULES.md` is %d bytes against the installed %d, both read by this\n"
            "generator; `const HOOK` is unchanged, so the harness the arm loads is the\n"
            "primary checkout's at generation time and the arm is not pinned to a commit.\n"
            "That omp itself loads this directory at runtime is not verified here: no row\n"
            "has been scored on these arms, and the positive control needs a paid run.\n\n"
            "---\n\n%s\n"
            % (name, SOURCE, len(ablated), len(text), removed), encoding="utf-8")
        print("%-20s removed %d chars, contract now %d chars"
              % (name, len(removed), len(ablated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
