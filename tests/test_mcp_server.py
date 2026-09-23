"""bin/tezgah-mcp: the stdio JSON-RPC surface, driven over its own stdio.

The server is spawned from the checkout and speaks to a test-owned pipe: request
lines in, replies read back. Every tool is answered by a stub CLI installed in a
throwaway HOME's ~/.config/tezgah/bin, so what is pinned here is the server's own
behaviour - the framing, which tezgah command each tool delegates to, the
summary/log split - and not the machine's real install. The real delegates are
exercised by e2e_tezgah_mcp.py.
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import support  # noqa: E402

REPO = os.path.dirname(HERE)
MCP = os.path.join(REPO, "bin", "tezgah-mcp")

# The property set each tool may declare. A property outside this set is one the
# tool does not read - the defect the schema would then carry - and a property
# missing from here is one the tool claims to read and does not.
PROPERTIES = {
    "tezgah_status": {"path"},
    "tezgah_gate_check": {"command", "path"},
    "tezgah_features": set(),
    "tezgah_consult": {"question"},
    "tezgah_research_check": {"path"},
}

# name -> (the program run, its argv after the program). The program is pinned
# because "which tezgah command answers this tool" is the whole design.
DELEGATE = {
    "tezgah_status": ("tezgah-status", None),
    "tezgah_gate_check": ("tezgah-gate", "check"),
    "tezgah_features": ("tezgah-setup", "--features"),
    "tezgah_consult": ("consult", None),
    "tezgah_research_check": ("tezgah-research", "check"),
}

# A stub delegate: it reports the call it was given, reads stdin only if there is
# something to read (with a deadline, so a stolen pipe cannot hang the suite),
# then takes its exit status, stdout and stderr from the environment.
STUB = '''
import os, select, sys
print("program: " + os.path.basename(sys.argv[0]))
print("args: " + " ".join(sys.argv[1:]))
print("cwd: " + os.getcwd())
ready = select.select([sys.stdin.buffer], [], [], 0.2)[0]
data = sys.stdin.buffer.read().decode() if ready else ""
if data.strip():
    print("stdin: " + data.strip())
sys.stdout.write(os.environ.get("STUB_OUT", ""))
sys.stderr.write(os.environ.get("STUB_ERR", ""))
sys.exit(int(os.environ.get("STUB_RC", "0")))
'''


class Server:
    """bin/tezgah-mcp over a pipe the test owns."""

    def __init__(self, home, extra=None):
        env = support.base_env(home, extra=dict(extra or {}))
        # the delegates are resolved as $XDG_CONFIG_HOME/tezgah/bin/<name>
        env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
        self.proc = subprocess.Popen(
            [sys.executable, MCP], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        self._id = 0

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params=None):
        self._id += 1
        self.send({"jsonrpc": "2.0", "id": self._id, "method": method,
                   "params": params or {}})
        return self.reply(self._id)

    def line(self):
        raw = self.proc.stdout.readline()
        if not raw:
            raise AssertionError("the server closed its stdout: %s"
                                 % (self.stderr() or "no stderr"))
        return raw

    def reply(self, msg_id):
        """The reply carrying `msg_id`, whatever arrives in between."""
        while True:
            msg = json.loads(self.line())
            if msg.get("id") == msg_id:
                return msg

    def error_of(self, msg):
        error = msg.get("error")
        if not isinstance(error, dict):
            raise AssertionError("expected an error, got %r" % (msg,))
        return error

    def result_of(self, msg):
        if "error" in msg:
            raise AssertionError("unexpected error: %r" % (msg["error"],))
        return msg.get("result")

    def stderr(self):
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)
        return (self.proc.stderr.read() or "").strip()[-400:]

    def close(self):
        """EOF, then the exit status: a closed pipe must end the server."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            status = self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            status = None
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        return status


