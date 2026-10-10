"""hooks/tezgah_product.py: the product ledger's writer, checker, due list and
citation reader, on the research tests' throwaway-repo fixture."""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_product as tprod  # noqa: E402
import tezgah_research as tr  # noqa: E402

from test_research import AFTER, BEFORE, CLAIM, Workspace, read  # noqa: E402

DAY = "2026-01-05"
ROWS = {
    "O": {"type": "O", "topic": "export", "from": [], "class": "user-verbatim",
          "source": "interview 3", "quote": "I could not find the export"},
    "I": {"type": "I", "topic": "export", "from": ["O1"],
          "statement": "the export is hidden", "confidence": "medium",
          "downgrade": ["indirectness"]},
    "A": {"type": "A", "topic": "export", "from": ["I1"], "kind": "usability",
          "statement": "a toolbar button is found", "importance": "high",
          "evidence": "weak"},
    "M": {"type": "M", "topic": "export", "from": ["I1"], "goal": "more exports",
          "signal": "export_clicked", "definition": "clicks per session",
          "window": "28d", "baseline": 0.1, "direction": "up", "leading": True,
          "logged": "yes", "data": "events table"},
    "D": {"type": "D", "topic": "export", "from": ["I1", "A1", "M1"],
          "statement": "move export to the toolbar", "outcome": "fix",
          "metric": "M1", "threshold": "0.2", "observe_after": "2026-02-01",
          "reopen": "clicks stay under 0.15"},
    "R": {"type": "R", "topic": "export", "from": ["D1"], "decision": "D1",
          "verdict": "met", "value": 0.22, "class": "behaviour",
          "source": "events table"},
}
REWRITTEN = "product ledger (product/ledger.jsonl) was rewritten"
REMOVED = "product ledger (product/ledger.jsonl) was removed after it was committed"
DEEP = "[" * 100000

# (needle, type, changed fields, dropped fields): one row per rule the shape
# refuses, every one of them fed to the writer and to the checker.
REFUSALS = [
    ("type", "O", {"type": "X"}, ()),
    ("topic", "O", {"topic": "Export Flow"}, ()),
    ("topic", "O", {}, ("topic",)),
    ("at most 64", "O", {"topic": "-".join(["ab"] * 30)}, ()),
    ("from is", "I", {"from": "O1"}, ()),
    ("does not hold", "I", {"from": ["O9"]}, ()),
    ("rests on I", "A", {"from": ["O1"]}, ()),
    ("rests on nothing", "O", {"from": ["O1"]}, ()),
    ("claim q:c9", "O", {"claims": ["q:c9"]}, ()),
    ("claim ../x:c1", "O", {"claims": ["../x:c1"]}, ()),
    ("claims is", "O", {"claims": "q:c1"}, ()),
    ("class", "O", {"class": "hearsay"}, ()),
    ("source", "O", {}, ("source",)),
    ("quote", "O", {}, ("quote",)),
    ("over 500", "O", {"quote": "x" * 501}, ()),
    ("statement", "I", {}, ("statement",)),
    ("confidence", "I", {"confidence": "sure"}, ()),
    ("downgrade", "I", {}, ("downgrade",)),
    ("downgrade", "I", {"downgrade": ["vibes"]}, ()),
    ("downgrade", "I", {"confidence": "high", "downgrade": "vibes"}, ()),
    ("kind", "A", {"kind": "delight"}, ()),
    ("statement", "A", {}, ("statement",)),
    ("importance", "A", {"importance": "medium"}, ()),
    ("evidence", "A", {"evidence": "some"}, ()),
    ("goal", "M", {}, ("goal",)),
    ("signal", "M", {}, ("signal",)),
    ("definition", "M", {}, ("definition",)),
    ("window", "M", {}, ("window",)),
    ("baseline", "M", {"baseline": True}, ()),
    ("data", "M", {}, ("data",)),
    ("direction", "M", {"direction": "sideways"}, ()),
    ("leading", "M", {"leading": "yes"}, ()),
    ("logged", "M", {"logged": "maybe"}, ()),
    ("statement", "D", {}, ("statement",)),
    ("outcome", "D", {"outcome": "ship"}, ()),
    ("metric", "D", {"metric": "I1"}, ()),
    ("metric", "D", {"metric": "M9"}, ()),
    ("metric", "D", {"metric": ["M1"]}, ()),
    ("threshold", "D", {}, ("threshold",)),
    ("reopen", "D", {}, ("reopen",)),
    ("observe_after", "D", {"observe_after": "02/01/2026"}, ()),
    ("before the row's date", "D", {"observe_after": "2026-01-01"}, ()),
    ("decision", "R", {"decision": "M1"}, ()),
    ("decision", "R", {"decision": ["D1"]}, ()),
    ("verdict", "R", {"verdict": "maybe"}, ()),
    ("value", "R", {}, ("value",)),
    ("class", "R", {"class": "hearsay"}, ()),
    ("source", "R", {}, ("source",)),
]


