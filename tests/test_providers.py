"""bin/consult and bin/codegen: provider selection and per-provider key lookup.

Each case runs the script in a throwaway HOME with no provider key, so the
unknown-provider and missing-key paths are exercised without any network call.
"""
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSULT = os.path.join(REPO, "bin", "consult")
CODEGEN = os.path.join(REPO, "bin", "codegen")


class Providers(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.path.realpath(self._tmp.name),
        }

    def invoke(self, script, *args):
        return subprocess.run([sys.executable, script] + list(args),
                              capture_output=True, text=True, env=self.env)

    def test_consult_rejects_unknown_provider(self):
        p = self.invoke(CONSULT, "q", "--provider", "nope")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unknown provider", p.stderr)

    def test_codegen_rejects_unknown_provider(self):
        p = self.invoke(CODEGEN, "t", "--files", __file__, "--provider", "nope")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unknown provider", p.stderr)

    def test_consult_deepseek_wants_its_own_key(self):
        # exit 2 is "no key", distinct from misuse (1) and all-failed (3)
        p = self.invoke(CONSULT, "q", "--provider", "deepseek")
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("no API key for deepseek", p.stderr)
        self.assertIn("DEEPSEEK_API_KEY", p.stderr)

    def test_consult_online_is_openrouter_only(self):
        p = self.invoke(CONSULT, "q", "--provider", "deepseek", "--online")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("--online is OpenRouter-only", p.stderr)

    def test_codegen_deepseek_wants_its_own_key(self):
        p = self.invoke(CODEGEN, "t", "--files", __file__, "--provider", "deepseek")
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("no API key for deepseek", p.stderr)

    def test_codegen_rejects_the_misleading_apply_to_alias(self):
        p = self.invoke(CODEGEN, "t", "--files", __file__, "--apply-to", "/tmp/x")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("unknown argument --apply-to", p.stderr)

    def test_consult_rejects_a_flag_without_a_value(self):
        # A trailing flag used to miss its arm and fall through to the question
        # arm, so the flag text became the prompt and a paid request went out
        # for it, answered with exit 3 instead of the documented misuse exit 1.
        for args in (("--provider",), ("--models",), ("--timeout",), ("q", "--models")):
            p = self.invoke(CONSULT, *args)
            self.assertEqual(p.returncode, 1, "%s: %s" % (args, p.stderr))
            self.assertIn("needs a value", p.stderr)
            self.assertNotIn("consulted:", p.stderr)


if __name__ == "__main__":
    unittest.main()
