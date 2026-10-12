#!/usr/bin/env python3
"""The setting answers to its new name in every place it can be set.

Four sources (defaults.ini, a --config file, the environment, the command line)
plus the summary line, and no shipped file still naming the old setting in any
of its spellings: snake case, the INI/flag dash form, the environment's upper
case.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def counting():
    calls = []

    def opener(url, timeout):
        calls.append(url)
        raise OSError("down")
    return calls, opener


def drive(argv):
    from fetcher import cli
    calls, opener = counting()
    lines = []
    try:
        cli.main(argv + ["--backoff", "0"], opener=opener, env={}, out=lines.append)
        failures.append("%r: fetch did not raise" % argv)
    except OSError:
        pass
    except SystemExit as exc:
        failures.append("%r: the command line rejected it (exit %s)" % (argv, exc.code))
    except Exception as exc:
        failures.append("%r raised %r" % (argv, exc))
    return len(calls), lines


def main():
    from fetcher import settings
    loaded = settings.load(env={})
    expect(loaded.get("retry_limit"), 3, "defaults retry_limit")
    expect(sorted(loaded), ["backoff", "retry_limit", "timeout"], "setting names")
    expect(settings.load(env={"FETCHER_RETRY_LIMIT": "7"}).get("retry_limit"), 7,
           "FETCHER_RETRY_LIMIT=7")
    example = settings.load("config/example.ini", env={})
    expect(example.get("retry_limit"), 6, "config/example.ini retry_limit")

    tries, lines = drive(["http://example.invalid", "--retry-limit", "5"])
    expect(tries, 6, "--retry-limit 5: tries")
    expect(any("retry_limit=5" in line for line in lines), True,
           "--retry-limit 5: summary names retry_limit=5 (got %r)" % lines)
    tries, lines = drive(["http://example.invalid", "--config", "config/example.ini"])
    expect(tries, 7, "--config config/example.ini: tries")

    old = re.compile(r"max[-_ ]?retries", re.IGNORECASE)
    shipped = [p for p in Path("fetcher").rglob("*.py")]
    shipped += list(Path("config").glob("*")) + [Path("README.md")]
    for path in shipped:
        for number, line in enumerate(open(path).read().splitlines(), 1):
            if old.search(line):
                failures.append("%s:%d still names the old setting: %s"
                                % (path, number, line.strip()))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % exc)
    for detail in failures:
        print(detail)
    print("rename: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
