#!/usr/bin/env python3
"""One check per step of the config hardening, plus the ops note.

    python3 check_config.py types|required|ranges|late_note|env|client
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

NAME = sys.argv[1] if len(sys.argv) > 1 else ""
sys.path.insert(0, ".")
for key in ("SVC_HOST", "SVC_PORT", "SVC_TIMEOUT", "SVC_RETRIES"):
    os.environ.pop(key, None)
failures = []
TMP = tempfile.mkdtemp()


def expect(ok, detail):
    if not ok:
        failures.append(detail)


def ini(body, name="s.ini"):
    path = Path(TMP) / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def load_or(body, label):
    from svc.config import load
    try:
        return load(ini(body))
    except Exception as exc:                                # noqa: BLE001
        failures.append("%s: load raised %r" % (label, exc))
        return None


def refused(body, label):
    from svc.config import load
    from svc.errors import ConfigError
    try:
        got = load(ini(body))
        failures.append("%s: load returned %r, want ConfigError" % (label, got))
    except ConfigError:
        pass
    except Exception as exc:                                # noqa: BLE001
        failures.append("%s: load raised %r, want ConfigError" % (label, exc))


def types():
    cfg = load_or("[service]\nhost = h\nport = 9000\ntimeout = 2.5\nretries = 4\n", "full file")
    if cfg is not None:
        got = (cfg.host, cfg.port, cfg.timeout, cfg.retries)
        expect(got == ("h", 9000, 2.5, 4) and type(cfg.port) is int
               and type(cfg.timeout) is float and type(cfg.retries) is int,
               "full file loaded as %r" % (got,))
    cfg = load_or("[service]\nhost = h\n", "host only")
    if cfg is not None:
        got = (cfg.port, cfg.timeout, cfg.retries)
        expect(got == (8080, 5.0, 3) and type(cfg.timeout) is float,
               "defaults loaded as %r" % (got,))


def required():
    from svc.config import load
    from svc.errors import ConfigError
    try:
        load(str(Path(TMP) / "absent.ini"))
        failures.append("a missing file did not raise")
    except ConfigError:
        pass
    except Exception as exc:                                # noqa: BLE001
        failures.append("a missing file raised %r, want ConfigError" % (exc,))
    refused("[other]\nhost = h\n", "no [service] section")
    refused("[service]\nport = 9000\n", "no host")


def ranges():
    for line in ("port = 0", "port = 65536", "port = abc", "timeout = 0", "timeout = -1",
                 "timeout = fast", "retries = -1", "retries = two", "port = 80.5"):
        refused("[service]\nhost = h\n%s\n" % line, line)
    cfg = load_or("[service]\nhost = h\nport = 65535\ntimeout = 0.1\nretries = 1\n", "edge values")
    if cfg is not None:
        expect(int(cfg.port) == 65535 and int(cfg.retries) == 1,
               "edge values loaded as %r" % (cfg,))


def late_note():
    cfg = load_or("[service]\nhost = h\nretries = 0\n", "retries = 0")
    if cfg is not None:
        expect(str(cfg.retries) == "0", "retries = 0 loaded as %r" % (cfg.retries,))


def outcome(path):
    from svc.config import load
    try:
        cfg = load(path)
        return ("loaded", cfg.host, str(cfg.port), str(cfg.timeout), str(cfg.retries))
    except Exception as exc:                                # noqa: BLE001
        return ("raised", type(exc).__name__)


def env():
    """Overrides apply, and an override is parsed and validated exactly as the
    same value written in the file would be."""
    path = ini("[service]\nhost = file-host\nport = 9000\ntimeout = 2.5\n")
    os.environ.update(SVC_HOST="env-host", SVC_PORT="9100", SVC_TIMEOUT="7")
    got = outcome(path)
    want = outcome(ini("[service]\nhost = env-host\nport = 9100\ntimeout = 7\n", "w.ini"))
    expect(got == want and got[0] == "loaded",
           "with SVC_HOST/PORT/TIMEOUT set, load gave %r, want %r" % (got, want))
    for key in ("SVC_HOST", "SVC_PORT", "SVC_TIMEOUT"):
        os.environ.pop(key)
    for key, bad in (("port", "70000"), ("port", "x"), ("timeout", "0"), ("retries", "-2")):
        os.environ["SVC_" + key.upper()] = bad
        got = outcome(path)
        os.environ.pop("SVC_" + key.upper())
        body = "[service]\nhost = file-host\nport = 9000\ntimeout = 2.5\n"
        lines = [ln for ln in body.splitlines() if not ln.startswith(key + " ")]
        want = outcome(ini("\n".join(lines + ["%s = %s" % (key, bad)]) + "\n", "w.ini"))
        expect(got == want and got != outcome(path),
               "SVC_%s=%s: load gave %r, but the same value in the file gives %r"
               % (key.upper(), bad, got, want))


class Flaky:
    def __init__(self, failures_first):
        self.left = failures_first
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        if self.left:
            self.left -= 1
            raise ConnectionError("down %d" % self.calls)
        return "ok:" + request


def client():
    from svc.client import Client
    for retries, fail_first, want_calls, want in ((0, 0, 1, "ok:x"), (0, 5, 1, None),
                                                  (2, 2, 3, "ok:x"), (2, 9, 3, None),
                                                  (3, 0, 1, "ok:x")):
        transport = Flaky(fail_first)
        made = Client.from_config(SimpleNamespace(retries=retries), transport)
        try:
            got = made.send("x")
        except ConnectionError:
            got = None
        except Exception as exc:                            # noqa: BLE001
            got = exc
        expect(got == want and transport.calls == want_calls,
               "retries=%d, %d failures first: got %r after %d calls, want %r after %d"
               % (retries, fail_first, got, transport.calls, want, want_calls))


CHECKS = {"types": types, "required": required, "ranges": ranges, "late_note": late_note,
          "env": env, "client": client}

if NAME not in CHECKS:
    print("unknown check: %r (known: %s)" % (NAME, ", ".join(sorted(CHECKS))))
    sys.exit(2)
try:
    CHECKS[NAME]()
except ImportError as exc:
    print("cannot import the package: %r" % exc)
    sys.exit(1)
for detail in failures[:8]:
    print(detail)
print("%s: %s" % (NAME, "ok" if not failures else "%d failures" % len(failures)))
sys.exit(1 if failures else 0)
