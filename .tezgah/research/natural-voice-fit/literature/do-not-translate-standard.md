# Do-not-translate as a standard: W3C ITS 2.0 and XLIFF 2.0

**What it is and claims.** The category the user described has a published name and carrier formats. HTML's `translate` attribute and ITS 2.0's Translate data category mark text as non-translatable, and the W3C's own guidance states the failure mode: attribute values should not be translated, and if they are, the page breaks. XLIFF 2.0 carries the flag per unit and per inline marker, with the fallback of extracting non-translatable content as inline code, and the option of not extracting it at all.

**How it changes the skill.** A term policy is not prose advice: it is a flag on a segment, which means the skill can mark what must stay and a checker can verify it, instead of asking a model to remember.

**Quality.** Formal: a standard, a peer-reviewed paper or an institutional framework.