def row(kind, drop=(), /, **changes):
    out = dict(ROWS[kind], **changes)
    for key in drop:
        out.pop(key, None)
    return out


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


class Ledger(Workspace):
    def setUp(self):
        super().setUp()
        self.main = self.repo()
        self.path = tprod.ledger_path(self.main)

    def record(self, *kinds, repo=None, date=DAY):
        ids = []
        for kind in kinds:
            rid, problems = tprod.append_row(repo or self.main, row(kind), date=date)
            self.assertEqual(problems, [], kind)
            ids.append(rid)
        return ids

    def hand(self, *rows):
        """A ledger written by hand, rows exactly as given."""
        self.write(self.path, "".join(json.dumps(r) + "\n" for r in rows))

    def check(self, repo=None, **kw):
        return tprod.check_ledger(repo or self.main, **kw)


class Writer(Ledger):
    def test_the_record_writer_and_the_checker_agree(self):
        # Kills: the writer skipping row_problems (it would write the row), the
        # checker skipping it (no error), and any rule living on one side only
        # (the two problem lists would differ).
        self.line(self.main)
        self.claims(self.main, CLAIM)
        self.record("O", "I", "A", "M", "D")
        self.assertEqual(self.check(git=False)["errors"], [])
        base = read_bytes(self.path)
        held = {"O": 1, "I": 1, "A": 1, "M": 1, "D": 1, "R": 0}
        for needle, kind, changes, drop in REFUSALS:
            bad = row(kind, drop, **changes)
            with self.subTest(needle=needle, row=bad):
                rid, problems = tprod.append_row(self.main, bad, date=DAY)
                self.assertIsNone(rid)
                self.assertTrue(any(needle in p for p in problems), problems)
                self.assertEqual(read_bytes(self.path), base)
                hand = dict(bad, date=DAY,
                            id="%s%d" % (bad["type"], held.get(bad["type"], 0) + 1))
                with open(self.path, "ab") as fh:
                    fh.write(json.dumps(hand).encode("utf-8") + b"\n")
                errors = self.check(git=False)["errors"]
                with open(self.path, "wb") as fh:
                    fh.write(base)
                self.assertEqual([e.split("): ", 1)[1] for e in errors], problems)

    def test_a_bad_date_is_refused_by_both(self):
        # Kills: a date taken through fromisoformat alone (3.11 reads 20260105).
        rid, problems = tprod.append_row(self.main, row("O"), date="20260105")
        self.assertIsNone(rid)
        self.assertEqual(problems, ["date '20260105' is not YYYY-MM-DD"])
        self.hand(dict(row("O"), id="O1", date="20260105"))
        self.assertEqual(self.check(git=False)["errors"],
                         ["product ledger line 1 (O1): date '20260105' is not "
                          "YYYY-MM-DD"])

    def test_ids_are_one_past_the_highest_of_their_type(self):
        # Kills: ids counted over every row (I1 would be I3) or by row count
        # (O8 would be O4).
        self.assertEqual(self.record("O", "O", "I"), ["O1", "O2", "I1"])
        self.append_line(self.path, dict(row("O"), id="O7", date=DAY))
        self.assertEqual(self.record("O"), ["O8"])

    def test_a_caller_supplied_id_or_date_is_refused(self):
        # Kills: a writer that keeps a caller's id (ids collide) or date (an
        # observe_after check against a backdated row).
        self.record("O")
        before = read_bytes(self.path)
        rid, problems = tprod.append_row(self.main, dict(row("O"), id="O9",
                                                         date="2020-01-01"))
        self.assertIsNone(rid)
        self.assertEqual(problems, ["id is the writer's to assign; drop it from "
                                    "the row", "date is the writer's to assign; "
                                    "drop it from the row"])
        self.assertEqual(read_bytes(self.path), before)

    def test_the_optional_fields_stay_optional(self):
        # Kills: downgrade required on a high I, value/class/source required on an
        # unobservable R, a resolving claim refused.
        self.line(self.main)
        self.claims(self.main, CLAIM)
        self.record("O", "I", "A", "M", "D")
        for kind, extra, drop in (("O", {"claims": ["q:c1"]}, ()),
                                  ("I", {"confidence": "high"}, ("downgrade",)),
                                  ("R", {"verdict": "unobservable"},
                                   ("value", "class", "source"))):
            rid, problems = tprod.append_row(self.main, row(kind, drop, **extra),
                                             date=DAY)
            self.assertEqual(problems, [], kind)
        self.assertEqual(self.check(git=False)["errors"], [])

    def test_the_id_and_the_judgement_are_read_under_the_lock(self):
        # Kills: ids or held rows read before the lock - the writer would assign
        # I1 again and refuse a `from` naming the O that landed meanwhile.
        os.makedirs(os.path.dirname(self.path))
        open(self.path, "w").close()
        raced = []

        def racing():
            if not raced:
                raced.append(1)
                self.append_line(self.path, dict(row("O"), id="O1", date=DAY))
                self.append_line(self.path, dict(row("I"), id="I1", date=DAY))

        self.race_at_the_lock(racing)
        self.assertEqual(self.record("I"), ["I2"])
        ids = [json.loads(line)["id"] for line in read(self.path).splitlines()]
        self.assertEqual(ids, ["O1", "I1", "I2"])

    def test_no_fcntl_refuses_rather_than_append_unlocked(self):
        # Kills: an unlocked fallback, and a refused first write leaving an empty
        # ledger behind.
        saved = tr.fcntl
        tr.fcntl = None
        try:
            rid, problems = tprod.append_row(self.main, row("O"), date=DAY)
        finally:
            tr.fcntl = saved
        self.assertIsNone(rid)
        self.assertEqual(problems,
                         ["product/ledger.jsonl cannot be locked on this platform"])
        self.assertFalse(os.path.exists(self.path))

    def test_an_unterminated_fragment_is_cut_before_the_new_row(self):
        # Kills: the append without truncate_to_committed (the row would be glued
        # onto the fragment) and _held reading past committed_size (the
        # fragment's O5 would make the new id O6).
        self.record("O")
        with open(self.path, "a") as fh:
            fh.write(json.dumps(dict(row("O"), id="O5", date=DAY)))
        self.assertEqual(self.record("O"), ["O2"])
        text = read(self.path)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual([json.loads(line)["id"] for line in text.splitlines()],
                         ["O1", "O2"])


