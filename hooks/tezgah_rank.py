"""BM25 over a handful of short texts: which of them a query is about.

Two callers rank a short list against free text with no model and no network:
the per-turn lessons block (`tezgah_context.relevant_lessons`) and the docs
fallback when the judge is unavailable (`bin/tezgah-docs`). The lists are tens
of entries, so the whole index is rebuilt per call. Measured on 12 prompts
against a 42-line lessons ledger (Turkish and English): recall@5 0.647, against
0.103 for the last five lines the session block injects.
"""
import math
import re
from collections import Counter

# Lowercased words, Turkish letters kept; one- and two-letter words carry no topic.
WORD = re.compile(r"[a-zçğıöşü0-9_]+")
MIN_WORD = 3
K1 = 1.2
B = 0.75


def words(text):
    """The terms of `text`: lowercased runs of letters, digits and `_`, 3+ long."""
    return [w for w in WORD.findall(str(text).lower()) if len(w) >= MIN_WORD]


def rank(query, texts, k):
    """Indices of the `k` texts that score highest for `query`, best first.

    Only a text sharing at least one term with the query is returned (score > 0),
    so an unrelated query gets [] rather than an arbitrary order."""
    docs = [Counter(words(t)) for t in texts]
    terms = set(words(query))
    if not docs or not terms:
        return []
    avg = sum(sum(d.values()) for d in docs) / len(docs) or 1.0
    idf = {}
    for t in terms:
        df = sum(1 for d in docs if t in d)
        idf[t] = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
    scored = []
    for i, d in enumerate(docs):
        size = sum(d.values())
        score = sum(idf[t] * d[t] * (K1 + 1)
                    / (d[t] + K1 * (1 - B + B * size / avg))
                    for t in terms if t in d)
        if score > 0:
            scored.append((-score, i))
    return [i for _s, i in sorted(scored)[:k]]
