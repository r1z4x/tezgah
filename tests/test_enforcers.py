"""The enforcement matrix: every always-on CORE rule against the mechanism that
enforces it, or a recorded prose-only row.

The rows come from the policy text (each CORE paragraph's bold head), the
enforcers from the code (`bin/tezgah-docs`'s AST readers of `decision`, the Stop
classes and the report-only shape flags), and the prose-only record from the
table in docs/contract.md. A CORE rule with neither an enforcer nor a record
row fails here, and so does a record row that has gone stale.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import support
from test_docs import docs_module

sys.path.insert(0, support.HOOKS)
import tezgah_policy  # noqa: E402

STATUS = os.path.join(support.REPO, "bin", "tezgah-status")


def heads(core):
    """The bold heads of CORE's rule paragraphs, read independently of the
    module under test: every paragraph that opens with `**`, the kill-switch
    paragraph left out (it lists switches, it is not a rule)."""
    out = []
    for para in core.split("\n\n"):
        para = para.strip()
        if para.startswith("**") and not para.startswith("**Kill switches"):
            out.append(para[2:para.index("**", 2)])
    return out


class Matrix(unittest.TestCase):
    def setUp(self):
        self.d = docs_module()

    def row(self, rule):
        return next(r for r in self.d.enforcers() if r["rule"] == rule)

    def test_every_core_rule_has_an_enforcer_or_a_prose_only_row(self):
        self.assertEqual(self.d.enforcer_failures(), [])

    def test_one_row_per_core_paragraph_in_policy_order(self):
        self.assertEqual([r["label"] for r in self.d.enforcers()],
                         heads(tezgah_policy.CORE))

    def test_links_read_off_the_code(self):
        # each pair is a fact of the shipped code, not of the reader: the
        # shortcut deny sits under `verify-off`, which drops the integrity
        # paragraph; the list cap returns under the adhd switches; the reply
        # language block under `exec-mode.off`; the evidence classes under the
        # Stop hook's own `verify-off`.
        expect = {
            "integrity": ("gate:shortcut", "gate:piped", "gate:order",
                          "stop:check failed", "stop:no verify_ok"),
            "loop": ("gate:loop", "gate:retry"),
            "attribution": ("gate:attribution",),
            "lang": ("gate:lang",),
            "workspace": ("gate:workspace",),
            "adhd": ("stop:list cap", "stop:forbidden closer",
                     "flag:recap-close", "flag:preamble-open"),
            "exec": ("stop:reply language",),
            "graph": ("gate:explorer",),
            "fidelity": ("stop:placating opener",),
        }
        for rule, enforcers in expect.items():
            got = self.row(rule)["enforcers"]
            for e in enforcers:
                self.assertIn(e, got, rule)

    def test_an_unenforced_rule_carries_its_record(self):
        consult = self.row("consult")
        self.assertEqual(consult["enforcers"], [])
        self.assertTrue(consult["decision"])

    def test_a_new_rule_with_neither_fails(self):
        core = tezgah_policy.CORE.replace(
            "**Kill switches:**", "**Brand new rule.** Prose only.\n\n"
            "**Kill switches:**")
        fails = self.d.enforcer_failures(core=core)
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("Brand new rule.", fails[0])

    def test_a_dropped_record_row_fails(self):
        record = [r for r in self.d.prose_only_rows() if r["rule"] != "consult"]
        fails = self.d.enforcer_failures(record=record)
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("consult", fails[0])

    def test_a_record_row_for_an_enforced_rule_fails(self):
        record = self.d.prose_only_rows() + [
            {"rule": "lang", "decision": "stale"},
            {"rule": "no-such-rule", "decision": "typo"}]
        fails = self.d.enforcer_failures(record=record)
        self.assertEqual(len(fails), 2, fails)
        self.assertTrue(any("`lang`" in f and "gate:lang" in f for f in fails))
        self.assertTrue(any("no-such-rule" in f for f in fails))

    def test_the_citations_pass_carries_the_check(self):
        self.assertIn(self.d.enforcer_failures, self.d.INVENTORY_CHECKS)


class Cli(unittest.TestCase):
    def run_status(self, *args):
        with tempfile.TemporaryDirectory() as home:
            return subprocess.run(
                [sys.executable, STATUS, "--enforcers"] + list(args),
                capture_output=True, text=True, timeout=60,
                env=support.base_env(home))

    def test_report_prints_one_row_per_rule_and_exits_0(self):
        proc = self.run_status()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertRegex(lines[0], r"^16 always-on CORE rules: \d+ enforced, "
                                   r"\d+ prose-only")
        rules = [r["rule"] for r in docs_module().enforcers()]
        for rule in rules:
            self.assertTrue(any(line.split()[:1] == [rule] for line in lines),
                            rule)
        self.assertIn("gate:shortcut", proc.stdout)
        self.assertIn("none - ", proc.stdout)

    def test_json_carries_the_rows(self):
        proc = self.run_status("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        found = json.loads(proc.stdout)
        self.assertEqual(len(found["rows"]), 16)
        self.assertEqual(found["failures"], [])


if __name__ == "__main__":
    unittest.main()
