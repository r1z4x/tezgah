"""hosts/dsh/statusline/lib/index.js: the argv the status route hands tezgah-status.

The route is driven by node with a stand-in for dsh's `ctx` (the route
registry and the session map) and a stub tezgah-status that prints the argv it
was given, so what reaches the CLI is read rather than inferred.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

import support

ROUTE = os.path.join(support.REPO, "hosts", "dsh", "statusline", "lib", "index.js")

# Registers the route against a fake ctx, calls it once per query, and prints
# the stub's answers (the argv tezgah-status received) as one JSON list.
DRIVER = """
import { apply } from %s;
let route;
const sessions = new Map([["ses-known.1", { header: { cwd: %s } }]]);
apply({ connection: { fetch: { register: (r) => { route = r; } } }, sessions });
const out = [];
for (const q of JSON.parse(process.argv[2])) {
  const res = await route.fetch(new Request("http://x/api/tezgah.status?" + q));
  out.push(await res.text());
}
console.log(JSON.stringify(out));
"""

STUB = "import json, sys\nprint(json.dumps(sys.argv[1:]))\n"


class DshStatusRoute(support.TempHome):
    def setUp(self):
        super().setUp()
        self.node = shutil.which("node")
        if not self.node:
            self.skipTest("node is not installed")
        self.repo = self.make_repo("proj")
        self.stub = os.path.join(self.home, "status-stub.py")
        with open(self.stub, "w") as fh:
            fh.write(STUB)
        self.driver = os.path.join(self.home, "driver.mjs")
        with open(self.driver, "w") as fh:
            fh.write(DRIVER % (json.dumps("file://" + ROUTE), json.dumps(self.repo)))

    def argv(self, *queries):
        env = dict(os.environ, TEZGAH_STATUS_BIN=self.stub,
                   TEZGAH_PYTHON=sys.executable)
        proc = subprocess.run([self.node, self.driver, json.dumps(list(queries))],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(text) for text in json.loads(proc.stdout)]

    def test_a_session_id_reaches_the_cli_only_known_and_after_a_double_dash(self):
        # Audit L-7 (SEC-07): `sessionId=--failure-shapes` went into the argv
        # whether or not dsh knew the session, and tezgah-status read it as the
        # flag that runs the machine-wide report.
        known, flag, unknown = self.argv("sessionId=ses-known.1",
                                         "sessionId=--failure-shapes",
                                         "sessionId=nobody")
        self.assertEqual(known[-3:], ["--", self.repo, "ses-known.1"])
        for got in (flag, unknown):
            self.assertNotIn("--failure-shapes", got)
            self.assertNotIn("nobody", got)
            self.assertEqual(got[-2], "--")
        # every option sits before the separator
        self.assertTrue(all(a.startswith("--") for a in known[:known.index("--")]))


if __name__ == "__main__":
    unittest.main()
