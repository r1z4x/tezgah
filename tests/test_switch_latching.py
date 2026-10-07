"""Switch latching (plan 051): a kill switch created after a session's first
ledger row is ignored by that session's `off()` unless the user's own prompt
named it; a switch present before the first row is honored as before.

Every probe runs in a subprocess with a throwaway HOME, because the switch
directories and the cache are module constants read at import."""
import json
import os
import subprocess
import sys
import time

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_integrity as ti  # noqa: E402
import tezgah_paths as tp  # noqa: E402

PROBE = r"""
import json, sys
import tezgah_integrity as ti
import tezgah_paths as tp
spec = json.loads(sys.argv[1])
if spec.get("prompt") is not None:
    ti.note_turn("s", spec["prompt"])
if spec.get("bind", True):
    ti.bind_session("s")
print(json.dumps({n: tp.off(n) for n in spec["names"]}))
"""

GATE = r"""
import json, sys
import tezgah_gate
cwd, sid = sys.argv[1], sys.argv[2]
print(json.dumps(tezgah_gate.decision(
    "Bash", {"command": "git commit --no-verify -m x"}, cwd, sid)))
"""


class Latching(TempHome):
    def switch(self, name, legacy=False, content=""):
        d = (os.path.join(self.home, ".claude") if legacy
             else os.path.join(self.home, ".config", "tezgah"))
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def ledger(self, first_ts, session="s"):
        """A ledger whose first row is stamped `first_ts`: the latch compares
        a switch file's ctime (which no caller can set) with this stamp, so a
        stamp in the future stands for "the switch was there first"."""
        path = os.path.join(self.home, ".cache", "tezgah", "evidence",
                            ti._slug(session) + ".jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps({"kind": "attest", "ts": first_ts, "v": 3,
                                 "detail": ""}) + "\n")
        return path

    def rows(self, path):
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def probe(self, names, prompt=None, bind=True):
        spec = {"names": list(names), "prompt": prompt, "bind": bind}
        proc = subprocess.run([sys.executable, "-c", PROBE, json.dumps(spec)],
                              capture_output=True, text=True, env=self.env(),
                              timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_switch_created_after_the_first_row_is_ignored(self):
        self.ledger(int(time.time()) - 100)
        self.switch("verify-off")
        self.assertEqual(self.probe(["verify-off"]), {"verify-off": False})

    def test_a_switch_present_before_the_first_row_is_honored(self):
        self.switch("verify-off")
        self.ledger(int(time.time()) + 100)
        self.assertEqual(self.probe(["verify-off"]), {"verify-off": True})

    def test_a_session_with_no_ledger_and_an_unbound_process_honor_it(self):
        self.switch("verify-off")
        self.assertEqual(self.probe(["verify-off"]), {"verify-off": True})
        self.ledger(int(time.time()) - 100)
        self.assertEqual(self.probe(["verify-off"], bind=False),
                         {"verify-off": True})

    def test_a_backdated_mtime_does_not_pass_the_latch(self):
        """`touch -t` sets mtime; ctime moves with it and cannot be set back."""
        self.ledger(int(time.time()) - 100)
        path = self.switch("verify-off")
        os.utime(path, (time.time() - 10 ** 6, time.time() - 10 ** 6))
        self.assertEqual(self.probe(["verify-off"]), {"verify-off": False})

    def test_the_legacy_directory_is_latched_too(self):
        self.ledger(int(time.time()) - 100)
        self.switch("consult-off", legacy=True)
        self.assertEqual(self.probe(["consult-off"]), {"consult-off": False})

    def test_a_prompt_naming_the_switch_authorizes_it(self):
        path = self.ledger(int(time.time()) - 100)
        self.switch("verify-off")
        self.switch("adhd-off")
        out = self.probe(["verify-off", "adhd-off"],
                         prompt="please create verify-off for this session")
        self.assertEqual(out, {"verify-off": True, "adhd-off": False})
        auth = [r for r in self.rows(path) if r["kind"] == "authorized"]
        self.assertEqual([r.get("authorized") for r in auth], [["verify-off"]])
        self.assertIn("authorized", ti.LEDGER_FIELDS)
        # honored from that turn on: a later process with no prompt still sees it
        self.assertEqual(self.probe(["verify-off"]), {"verify-off": True})

    def test_a_name_inside_a_longer_word_authorizes_nothing(self):
        path = self.ledger(int(time.time()) - 100)
        self.switch("verify-off")
        out = self.probe(["verify-off"], prompt="see my-verify-offset.txt")
        self.assertEqual(out, {"verify-off": False})
        self.assertFalse([r for r in self.rows(path) if r["kind"] == "authorized"])

    def test_the_uninstall_stand_down_is_the_carve_out(self):
        self.ledger(int(time.time()) - 100)
        self.switch("pretooluse-off")
        self.assertEqual(self.probe(["pretooluse-off"]), {"pretooluse-off": False})
        self.switch("pretooluse-off", content=tp.STAND_DOWN)
        self.assertEqual(self.probe(["pretooluse-off"]), {"pretooluse-off": True})

    def test_the_gate_keeps_its_denial_until_the_prompt_names_the_switch(self):
        """End to end through `decision`, the entry every host's PreToolUse
        reaches: an agent-made verify-off leaves the shortcut denial armed, and
        the user's prompt naming it stands it down."""
        repo = self.make_repo()
        self.ledger(int(time.time()) - 100)
        self.switch("verify-off")

        def gate():
            proc = subprocess.run([sys.executable, "-c", GATE, repo, "s"],
                                  capture_output=True, text=True,
                                  env=self.env(), timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)

        self.assertIn("--no-verify", gate() or "")
        self.probe([], prompt="I created verify-off on purpose")
        self.assertIsNone(gate())
