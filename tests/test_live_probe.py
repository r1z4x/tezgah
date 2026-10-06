"""`--report --live` proves the gate runs: one PreToolUse deny per host.

Written from plan 047's Phase B acceptance list (REPORT.md R03 part 4): the live
report fired only PostToolUse, so nothing proved that a host's gate executes.
Per planned host it now sends `git commit --no-verify -m x` through the host's
own PreToolUse wiring and requires both the host's deny envelope (Claude, Codex
and dsh `permissionDecision: deny`, Cursor `permission: deny`, omp `block: true`,
opencode a throw) and a deny row in the ledger. `pretooluse-off` and
`verify-off` stand that refusal down, so the row is UNVERIFIED and names the
switch. The omp bridge must also match a fresh render byte for byte.

Six hosts are installed into a throwaway HOME from a release-shaped copy of the
tree, with stub `claude` and `omp` CLIs; no real host CLI or config is touched.

Guards bin/tezgah-setup (`live_plan`, `live_probe`, `omp_bridge`),
hooks/tezgah_gate.py and hooks/tezgah_integrity.py (the deny and its row), and
hosts/opencode/plugins/tezgah.js (its own deny row).
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_claude_registration import ClaudeHome  # noqa: E402

HOSTS = ("claude", "codex", "cursor", "dsh", "opencode", "omp")

# An omp CLI that keeps `extensions` in a file: `config get extensions --json`
# answers it, `config set extensions <json>` replaces it.
OMP_STUB = r'''#!%s
import json, os, sys
store = os.path.join(os.environ["HOME"], "omp-extensions.json")
args = [a for a in sys.argv[1:] if a != "--json"]
if args[:2] == ["config", "get"]:
    try:
        value = json.load(open(store))
    except OSError:
        value = []
    print(json.dumps({"value": value}))
elif args[:2] == ["config", "set"]:
    json.dump(json.loads(args[3]), open(store, "w"))
elif args[:2] == ["config", "reset"]:
    os.path.exists(store) and os.remove(store)
else:
    sys.exit(1)
''' % sys.executable


class LiveDeny(ClaudeHome):
    def setUp(self):
        super().setUp()
        for d in (".codex", ".cursor", ".dsh", ".config/opencode", ".omp/agent"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        omp = os.path.join(os.path.dirname(self.home), "omp")
        with open(omp, "w") as fh:
            fh.write(OMP_STUB)
        os.chmod(omp, 0o755)
        self.env["TEZGAH_OMP_BIN"] = omp
        proc = self.setup("--install", "--hosts", ",".join(HOSTS))
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".codex", "hooks.json")),
                        proc.stdout + proc.stderr)
        self.trust_codex()

    def trust_codex(self):
        """Write the [hooks.state] keys an interactive codex run would, one per
        tezgah group, so the codex row measures the hook and not the trust."""
        path = os.path.join(self.home, ".codex", "hooks.json")
        with open(path) as fh:
            events = json.load(fh)["hooks"]
        lines = []
        for event, groups in events.items():
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", event).lower()
            for i, group in enumerate(groups):
                if "tezgah" in json.dumps(group):
                    lines.append('[hooks.state."%s:%s:%d:0"]\ntrusted = true\n'
                                 % (path, snake, i))
        with open(os.path.join(self.home, ".codex", "config.toml"), "a") as fh:
            fh.write("\n" + "\n".join(lines))

    def live(self):
        proc = self.setup("--report", "--live", "--hosts", ",".join(HOSTS))
        rows = [ln.strip() for ln in proc.stdout.splitlines()
                if ln.strip().split(" ", 1)[-1].lstrip().startswith("live ")]
        return proc, rows

    def deny_rows(self, rows):
        return {h: next((r for r in rows if "live %s deny:" % h in r), "")
                for h in HOSTS}

    def switch(self, name):
        d = os.path.join(self.home, ".config", "tezgah")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, name), "w").close()

    def test_every_host_denies_the_probe_and_records_it(self):
        proc, rows = self.live()
        out = proc.stdout + proc.stderr
        for host, row in self.deny_rows(rows).items():
            self.assertTrue(row.startswith("ok"), (host, row, out))
            self.assertIn("PreToolUse denied `git commit --no-verify -m x` and "
                          "wrote a deny row", row)
        self.assertEqual(proc.returncode, 0, out)

    def test_each_switch_that_stands_the_refusal_down_is_named(self):
        for name in ("pretooluse-off", "verify-off"):
            self.switch(name)
            proc, rows = self.live()
            for host, row in self.deny_rows(rows).items():
                self.assertTrue(row.startswith("UNVERIFIED"), (name, host, row))
                self.assertIn("%s is set" % name, row)
            os.remove(os.path.join(self.home, ".config", "tezgah", name))

    def test_a_hand_edited_omp_bridge_is_a_miss(self):
        bridge = os.path.join(self.home, ".omp", "agent", "hooks", "pre", "tezgah-hook.ts")
        with open(bridge, "a") as fh:
            fh.write("\n// edited by hand\n")
        proc, rows = self.live()
        row = self.deny_rows(rows)["omp"]
        self.assertTrue(row.startswith("MISS"), (row, proc.stdout))
        self.assertIn("differs from a fresh render", row)
        self.assertNotEqual(proc.returncode, 0)

    def test_a_gate_that_lets_the_commit_through_is_a_miss(self):
        """The envelope is what is asserted, not that a hook ran: a PreToolUse
        command that answers nothing is a MISS for that host."""
        copy = self.registry("installed_plugins.json")["plugins"][
            "tezgah@tezgah-local"][0]["installPath"]
        hooks = os.path.join(copy, "hooks", "hooks.json")
        with open(hooks) as fh:
            data = json.load(fh)
        for group in data["hooks"]["PreToolUse"]:
            for entry in group.get("hooks") or []:
                entry["command"] = "true"
        with open(hooks, "w") as fh:
            json.dump(data, fh)
        proc, rows = self.live()
        row = self.deny_rows(rows)["claude"]
        self.assertTrue(row.startswith("MISS"), (row, proc.stdout))
        self.assertIn("no deny envelope", row)


if __name__ == "__main__":
    unittest.main()
