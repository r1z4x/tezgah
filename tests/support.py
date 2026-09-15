"""Shared helpers for the tezgah test suite.

Every test that exercises a hook runs it in a subprocess with an explicit
environment: a throwaway HOME and TEZGAH_ROOTS under tempfile, so the real
~/.claude, ~/.config/tezgah and ~/.cache are never read or written.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
TESTS = os.path.dirname(os.path.abspath(__file__))

PROBE_PATHS = os.path.join(TESTS, "_probe_paths.py")
PROBE_GATE = os.path.join(TESTS, "_probe_gate.py")
PROBE_CONTEXT = os.path.join(TESTS, "_probe_context.py")
PROBE_AGENTS = os.path.join(TESTS, "_probe_agents.py")
AUTO_INIT = os.path.join(REPO, "hooks", "projects-auto-init.py")
PRETOOLUSE = os.path.join(REPO, "hooks", "projects-pretooluse.py")
CODEX_HOOK = os.path.join(REPO, "hosts", "codex", "hook.py")
CURSOR_HOOK = os.path.join(REPO, "hosts", "cursor", "hook.py")
STATUSLINE = os.path.join(REPO, "statusline.py")


def slug(path):
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def base_env(home, roots=None, extra=None):
    """A minimal environment: temp HOME, optional roots, no real host config."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": home,
        "LANG": "C.UTF-8",
        "PYTHONPATH": HOOKS,
        # a path that does not exist => cbm_bin() is None => no auto-index runs
        "TEZGAH_CBM_BIN": os.path.join(home, "no-such-cbm"),
        # likewise orx: research routing is off unless a test points it at a real
        # binary, so the machine's own orx cannot leak into the assertions
        "TEZGAH_ORX_BIN": os.path.join(home, "no-such-orx"),
    }
    if roots:
        env["TEZGAH_ROOTS"] = os.pathsep.join(roots)
    if extra:
        env.update(extra)
    return env


def run(args, payload=None, env=None, cwd=None):
    data = None if payload is None else json.dumps(payload)
    return subprocess.run(
        [sys.executable] + args, input=data, capture_output=True, text=True,
        env=env, cwd=cwd, timeout=60,
    )


def run_json(args, payload=None, env=None, cwd=None):
    proc = run(args, payload, env, cwd)
    out = proc.stdout.strip()
    return (json.loads(out) if out else None), proc


class TempHome(unittest.TestCase):
    """A test with a fresh temp HOME and a Projects root inside it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        self.roots = os.path.join(self.home, "Projects")
        os.makedirs(self.roots, exist_ok=True)

    def env(self, roots=None, extra=None):
        return base_env(self.home, roots or [self.roots], extra)

    def make_repo(self, name="repo"):
        path = os.path.join(self.roots, name)
        os.makedirs(path, exist_ok=True)
        return os.path.realpath(path)

    def config(self, data):
        path = os.path.join(self.home, ".config", "tezgah", "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh)

    def touch(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
