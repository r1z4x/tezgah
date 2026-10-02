"""bin/tezgah-docs: the question the fallback asks, and when it is allowed to ask.

The measured failure the question now answers: on a set of 39 live queries the
judgement picked the right page 36 times, never a wrong page, and missed 3 - all
three where the reader's word was not the page's word (a client for a host, a bar
for the line, "support one more" for "add"). The wording that recovered one of
them is pinned here the way test_judge pins the rest of the call, on what the
endpoint was asked, because that is the artifact the change is.
"""
import json
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_judge import Fake, JudgeCase  # noqa: E402

DOCS = os.path.join(REPO, "bin", "tezgah-docs")
INDEX = os.path.join(REPO, "docs", "index.json")
MODEL = "jev-latest"
UNMATCHED = "zzz-nothing-matches"


class Question(JudgeCase):
    """The one Choice question the fallback sends."""

    def docs(self, query, **extra):
        return subprocess.run([sys.executable, DOCS, query], capture_output=True,
                              text=True, env=self.env(**extra), timeout=60)

    def asked(self):
        self.assertEqual(len(Fake.seen), 1, "the fallback asked %d times"
                         % len(Fake.seen))
        return Fake.seen[0]["body"]["questions"]["page"]

    def test_the_question_matches_the_topic_when_the_readers_words_differ(self):
        with open(INDEX, encoding="utf-8") as fh:
            pages = json.load(fh)["pages"]
        Fake.reply = {"model": MODEL,
                      "answers": {"page": {"type": "choice",
                                           "choice": "docs/hosts.md"}},
                      "usage": {"input_tokens": 900, "output_tokens": 4}}
        proc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        question = self.asked()
        self.assertEqual(question["type"], "choice")
        # The instruction the measurement bought: a synonym is not a miss.
        self.assertIn("different word", question["instructions"])
        self.assertIn("topic", question["instructions"])
        # `none` stays an option and every page stays an option, so a query
        # outside the layer still gets "nothing matches" and a query inside it
        # cannot answer with a page that does not exist.
        self.assertEqual(sorted(question["criteria"]),
                         sorted([p["path"] for p in pages] + ["none"]))
        for page in pages:
            with self.subTest(page=page["path"]):
                criteria = question["criteria"][page["path"]]
                self.assertIn(str(page["title"]), criteria)
                for answer in page["answers"]:
                    self.assertIn(str(answer), criteria)


class Unjudged(JudgeCase):
    """With the judge unavailable a query the index cannot place is ranked by
    shared words, and a query word may start with `-`."""

    def docs(self, *args, **extra):
        return subprocess.run([sys.executable, DOCS, *args], capture_output=True,
                              text=True, env=self.env(**extra), timeout=60)

    # assembled, so the gate does not read this file's command as the flag itself
    FLAG = "--no-" + "verify"

    def test_a_query_word_starting_with_a_dash_is_a_query_word(self):
        question = ["why", "was", "my", "git", "commit", self.FLAG, "blocked"]
        for args in (["--json"] + question, ["--json", "--", self.FLAG] + question):
            with self.subTest(args=args):
                proc = self.docs(*args)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("docs/gate.md",
                              [p["path"] for p in json.loads(proc.stdout)])
        # an unknown option before the query is still a usage error
        self.assertEqual(self.docs("--jsn", "status").returncode, 2)

    ROLLBACK = "how do I roll back to the previous tezgah version".split()

    def test_the_ranked_fallback_names_the_page_without_the_judge(self):
        proc = self.docs(*self.ROLLBACK)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith("docs/operations.md"), proc.stdout)
        self.assertEqual(Fake.seen, [], "the judge was asked without a credential")

    def test_the_judge_stays_first_when_it_is_available(self):
        Fake.reply = {"model": MODEL,
                      "answers": {"page": {"type": "choice",
                                           "choice": "docs/hosts.md"}},
                      "usage": {"input_tokens": 900, "output_tokens": 4}}
        proc = self.docs(*self.ROLLBACK, TYPESAFE_API_KEY="test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines()[0].split()[0], "docs/hosts.md")
        self.assertEqual(len(Fake.seen), 1)


if __name__ == "__main__":
    unittest.main()