class McpTest(support.TempHome):
    """A throwaway HOME carrying a stub for every tezgah command the tools run."""

    def setUp(self):
        super().setUp()
        self.bin = os.path.join(self.home, ".config", "tezgah", "bin")
        self.asked = os.path.join(self.home, "asked")
        os.makedirs(self.bin, exist_ok=True)
        os.makedirs(self.asked, exist_ok=True)
        self.servers = []

    def tearDown(self):
        for srv in self.servers:
            srv.close()

    def stub(self, name):
        path = os.path.join(self.bin, name)
        with open(path, "w") as fh:
            fh.write("#!%s\n%s" % (sys.executable, STUB))
        os.chmod(path, 0o755)
        return path

    def server(self, extra=None):
        for program, _ in DELEGATE.values():
            self.stub(program)
        srv = Server(self.home, extra)
        self.servers.append(srv)
        return srv

    def call(self, srv, name, args=None):
        return srv.result_of(srv.request("tools/call",
                                         {"name": name, "arguments": args or {}}))

    def text(self, result):
        """Every content block's text, joined: what the card shows."""
        return "\n".join(block["text"] for block in result["content"])

    def summary(self, result):
        return self.text(result).splitlines()[0]

    def log(self, result):
        """The lines after the summary: the delegate's own output."""
        return self.text(result).splitlines()[1:]

    def tools(self, srv):
        return srv.result_of(srv.request("tools/list"))["tools"]


