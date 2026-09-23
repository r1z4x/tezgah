#!/usr/bin/env python3
"""CI smoke: bin/tezgah-mcp answers its handshake and runs its tools for real.

Spawns the server exactly as a host launches it - the interpreter `hosts` rows
are written with (`tp.python_cmd()`), the checkout's own `bin/tezgah-mcp` - and
speaks the same newline-delimited JSON-RPC that `bin/tezgah-setup --mcp-schemas`
probes with, so the server and the installer's probe agree by construction. The
tools then run the real CLIs: a delegate that moved, a summary line that stopped
being written, or a loop that dies on a bad frame is caught here instead of in a
host's transcript.

`tezgah_consult` is not called: a machine with a provider key would bill a real
model call for a smoke test, and its delegation is pinned by
`tests/test_mcp_server.py`.

Exits 0 when the server answers. A machine with no interpreter is a SKIP by
default, but a FAIL when TEZGAH_E2E_STRICT=1 - which is how CI runs it, so a
broken surface cannot hide behind a skip.

    TEZGAH_E2E_STRICT=1 python3 tests/e2e_tezgah_mcp.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, HERE)
import tezgah_paths as tp  # noqa: E402
from _mcp_stdio import Client  # noqa: E402

MCP = os.path.join(REPO, "bin", "tezgah-mcp")
TOOLS = ["tezgah_status", "tezgah_gate_check", "tezgah_features",
         "tezgah_consult", "tezgah_research_check"]
STRICT = os.environ.get("TEZGAH_E2E_STRICT") == "1"


def probe(python):
    """The installer's own one-shot shape: raw lines in, EOF, raw lines out.

    A malformed line rides first, so the answer proves the loop survived it and
    still answered the handshake that follows (the installer's probe sends the
    three requests and closes stdin, which is also why the exit status is here:
    EOF must end the server with 0)."""
    lines = ["this is not a request"]
    for message in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                        "clientInfo": {"name": "tezgah-e2e", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}):
        lines.append(json.dumps(message))
    proc = subprocess.run([python, MCP], input="\n".join(lines) + "\n",
                          capture_output=True, text=True, timeout=120)
    replies = []
    for line in proc.stdout.splitlines():
        if line.strip():
            replies.append(json.loads(line))
    tools = next((r["result"]["tools"] for r in replies
                  if r.get("id") == 2 and "result" in r), None)
    problems = []
    if proc.returncode != 0:
        problems.append("exited %d (stderr: %s)"
                        % (proc.returncode, proc.stderr.strip()[-200:]))
    if not any(r.get("error", {}).get("code") == -32700 for r in replies):
        problems.append("a malformed line was not answered with a parse error")
    if tools is None:
        problems.append("tools/list was not answered after the malformed line")
    elif [t["name"] for t in tools] != TOOLS:
        problems.append("tools/list is %r, not %r"
                        % ([t["name"] for t in tools], TOOLS))
    return problems


def content(result):
    """The call's text, split into its first line and the log under it."""
    text = "\n".join(block["text"] for block in result["content"])
    lines = text.splitlines()
    return lines[0], lines[1:]


def scratch_free_parent():
    """A temp parent the gate does not treat as the session's own scratch.

    `$TMPDIR` and `/tmp` are exempt from the gate's ask, so a call made there
    comes back with no reason whatever it does; /var/tmp is neither, which is
    also why the suite's own fixtures live there when it is writable."""
    if os.path.isdir("/var/tmp") and os.access("/var/tmp", os.W_OK):
        return "/var/tmp"
    return None


def drive(python, workdir, scratch_free=True):
    """Every tool a CI machine can run, over the handshake a host performs.

    The workdir is wired as the run's tezgah root: the gate is armed inside a
    configured root, so that is what makes the refused call below a refusal
    rather than a call outside tezgah's reach."""
    problems = []
    env = dict(os.environ)
    env["TEZGAH_ROOTS"] = workdir
    client = Client([python, MCP], env=env, timeout=180)
    try:
        info = client.initialize()
        if info.get("serverInfo", {}).get("name") != "tezgah":
            problems.append("initialize answered %r" % (info,))
        names = client.tools()
        if names != TOOLS:
            problems.append("tools/list is %r, not %r" % (names, TOOLS))
        calls = [
            ("tezgah_status", {}),
            ("tezgah_features", {}),
            # a call that passes: the gate's answer is the reason, or nothing
            ("tezgah_gate_check", {"command": "ls -la", "path": workdir}),
            # a call the gate refuses, so the reason reaches the card as the log
            ("tezgah_gate_check", {"command": "rm -rf /", "path": workdir}),
            # no research line here, so the answer is the same everywhere
            ("tezgah_research_check", {"path": workdir}),
        ]
        for name, arguments in calls:
            result = client.call(name, arguments)
            summary, log = content(result)
            who = "%s%r" % (name, arguments)
            if not summary.startswith(name + ": "):
                problems.append("%s: the first line is not the summary: %r"
                                % (who, summary))
            elif "exited 0" not in summary:
                problems.append("%s: the summary is %r" % (who, summary))
            if result.get("isError"):
                problems.append("%s: the call failed (log: %r)" % (who, log))
            if name == "tezgah_gate_check":
                refused = arguments["command"].startswith("rm")
                if refused and scratch_free and not log:
                    problems.append("%s: a refused call carries no reason" % who)
                if not refused and log:
                    problems.append("%s: a passing call carries a log: %r"
                                    % (who, log))
            elif not log:
                problems.append("%s: the log is empty" % who)
    except Exception as exc:  # a server that does not answer is the finding
        problems.append("the handshake or a call failed: %s" % exc)
    finally:
        client.close()
    return problems


def main():
    python = tp.python_cmd()
    if not (os.path.isfile(python) or shutil.which(python)):
        print("%s: %s (the interpreter a host launches) is not available"
              % ("FAIL" if STRICT else "SKIP", python))
        return 1 if STRICT else 0
    bad = False
    parent = scratch_free_parent()
    if parent is None:
        print("SKIP: the refused gate call: no scratch-free temp dir here")
    with tempfile.TemporaryDirectory(dir=parent) as workdir:
        for label, problems in (("the installer's probe shape", probe(python)),
                                ("the handshake and the tools",
                                 drive(python, workdir, parent is not None))):
            if problems:
                bad = True
                print("FAIL: %s: %s" % (label, "; ".join(problems)))
            elif label == "the installer's probe shape":
                print("OK: %s: a malformed line is answered, the handshake "
                      "follows, EOF exits 0" % label)
            else:
                print("OK: %s: %d tools answer with a summary and their log"
                      % (label, len(TOOLS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
