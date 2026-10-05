"""tests/neuter_matrix.py's generated half: one mutant per gate rule.

The weekly matrix (`.github/workflows/neuter.yml`) is too slow for the suite, so
this module checks only the generator: the rows come from the same AST reader
`bin/tezgah-docs --citations` uses for the rule list, and each one applies by
line span to the gate's text without touching any other rule."""
import ast
import os
import re
import unittest

import neuter_matrix
import support

GATE = os.path.join(support.REPO, "hooks", "tezgah_gate.py")


def gate_text():
    with open(GATE, encoding="utf-8") as fh:
        return fh.read()


class GeneratedGateMutants(unittest.TestCase):
    def test_one_row_per_gate_rule(self):
        rows = neuter_matrix.gate_mutants(gate_text())
        self.assertEqual(len(rows), 14)
        self.assertEqual(len({r[0] for r in rows}), 14)
        self.assertTrue(all(r[1] == neuter_matrix.GATE for r in rows))
        self.assertIn("gate-task", {r[0] for r in rows})

    def test_each_row_reverts_every_deny_site_of_its_rule_and_no_other(self):
        text = gate_text()
        denies = re.compile(r'return _deny\(session_id, "([a-z]+)"')
        before = denies.findall(text)
        for name, _file, apply, _guard in neuter_matrix.gate_mutants(text):
            rule = name[len("gate-"):]
            with self.subTest(rule=rule):
                mutated, error = apply(text)
                self.assertIsNone(error)
                ast.parse(mutated, filename=GATE)
                self.assertEqual(len(mutated.splitlines()), len(text.splitlines()))
                self.assertEqual(denies.findall(mutated),
                                 [r for r in before if r != rule])

    def test_a_span_that_no_longer_holds_its_rule_is_an_error_not_a_mutant(self):
        text = gate_text()
        row = next(r for r in neuter_matrix.gate_mutants(text) if r[0] == "gate-task")
        _mutated, error = row[2]("\n" + text)
        self.assertIn("task", error)


if __name__ == "__main__":
    unittest.main()