class AppendOnly(Ledger):
    def rewrite_first_row(self):
        lines = read(self.path).splitlines(True)
        first = json.loads(lines[0])
        first["quote"] = "a quote nobody said"
        self.write(self.path, json.dumps(first) + "\n" + "".join(lines[1:]))

    def test_an_appended_row_after_a_commit_is_clean(self):
        # The control for the two below: appending is never a rewrite.
        self.record("O")
        self.commit(self.main, "rows", when=BEFORE)
        self.record("O")
        self.commit(self.main, "more rows", when=AFTER)
        self.assertEqual(self.check()["errors"], [])

    def test_an_uncommitted_rewrite_is_refused(self):
        # Kills: no append-only check on the product ledger at all.
        self.record("O", "O")
        self.commit(self.main, "rows", when=BEFORE)
        self.rewrite_first_row()
        errors = self.check()["errors"]
        self.assertTrue(any(e.startswith(REWRITTEN) for e in errors), errors)
        self.assertIn("product ledger rows are append-only", errors[0])
        self.assertEqual(self.check(git=False)["errors"], [])

    def test_a_committed_rewrite_is_refused(self):
        # Kills: a check of the working copy against HEAD only - once the rewrite
        # is committed they agree, and only the history shows it.
        self.record("O", "O")
        self.commit(self.main, "rows", when=BEFORE)
        self.rewrite_first_row()
        self.commit(self.main, "rewrite", when=AFTER)
        errors = self.check()["errors"]
        self.assertTrue(any(e.startswith(REWRITTEN) for e in errors), errors)

    def test_a_removed_ledger_is_refused_committed_or_not(self):
        # Kills: no check when the file is gone - the working copy was the only
        # version compared, and a committed deletion is a commit git show skips.
        self.record("O", "O")
        self.commit(self.main, "rows", when=BEFORE)
        os.remove(self.path)
        self.assertTrue(tprod.in_use(self.main))
        errors = self.check()["errors"]
        self.assertTrue(any(e.startswith(REMOVED) for e in errors), errors)
        self.assertEqual(self.check(git=False)["errors"], [])
        self.commit(self.main, "drop", when=AFTER)
        errors = self.check()["errors"]
        self.assertTrue(any(e.startswith(REMOVED) for e in errors), errors)

    def test_a_recreated_shorter_ledger_is_refused(self):
        self.record("O", "O")
        self.commit(self.main, "rows", when=BEFORE)
        first = read(self.path).splitlines(True)[0]
        os.remove(self.path)
        self.write(self.path, first)
        errors = self.check()["errors"]
        self.assertTrue(any(e.startswith(REWRITTEN) for e in errors), errors)

    def test_in_use_reads_the_file_the_history_and_the_citations(self):
        self.assertFalse(tprod.in_use(self.main))
        self.record("O")
        self.assertTrue(tprod.in_use(self.main))
        other = self.repo("cites")
        self.assertFalse(tprod.in_use(other))
        self.write(os.path.join(other, ".tezgah", "plans", "open", "p.md"),
                   "per product:O1\n")
        self.assertTrue(tprod.in_use(other))


