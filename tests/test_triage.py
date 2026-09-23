"""bin/tezgah-triage: the flattening, the selection and the printed arithmetic.

The snapshot is a fixed fixture written into a temp HOME and the judgement comes
from the loopback endpoint test_judge stands up, so a case pins the line numbers
and the printed ids instead of whatever a real screen happened to contain. The
`Fake` (and the temp-HOME harness) is shared with that module on purpose: a
second copy of an endpoint stub would be a second thing to keep in step.
"""
import json
import os
import re
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_judge import DOCS, UNMATCHED, Fake, JudgeCase  # noqa: E402

TRIAGE = os.path.join(REPO, "bin", "tezgah-triage")
MODEL = "jev-latest"
# A snapshot as the MCP tool returns it, with a blank line and a fence that the
# flattening must drop. The row is written the way a real table comes back - its
# two buttons are siblings inside one cell - because that is the shape the
# per-line selection was measured losing: the unit that holds the cell holds both
# buttons, so a judgement cannot keep one and drop the other.
SNAPSHOT = [
    "- generic [ref=e1]:",
    '  - heading "Payouts" [level=1] [ref=e2]',
    '  - combobox "Status" [ref=e3]:',
    '    - option "All" [selected]',
    '  - button "Apply filters" [ref=e4]',
    "  - table [ref=e5]:",
    "    - row [ref=e6]:",
    '      - cell "failed" [ref=e7]',
    "      - cell [ref=e8]:",
    '        - button "Retry" [ref=e9]',
    '        - button "Delete" [ref=e10]',
    "  - footer:",
]
# 1-based ids in the flattened snapshot (the four header lines the result carries,
# then SNAPSHOT, then the closing fence), and the twelve units `select` asks about:
# the seven lines the tree does not mark standing alone, the combobox with its
# options, the lone button, the row with its cell and both buttons, and the footer.
LINES = len(SNAPSHOT) + 5
UNITS = 12
COMBOBOX_UNIT = 7
ROW_UNIT = 10
COMBOBOX = 7
FILTER = 9
ROW = 11
RETRY = 14
DELETE = 15
STATES = 13
# The one Choice that answers focus and active together, so 13 states travel as 12
# questions.
INTERACTIVE = "interactive"
TABLE = 10
TABLE_SPAN = 6


def mcp_result(body):
    return json.dumps({"content": [{"type": "text", "text": body}]})


def snapshot_text():
    return ("### Page\n- Page URL: http://127.0.0.1:8931/\n\n"
            "### Snapshot\n```yaml\n" + "\n".join(SNAPSHOT) + "\n```\n")


def answer_asking_for(keys, choice="neither"):
    """A reply function: 0.9 for the named question ids, 0.05 for the rest, and -
    for the one Choice - the option named, with its whole probability."""
    def reply(body):
        answered = {}
        for key, question in body["questions"].items():
            if question["type"] == "choice":
                answered[key] = {"type": "choice", "choice": choice,
                                 "probabilities": {choice: 0.9}, "confidence": 0.9}
            else:
                answered[key] = {"type": "noul", "noul": 0.9 if key in keys else 0.05}
        return {"model": MODEL, "answers": answered,
                "usage": {"input_tokens": 500, "output_tokens": 40}}
    return reply


def state_row(stdout, name):
    """The printed table row for one state as (value, shown), or None."""
    for line in stdout.splitlines():
        m = re.match(r"^  (\S+)\s+([\d.]+)\s+(shown|not shown)$", line)
        if m and m.group(1) == name:
            return float(m.group(2)), m.group(3) == "shown"
    return None


class TriageCase(JudgeCase):
    def write(self, name, text):
        path = os.path.join(self.home, name)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def snapshot_file(self, name="snapshot.json", body=None):
        return self.write(name, mcp_result(snapshot_text() if body is None else body))

    def triage(self, *args, **extra):
        return subprocess.run([sys.executable, TRIAGE] + list(args),
                              capture_output=True, text=True, timeout=60,
                              env=self.env(**extra))

    def docs(self, *args, **extra):
        return subprocess.run([sys.executable, DOCS] + list(args),
                              capture_output=True, text=True, timeout=60,
                              env=self.env(**extra))

    def judged(self, *args, **extra):
        return self.triage(*args, TYPESAFE_API_KEY="test", **extra)


