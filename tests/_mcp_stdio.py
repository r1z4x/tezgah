#!/usr/bin/env python3
"""Minimal MCP stdio client for the opt-in app-analysis smoke tests.

Speaks just enough JSON-RPC over stdio - initialize, tools/list, tools/call - to
prove a wired MCP server starts and exposes its tools. Stdlib only, so it runs
anywhere Python does; the servers themselves need node/npx.
"""
import json
import os
import subprocess


class McpError(RuntimeError):
    pass


class Client:
    def __init__(self, command, env=None, timeout=90):
        self.timeout = timeout
        self._id = 0
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
            env=env if env is not None else os.environ.copy())

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _read(self):
        line = self.proc.stdout.readline()
        if not line:
            err = (self.proc.stderr.read() or "").strip()
            raise McpError("server closed the pipe: %s" % (err[-400:] or "no stderr"))
        return json.loads(line)

    def request(self, method, params=None):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method,
                    "params": params or {}})
        while True:
            msg = self._read()
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise McpError(msg["error"])
                return msg.get("result", {})

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tezgah-e2e", "version": "0"}})
        self.notify("notifications/initialized")
        return result

    def tools(self):
        return [t["name"] for t in self.request("tools/list").get("tools", [])]

    def call(self, name, args=None):
        return self.request("tools/call", {"name": name, "arguments": args or {}})

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
