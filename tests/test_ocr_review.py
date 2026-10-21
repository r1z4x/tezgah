"""tezgah-ocr-review: OCR's review loop on omp's model through a loopback shim.

Hermetic: TEZGAH_OCR_BIN / TEZGAH_OMP_BIN point at stub scripts. The stub omp
speaks the `omp auth-gateway stdio` JSON-lines protocol; the stub ocr POSTs one
chat completion to $OCR_LLM_URL with the run's bearer token and prints what came
back plus the env it saw, so a pass proves the round trip through the shim.
With STUB_OCR_PROBE set it also sends the requests the shim must refuse.
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

# git's own config must not reach a fixture repository
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_TERMINAL_PROMPT": "0"}

STUB_OMP = textwrap.dedent("""\
    #!%s
    import json, os, sys
    assert sys.argv[1:] == ["auth-gateway", "stdio"], sys.argv
    open(os.environ["STUB_OMP_PIDFILE"], "w").write(str(os.getpid()))
    if os.environ.get("STUB_OMP_SILENT"):
        sys.stdin.read()
        sys.exit(0)
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        req = json.loads(line)
        body = {"choices": [{"message": {"role": "assistant",
                "content": "echo:" + req["path"] + ":" + str(req.get("body", {}).get("model"))}}]}
        print(json.dumps({"id": req["id"], "status": 200, "body": body}), flush=True)
    """) % sys.executable

STUB_OCR = textwrap.dedent("""\
    #!%s
    import json, os, sys, urllib.error, urllib.request
    base = os.environ["OCR_LLM_URL"]
    good = "Bearer " + os.environ["OCR_LLM_TOKEN"]

    def send(path, data=None, auth=good, method=None):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = auth
        req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    chat = json.dumps({"model": os.environ["OCR_LLM_MODEL"], "messages": []}).encode()
    status, reply = send("/chat/completions", chat)
    probe = {}
    if os.environ.get("STUB_OCR_PROBE"):
        probe = {"no_token": send("/chat/completions", chat, auth=None),
                 "wrong_token": send("/chat/completions", chat, auth=good + "x"),
                 "usage": send("/usage", method="GET"),
                 "usage_post": send("/usage", chat),
                 "models": send("/models?x=1", method="GET"),
                 "bad_json": send("/chat/completions", b"{nope")}
    home = os.environ["HOME"]
    print(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "status": status,
                      "reply": reply["choices"][0]["message"]["content"],
                      "probe": probe, "home": home, "home_entries": os.listdir(home),
                      "xdg": os.environ.get("XDG_CONFIG_HOME"),
                      "git_global": os.environ.get("GIT_CONFIG_GLOBAL"),
                      "env": {k: v for k, v in os.environ.items() if k.startswith("OCR_")},
                      "leaked": [k for k in os.environ
                                 if k.startswith(("ANTHROPIC_", "OPENAI_"))]}))
    """) % sys.executable


class OcrReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = self.tmp.name
        self.home = os.path.join(t, "home")
        os.mkdir(self.home)
        self.repo = os.path.join(t, "repo")
        os.mkdir(self.repo)
        self.git("init", "-q")
        self.write("main.py", "print(1)\n")
        self.ocr, self.omp = os.path.join(t, "ocr"), os.path.join(t, "omp")
        for path, text in ((self.ocr, STUB_OCR), (self.omp, STUB_OMP)):
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)
        self.pidfile = os.path.join(t, "omp.pid")
        self.env = dict(os.environ, HOME=self.home, TEZGAH_OCR_BIN=self.ocr,
                        TEZGAH_OMP_BIN=self.omp, STUB_OMP_PIDFILE=self.pidfile,
                        OCR_PROVIDER="leak", ANTHROPIC_API_KEY="leak",
                        OPENAI_API_KEY="leak", XDG_CONFIG_HOME=os.path.join(t, "xdg"),
                        **GIT_ENV)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo, *args], check=True,
                              capture_output=True, text=True,
                              env=dict(os.environ, **GIT_ENV)).stdout.strip()

    def write(self, rel, text, add=True):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        if add:
            self.git("add", rel)

    def tree(self):
        """The index as a tree object: a ref for --to/--commit with no commit."""
        return self.git("write-tree")

    def run_tool(self, *args, repo=None, **env):
        return subprocess.run([sys.executable, TOOL, "--repo", repo or self.repo, *args],
                              capture_output=True, text=True, timeout=60,
                              env=dict(self.env, **env))

    def test_round_trip(self):
        tree = self.tree()
        r = self.run_tool("--from", tree, "--to", tree, "--model", "pi/x")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual((out["status"], out["reply"]), (200, "echo:/v1/chat/completions:pi/x"))
        self.assertEqual(out["argv"], ["review", "--format", "json", "--color", "never",
                                       "--from", tree, "--to", tree])
        self.assertEqual(os.path.realpath(out["cwd"]), os.path.realpath(self.repo))
        env = out["env"]
        self.assertEqual(sorted(env), ["OCR_LLM_MODEL", "OCR_LLM_PROTOCOL", "OCR_LLM_TOKEN",
                                       "OCR_LLM_URL", "OCR_NO_UPDATE"])
        self.assertEqual((env["OCR_LLM_MODEL"], env["OCR_LLM_PROTOCOL"], env["OCR_NO_UPDATE"]),
                         ("pi/x", "openai", "1"))
        self.assertGreaterEqual(len(env["OCR_LLM_TOKEN"]), 40)
        self.assertRegex(env["OCR_LLM_URL"], r"^http://127\.0\.0\.1:\d+/v1$")
        self.assertEqual(out["leaked"], [])
        with open(self.pidfile) as f:
            pid = int(f.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_shim_refuses_without_the_token_and_off_the_allowlist(self):
        r = self.run_tool(STUB_OCR_PROBE="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        probe = json.loads(r.stdout)["probe"]
        self.assertEqual(probe["no_token"][0], 401)
        self.assertEqual(probe["wrong_token"][0], 401)
        self.assertIn("error", probe["no_token"][1])
        self.assertEqual(probe["usage"][0], 404)
        self.assertEqual(probe["usage_post"][0], 404)
        self.assertEqual(probe["models"][0], 200)
        self.assertEqual(probe["bad_json"][0], 400)

    def test_ocr_gets_a_private_empty_home(self):
        planted = os.path.join(self.home, ".opencodereview")
        os.mkdir(planted)
        with open(os.path.join(planted, "config.json"), "w") as f:
            json.dump({"provider": "own"}, f)
        gitconfig = os.path.join(self.home, ".gitconfig")
        with open(gitconfig, "w") as f:
            f.write("[core]\n")
        del self.env["GIT_CONFIG_GLOBAL"]
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertNotEqual(os.path.realpath(out["home"]), os.path.realpath(self.home))
        self.assertEqual(out["home_entries"], [])
        self.assertFalse(os.path.exists(out["home"]))
        self.assertIsNone(out["xdg"])
        self.assertEqual(out["git_global"], gitconfig)

    def test_output_file_and_default_model(self):
        dest = os.path.join(self.tmp.name, "review.json")
        tree = self.tree()
        r = self.run_tool("--commit", tree, "--output", dest)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        with open(dest) as f:
            out = json.load(f)
        self.assertEqual(out["env"]["OCR_LLM_MODEL"], "@default")
        self.assertEqual(out["argv"][-2:], ["--commit", tree])

    def test_missing_ocr(self):
        r = self.run_tool(TEZGAH_OCR_BIN=os.path.join(self.tmp.name, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("`ocr`", r.stderr)

    def test_missing_omp(self):
        r = self.run_tool(TEZGAH_OMP_BIN=os.path.join(self.tmp.name, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("`omp`", r.stderr)

    def test_not_a_git_repo_is_a_setup_failure(self):
        plain = os.path.join(self.tmp.name, "plain")
        os.mkdir(plain)
        r = self.run_tool(repo=plain)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_gateway_never_ready_is_a_setup_failure(self):
        r = self.run_tool(STUB_OMP_SILENT="1", TEZGAH_OCR_REVIEW_READY_TIMEOUT="0.5")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("ready", r.stderr)

    def test_unspawnable_omp_is_a_setup_failure(self):
        with open(self.omp, "w") as f:
            f.write("#!/nonexistent/interpreter\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_tracked_env_refused(self):
        self.write("cfg/.env", "KEY=1\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 3)
        self.assertIn("cfg/.env", r.stderr)
        self.assertFalse(os.path.exists(self.pidfile))

    def test_untracked_env_refused_in_workspace_mode(self):
        self.write(".env", "KEY=1\n", add=False)
        r = self.run_tool()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn(".env", r.stderr)

    def test_ignored_env_refused_in_workspace_mode(self):
        self.write(".gitignore", ".env\n")
        self.write(".env", "KEY=1\n", add=False)
        r = self.run_tool()
        self.assertEqual(r.returncode, 3, r.stderr)

    def test_range_mode_checks_the_target_tree_only(self):
        tree = self.tree()
        self.write(".env", "KEY=1\n", add=False)
        r = self.run_tool("--from", tree, "--to", tree)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.write(".env", "KEY=1\n")
        secret_tree = self.tree()
        r = self.run_tool("--from", tree, "--to", secret_tree)
        self.assertEqual(r.returncode, 3, r.stderr)
        r = self.run_tool("--commit", secret_tree)
        self.assertEqual(r.returncode, 3, r.stderr)

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