class Unparseable(Ledger):
    def test_a_deeply_nested_line_is_a_bad_line_not_an_exception(self):
        # Kills: RecursionError escaping _lines (and with it every reader:
        # due, check, record) or the design contract's parse.
        self.hand(dated("M", "M1"), dated("D", "D1", observe_after="2020-03-01"))
        with open(self.path, "a") as fh:
            fh.write('{"observe_after": "2000-01-01", "x": %s\n' % DEEP)
        self.assertEqual([d["id"] for d in tprod.due(self.main, "2020-04-01")],
                         ["D1"])
        self.assertIn("product ledger line 3 is not a JSON object",
                      self.check(git=False)["errors"])
        ws = os.path.join(self.main, ".tezgah")
        self.write(os.path.join(ws, "design-contract.md"),
                   "```json\n%s\n```\n" % DEEP)
        self.write(os.path.join(ws, "plans", "open", "p.md"), "per product:M1\n")
        self.assertEqual(tprod.consumer_tokens(self.main),
                         [(".tezgah/plans/open/p.md", 1, "M1")])

    def test_a_line_separator_in_a_quote_stays_inside_its_row(self):
        # Kills: a writer that leaves U+2028/U+2029/U+0085 raw while the readers
        # split on them (the row breaks in two, the next id is reused), and a
        # reader that splits on anything but "\n".
        quote = "line one\u2028line two\u2029three\x85four"
        first, problems = tprod.append_row(self.main, row("O", quote=quote), date=DAY)
        self.assertEqual((first, problems), ("O1", []))
        self.assertEqual(self.record("O"), ["O2"])
        self.assertEqual(self.check(git=False)["errors"], [])
        self.assertEqual(tprod.read_rows(self.main)[0]["quote"], quote)
        self.assertEqual(read_bytes(self.path).count(b"\n"), 2)


