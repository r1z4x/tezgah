"""tezgah-ocr-review: OCR's review loop on omp's model through a loopback shim.

Hermetic: TEZGAH_OCR_BIN / TEZGAH_OMP_BIN point at stub scripts. The stub omp
speaks the `omp auth-gateway stdio` JSON-lines protocol; the stub ocr POSTs one
chat completion to $OCR_LLM_URL and prints what came back plus the OCR_* env it
saw, so a pass proves the round trip through the shim.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from support import REPO

TOOL = os.path.join(REPO, "bin", "tezgah-ocr-review")

STUB_OMP = textwrap.dedent("""\
    #!%s
    import json, os, sys
    assert sys.argv[1:] == ["auth-gateway", "stdio"], sys.argv
    open(os.environ["STUB_OMP_PIDFILE"], "w").write(str(os.getpid()))
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        req = json.loads(line)
        body = {"choices": [{"message": {"role": "assistant",
                "content": "echo:" + req["path"] + ":" + req["body"]["model"]}}]}
        print(json.dumps({"id": req["id"], "status": 200, "body": body}), flush=True)
    """) % sys.executable

STUB_OCR = textwrap.dedent("""\
    #!%s
    import json, os, sys, urllib.request
    url = os.environ["OCR_LLM_URL"] + "/chat/completions"
    data = json.dumps({"model": os.environ["OCR_LLM_MODEL"], "messages": []}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    reply = json.load(urllib.request.urlopen(req, timeout=10))
    print(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                      "reply": reply["choices"][0]["message"]["content"],
                      "env": {k: v for k, v in os.environ.items() if k.startswith("OCR_")},
                      "leaked": [k for k in os.environ
                                 if k.startswith(("ANTHROPIC_", "OPENAI_"))]}))
    """) % sys.executable


class OcrReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = self.tmp.name
        self.repo = os.path.join(t, "repo")
        os.mkdir(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.write("main.py", "print(1)\n")
        self.ocr, self.omp = os.path.join(t, "ocr"), os.path.join(t, "omp")
        for path, text in ((self.ocr, STUB_OCR), (self.omp, STUB_OMP)):
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)
        self.pidfile = os.path.join(t, "omp.pid")
        self.env = dict(os.environ, HOME=t, TEZGAH_OCR_BIN=self.ocr, TEZGAH_OMP_BIN=self.omp,
                        STUB_OMP_PIDFILE=self.pidfile, OCR_PROVIDER="leak",
                        ANTHROPIC_API_KEY="leak", OPENAI_API_KEY="leak")

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        subprocess.run(["git", "-C", self.repo, "add", rel], check=True)

    def run_tool(self, *args, **env):
        return subprocess.run([sys.executable, TOOL, "--repo", self.repo, *args],
                              capture_output=True, text=True, timeout=60,
                              env=dict(self.env, **env))

    def test_round_trip(self):
        r = self.run_tool("--from", "main", "--to", "dev", "--model", "pi/x")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["reply"], "echo:/v1/chat/completions:pi/x")
        self.assertEqual(out["argv"], ["review", "--format", "json", "--color", "never",
                                       "--from", "main", "--to", "dev"])
        self.assertEqual(os.path.realpath(out["cwd"]), os.path.realpath(self.repo))
        env = out["env"]
        self.assertEqual(sorted(env), ["OCR_LLM_MODEL", "OCR_LLM_PROTOCOL", "OCR_LLM_TOKEN",
                                       "OCR_LLM_URL", "OCR_NO_UPDATE"])
        self.assertEqual((env["OCR_LLM_MODEL"], env["OCR_LLM_PROTOCOL"], env["OCR_NO_UPDATE"]),
                         ("pi/x", "openai", "1"))
        self.assertRegex(env["OCR_LLM_URL"], r"^http://127\.0\.0\.1:\d+/v1$")
        self.assertEqual(out["leaked"], [])
        with open(self.pidfile) as f:
            pid = int(f.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_output_file_and_default_model(self):
        dest = os.path.join(self.tmp.name, "review.json")
        r = self.run_tool("--commit", "abc", "--output", dest)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        with open(dest) as f:
            out = json.load(f)
        self.assertEqual(out["env"]["OCR_LLM_MODEL"], "@default")
        self.assertEqual(out["argv"][-2:], ["--commit", "abc"])

    def test_missing_ocr(self):
        r = self.run_tool(TEZGAH_OCR_BIN=os.path.join(self.tmp.name, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("`ocr`", r.stderr)

    def test_missing_omp(self):
        r = self.run_tool(TEZGAH_OMP_BIN=os.path.join(self.tmp.name, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("`omp`", r.stderr)

    def test_tracked_env_refused(self):
        self.write("cfg/.env", "KEY=1\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 3)
        self.assertIn("cfg/.env", r.stderr)
        self.assertFalse(os.path.exists(self.pidfile))

    def test_env_example_allowed(self):
        self.write(".env.example", "KEY=\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_allow_secrets(self):
        self.write(".ssh/id_rsa", "x\n")
        self.assertEqual(self.run_tool().returncode, 3)
        r = self.run_tool("--allow-secrets")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
