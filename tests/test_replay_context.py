"""The context replay harness (tests/replay_context.py) on a seeded fixture:
two fake transcripts, one per host, in a throwaway HOME."""
import json
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import replay_context as rc  # noqa: E402

HOOKS = os.path.join(rc.HERE, "hooks")
PROMPTS = ["fix the failing test in the parser",
           "run an experiment to test the hypothesis that caching helps",
           "refactor the config loader, keep it minimal",
           "don't touch the release script; ask before pushing",
           "what is left?"]


def jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n")


def fixture(home, seed=56):
    """One omp and one Claude session under ~/Projects/demo, prompts drawn with
    a fixed seed; each carries one harness injection, one tool result and one
    compaction, which the replay must skip, skip and count."""
    rng = random.Random(seed)
    cwd = os.path.join(home, "Projects", "demo")
    picks = [rng.choice(PROMPTS) for _ in range(6)]
    omp = [{"type": "session", "id": "omp-1", "cwd": cwd}]
    omp += [{"type": "message", "message": {"role": "user", "content": [
        {"type": "text", "text": p}]}} for p in picks[:3]]
    omp += [{"type": "message", "message": {"role": "user", "content": "<system-reminder>x"}},
            {"type": "message", "message": {"role": "toolResult", "toolName": "edit"}},
            {"type": "compaction", "summary": "s"}]
    omp += [{"type": "message", "message": {"role": "user", "content": p}} for p in picks[3:]]
    jsonl(os.path.join(home, ".omp", "agent", "sessions", "d", "a.jsonl"), omp)
    claude = [{"type": "user", "sessionId": "cl-1", "cwd": cwd,
               "message": {"role": "user", "content": p}} for p in picks[:3]]
    claude += [{"type": "user", "sessionId": "cl-1", "cwd": cwd, "message": {
                   "role": "user", "content": [{"type": "tool_result", "tool_use_id": "t"}]}},
               {"type": "user", "sessionId": "cl-1", "cwd": cwd, "isCompactSummary": True,
                "message": {"role": "user", "content": "This session is being continued"}}]
    claude += [{"type": "user", "sessionId": "cl-1", "cwd": cwd,
                "message": {"role": "user", "content": p}} for p in picks[3:]]
    jsonl(os.path.join(home, ".claude", "projects", "d", "b.jsonl"), claude)


class Replay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)
        fixture(self.home)
        with mock.patch.dict(os.environ, {"HOME": self.home}):
            self.sessions = rc.mine("all", os.path.join(self.home, "Projects"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_mine_reads_both_hosts_and_skips_injections(self):
        self.assertEqual([(s["host"], s["id"]) for s in self.sessions],
                         [("omp", "omp-1"), ("claude", "cl-1")])
        for s in self.sessions:
            self.assertEqual([e[0] for e in s["events"]], ["prompt"] * 3 + ["compact"]
                             + ["prompt"] * 3)

    def test_same_tree_twice_gives_ratio_one_and_real_bytes(self):
        got = rc.compare(self.sessions, HOOKS, HOOKS, self.home)
        self.assertEqual((got["n"], got["prompts"], got["compactions"]), (2, 12, 2))
        self.assertGreater(got["base"]["median"], 1000)  # reminder x6 at least
        self.assertEqual(got["base"], got["head"])
        self.assertEqual(got["ratio"], {"median": 1.0, "p90": 1.0, "total": 1.0})

    def test_stats(self):
        self.assertEqual(rc.stats([5, 1, 3, 2]), {"median": 2.5, "p90": 5, "total": 11})
        self.assertEqual(rc.stats(list(range(1, 11)))["p90"], 9)


if __name__ == "__main__":
    unittest.main()