class Worktree(Ledger):
    def test_a_linked_worktree_reads_the_main_ledger_and_never_writes(self):
        # Kills: a writer that appends in its own checkout (ids collide across
        # checkouts), and a reader that reads the worktree's own (empty) ledger -
        # product:O1 would then be unresolved there.
        self.commit(self.main, "base", when=BEFORE)
        self.record("O")
        wt = os.path.join(self.roots, "wt")
        self.git(self.main, "worktree", "add", "-q", "-b", "side", wt)
        self.assertEqual(tprod.main_checkout(wt), self.main)
        rid, problems = tprod.append_row(wt, row("O"), date=DAY)
        self.assertIsNone(rid)
        self.assertEqual(len(problems), 1)
        self.assertIn("main checkout %s;" % self.main, problems[0])
        self.assertFalse(os.path.exists(os.path.join(wt, ".tezgah", "product")))
        self.assertEqual(len(tprod.read_rows(self.main)), 1)
        self.assertEqual(tprod.read_rows(wt), tprod.read_rows(self.main))
        self.write(os.path.join(wt, ".tezgah", "plans", "open", "p.md"),
                   "cites product:O1\nand product:O7\n")
        self.assertEqual(self.check(wt, git=False)["errors"],
                         [".tezgah/plans/open/p.md:2 cites product:O7, which the "
                          "product ledger does not hold"])


class Tokens(Ledger):
    CONTRACT = ('# Contract\n\n```json\n{\n  "components": [\n'
                '    {"name": "btn", "decision": "product:D8"}\n  ],\n'
                '  "note": "product:D7 is prose, not a decision"\n}\n```\n')

    def test_tokens_resolve_and_a_bare_id_is_never_read(self):
        # Kills: a TOKEN without its `product:` prefix (bare D62 would be an
        # unresolved citation), a line number off by one, the design contract's
        # decision fields skipped, or a non-decision field read as one.
        self.record("O")
        ws = os.path.join(self.main, ".tezgah")
        self.write(os.path.join(ws, "analysis", "a.md"),
                   "# A\n\nper product:O1 and the old D62 table\n")
        self.write(os.path.join(ws, "plans", "open", "p.md"),
                   "line one\nline two\nsee product:D9\n")
        self.write(os.path.join(ws, "design-contract.md"), self.CONTRACT)
        self.assertEqual(tprod.consumer_tokens(self.main),
                         [(".tezgah/analysis/a.md", 3, "O1"),
                          (".tezgah/plans/open/p.md", 3, "D9"),
                          (".tezgah/design-contract.md", 6, "D8")])
        self.assertEqual(self.check(git=False)["errors"],
                         [".tezgah/plans/open/p.md:3 cites product:D9, which the "
                          "product ledger does not hold",
                          ".tezgah/design-contract.md:6 cites product:D8, which "
                          "the product ledger does not hold"])

    def test_a_bare_id_alone_passes(self):
        self.record("O")
        self.write(os.path.join(self.main, ".tezgah", "analysis", "a.md"),
                   "the D62 table, per product:O1\n")
        self.assertEqual(self.check(git=False), {"errors": [], "warnings": []})


def dated(kind, rid, date="2020-01-01", **changes):
    return dict(row(kind, **changes), id=rid, date=date)


