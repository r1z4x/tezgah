"""tests/neuter_matrix.py's generated halves - one mutant per gate rule and one
per Stop-class return site - and its killer cache.

The matrix itself runs in CI (`.github/workflows/neuter.yml`), too slow for the
suite, so this module checks the generator and the cache path: the rows come
from the same AST reader `bin/tezgah-docs --citations` uses for the rule list,
each one applies by line span to the gate's text without touching any other
rule, and a cached killer kills only when that very test fails."""
import ast
import os
import re
import unittest

import neuter_matrix
import support

GATE = os.path.join(support.REPO, "hooks", "tezgah_gate.py")
STOP = os.path.join(support.REPO, "hooks", "tezgah_integrity.py")


def gate_text():
    with open(GATE, encoding="utf-8") as fh:
        return fh.read()


class GeneratedGateMutants(unittest.TestCase):
    def test_one_row_per_gate_rule(self):
        rows = neuter_matrix.gate_mutants(gate_text())
        self.assertEqual(len(rows), 17)
        self.assertEqual(len({r[0] for r in rows}), 17)
        self.assertTrue(all(r[1] == neuter_matrix.GATE for r in rows))
        self.assertIn("gate-task", {r[0] for r in rows})
        self.assertIn("gate-control", {r[0] for r in rows})

    def test_each_row_reverts_every_deny_site_of_its_rule_and_no_other(self):
        text = gate_text()
        denies = re.compile(r'return _deny\(session_id, "([a-z-]+)"')
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


class GeneratedStopMutants(unittest.TestCase):
    CLASS = re.compile(r'return \("([a-z_ ]+)",')

    def setUp(self):
        with open(STOP, encoding="utf-8") as fh:
            self.text = fh.read()

    def test_every_stop_class_has_a_mutant(self):
        rows = neuter_matrix.stop_mutants(self.text)
        self.assertEqual(len({r[0] for r in rows}), len(rows))
        named = {re.search(r"`([^`]+)`", r[3]).group(1) for r in rows}
        self.assertEqual(named, neuter_matrix.docs_module().stop_triggers())

    def test_each_row_reverts_one_return_site_and_no_other(self):
        before = self.CLASS.findall(self.text)
        for name, _file, apply, _guard in neuter_matrix.stop_mutants(self.text):
            with self.subTest(mutant=name):
                mutated, error = apply(self.text)
                self.assertIsNone(error)
                ast.parse(mutated, filename=STOP)
                self.assertEqual(len(mutated.splitlines()), len(self.text.splitlines()))
                self.assertEqual(len(self.CLASS.findall(mutated)), len(before) - 1)

    def test_every_hand_row_applies_to_its_file(self):
        for name, path, apply, _guard in neuter_matrix.MUTANTS:
            with self.subTest(mutant=name):
                with open(os.path.join(support.REPO, path), encoding="utf-8") as fh:
                    _mutated, error = apply(fh.read())
                self.assertIsNone(error)


class KillerCache(unittest.TestCase):
    """`verdict` driven by a stub runner: no clone, no subprocess."""

    def stub(self, failing):
        """A runner where each test id in `failing` fails; records each argv."""
        calls = []

        def runner(argv, _cwd, _env):
            calls.append(argv)
            module = argv[argv.index("-p") + 1][:-len(".py")]
            only = [argv[i + 1] for i, a in enumerate(argv) if a == "-k"]
            hit = [t for t in failing if t.startswith(module + ".")
                   and (not only or t in only)]
            # 3.10's line shape: `FAIL: method (module.Class)`
            stderr = "".join("FAIL: %s (%s)\n" % (t.rsplit(".", 1)[1], t.rsplit(".", 1)[0])
                             for t in hit[:1]) + ("FAILED (failures=1)\n" if hit else "OK\n")
            return type("Proc", (), {"returncode": 1 if hit else 0, "stderr": stderr})()
        return runner, calls

    def verdict(self, known, failing):
        runner, calls = self.stub(failing)
        return neuter_matrix.verdict("test_gate.py", known, "tree", {}, runner), calls

    def test_a_cached_killer_that_still_fails_is_the_only_run(self):
        (status, _last, killer), calls = self.verdict(
            "test_gate.G.test_old", ["test_gate.G.test_old"])
        self.assertEqual((bool(status), killer), (True, "test_gate.G.test_old"))
        self.assertEqual(len(calls), 1)

    def test_a_stale_entry_falls_back_and_is_replaced(self):
        (status, _last, killer), calls = self.verdict(
            "test_gate.G.test_old", ["test_integrity.I.test_new"])
        self.assertEqual((bool(status), killer), (True, "test_integrity.I.test_new"))
        # the cached test, then the target module first, then the rest in order
        modules = [c[c.index("-p") + 1] for c in calls]
        self.assertEqual(modules[:3], ["test_gate.py", "test_gate.py", "test_integrity.py"])
        results = [("m", status, _last, killer), ("gone-from-run", 0, "", None)]
        self.assertEqual(
            neuter_matrix.updated({"m": "test_gate.G.test_old", "dropped": "x.Y.test_z",
                                   "kept": "test_gate.G.test_k"},
                                  results, {"m", "kept", "gone-from-run"}),
            {"m": "test_integrity.I.test_new", "kept": "test_gate.G.test_k"})

    def test_a_missing_entry_runs_the_modules_and_records_the_killer(self):
        (status, _last, killer), calls = self.verdict(None, ["test_gate.G.test_a"])
        self.assertEqual((bool(status), killer), (True, "test_gate.G.test_a"))
        self.assertEqual(len(calls), 1)
        self.assertNotIn("-k", calls[0])

    def test_a_cached_run_that_fails_for_another_reason_is_no_kill(self):
        # a renamed test: the module's import error is not the cached id failing
        def runner(argv, _cwd, _env):
            stderr = ("ERROR: test_gate (unittest.loader._FailedTest)\n"
                      if "-k" in argv else "OK\n")
            return type("Proc", (), {"returncode": 1 if "-k" in argv else 0,
                                     "stderr": stderr})()
        status, _last, killer = neuter_matrix.verdict(
            "test_gate.py", "test_gate.G.test_gone", "tree", {}, runner)
        self.assertEqual((status, killer), (0, None))

    def test_a_survivor_runs_every_module(self):
        (status, _last, killer), calls = self.verdict("test_gate.G.test_old", [])
        self.assertEqual((status, killer), (0, None))
        self.assertEqual(len(calls), 1 + len(neuter_matrix.MODULES))


if __name__ == "__main__":
    unittest.main()
