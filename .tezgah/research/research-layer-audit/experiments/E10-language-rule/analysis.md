# E10 analysis — coverage 57/57, precision 24/24 English

Raw: `raw/probe.txt`.

The first reading was **30 of 57 Turkish words caught**: the list held the stems
whose English word is obvious (`duzelt`, `ekle`, `guncelle`) and missed every
noun and passive form (`hazirlik`, `silindi`, `degisiklik`, `temizlik`, `arama`,
`veri`, ...). The writer widened it, keeping the two guards that make precision
possible - the `SHORT` floor that matches a four-letter stem whole-token only
(so `sil` cannot refuse `silent`) and a `WHOLE` set for the three stems that are
also prefixes of English words (`arama`, `veri`, `girdi`, where `veri` would
otherwise refuse `verify`/`verification`).

Second reading, and the one this claim rests on: **57 of 57 caught, 0 of 24
English refused**, the reported slug yields both tokens, and the refusal names
them with the English to write instead.

## What this does not show

The list is a curated vocabulary, not a detector, and the rule says so in its own
refusal: a Turkish word outside the 57 - a proper noun, a product name, a rare
stem - is not caught, and a listed word may be the user's own term. The honest
reading is "it catches the identifier words this repository has actually seen plus
their family", and the escape is stated in the text rather than hidden: where the
wording is the user's, say so and re-issue.

The 24 English words are a probe list, not a corpus. A wider precision test (the
repository's own English identifiers, say) would be a better instrument, and is
the obvious next measurement if the list grows again.

Rows here are scope: fixture (protocol.md: "`caught / 57` Turkish words, and `refused / 24` English words"; analysis.md: "The 24 English words are a probe list, not a corpus.").
