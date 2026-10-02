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
import tezgah_rank  # noqa: E402

LESSONS = [
    "never pipe a test run into tail; write it to a file and read it",
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
        # `kırmızı`, `satırını` keep their dotless ı: a tokenizer that split on
        # it would leave `rm`/`z` fragments and rank nothing
        got = tezgah_rank.rank("citation satırını kaydırmam lazım, test kırmızı",
                               LESSONS, 3)
        self.assertEqual(got[0], 3, got)

    def test_a_query_sharing_no_word_ranks_nothing(self):
        self.assertEqual(tezgah_rank.rank("zzz qq", LESSONS, 3), [])


if __name__ == "__main__":
    unittest.main()
