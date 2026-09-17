"""The untrusted-content control on the hosts that share Claude's hook envelope:
hooks/tezgah_untrusted.py through hooks/projects-posttooluse.py, plus the
PostToolUse matchers in the two manifests that run it.

A result can arrive through a channel that is neither the user nor this
workspace - a fetched page, an MCP server's answer, a shell read that left the
machine - and tezgah's other surfaces never see where the text in a call came
from. The host half is two marks: the label on that result, and the taint notice
on the first effect the turn makes afterwards.
"""
import json
import os
import re
import unittest

import support
from support import TempHome, run_json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The manifests that run hooks/projects-posttooluse.py: Claude's plugin manifest
# and the copy dsh's bridge is pointed at.
MANIFESTS = {"claude": os.path.join(REPO, "hooks", "hooks.json"),
             "dsh": os.path.join(REPO, "hosts", "dsh", "hooks.json")}
# Claude's matcher dialects: a pattern made only of these characters is a list of
# exact names, anything else is an unanchored regular expression. The dsh bridge
# implements the same rule (@deepseek-ai/dsh-hook-protocol matchesMatcher), so
# both manifests are read through it here.
LITERAL = re.compile(r"^[A-Za-z0-9_\- ,|]+$")


def selects(matcher, tool):
    if LITERAL.match(matcher):
        return tool in matcher.split("|")
    return re.search(matcher, tool) is not None


class PostToolUseProvenance(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-untrusted"

    def post(self, tool, inp, session=None, event="PostToolUse", **extra):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": session or self.session, "tool_name": tool,
                   "tool_input": inp}
        payload.update(extra)
        out, proc = run_json([support.POSTTOOLUSE], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def line(self, tool, inp, **kw):
        """The one line the model reads with this result, or "" when the hook
        showed none."""
        out = self.post(tool, inp, **kw)
        return out.get("hookSpecificOutput", {}).get("additionalContext", "")

    def rows(self, session=None):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": session or self.session},
                          env=self.envv)
        return out

    def test_a_result_from_outside_is_labelled_with_its_channel(self):
        # The three channels, on the spellings the hosts actually send: Claude's
        # WebFetch/WebSearch, dsh's web_fetch/web_search, and an MCP tool on
        # either (mcp__<server>__<tool>).
        cases = [("WebFetch", {"url": "https://x"}, "a web result"),
                 ("web_fetch", {"url": "https://x"}, "a web result"),
                 ("web_search", {"query": "x"}, "a web result"),
                 ("mcp__github__get_file", {"path": "x"}, "an MCP server"),
                 ("Bash", {"command": "curl -s https://x"}, "a network read")]
        for i, (tool, inp, channel) in enumerate(cases):
            with self.subTest(tool=tool):
                text = self.line(tool, inp, session="s-label-%d" % i)
                self.assertIn("untrusted content", text)
                self.assertIn(channel, text)
                self.assertTrue(text.startswith("tezgah:"), text)
                self.assertEqual(
                    self.post(tool, inp, session="s-label-%d" % i)["hookSpecificOutput"],
                    {"hookEventName": "PostToolUse", "additionalContext": text})

    def test_a_workspace_result_wears_no_label(self):
        # The label names an exception. An ordinary result must not wear one, or
        # the model learns to skip the line, and the ledger must not claim a
        # provenance it does not have.
        cases = [("Bash", {"command": "pytest -q"}),
                 ("Bash", {"command": 'git commit -m "curl is not a read"'}),
                 ("Bash", {"command": "grep -n curl hooks/"}),
                 ("Edit", {"file_path": "/tmp/x.py"}),
                 ("Grep", {"pattern": "curl"})]
        for i, (tool, inp) in enumerate(cases):
            with self.subTest(tool=tool):
                self.assertEqual(self.line(tool, inp, session="s-plain-%d" % i), "")
        self.assertEqual([r for r in self.rows("s-plain-0") if r.get("source")], [])

    def test_an_effect_after_an_untrusted_read_is_noticed_once(self):
        # The second half of the control: an action taken in a turn that has read
        # text tezgah cannot vouch for is visible as such. The notice names the
        # turn, and the effect's own row carries the channel it inherited.
        self.post("mcp__github__get_file", {"path": "x"})
        text = self.line("Edit", {"file_path": "/tmp/x.py"})
        self.assertIn("already read an MCP server", text)
        rows = self.rows()
        self.assertEqual([(r["kind"], r.get("source")) for r in rows],
                         [("external", "mcp"), ("edit", "mcp")])
        # one notice per read: the next effect of the same turn has nothing to say
        self.assertEqual(self.line("Bash", {"command": "git status"}), "")
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("external", "mcp"), ("edit", "mcp"), ("run", None)])

    def test_a_read_is_not_an_effect_and_a_later_read_is_its_own_label(self):
        # The taint marks the sink side only: reading one channel after another
        # gets each result its own label instead of a notice about the turn.
        self.post("web_fetch", {"url": "https://x"})
        text = self.line("mcp__github__get_file", {"path": "x"})
        self.assertIn("untrusted content", text)
        self.assertIn("an MCP server", text)
        self.assertNotIn("already read", text)

    def test_a_failure_is_not_labelled(self):
        # Both lines assert a result arrived ("came from ..."), and a failed or
        # denied call has none; the row still keeps the channel the call went
        # through, which is a property of the call.
        out = self.post("WebFetch", {"url": "https://x"},
                        event="PostToolUseFailure", error="fetch failed")
        self.assertEqual(out, {})
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("external", "web")])

    def test_outside_a_root_nothing_is_shown(self):
        out = self.post("WebFetch", {"url": "https://x"}, cwd=self.home)
        self.assertEqual(out, {})

    def test_the_manifests_run_the_hook_for_the_untrusted_result_tools(self):
        # A hook the platform never calls cannot label anything: on both hosts
        # the PostToolUse group has to select the web and MCP tool names the
        # host sends, and leave an ordinary read alone.
        for host, path in sorted(MANIFESTS.items()):
            with open(path) as fh:
                groups = json.load(fh)["hooks"]["PostToolUse"]
            matchers = [g["matcher"] for g in groups if g.get("matcher")]
            for tool in ("WebFetch", "WebSearch", "web_fetch", "web_search",
                         "mcp__github__get_file"):
                self.assertTrue(any(selects(m, tool) for m in matchers),
                                "%s does not run the hook for %s" % (host, tool))
            self.assertFalse(any(selects(m, "Read") for m in matchers), host)


if __name__ == "__main__":
    unittest.main()