class Select(TriageCase):
    def test_the_selected_unit_brings_every_line_under_it(self):
        # The row and the combobox are chosen; the lone button is not. The caller
        # gets the row's cell and BOTH of its buttons - the sibling a per-line
        # judgement was measured dropping - and the rule's own reply is what the
        # two rows print.
        Fake.reply_fn = answer_asking_for({str(COMBOBOX_UNIT), str(ROW_UNIT)})
        proc = self.judged("--select", self.snapshot_file(), "--task",
                           "find the control that retries a failed payout")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("selected 2 of %d units, 7 of %d lines" % (UNITS, LINES),
                      proc.stdout)
        self.assertIn("#%d" % COMBOBOX, proc.stdout)
        self.assertIn("ref=e3", proc.stdout)
        self.assertIn("#%d" % ROW, proc.stdout)
        self.assertIn("ref=e6", proc.stdout)
        self.assertIn("#%d" % RETRY, proc.stdout)
        self.assertIn("ref=e9", proc.stdout)
        self.assertIn("#%d" % DELETE, proc.stdout)
        self.assertIn("ref=e10", proc.stdout)
        self.assertNotIn("#%d" % FILTER, proc.stdout)
        self.assertIn("not selected: %d lines" % (LINES - 7), proc.stdout)

    def test_a_unit_is_one_question_and_the_tree_decides_its_lines(self):
        Fake.reply_fn = answer_asking_for({str(COMBOBOX_UNIT)})
        self.judged("--select", self.snapshot_file(), "--task", "the filters")
        self.assertEqual(len(Fake.seen), 1, "more than one request went out")
        body = Fake.seen[0]["body"]
        # One question per unit, not per line: every line is in exactly one unit,
        # and the row's two buttons are in the same one rather than in two.
        self.assertEqual(sorted(body["questions"]),
                         sorted(str(k) for k in range(1, UNITS + 1)))
        self.assertIn(": the filters", body["state"])
        for line in SNAPSHOT:
            self.assertIn(line, body["state"])
        row_unit = body["state"].split("%d: " % ROW_UNIT)[1]
        self.assertIn('cell "failed"', row_unit)
        self.assertIn('button "Retry"', row_unit)
        self.assertIn('button "Delete"', row_unit)
        # The combobox keeps its options, and the footer the tree does not mark
        # still reaches the judgement as a unit of its own.
        self.assertIn('option "All"', body["state"].split("%d: " % COMBOBOX_UNIT)[1])
        self.assertIn("footer", body["state"])

    def test_the_arithmetic_is_printed_from_the_reported_usage(self):
        Fake.reply_fn = answer_asking_for({str(COMBOBOX_UNIT)})
        proc = self.judged("--select", self.snapshot_file(), "--task", "the filters")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # 500 input tokens at $0.042 per 1M, the characters of the lines the caller
        # may now skip, and the recall the shape was measured at.
        self.assertIn("$0.000021 at $0.042/1M input", proc.stdout)
        self.assertIn("500 input tokens", proc.stdout)
        self.assertIn("the caller may skip", proc.stdout)
        self.assertIn("measured: 100% of the control lines at a 94% read",
                      proc.stdout)

    def test_the_text_flat_shapes_of_the_snapshot_are_read_the_same(self):
        Fake.reply_fn = answer_asking_for({str(COMBOBOX_UNIT)})
        held = self.snapshot_file()
        as_string = self.write("string.json", json.dumps(snapshot_text()))
        as_text = self.write("snapshot.txt", snapshot_text())
        # Everything but the judge line, whose millisecond reading is a property
        # of the run rather than of the input shape.
        outputs = [self.judged("--select", path, "--task", "x").stdout.split("judge:")[0]
                   for path in (held, as_string, as_text)]
        self.assertEqual(len(set(outputs)), 1, "the input shape changed the reading")
        self.assertIn("selected 1 of %d units, 2 of %d lines" % (UNITS, LINES),
                      outputs[0])


