"""hosts/cursor/hook.py: the per-turn text fits Cursor's additional_context cap."""
import contextlib
import importlib.util
import io
import json
import unittest
from unittest import mock

import support
from support import TempHome, run_json

# cursor-agent 2026.10.01-2026.10.19 (`hooks-carriers`, 6121.index.js) trims
# the additional_context of beforeSubmitPrompt, preToolUse, postToolUse and
# postToolUseFailure and drops it whole when `o.length>1e4`: JavaScript length,
# so UTF-16 code units, not code points.
CAP = 10000
BUSY = ("analyse this product's retention and which feature next, research the "
        "literature and run experiments, use parallel subagents for each of the 3 "
        "items, consult a second opinion, design the UI screens, who calls parse_config")


def units(text):
    """The length Cursor measures: UTF-16 code units."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def load_hook(home):
    """hosts/cursor/hook.py as a module. It calls main() when it loads, so it
    loads under a no-op payload on a patched stdin (as test_codex_hook does)."""
    payload = json.dumps({"hook_event_name": "Noop", "cwd": home})
    with mock.patch("sys.stdin", io.StringIO(payload)), \
            contextlib.redirect_stdout(io.StringIO()):
        spec = importlib.util.spec_from_file_location("cursor_hook", support.CURSOR_HOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class CursorCap(TempHome):
    def test_a_busy_turn_arrives_cut_instead_of_dropped(self):
        repo = self.make_repo("proj")
        payload = {"hook_event_name": "beforeSubmitPrompt", "cwd": repo,
                   "conversation_id": "busy", "prompt": BUSY}
        raw, proc = run_json([support.PROBE_CONTEXT], {
            "fn": "context_for", "event": "user_prompt", "cwd": repo,
            "payload": dict(payload, conversation_id="busy-raw")}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # the turn really is over the cap, so the cut path is what runs here
        self.assertGreater(units(raw.strip()), CAP)
        out, proc = run_json([support.CURSOR_HOOK], payload, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = out["additional_context"]
        self.assertLessEqual(units(text.strip()), CAP)
        self.assertTrue(text.endswith(load_hook(self.home).CONTEXT_CUT), text[-200:])
        self.assertIn("harness-reminder", text)

    def test_the_cap_boundary_is_exact(self):
        hook = load_hook(self.home)
        fit, cut = hook.fit, hook.CONTEXT_CUT
        self.assertEqual(fit("a" * CAP), "a" * CAP)
        over = fit("a" * (CAP + 1))
        self.assertEqual(units(over), CAP)
        self.assertTrue(over.endswith(cut))

    def test_astral_characters_count_as_two_units(self):
        hook = load_hook(self.home)
        # 10000 code points but 10020 UTF-16 units: Cursor would drop it whole
        text = "\U0001F600" * 20 + "a" * (CAP - 20)
        self.assertEqual(len(text), CAP)
        out = hook.fit(text)
        self.assertLessEqual(units(out), CAP)
        self.assertTrue(out.endswith(hook.CONTEXT_CUT))
        # exactly at the cap in units: kept whole
        self.assertEqual(hook.fit("\U0001F600" * (CAP // 2)), "\U0001F600" * (CAP // 2))
        # a cut never splits a surrogate pair: the head stays valid text
        out = hook.fit("\U0001F600" * CAP)
        out.encode("utf-16-le")
        self.assertLessEqual(units(out), CAP)

    def test_session_start_is_not_cut(self):
        # cursor-agent hands sessionStart's text to the request context
        # (`hooksAdditionalContextPromise`), never through the capped carrier;
        # stored Cursor chats carry 15000-character session contexts whole. A cut
        # here would only lose the tail of the always-on core.
        repo = self.make_repo("proj")
        out, proc = run_json([support.CURSOR_HOOK], {
            "hook_event_name": "sessionStart", "cwd": repo,
            "conversation_id": "start"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = out["additional_context"]
        self.assertGreater(units(text), CAP)
        self.assertNotIn(load_hook(self.home).CONTEXT_CUT.strip(), text)


if __name__ == "__main__":
    unittest.main()
