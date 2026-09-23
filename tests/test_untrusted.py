"""The untrusted-content control on the hosts that share Claude's hook envelope:
hooks/tezgah_untrusted.py through hooks/projects-posttooluse.py, plus the
PostToolUse matchers in the two manifests that run it.

A result can arrive through a channel that is neither the user nor this
workspace - a fetched page, an MCP server's answer, a shell read that left the
machine, or the tier's own answer (`bin/consult`, `bin/codegen`, a model on the
far side of the network) - and tezgah's other surfaces never see where the text
in a call came from. The host half is two marks: the label on that result, and
the taint notice on the first effect the turn makes afterwards.

Both marks are asked per user turn, so the ledger read behind them is scoped to
the turn (hooks/tezgah_integrity.turn_rows); its equality with the whole-ledger
slice and its price are pinned in-process at the end, which is what a host's
envelope cannot show.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import support
from support import TempHome, run_json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402
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

    def turn(self, prompt, session=None):
        """The user-turn marker, written the way the prompt path writes it: the
        row every turn-scoped reader starts after."""
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "note_turn", "session": session or self.session,
                              "prompt": prompt}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

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

    def test_a_stale_turn_s_read_is_not_this_turn_s(self):
        # The turn marker bounds the read, so a page the *previous* turn fetched
        # and never spent is not this turn's: inheriting it would hold this
        # turn's first effect for content it never saw, and name the wrong
        # channel while doing it.
        self.post("mcp__github__get_file", {"path": "old"})
        self.turn("the first prompt")
        self.post("web_fetch", {"url": "https://x"})
        text = self.line("Edit", {"file_path": "/tmp/x.py"})
        self.assertIn("already read a web result", text)
        self.assertNotIn("an MCP server", text)
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("external", "mcp"), ("turn", None),
                          ("external", "web"), ("edit", "web")])

    def test_a_stale_turn_s_taint_does_not_reach_the_next_one(self):
        # A channel an earlier turn read and never spent is not pending here: a
        # turn-scoped read starts at the marker, so this turn's first effect is
        # ordinary and its row carries no channel. Reading the ledger whole would
        # hold this turn's write for a curl the last turn ran - the false
        # positive the whole-ledger read was rejected for.
        self.post("Bash", {"command": "curl -s https://x"})
        self.turn("the first prompt")
        self.assertEqual(self.line("Edit", {"file_path": "/tmp/x.py"}), "")
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("run", "network"), ("turn", None), ("edit", None)])

    def test_a_ledger_with_no_turn_marker_reads_whole(self):
        # Hosts that never fire the prompt path leave a ledger with no marker;
        # the turn is the whole of it, which is the answer the whole-ledger read
        # gave and the one this must keep giving.
        self.post("web_fetch", {"url": "https://x"})
        self.assertIn("already read a web result",
                      self.line("Edit", {"file_path": "/tmp/x.py"}))
        self.assertEqual([(r["kind"], r.get("source")) for r in self.rows()],
                         [("external", "web"), ("edit", "web")])

    def test_the_taint_is_spent_in_its_own_turn_only(self):
        # The first effect row spends the channel, and the next turn starts with
        # nothing owed: the marker is where the spend stops as well as where the
        # read starts.
        self.turn("the first prompt")
        self.post("mcp__github__get_file", {"path": "x"})
        self.assertIn("already read an MCP server",
                      self.line("Edit", {"file_path": "/tmp/x.py"}))
        self.assertEqual(self.line("Bash", {"command": "git status"}), "")
        self.turn("the next prompt")
        self.assertEqual(self.line("Edit", {"file_path": "/tmp/y.py"}), "")

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


class TurnRows(unittest.TestCase):
    """turn_rows: the turn-scoped ledger read `turn_channel` asks with.

    In-process with `_path` patched, the way test_integrity's ledger tests read
    a throwaway ledger: the equality with the whole-ledger slice and the price of
    the read are properties of the reader, and neither is visible from a host's
    envelope, which is all the class above can see."""

    # Long enough that parsing it all would dominate the numbers asserted below,
    # short enough that building it stays cheap.
    PREFIX = 4000

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "%s.jsonl" % session)

    def path(self, session):
        return ti._path(session)

    def seed(self, session, rows):
        for kind, detail in rows:
            ti.note(session, kind, detail)

    def whole(self, session):
        """The rows from the current turn's start, read the way `events` reads
        them: the answer `turn_rows` has to reproduce for every ledger."""
        rows = ti.events(session)
        return rows[ti._turn_start(rows):]

    def test_a_turn_scoped_read_is_the_whole_ledger_s_own_slice(self):
        # The shapes a ledger takes: no marker at all, one, several with rows on
        # both sides, a marker with nothing after it, and a row whose `detail`
        # carries the marker's text - escaped by the row's own serialization, so
        # a scan on the text alone must not start the turn there.
        ledgers = (
            [("run", "make"), ("external", "web")],
            [("turn", "abc"), ("run", "make"), ("external", "mcp")],
            [("run", "old"), ("turn", "abc"), ("external", "web"),
             ("edit", "a.py"), ("turn", "def"), ("run", "make")],
            [("run", "make"), ("turn", "abc")],
            [("run", '{"kind": "turn"}'), ("turn", "abc"), ("external", "web")],
        )
        for i, ledger in enumerate(ledgers):
            with self.subTest(ledger=i):
                session = "s%d" % i
                self.seed(session, ledger)
                self.assertEqual(ti.turn_rows(session), self.whole(session))
        # the last shape is the interesting one: the marker's text is in a row of
        # its own, and the turn still starts at the real marker
        self.assertEqual([r.get("kind") for r in ti.turn_rows("s4")],
                         ["external"])

    def test_a_half_written_marker_line_is_not_a_turn(self):
        # A killed process leaves half a line, and the marker's text can be in
        # it. The line is not a row - `events` drops it - so a scan that treated
        # its text as a marker would start the turn past the end of the ledger
        # and answer about a turn with nothing in it.
        self.seed("s", [("turn", "abc"), ("run", "make")])
        with open(self.path("s"), "a") as fh:
            fh.write('{"kind": "turn"')
        self.assertEqual(ti.turn_rows("s"), self.whole("s"))
        self.assertEqual([r.get("detail") for r in ti.turn_rows("s")], ["make"])

    def test_only_the_current_turn_is_parsed(self):
        # The price: the file is read whole, but the JSON parse starts after the
        # newest marker, so a turn-scoped question costs the length of the turn
        # and not the length of the session.
        for i in range(self.PREFIX):
            ti.note("s", "run", "cmd %d" % i, id="a%d" % i, exit=0)
        ti.note("s", "turn", "abc")
        ti.note("s", "run", "make", id="b0", exit=0)
        parsed = []
        real = ti._parse

        def counting(lines):
            parsed.append(len(lines))
            return real(lines)

        with mock.patch.object(ti, "_parse", counting):
            rows = ti.turn_rows("s")
        self.assertEqual([r.get("id") for r in rows], ["b0"])
        self.assertLess(sum(parsed), self.PREFIX // 10,
                        "a turn-scoped read parsed the whole ledger")


if __name__ == "__main__":
    unittest.main()
