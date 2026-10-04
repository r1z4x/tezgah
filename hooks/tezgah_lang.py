#!/usr/bin/env python3
"""A non-English identifier tezgah is about to write: a heuristic, not a
language detector.

What this answers: the contract has always said code, commits, branches and docs
are English, and nothing checked it - a plan branch was created as
`plan/004-admin-durum-onarimi`, and the repository carries that folded slug in
its history for the rest of its life. `hooks/tezgah_gate.py` refuses the command
that would create such an identifier (the language rule in `decision`); this
module is the detector behind it, so the predicate and the word list live in one
place and a test can read them without a session.

Two halves, and they answer different failures:

- **Any letter outside ASCII.** The contract is "identifiers and messages stay
  English", not "no Turkish", so a Russian, Greek, Arabic, Chinese or
  accented-Latin identifier is refused for the same reason a Turkish one is -
  `non_english()` is a predicate rather than a list of one language's letters.
- **A curated Turkish word list.** Turkish is the language this repository has
  actually seen folded into ASCII, where the alphabet half cannot see it
  (`durum`, `onarim`, `hazirlik`). The list carries the English each stem should
  be written as, so a refusal can name the replacement instead of leaving the
  session to guess.

What this is NOT: it does not read meaning and it is not a language detector. A
word outside the two halves passes - an ASCII-folded word from any other
language (`naprawa-stanu`, `reparatur`) is invisible here, and that is the
ceiling this module states rather than hides: catching it would take a language
package or a model, which is a dependency and a nondeterministic answer on a
denial path. A proper noun, a product name and the user's own term are the cases
no list can decide, which is why the refusal says it is a heuristic and hands the
call back to the user instead of asserting a language.
"""
import re

# The characters an English identifier never contains: a letter or digit outside
# ASCII. A predicate rather than a list, because the contract is "identifiers and
# messages stay English" and not "no Turkish": a Russian, Greek, Arabic, Chinese
# or accented-Latin identifier is refused for the same reason `durum-onarimi` is,
# and Turkish is one case of it. Measured before this change: every one of
# `статус`, `إصلاح`, `状态修复`, `κατάσταση`, `kế-hoạch` and `état` passed, while
# ASCII `I` - the letter `İ` folds to - was refused, which refused `CI`, `ID` and
# `I1` as well. The cost is stated in the refusal: a proper noun or a product name
# in another language is refused too, and the user's own term is theirs to settle.
def non_english(token):
    """True when the token holds a character English identifiers do not: any
    alphanumeric outside ASCII. Digits and `-`/`_`/`/` are boundaries, so a slug
    keeps its words whole and a version like `4.2.1` is untouched."""
    return any(ord(ch) > 127 and ch.isalnum() for ch in token)

# The ASCII a Turkish letter folds to when a slug or a filename strips it. The
# reverse direction is what makes the word list work on `onarım` as it works on
# `onarim`: the token is folded before it is looked up, so the English the list
# knows is offered for either spelling.
_FOLD = str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g",
                       "Ğ": "G", "ü": "u", "Ü": "U", "ö": "o", "Ö": "O",
                       "ç": "c", "Ç": "C"})

# A token is a run of letters and digits; everything else - `-`, `_`, `/`,
# space, a dot, a colon - is a boundary. That is the set the identifier
# vocabulary is built from, so `plan/004-admin-durum-onarimi` yields `durum` and
# `onarimi` and not one long string.
# A token is a run of ASCII or non-ASCII alphanumerics; `-`, `_`, `/`, space
# and punctuation are boundaries. Splitting on ASCII-alnum alone is what keeps
# a non-Latin word whole, so the refusal names it instead of a fragment.
_TOKENS = re.compile(r"[^0-9A-Za-z\u00c0-\U0010ffff]+")

