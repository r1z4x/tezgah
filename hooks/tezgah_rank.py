"""BM25 over a handful of short texts: which of them a query is about.

Two callers rank a short list against free text with no model and no network:
the per-turn lessons block (`tezgah_context.relevant_lessons`) and the docs
fallback when the judge is unavailable (`bin/tezgah-docs`), through
`tezgah_embed.fuse` and `tezgah_embed.nearest`, which are exactly this ranking
unless the opt-in embedding feature is on. The lists are tens of entries, so
the whole index is rebuilt per call. Measured on 12 prompts against a 42-line
lessons ledger (Turkish and English): recall@5 0.647, against 0.103 for the
last five lines the session block injects.
"""
import math
import re
from collections import Counter

from tezgah_paths import packs

# Lowercased words, Turkish letters kept; one- and two-letter words carry no topic.
# Dotted and dotless i fold together (İ, I, ı -> i) so "İSTEK" meets "istek" and
# "KIRMIZI" meets "kırmızı" while English capitals stay "index"; plain lower()
# would turn İ into i + U+0307 and split the word. A pack's `fold` pairs (tr:
# dotless i and the circumflexes) fold too.
WORD = re.compile(r"[a-zçğöşü0-9_]+")
FOLD = str.maketrans({pair[0]: pair[1] for p in packs().values() for pair in p["fold"]})
MIN_WORD = 3
K1 = 1.2
B = 0.75


def words(text):
    """The terms of `text`: lowercased runs of letters, digits and `_`, 3+ long."""
    return [w for w in WORD.findall(str(text).replace("İ", "i").lower()
                                    .translate(FOLD)) if len(w) >= MIN_WORD]


# The lessons path's own filter, passed as `max_df` (`tezgah_context.LESSON_MAX_DF`):
# a word in most of the ledger ("the", "and" in 41 of 47 lines) ranked lines 9,
# 7 and 34 for "update the changelog", a prompt no line is about. Function words
# go first, every pack's `rank_stopwords` (folded the way `words` folds them);
# then any term in more than `max_df` of the texts - once there are
# MIN_CAP_TEXTS of them, because on one or two texts a 50% cap drops every term.
# The docs fallback passes no cap.
STOPWORDS = frozenset(w for p in packs().values() for w in p["rank_stopwords"])
MIN_CAP_TEXTS = 10


def rank(query, texts, k, max_df=None):
    """Indices of the `k` texts that score highest for `query`, best first.

    Only a text sharing at least one term with the query is returned (score > 0),
    so an unrelated query gets [] rather than an arbitrary order. `max_df` (a
    fraction) drops STOPWORDS and, on MIN_CAP_TEXTS or more texts, every query
    term found in more than that share of them."""
    docs = [Counter(words(t)) for t in texts]
    terms = set(words(query))
    if not docs or not terms:
        return []
    avg = sum(sum(d.values()) for d in docs) / len(docs) or 1.0
    df = {t: sum(1 for d in docs if t in d) for t in terms}
    if max_df is not None:
        terms = {t for t in terms - STOPWORDS
                 if len(docs) < MIN_CAP_TEXTS or df[t] <= max_df * len(docs)}
    idf = {t: math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
           for t in terms}
    scored = []
    for i, d in enumerate(docs):
        size = sum(d.values())
        score = sum(idf[t] * d[t] * (K1 + 1)
                    / (d[t] + K1 * (1 - B + B * size / avg))
                    for t in terms if t in d)
        if score > 0:
            scored.append((-score, i))
    return [i for _s, i in sorted(scored)[:k]]
