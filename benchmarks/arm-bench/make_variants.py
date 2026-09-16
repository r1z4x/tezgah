#!/usr/bin/env python3
"""Derive the clause-ablation contract variants from the installed contract.

    python3 make_variants.py            # regenerate arms/orx-*/RULES.md

Each variant is the managed tezgah contract with exactly one clause removed, so
an arm that loads it runs with the same harness minus that clause. The variants
are committed: the arm points `PI_CODING_AGENT_DIR` at the directory and omp
reads `RULES.md` from there, exactly as `arms/omp-bare` reads nothing.

The positive control is `orx-no-reporting`: clause 1 is the reply-language rule,
and `c04-turkish-explain-readonly` grades it, so if that ablation does not break
c04 the variant mechanism itself is broken and no other reading is admissible.
"""
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path.home() / ".omp" / "agent" / "RULES.md"

# variant name -> the clause lead to strip
CLAUSES = {
    "orx-no-reporting": "**Turkish, BLUF.**",
    "orx-no-ponytail": "**Ponytail (minimal code).**",
    "orx-no-whole-ask": "**Deliver the whole ask; never the shortcut.**",
    "orx-no-integrity": '**Integrity: evidence, or "doğrulanmadı".**',
}


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit("no installed contract at %s - run tezgah-setup first" % SOURCE)
    text = SOURCE.read_text(encoding="utf-8")
    paragraphs = text.split("\n\n")
    for name, lead in CLAUSES.items():
        kept = [p for p in paragraphs if not p.lstrip().startswith(lead)]
        if len(kept) == len(paragraphs):
            raise SystemExit("%s: no paragraph starts with %r" % (name, lead))
        out = ROOT / "arms" / name
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        (out / "RULES.md").write_text("\n\n".join(kept), encoding="utf-8")
        removed = [p for p in paragraphs if p.lstrip().startswith(lead)][0]
        # a header naming what this arm is missing, so a run log identifies the arm
        (out / "PROVENANCE.md").write_text(
            "# %s\n\nDerived from the installed contract at %s by removing the clause below.\n"
            "Regenerate with `python3 make_variants.py`.\n\n---\n\n%s\n"
            % (name, SOURCE, removed), encoding="utf-8")
        print("%-20s removed %d chars, contract now %d chars"
              % (name, len(removed), len("\n\n".join(kept))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
