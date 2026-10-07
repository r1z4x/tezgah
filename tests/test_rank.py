"""hooks/tezgah_rank.py: which of a few short texts a query is about.

Pinned on a small ledger in both languages the user writes, because the ranking
feeds the per-turn lessons block and the docs fallback, and a tokenizer that
lost the Turkish letters would rank a Turkish prompt by its stray English words.
"""
import os
import sys
import unittest

import support

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_integrity  # noqa: E402
import tezgah_rank  # noqa: E402

# the first lesson quotes the gate's piped-check remedy, pinned with the other
# copies in tests/test_integrity.py
LESSONS = [
    "never pipe a test run into tail; " + tezgah_integrity.PIPED_REMEDY,
    "worktree'de paralel ajan çalıştırmadan önce dalı ayır",
    "a commit that adds a tracked file regenerates the MANIFEST first",
    "kırmızı citation satırını kaydırınca tezgah-docs --citations koş",
    "do not store an API key in a tracked file",
]


class Rank(unittest.TestCase):
    def test_an_english_prompt_ranks_its_lesson_first(self):
        got = tezgah_rank.rank("I added a new tracked file, commit it", LESSONS, 3)
        self.assertEqual(got[0], 2, got)

    def test_a_turkish_prompt_ranks_its_lesson_first(self):
        # `kırmızı`, `satırını` fold their dotless ı into i: a tokenizer that
        # split on it would leave `rm`/`z` fragments and rank nothing
        got = tezgah_rank.rank("citation satırını kaydırmam lazım, test kırmızı",
                               LESSONS, 3)
        self.assertEqual(got[0], 3, got)

    def test_a_capitalised_turkish_word_meets_its_lower_case_form(self):
        # str.lower() maps İ to i + U+0307 and I to i, so the capital forms
        # used to miss the ledger's lower-case word
        for upper, lower in (("İSTEK", "istek"), ("KIRMIZI", "kırmızı"),
                             ("Işık", "ışık"), ("hâlâ", "hala")):
            self.assertEqual(tezgah_rank.words(upper), tezgah_rank.words(lower))
        self.assertEqual(tezgah_rank.words("INDEX Index"), ["index", "index"])
        self.assertEqual(tezgah_rank.rank("KIRMIZI", LESSONS, 3), [3])

    def test_a_query_sharing_no_word_ranks_nothing(self):
        self.assertEqual(tezgah_rank.rank("zzz qq", LESSONS, 3), [])


class LessonsCap(unittest.TestCase):
    """`max_df`, the lessons path's cap: function words and a word most of the
    ledger carries name no lesson, so a prompt about none of them ranks none."""

    LEDGER = ["the rule %d about the %s" % (i, w) for i, w in enumerate(
        ("suite", "pipe", "branch", "worktree", "manifest", "citation", "stash",
         "commit", "probe", "heredoc", "budget", "ledger"))]

    def test_a_common_word_and_a_stopword_rank_nothing_under_the_cap(self):
        q = "update the changelog about it"
        self.assertTrue(tezgah_rank.rank(q, self.LEDGER, 3))
        self.assertEqual(tezgah_rank.rank(q, self.LEDGER, 3, 0.5), [])
        self.assertEqual(tezgah_rank.rank("bunu bir daha", ["bunu bir daha yap"],
                                          3, 0.5), [])

    def test_a_topic_word_still_ranks_its_lesson(self):
        self.assertEqual(tezgah_rank.rank("pipe the suite", self.LEDGER, 3, 0.5),
                         [0, 1])

    def test_a_one_or_two_text_corpus_keeps_its_terms(self):
        # every term is in half of two texts: a 50% cap with no corpus guard
        # would drop each of them
        for texts in (["red apples"], ["red apples", "green apples"]):
            self.assertEqual(tezgah_rank.rank("apples", texts, 3, 0.5),
                             tezgah_rank.rank("apples", texts, 3))
            self.assertTrue(tezgah_rank.rank("apples", texts, 3, 0.5))


if __name__ == "__main__":
    unittest.main()
