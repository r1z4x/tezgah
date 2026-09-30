"""The cheap tier has one source: `hooks/tezgah_models.py`'s cheap row.

`bin/codegen`'s OpenRouter default and the judge's chat fallback used to name a
cheap model of their own. Both now read `cheap_model("any")`, and keep the old id
only for a table that cannot be read - a standalone CLI must still draft and a
hook must still judge. The last two cases are the cycle guard: `tezgah_models`
imports `tezgah_judge`, so the judge must import on its own, with no table on its
path and none pulled in at module level.
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
CODEGEN = os.path.join(REPO, "bin", "codegen")
sys.path.insert(0, HOOKS)

import tezgah_judge  # noqa: E402
import tezgah_models  # noqa: E402

OVERRIDES = ("TEZGAH_JUDGE_MODEL", "CODEGEN_MODEL")
TABLE_ROW = ("vendor/table-cheap", None)


def load_codegen():
    """`bin/codegen` as a module: the script has no `.py` name to import, so the
    spec is built from a source loader rather than from its path."""
    loader = importlib.machinery.SourceFileLoader("codegen_under_test", CODEGEN)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


class CheapSourceCase(unittest.TestCase):
    """Both cheap paths answer from the table, and survive a table that cannot."""

    def setUp(self):
        # The env overrides are the documented first channel; a developer's own
        # value must not decide what these cases measure.
        env = {k: v for k, v in os.environ.items() if k not in OVERRIDES}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.codegen = load_codegen()
        self.row = tezgah_models.cheap_model("any")

    def test_the_table_names_a_cheap_row(self):
        self.assertTrue(self.row, "the table has no cheap `any` row")

    def test_the_codegen_default_is_the_cheap_row(self):
        self.assertEqual(self.codegen.cheap_default(), self.row[0])
        self.assertEqual(self.codegen.MODEL, self.row[0])

    def test_the_judge_fallback_is_the_cheap_row(self):
        self.assertEqual(tezgah_judge.fallback_model(), self.row[0])

    def test_both_paths_ask_the_table_for_the_any_family(self):
        for read in (self.codegen.cheap_default, tezgah_judge.fallback_model):
            with mock.patch.object(tezgah_models, "cheap_model",
                                   return_value=TABLE_ROW) as asked:
                self.assertEqual(read(), TABLE_ROW[0])
            asked.assert_called_once_with("any")

    def test_each_keeps_its_literal_when_the_table_cannot_answer(self):
        for broken in (mock.Mock(return_value=None),               # no such row
                       mock.Mock(side_effect=ImportError("gone"))):  # unreadable
            with mock.patch.object(tezgah_models, "cheap_model", broken):
                self.assertEqual(self.codegen.cheap_default(),
                                 self.codegen.FALLBACK_MODEL)
                self.assertEqual(tezgah_judge.fallback_model(),
                                 tezgah_judge.FALLBACK_MODEL)


class ImportCycleCase(unittest.TestCase):
    """`tezgah_models` imports the judge: the judge must not import back."""

    def probe(self, code):
        """`code` in a fresh interpreter on the hooks dir, with a temp HOME."""
        with tempfile.TemporaryDirectory() as home:
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home}
            return subprocess.run([sys.executable, "-c", code], cwd=HOOKS,
                                  env=env, capture_output=True, text=True)

    def test_the_judge_imports_on_its_own(self):
        proc = self.probe("import tezgah_judge\n")
        self.assertEqual(proc.returncode, 0, proc.stderr.rstrip())

    def test_the_judge_pulls_the_table_in_only_when_it_asks(self):
        proc = self.probe("import sys, tezgah_judge\n"
                          "raise SystemExit(1 if 'tezgah_models' in sys.modules "
                          "else 0)\n")
        self.assertEqual(proc.returncode, 0,
                         "import tezgah_judge imported tezgah_models at module "
                         "level, which is the cycle")


if __name__ == "__main__":
    unittest.main()
