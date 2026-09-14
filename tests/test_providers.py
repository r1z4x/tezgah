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
        p = self.invoke(CONSULT, "q", "--provider", "deepseek")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("no API key for deepseek", p.stderr)
        self.assertIn("DEEPSEEK_API_KEY", p.stderr)

    def test_codegen_deepseek_wants_its_own_key(self):
        p = self.invoke(CODEGEN, "t", "--files", __file__, "--provider", "deepseek")
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("no API key for deepseek", p.stderr)


if __name__ == "__main__":
    unittest.main()
