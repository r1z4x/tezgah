"""hooks/tezgah_clarity.py: the clarity ratchet over the English docs.

Pinned on the cases the research line's review found or named: a code span broken
across lines must count 0 (the K6 correction), code fences and Turkish lines are
never read, a file grows no count past its baseline, and the committed baseline
holds for the tree as it stands.
"""
import json
import os
import sys
import tempfile
import unittest

import support

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_clarity as tc  # noqa: E402

LONG = ("This sentence keeps going with one plain word after another until it has "
        "far more than twenty five words in it, which the ratchet must count as one.")


def counts(text):
    return tc.measure(text)[0]


class Measure(unittest.TestCase):
    def test_a_code_span_broken_across_lines_counts_zero(self):
        text = ("Run `a; b is verified\nin order to; ensure` now.\n\n"
                "The flag ``x; `y`\nwas utilized; z`` stays.\n")
        self.assertEqual(counts(text), dict.fromkeys(tc.RULES, 0))

    def test_a_code_fence_is_ignored(self):
        text = "Plain words.\n\n```sh\nfoo; bar  # %s it was verified\n```\n" % LONG
        self.assertEqual(counts(text), dict.fromkeys(tc.RULES, 0))

    def test_turkish_text_is_ignored(self):
        text = ("Bu cümle uzun; çok uzun ve %s ensure edilir, verify edilmiş.\n" % LONG)
        self.assertEqual(counts(text), dict.fromkeys(tc.RULES, 0))

    def test_each_rule_counts_in_english_prose(self):
        text = "%s\n\nIt was checked; we ensure it.\n" % LONG
        self.assertEqual(counts(text), {"long_sentences": 1, "semicolons": 1,
                                        "replace_words": 1, "passive": 1})


class Ratchet(unittest.TestCase):
    def tree(self, page, baseline):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        os.mkdir(os.path.join(root, "docs"))
        with open(os.path.join(root, "docs", "page.md"), "w", encoding="utf-8") as fh:
            fh.write(page)
        if baseline is not None:
            tc.save(os.path.join(root, tc.BASELINE), baseline)
        return root

    def run_report(self, root, update=False):
        lines = []
        code = tc.report(root, update=update, out=lines.append)
        with open(os.path.join(root, tc.BASELINE), encoding="utf-8") as fh:
            return code, lines, json.load(fh)

    def test_a_new_long_sentence_over_the_baseline_fails(self):
        base = {"docs/page.md": dict.fromkeys(tc.RULES, 0)}
        code, lines, after = self.run_report(self.tree("Short.\n\n%s\n" % LONG, base))
        self.assertEqual(code, 1)
        self.assertIn("docs/page.md:3  long_sentences", "\n".join(lines))
        self.assertEqual(after, base)  # a failing run never raises the baseline

    def test_a_file_absent_from_the_baseline_is_held_to_zero(self):
        code, _, _ = self.run_report(self.tree("It was checked.\n", {}))
        self.assertEqual(code, 1)

    def test_a_dropped_count_is_lowered_and_only_update_raises(self):
        base = {"docs/page.md": {"long_sentences": 3, "semicolons": 0,
                                 "replace_words": 0, "passive": 0}}
        root = self.tree("%s\n" % LONG, base)
        code, _, after = self.run_report(root)
        self.assertEqual((code, after["docs/page.md"]["long_sentences"]), (0, 1))
        with open(os.path.join(root, "docs", "page.md"), "a", encoding="utf-8") as fh:
            fh.write("\n%s\n\n%s\n" % (LONG, LONG))
        self.assertEqual(self.run_report(root)[0], 1)
        code, _, after = self.run_report(root, update=True)
        self.assertEqual((code, after["docs/page.md"]["long_sentences"]), (0, 3))
        self.assertEqual(self.run_report(root)[0], 0)

    def test_the_tree_as_it_stands_holds_its_baseline(self):
        measured = tc.tree(support.REPO)
        baseline = tc.load(os.path.join(support.REPO, tc.BASELINE))
        self.assertEqual(tc.over(measured, baseline), [])


if __name__ == "__main__":
    unittest.main()