class Handshake(McpTest):
    def test_initialize_and_the_notification_after_it(self):
        srv = self.server()
        result = srv.result_of(srv.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"}}))
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"]["name"], "tezgah")
        self.assertIn("tools", result["capabilities"])
        # the notification is not answered: the very next line is the reply to
        # the request that follows it
        srv.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        srv.send({"jsonrpc": "2.0", "id": 99, "method": "tools/list",
                  "params": {}})
        self.assertEqual(json.loads(srv.line())["id"], 99)
        self.assertEqual(srv.close(), 0)

    def test_the_tool_list_is_five_tools_with_tight_schemas(self):
        tools = self.tools(self.server())
        names = [t["name"] for t in tools]
        self.assertLessEqual(len(tools), 5)
        self.assertEqual(set(names), set(PROPERTIES))
        for spec in tools:
            name = spec["name"]
            schema = spec["inputSchema"]
            self.assertEqual(schema["type"], "object")
            self.assertEqual(set(schema["properties"]), PROPERTIES[name])
            self.assertFalse(schema["additionalProperties"])
            self.assertTrue(set(schema["required"]) <= set(schema["properties"]))
            self.assertIn(" ".join(p for p in DELEGATE[name] if p),
                          spec["description"])
            for prop in schema["properties"].values():
                self.assertEqual(prop["type"], "string")

    def test_a_malformed_line_is_an_error_and_the_loop_continues(self):
        srv = self.server()
        srv.proc.stdin.write("this is not json\n")
        srv.proc.stdin.flush()
        error = srv.error_of(json.loads(srv.line()))
        self.assertEqual(error["code"], -32700)
        self.assertEqual(len(self.tools(srv)), len(PROPERTIES))
        self.assertEqual(srv.close(), 0)

    def test_eof_is_a_clean_exit(self):
        srv = self.server()
        srv.request("initialize", {})
        self.assertEqual(srv.close(), 0)


class Calls(McpTest):
    def cases(self):
        """Each tool with every property it declares, and what the delegate and
        the server's own cwd must then show."""
        asked = self.asked
        here = os.path.realpath(os.getcwd())
        return {
            # tezgah-status reports on the directory it is given, so the path is
            # its argument and not where it runs
            "tezgah_status": ({"path": asked}, None, here),
            "tezgah_gate_check": ({"command": "echo mcp-gate", "path": asked},
                                  "echo mcp-gate", here),
            "tezgah_features": ({}, None, here),
            "tezgah_consult": ({"question": "mcp consult question"}, None, here),
            # tezgah-research check is repo-scoped, so the path is its cwd
            "tezgah_research_check": ({"path": asked}, None, asked),
        }

    def test_every_tool_runs_its_own_command_with_every_property_it_declares(self):
        srv = self.server()
        for name, (args, stdin_text, cwd) in self.cases().items():
            program, argv = DELEGATE[name]
            expected = argv if argv is not None else next(
                v for v in args.values())
            log = "\n".join(self.log(self.call(srv, name, args)))
            self.assertIn("program: %s" % program, log, name)
            self.assertIn("args: %s" % expected, log, name)
            self.assertIn("cwd: %s" % cwd, log, name)
            if stdin_text:
                self.assertIn("stdin: ", log, name)
                self.assertIn(stdin_text, log, name)
                # the path is the scope the gate judges, so it must arrive there
                self.assertIn('"cwd": "%s"' % args["path"], log, name)
            else:
                # nothing to feed it: the delegate gets no pipe at all
                self.assertNotIn("stdin: ", log, name)
        self.assertEqual(srv.close(), 0)

    def test_a_property_absent_from_the_call_is_absent_from_the_delegate(self):
        srv = self.server()
        log = self.log(self.call(srv, "tezgah_status"))
        self.assertNotIn(self.asked, "\n".join(log))
        self.assertIn("args: ", "\n".join(log))
        research = self.log(self.call(srv, "tezgah_research_check"))
        self.assertNotIn(self.asked, "\n".join(research))

    def test_the_summary_comes_first_and_the_log_follows_verbatim(self):
        srv = self.server({"STUB_OUT": "out-a\nout-b\n", "STUB_ERR": "err-a\n"})
        result = self.call(srv, "tezgah_status")
        text = self.text(result)
        first = text.splitlines()[0]
        self.assertTrue(first.startswith("tezgah_status: "), first)
        self.assertIn("tezgah-status", first)
        self.assertIn("exited 0", first)
        self.assertEqual(text.splitlines()[1:],
                         ["program: tezgah-status", "args: ",
                          "cwd: %s" % os.path.realpath(os.getcwd()),
                          "out-a", "out-b", "err-a"])
        self.assertNotIn(first, self.log(result))
        self.assertNotIn("isError", result)

    def test_a_failing_delegate_is_the_call_s_own_error(self):
        srv = self.server({"STUB_RC": "3", "STUB_ERR": "tezgah-status: boom\n"})
        result = self.call(srv, "tezgah_status")
        self.assertTrue(result["isError"])
        self.assertIn("exited 3", self.summary(result))
        self.assertIn("tezgah-status: boom", self.log(result))
        self.assertEqual(srv.close(), 0)

    def test_a_delegate_that_cannot_run_is_the_call_s_own_error(self):
        # the resolution falls back to the checkout's own copy, so the way to
        # reach the failure is a working directory that is not there
        srv = self.server()
        missing = os.path.join(self.home, "not-here")
        result = self.call(srv, "tezgah_research_check", {"path": missing})
        self.assertTrue(result["isError"])
        self.assertIn("did not run", self.summary(result))
        self.assertIn("did not start", self.log(result)[0])
        self.assertEqual(srv.close(), 0)

    def test_a_delegate_never_reads_the_server_s_own_stdin(self):
        srv = self.server()
        self.call(srv, "tezgah_features")
        # a delegate handed the JSON-RPC pipe would have read the request that
        # follows this one, so the caller's next call would never be answered
        self.assertEqual(len(self.tools(srv)), len(PROPERTIES))
        self.assertEqual(srv.close(), 0)

    def test_arguments_are_closed_in_both_directions(self):
        srv = self.server()
        refused = [
            ("tezgah_status", {"path": self.asked, "extra": "x"}, "extra"),
            ("tezgah_consult", {}, "question"),
            ("tezgah_gate_check", {"command": 7}, "command"),
            ("tezgah_features", {"path": self.asked}, "path"),
        ]
        for name, args, word in refused:
            error = srv.error_of(srv.request("tools/call",
                                             {"name": name,
                                              "arguments": args}))
            self.assertEqual(error["code"], -32602)
            self.assertIn(word, error["message"])
        error = srv.error_of(srv.request("tools/call",
                                         {"name": "tezgah_nope",
                                          "arguments": {}}))
        self.assertEqual(error["code"], -32602)
        error = srv.error_of(srv.request("tezgah_nothing", {}))
        self.assertEqual(error["code"], -32601)
        self.assertEqual(len(self.tools(srv)), len(PROPERTIES))
        self.assertEqual(srv.close(), 0)


if __name__ == "__main__":
    unittest.main()
