# E9 analysis — the citation pass

Raw: `raw/audit.txt`.

The audit went from **36 judged citations outside the symbol they name to 0 of
329 judged**, through 33 token replacements across six pages, each replacement
derived from the audit's own statement of where the named symbol lives and applied
only where that file's shift was uniform.

Two honest limits, both stated rather than averaged away:

1. **Three audit rows were not applied** - they were substrings of a longer token
   already replaced in the same page (`hooks/tezgah_policy.py:758` inside the
   range token, `:1048` in `docs/glossary.md` appearing twice). The audit's
   post-pass reading of 0 is what confirms none of them was left stale.
2. **748 citations are not judgeable by this audit** (no single symbol named
   beside them) and this pass says nothing about them. They are the standing
   residue the earlier citation audit (plan 003) named, and re-adjudicating them
   page by page is a separate work item, not something a green audit covers.

Rows here are scope: real for the audit's two readings and derived for the per-file shifts and the replacement count (protocol.md: "the per-file shift is *derived* (`new_start - old_start`)").
