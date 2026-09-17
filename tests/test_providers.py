"""bin/consult and bin/codegen: provider selection, key lookup and deadlines.

Each case runs the script in a throwaway HOME with no provider key, so the
unknown-provider and missing-key paths are exercised without any network call;
the deadline case talks to a local stalling server and never to a provider.
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSULT = os.path.join(REPO, "bin", "consult")
CODEGEN = os.path.join(REPO, "bin", "codegen")


class ProviderCase(unittest.TestCase):
    """A throwaway HOME and a minimal env, so no case can reach a real key."""

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


class Providers(ProviderCase):
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


class Trickle(threading.Thread):
    """A server that answers with headers, then one chunked byte at a time.

    Every socket read stays well inside --timeout, which is exactly how a
    per-operation timeout fails to bound the whole request: `urlopen` restarts
    its clock on each recv. Observed live as a 3-minute hold under --timeout 90.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()

    def run(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        try:
            conn.recv(65536)
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         b"Transfer-Encoding: chunked\r\n\r\n")
            while not self.stop.is_set():
                conn.sendall(b"1\r\n \r\n")
                self.stop.wait(0.5)
        except OSError:
            pass
        finally:
            conn.close()

    def close(self):
        self.stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


class CodegenDeadline(ProviderCase):
    """--timeout is the contract for the WHOLE request: the caller (the router)
    falls back to the main model on exit 2, so a request that never returns is
    the one failure it cannot recover from."""

    def test_a_trickling_response_exits_two_within_the_timeout(self):
        server = Trickle()
        server.start()
        self.addCleanup(server.close)
        env = dict(self.env, OPENROUTER_API_KEY="test",
                   CODEGEN_URL="http://127.0.0.1:%d/v1/chat/completions"
                               % server.port)
        start = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, CODEGEN, "t", "--files",
                                   __file__, "--timeout", "2"],
                                  capture_output=True, text=True, env=env,
                                  timeout=30)
        except subprocess.TimeoutExpired:
            self.fail("codegen hung past --timeout: the request is not bounded "
                      "end to end")
        elapsed = time.monotonic() - start
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("outlived --timeout=2s", proc.stderr)
        self.assertLess(elapsed, 15, "the deadline did not fire promptly")


if __name__ == "__main__":
    unittest.main()
