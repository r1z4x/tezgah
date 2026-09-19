"""The untrusted-content control on the hosts that share Claude's hook envelope:
hooks/tezgah_untrusted.py through hooks/projects-posttooluse.py, plus the
PostToolUse matchers in the two manifests that run it.

A result can arrive through a channel that is neither the user nor this
workspace - a fetched page, an MCP server's answer, a shell read that left the
machine, or the tier's own answer (`bin/consult`, `bin/codegen`, a model on the
far side of the network) - and tezgah's other surfaces never see where the text
in a call came from. The host half is two marks: the label on that result, and
the taint notice on the first effect the turn makes afterwards.
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

    def refuse(self, tool, inp, session=None):
        """The gate's reason for this call, or None when it passes."""
        out, proc = run_json([support.PROBE_GATE],
                             {"tool": tool, "input": inp, "cwd": self.repo,
                              "session_id": session or self.session},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_a_result_from_outside_is_labelled_with_its_channel(self):
        # Three of the channels, on the spellings the hosts actually send: Claude's
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

    def test_the_tiers_own_answer_is_an_outside_channel(self):
        # bin/consult and bin/codegen read their answer from a model over the
        # network: third-party text by construction, and the same outside channel
        # `curl` to that endpoint is - `--online` folds live web results into the
        # same reply. A program reached by name is how tezgah's own tier is run,
        # and it used to arrive unlabelled with no `source` on its row.
        cases = ('consult "q"',
                 '~/.config/tezgah/bin/consult --online "q"',
                 './bin/codegen "task" --files a.py')
        for i, cmd in enumerate(cases):
            with self.subTest(cmd=cmd):
                text = self.line("Bash", {"command": cmd}, session="s-tier-%d" % i)
                self.assertIn("untrusted content", text)
                self.assertIn("an external model answer", text)
                self.assertEqual(
                    [r.get("source") for r in self.rows("s-tier-%d" % i)], ["tier"])

    def test_naming_the_tier_is_not_running_it(self):
        # The same reader the status line uses to decide a shell command really
        # ran consult, so a grep, a sed and a commit message that name the tool
        # are ordinary results and the ledger claims no provenance for them.
        for i, cmd in enumerate(('grep -n consult hooks/',
                                 'sed -n 26,38p bin/codegen',
                                 'git commit -m "consult is not a run"')):
            with self.subTest(cmd=cmd):
                self.assertEqual(
                    self.line("Bash", {"command": cmd}, session="s-mention-%d" % i), "")

    def test_asking_the_tier_for_its_usage_is_not_a_read_of_a_model(self):
        # `consult --help` runs the program but reaches no model: it prints its
        # usage and exits. Calling that an external answer tainted the turn, and
        # every write after it waited on a consent the user gives for a help
        # screen - measured on a live turn before this rule existed.
        for i, cmd in enumerate(('consult --help',
                                 'bin/consult -h',
                                 '~/.config/tezgah/bin/codegen --help',
                                 'consult')):
            with self.subTest(cmd=cmd):
                session = "s-help-%d" % i
                self.assertEqual(self.line("Bash", {"command": cmd}, session=session), "")
                self.assertEqual([r for r in self.rows(session) if r.get("source")], [])

    def test_a_write_after_a_help_invocation_is_not_held(self):
        # The same case read at the sink: no channel was read, so the gate's
        # sink rule has nothing to hold the next write for.
        self.post("Bash", {"command": "bin/consult --help"})
        self.assertIsNone(
            self.refuse("Write", {"file_path": os.path.join(self.home, "out.py"),
                                  "content": "x = 1\n"}))

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

    def test_a_consult_taints_the_turn_like_any_other_read(self):
        # An answer from the tier is the same kind of read, so the effect after
        # it wears the same notice and its own row carries the channel.
        self.post("Bash", {"command": 'consult "q"'})
        text = self.line("Edit", {"file_path": os.path.join(self.repo, "a.py")})
        self.assertIn("already read an external model answer", text)
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("run", "tier"), ("edit", "tier")])

    def test_a_write_outside_the_workspace_waits_for_the_user_after_a_consult(self):
        """What the next write in a turn that consulted costs.

        The gate's sink rule reads the channel off the same rows, so an effect
        that leaves this workspace is refused until the user's own approval is
        on the ledger: consulting buys a consent ask, not a label the model may
        read past. A write inside the root is left to the notice - the snapshot
        already keeps those bytes - and that half is asserted here too, so the
        cost of the channel is bounded and visible rather than assumed."""
        self.post("Bash", {"command": 'consult "q"'})
        reason = self.refuse("Write", {"file_path": os.path.join(self.home, "out.py"),
                                       "content": "x = 1\n"})
        self.assertIsNotNone(reason)
        self.assertIn("an external model answer", reason)
        self.assertIsNone(
            self.refuse("Write", {"file_path": os.path.join(self.repo, "in.py"),
                                  "content": "x = 1\n"}))

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