class States(TriageCase):
    def test_a_component_span_runs_to_the_end_of_its_subtree(self):
        Fake.reply_fn = answer_asking_for({"default", "error"})
        proc = self.judged("--states", self.snapshot_file(),
                           "--component", "#%d" % TABLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # The table and the three lines indented under it, no further.
        self.assertIn("lines %d-%d," % (TABLE, TABLE + TABLE_SPAN - 1), proc.stdout)
        body = Fake.seen[0]["body"]
        # One question per state, except the interactive pair: focus and active
        # travel as the single Choice the body carries beside the eleven nouls.
        self.assertEqual(sorted(set(body["questions"]) - {INTERACTIVE}),
                         sorted(["default", "hover", "disabled", "loading", "error",
                                 "empty", "skeleton", "offline", "partial",
                                 "long-text", "permission-denied"]))
        self.assertEqual(len(body["questions"]), STATES - 1)
        self.assertIn('row [ref=e6]', body["state"])
        self.assertNotIn('"Payouts"', body["state"], "the subtree includes the heading")
        self.assertIn("0.90  shown", proc.stdout)
        self.assertIn("not shown: 11 of 13", proc.stdout)
        self.assertIn("error", proc.stdout.split("not shown:")[0])

    def test_the_whole_screen_is_the_default_component(self):
        Fake.reply_fn = answer_asking_for({"default"})
        proc = self.judged("--states", self.snapshot_file())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("lines 1-%d," % LINES, proc.stdout)
        self.assertIn("not shown: 12 of 13", proc.stdout)

    def test_a_component_no_line_matches_is_misuse(self):
        proc = self.judged("--states", self.snapshot_file(), "--component", "zzz")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no line matches", proc.stderr)
        self.assertEqual(Fake.seen, [])

    def test_every_state_question_carries_what_counts_as_shown(self):
        # The wording alone was measured answering about the wrong lines (a form
        # called disabled because a child button was), so what counts as shown
        # travels with the question: [disabled] stands on the component's own line,
        # a child is not the component, and every state but the pair is one noul.
        Fake.reply_fn = answer_asking_for({"default"})
        self.judged("--states", self.snapshot_file(), "--component", "#%d" % TABLE)
        questions = Fake.seen[0]["body"]["questions"]
        self.assertEqual(len(questions), STATES - 1)
        for name, question in questions.items():
            if name == INTERACTIVE:
                continue
            with self.subTest(name=name):
                self.assertEqual(question["type"], "noul")
                self.assertTrue(question["criteria"]["true"])
                self.assertEqual(question["criteria"]["false"], "it is not")
        self.assertIn("[disabled]", questions["disabled"]["criteria"]["true"])
        self.assertIn("child", questions["disabled"]["criteria"]["true"])

    def test_the_interactive_pair_is_one_choice_of_three(self):
        # focus and active share one bit of evidence - [active] marks the element
        # that has focus, and the snapshot has no marker for a press - so they are
        # asked once, as a Choice whose option IS the verdict, instead of as two
        # nouls that can both come back high over the same bit.
        Fake.reply_fn = answer_asking_for(set(), choice="pressed")
        proc = self.judged("--states", self.snapshot_file(),
                           "--component", "#%d" % TABLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        questions = Fake.seen[0]["body"]["questions"]
        self.assertNotIn("focus", questions, "the noul it replaced is gone")
        self.assertNotIn("active", questions, "the noul it replaced is gone")
        question = questions[INTERACTIVE]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(sorted(question["criteria"]),
                         ["focus", "neither", "pressed"])
        self.assertIn("[active]", question["criteria"]["focus"])
        self.assertIn("[pressed]", question["criteria"]["pressed"])
        # The option that came back is the verdict, and the probability beside it
        # is what the row prints.
        self.assertEqual(state_row(proc.stdout, "active"), (0.9, True))
        self.assertEqual(state_row(proc.stdout, "focus"), (0.0, False))
        self.assertIn("not shown: 12 of 13", proc.stdout)

    def test_the_pair_reads_the_option_that_came_back(self):
        for taken, wanted in (
                ("focus", {"focus": (0.9, True), "active": (0.0, False)}),
                ("neither", {"focus": (0.0, False), "active": (0.0, False)})):
            with self.subTest(taken=taken):
                Fake.reply_fn = answer_asking_for(set(), choice=taken)
                proc = self.judged("--states", self.snapshot_file(),
                                   "--component", "#%d" % TABLE)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                for name, want in wanted.items():
                    self.assertEqual(state_row(proc.stdout, name), want)

    def test_a_pair_answer_of_the_wrong_shape_claims_neither_state(self):
        # A reply that answers the Choice question with a noul took no option, so
        # neither state is claimed rather than the run crashing or guessing one.
        Fake.reply_fn = lambda body: {
            "model": MODEL,
            "answers": {key: {"type": "noul", "noul": 0.9}
                        for key in body["questions"]},
            "usage": {"input_tokens": 500, "output_tokens": 40}}
        proc = self.judged("--states", self.snapshot_file(),
                           "--component", "#%d" % TABLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(state_row(proc.stdout, "focus"), (0.0, False))
        self.assertEqual(state_row(proc.stdout, "active"), (0.0, False))

    def test_the_states_an_aria_snapshot_cannot_carry_are_printed_apart(self):
        # hover, active, skeleton, long-text and default have no marker in an aria
        # snapshot - measured on a driven fixture - so the caller is told which
        # five its verdicts are not evidence for, whichever way they went: a
        # "shown" among them is as unsupported as a "not shown", and the workflow
        # reads the first as a state present.
        # active is now answered by the pair's Choice, so it is asked for there;
        # the other four are nouls.
        Fake.reply_fn = answer_asking_for({"default", "hover", "skeleton",
                                           "long-text"}, choice="pressed")
        proc = self.judged("--states", self.snapshot_file(),
                           "--component", "#%d" % TABLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("not shown: 8 of 13", proc.stdout)
        self.assertIn("unmarked: default, hover, active, skeleton, long-text",
                      proc.stdout)


class Fallbacks(TriageCase):
    def test_no_credential_exits_1_without_calling_out(self):
        proc = self.triage("--select", self.snapshot_file(), "--task", "x")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no judgement", proc.stderr)
        self.assertIn("read the snapshot yourself", proc.stderr)
        self.assertEqual(Fake.seen, [])

    def test_the_kill_switch_exits_1(self):
        self.switch("judge-off")
        proc = self.judged("--select", self.snapshot_file(), "--task", "x")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("judge-off", proc.stderr)
        self.assertEqual(Fake.seen, [])

    def test_the_triage_switch_exits_1_and_leaves_the_docs_judging(self):
        # The bug a per-caller switch introduces, in this direction: `triage-off`
        # answers for the triage alone, so the fallback `bin/tezgah-docs` shares
        # keeps working - a switch that silently took the other caller with it
        # would read as a working switch until a docs query came back empty.
        self.switch("triage-off")
        proc = self.judged("--select", self.snapshot_file(), "--task", "x")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("triage-off", proc.stderr)
        self.assertEqual(Fake.seen, [], "triage-off did not stop the call")
        Fake.reply_fn = answer_asking_for(set(), choice="docs/gate.md")
        doc = self.docs(UNMATCHED, TYPESAFE_API_KEY="test")
        self.assertEqual(doc.returncode, 0, doc.stderr)
        self.assertIn("docs/gate.md", doc.stdout)
        self.assertEqual(len(Fake.seen), 1, "the docs caller was silenced too")

    def test_a_failed_call_exits_1_and_names_the_call(self):
        Fake.status = 500
        proc = self.judged("--select", self.snapshot_file(), "--task", "x")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("the call failed", proc.stderr)

    def test_misuse_is_told_apart_from_a_failed_judgement(self):
        for args in ([], ["--select", self.snapshot_file()],
                     ["--states", self.snapshot_file(), "--task", "x"],
                     ["--select", os.path.join(self.home, "nope.json"), "--task", "x"],
                     ["--select", self.snapshot_file(), "--task", "x", "--component", "y"],
                     ["--select", self.snapshot_file(), "--task", "x", "--what"]):
            with self.subTest(args=args):
                self.assertEqual(self.judged(*args).returncode, 2)


class JudgeCost(TriageCase):
    """J4: one `judge` ledger row per paid call, in the shape the counters fold on.

    Read off the ledger rather than off a counter, so the row's own contract is
    what these cases pin: kind `judge`, and the detail naming the caller, the model
    and the arithmetic - a row counted by kind cannot be gamed by a command that
    merely mentions the caller, which is the bug a `detail` substring count has."""

    SHAPE = r"^tezgah-triage jev-latest in=500 out=40 ms=\d+$"

    def test_each_mode_writes_one_judge_row_with_its_cost(self):
        Fake.reply_fn = answer_asking_for({str(COMBOBOX_UNIT)})
        picked = self.judged("--select", self.snapshot_file(),
                             "--task", "the filters", TEZGAH_SESSION="s-j4")
        shown = self.judged("--states", self.snapshot_file(),
                            "--component", "#%d" % TABLE, TEZGAH_SESSION="s-j4")
        self.assertEqual((picked.returncode, shown.returncode), (0, 0),
                         shown.stderr)
        rows = self.ledger()
        self.assertEqual(len(rows), 2, rows)
        for row in rows:
            with self.subTest(detail=row.get("detail")):
                self.assertEqual(row["kind"], "judge")
                self.assertRegex(row["detail"], self.SHAPE)

    def test_a_run_with_no_session_id_writes_no_row_and_prints_the_same(self):
        # A row that cannot be written must not change the caller's behaviour: a
        # loop that reaches the tool without a session id reads one less ledger
        # line, not one less selection.
        Fake.reply_fn = answer_asking_for({str(COMBOBOX_UNIT)})
        named = self.judged("--select", self.snapshot_file(),
                            "--task", "the filters", TEZGAH_SESSION="s-j4")
        plain = self.judged("--select", self.snapshot_file(), "--task", "the filters")
        self.assertEqual((named.returncode, plain.returncode), (0, 0), plain.stderr)
        self.assertEqual(named.stdout.split("judge:")[0],
                         plain.stdout.split("judge:")[0])
        self.assertEqual(len(self.ledger()), 1,
                         "a row was written without a session id")


if __name__ == "__main__":
    unittest.main()