class Warnings(Ledger):
    def ledger(self, *extra):
        self.hand(dated("O", "O1"), dated("I", "I1", **{"from": []}),
                  dated("M", "M1", signal="s"),
                  dated("M", "M2", signal="s", logged="no"),
                  dated("D", "D1", metric="M2", observe_after="2020-02-01",
                        **{"from": ["I1"]}), *extra)

    WARNED = ["product ledger I1 (export) rests on no observation: its from is "
              "empty",
              "product ledger D1 (export) is due for re-measure since 2020-02-01 "
              "and no R records it",
              "product ledger D1 (export) is measured by M2, whose signal 's' is "
              "not logged and no later M logs it"]

    def test_behaviour_findings_are_warnings_and_strict_makes_them_errors(self):
        # Kills: the three findings raised as errors by default, `strict` ignored,
        # and "a later M" read as any M (M1, logged yes, comes before M2).
        self.ledger()
        self.assertEqual(self.check(git=False),
                         {"errors": [], "warnings": self.WARNED})
        self.assertEqual(self.check(git=False, strict=True),
                         {"errors": self.WARNED, "warnings": []})

    def test_a_later_logged_m_and_an_r_clear_their_warnings(self):
        # Kills: the metric warning blind to a later M of the same signal, the
        # overdue warning blind to an R.
        self.ledger(dated("M", "M3", signal="s"),
                    dated("R", "R1", decision="D1", verdict="unobservable",
                          **{"from": ["D1"]}))
        self.assertEqual(self.check(git=False),
                         {"errors": [], "warnings": self.WARNED[:1]})


class Due(Ledger):
    def test_due_lists_overdue_decisions_oldest_first(self):
        # Kills: file or id order instead of observe_after order, a future or
        # same-day observe_after listed, an R ignored.
        self.hand(dated("M", "M1"),
                  dated("D", "D1", observe_after="2020-03-01"),
                  dated("D", "D2", observe_after="2020-02-01"),
                  dated("D", "D3", observe_after="2099-01-01"),
                  dated("D", "D4", observe_after="2020-03-31"),
                  dated("D", "D5", observe_after="2020-04-01"))
        got = tprod.due(self.main, "2020-04-01")
        self.assertEqual([d["id"] for d in got], ["D2", "D1", "D4"])
        self.assertEqual(got[0], {"id": "D2", "topic": "export", "metric": "M1",
                                  "threshold": "0.2", "observe_after": "2020-02-01",
                                  "days_overdue": 60})
        self.assertEqual([d["days_overdue"] for d in got], [60, 31, 1])

    def test_due_is_empty_once_every_decision_has_an_r(self):
        self.hand(dated("M", "M1"), dated("D", "D1", observe_after="2020-03-01"),
                  dated("R", "R1", decision="D1"))
        self.assertEqual(tprod.due(self.main, "2020-04-01"), [])
        self.assertEqual(tprod.due(self.repo("empty"), "2020-04-01"), [])

    def test_due_parses_only_the_lines_that_can_matter(self):
        # The prefilter: an M and a future D cost no parse, an R and a
        # `\u`-escaped D still do - an escaped date is still due.
        self.hand(dated("M", "M1"),
                  dated("D", "D1", observe_after="2099-01-01"),
                  dated("D", "D2", observe_after="2020-03-01"),
                  dated("R", "R1", decision="D2"))
        with open(self.path, "a") as fh:
            fh.write('{"type": "D", "id": "D3", "topic": "export", "observe_after"'
                     ': "2020\\u002d02-01"}\n')
        parsed = []
        saved = tprod._lines
        tprod._lines = lambda text: parsed.append(text) or saved(text)
        try:
            got = tprod.due(self.main, "2020-04-01")
        finally:
            tprod._lines = saved
        self.assertEqual([d["id"] for d in got], ["D3"])
        self.assertEqual(got[0]["days_overdue"], 60)
        self.assertEqual([json.loads(line)["id"] for line in parsed[0].splitlines()],
                         ["D2", "R1", "D3"])


if __name__ == "__main__":
    unittest.main()
