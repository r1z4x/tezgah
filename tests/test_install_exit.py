"""`--install` exits non-zero when a planned host is not armed.

Written from plan 047's Phase A acceptance list (REPORT.md R03 part 2): the
install printed a MISS under a host it was asked to arm and still exited 0, so
`curl | sh` and every script reported success over a host with no gate. The
verdict reads an arming-row subset only: rows that are MISS on a correct fresh
install (Codex "hooks trusted", a provider key, the omp extension row when no
omp CLI exists) must not fail the run.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_install_safety import Home  # noqa: E402


class InstallExit(Home):
    def fake_omp(self, answers):
        """An omp CLI that answers `config get` with an empty list when
        `answers`, and fails every call otherwise."""
        script = self.path("fake-omp")
        with open(script, "w") as fh:
            fh.write("#!%s\nimport json, sys\n" % sys.executable
                     + ("print(json.dumps({'value': []}))\n" if answers
                        else "sys.exit(1)\n"))
        os.chmod(script, 0o755)
        self.env["TEZGAH_OMP_BIN"] = script

    def test_a_planned_host_with_an_arming_miss_exits_non_zero(self):
        # omp is present but refuses `omp config`: the bridge is written and
        # never registered, so omp draws nothing - the host is not armed
        self.fake_omp(answers=False)
        proc = self.setup("--install", "--hosts", "omp")
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn("hook registered in omp extensions", out.split("not armed")[-1], out)

    def test_untrusted_codex_hooks_and_missing_provider_keys_exit_zero(self):
        proc = self.setup("--install", "--hosts", "codex,opencode,dsh")
        out = proc.stdout
        self.assertEqual(proc.returncode, 0, out + proc.stderr)
        # the rows this run must not count are really MISS here
        for label in ("hooks trusted", "Inception provider key resolvable",
                      "OpenRouter route key resolvable"):
            row = next((ln for ln in out.splitlines() if label in ln), "")
            self.assertTrue(row.strip().startswith("MISS"), (label, out))

    def test_omp_without_its_cli_exits_zero(self):
        proc = self.setup("--install", "--hosts", "omp")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_removed_hook_wiring_is_reported_by_name(self):
        """The verdict reads the report rows: a host whose hook row is MISS is
        named, so a reader knows which host to fix."""
        self.fake_omp(answers=False)
        out = self.setup("--install", "--hosts", "omp,cursor").stdout
        tail = out.split("not armed")[-1]
        self.assertIn("omp", tail, out)
        self.assertNotIn("cursor", tail, out)


if __name__ == "__main__":
    unittest.main()
