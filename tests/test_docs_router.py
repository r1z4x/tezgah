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


if __name__ == "__main__":
    unittest.main()