# The Turkish stems the list knows, and the English each one is asking for. The
# replacements are the point of the list: the refusal can name what to write
# instead, so a refused session is not left guessing at a translation.
#
# Every key is a word English does not have, which is what keeps the list from
# refusing English text. `data` and `test` are the shape to avoid: they are
# English words AND Turkish ones, so a list that held them would refuse an
# ordinary commit subject.
ENGLISH = {
    "durum": "status",
    "kural": "rule",
    "dosya": "file",
    "sayfa": "page",
    "hata": "error",
    "rapor": "report",
    "ozet": "summary",
    "sonuc": "result",
    "kullanim": "usage",
    "calisma": "work",
    "onarim": "repair",
    "deneme": "experiment",
    "incele": "review",
    "kontrol": "check",
    "listele": "list",
    "goster": "show",
    "tasarla": "design",
    "duzelt": "fix",
    "ekle": "add",
    "kaldir": "remove",
    "guncelle": "update",
    "hazirla": "prepare",
    "olustur": "create",
    "degistir": "change",
    "temizle": "clean",
    "iyilestir": "improve",
    "karsilastir": "compare",
    "tasi": "move",
    "sil": "delete",
    # `sil` on its own is exact-matched (see SHORT below), so the suffixed form
    # Turkish actually uses needs its own entry: `silme` is the word a plan
    # says, and `sil*` would also swallow `silent` and `silk`.
    "silme": "deletion",
    # The second group: the words a 57-word probe of ordinary Turkish found
    # missing. Each one is here because the English side of that probe stayed
    # clean - no English word grows out of the stem - and the three that DO have
    # an English word growing out of them are in WHOLE below instead.
    "hazirlik": "preparation",
    "silin": "deleted",
    "degis": "change",
    "temizlik": "cleanup",
    "tasarim": "design",
    "baglanti": "link",
    "ayar": "settings",
    "kullanici": "user",
    "yetki": "permission",
    "guvenlik": "security",
    "testler": "tests",
    "senaryo": "scenario",
    "aciklama": "description",
    "ornek": "example",
    "cikti": "output",
    # the three WHOLE stems (below): listed here so the word itself is still
    # named and translated, and read whole-token so the English they grow is not
    "arama": "search",
    "veri": "data",
    "girdi": "input",
    "donusum": "conversion",
    "yapilandirma": "configuration",
    "surum": "version",
    "yayin": "release",
    "baslat": "start",
    "durdur": "stop",
    "bekle": "wait",
    "hiz": "speed",
    "hizmet": "service",
    "hizli": "fast",
    "boyut": "size",
}

# A stem this short is matched whole-token rather than as a prefix. English
# words are shorter than Turkish suffixes suggest: `sil` prefixes `silent` and
# `silk`, while every longer stem in the list above has no English word growing
# out of it, so the prefix match - which is what catches `onarimi`, `duzeltmesi`
# - costs nothing there. Raising this number would start missing Turkish
# suffixes; lowering it would start refusing English words.
SHORT = 4

# The stems long enough for the prefix match that must not use it, because the
# prefix IS an English word: `veri` grows `verify`, `verification` and
# `verifiable`, `arama` grows `Aramaic`, `girdi` grows `girding`. They are read
# whole-token, which still catches the word on its own and in every slug or
# subject that separates it (`veri-tabani`, `arama-sonuclari`, `girdi-dosyasi`)
# and misses only the inflections Turkish glues to it (`veriler`, `aramasi`) -
# the price of not refusing English. The English side of the probe is the guard
# on this whole list, pinned in tests/test_lang.py.
WHOLE = ("arama", "veri", "girdi")

DENY = (
    "Non-English identifier: the %s this command would create is not "
    "English (`%s`). Code, commits, branches, PR and issue text stay English, "
    "because an identifier outlives the session that typed it: a branch name "
    "and a commit subject are in the repository, and often in a public "
    "history, from the moment they exist. Say the same thing in English and "
    "re-issue the command with it.%s This is a heuristic - a letter set plus a "
    "curated word list, not a language detector - so it cannot tell a proper "
    "noun or a product name in another language from a word that ought to be "
    "English, and a word it lists may be the user's own term. Where the wording "
    "is the user's own, say so plainly and let them settle it: their explicit "
    "instruction overrides this rule, and re-issuing the same command is not "
    "that.")


def _folded(token):
    return token.translate(_FOLD).lower()


def replacement(token):
    """The English the list holds for this token, or None when it does not know
    it - a token the letter set caught, a word the user chose, a proper noun."""
    folded = _folded(token)
    for stem, english in ENGLISH.items():
        whole = len(stem) < SHORT or stem in WHOLE
        if folded == stem or (not whole and folded.startswith(stem)):
            return english
    return None


def offending(text):
    """The tokens of `text` that are not English, each once, in order.

    Empty for English text and for an empty string, so a caller can treat a
    non-empty answer as the whole condition."""
    out = []
    for token in _TOKENS.split(str(text or "")):
        if not token or token in out:
            continue
        if non_english(token) or replacement(token):
            out.append(token)
    return out


def _hint(tokens):
    """The English to write instead, for the tokens the list knows. Empty when
    it knows none of them - then the non-ASCII letter caught them and the
    refusal says only which token it read."""
    known = ["`%s` -> `%s`" % (token, replacement(token))
             for token in tokens if replacement(token)]
    if not known:
        return ""
    return " The English this list knows: %s." % ", ".join(known)


def refusal(what, text):
    """The refusal for a `text` that would become `what`, or None when the text
    reads as English.

    `what` is the identifier the command is about to create, in the words the
    session wrote it with ("branch name", "commit subject", "PR title"), so the
    refusal names the thing that will exist and not the regex that caught it."""
    tokens = offending(text)
    if not tokens:
        return None
    return DENY % (what, "`, `".join(tokens), _hint(tokens))
