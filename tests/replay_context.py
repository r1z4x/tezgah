#!/usr/bin/env python3
"""Replay real prompt sequences through `context_for` on two revisions and
print the bytes injected per session.

  python3 tests/replay_context.py [--base REV] [--head REV]
                                  [--host omp|claude|all] [--root DIR] [--json]

The sessions are the top-level omp and Claude transcripts `bin/tezgah-taste
mine` reads (same walkers, same `--root`, read-only). Each one replays as the
hosts deliver it: `session_start` (the core lives in the host's file on both,
so `with_core=False`), one `user_prompt` per user prompt that is not a harness
injection, and at each compaction omp's `post_compact` or Claude's
`session_start` with `source=compact`. Each revision is exported with
`git archive` and runs in its own throwaway HOME against one empty project
under `TEZGAH_ROOTS`, with no codegraph and no provider key, so the two
revisions see the same state and only their hook text differs. The bytes are
the UTF-8 length of every block `context_for` returns.

Prints n sessions and, per revision, the median, p90 and total bytes per
session, then head/base ratios. Exit 0 done, 2 misuse.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
HOSTS = ("omp", "claude")
# Variables that point a hook at real config or a provider: dropped from the
# child's environment so the replay reads only its throwaway HOME.
DROP_PREFIX = ("TEZGAH_", "XDG_", "CLAUDE_", "OMP_")
DROP_EXACT = {"CODEX_HOME", "DSH_HOME"}
DROP_SUFFIX = ("_API_KEY", "_TOKEN")


def taste():
    """`bin/tezgah-taste` as a module: its walkers define a session here too."""
    path = os.path.join(HERE, "bin", "tezgah-taste")
    loader = importlib.machinery.SourceFileLoader("tezgah_taste_cli", path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def events_of(t, host, path):
    """('prompt', text) and ('compact',) in transcript order."""
    for row in t.rows_of(path):
        if host == "omp" and row.get("type") == "compaction":
            yield ("compact",)
            continue
        if host == "claude" and row.get("isCompactSummary"):
            yield ("compact",)
            continue
        m = row.get("message")
        if not isinstance(m, dict) or m.get("role") != "user" or row.get("isMeta"):
            continue
        content = m.get("content")
        if isinstance(content, list) and any(
                isinstance(p, dict) and p.get("type") == "tool_result" for p in content):
            continue
        text = t.text_of(content)
        if not t.harness_prompt(text) and "[Request interrupted by user" not in text:
            yield ("prompt", text)


def mine(host="all", root=None):
    """[{host, id, events}] for every top-level session holding a prompt."""
    t = taste()
    root = os.path.abspath(os.path.expanduser(root or "~/Projects"))
    out = []
    for h in (HOSTS if host == "all" else (host,)):
        for path, _cwd in t.sessions(h, root):
            events = list(events_of(t, h, path))
            if any(e[0] == "prompt" for e in events):
                sid = t.session_id(h, path)[0] or os.path.basename(path)
                out.append({"host": h, "id": sid, "events": events})
    return out


def child_env(home):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(DROP_PREFIX) and k not in DROP_EXACT
           and not k.endswith(DROP_SUFFIX)}
    env.update(HOME=home, TEZGAH_ROOTS=os.path.join(home, "Projects"),
               TEZGAH_CODEGRAPH_BIN=os.path.join(home, "no-codegraph"))
    return env


def replay(hooks, sessions, scratch):
    """Bytes per session (input order) for the `hooks/` directory given, in a
    fresh HOME under `scratch`."""
    home = tempfile.mkdtemp(prefix="home-", dir=scratch)
    os.makedirs(os.path.join(home, "Projects", "p"))
    feed = os.path.join(home, "sessions.json")
    with open(feed, "w", encoding="utf-8") as fh:
        json.dump(sessions, fh)
    out = subprocess.run(
        [sys.executable, os.path.realpath(__file__), "--child", hooks, feed],
        cwd=home, env=child_env(home), capture_output=True, text=True, check=False)
    if out.returncode:
        raise SystemExit("replay failed in %s:\n%s" % (hooks, out.stderr))
    return json.loads(out.stdout)


def child(hooks, feed):
    """Runs inside the throwaway HOME: one process, every session in turn."""
    sys.path.insert(0, hooks)
    import tezgah_context as tc
    cwd = os.path.join(os.environ["HOME"], "Projects", "p")
    with open(feed, encoding="utf-8") as fh:
        sessions = json.load(fh)
    sizes = []
    for s in sessions:
        base = {"session_id": s["id"], "host": s["host"]}

        def size(event, **extra):
            text = tc.context_for(event, cwd, dict(base, **extra), with_core=False)
            return len((text or "").encode("utf-8"))
        total = size("session_start", source="startup")
        for e in s["events"]:
            if e[0] == "prompt":
                total += size("user_prompt", prompt=e[1])
            elif s["host"] == "omp":
                total += size("post_compact")
            else:
                total += size("session_start", source="compact")
        sizes.append(total)
    json.dump(sizes, sys.stdout)


def stats(sizes):
    """median, p90 (nearest rank) and total of a list of byte counts."""
    s = sorted(sizes)
    if not s:
        return {"median": 0, "p90": 0, "total": 0}
    mid = len(s) // 2
    median = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    p90 = s[max(0, -(-9 * len(s) // 10) - 1)]
    return {"median": median, "p90": p90, "total": sum(s)}


def export(rev, dest):
    """`rev`'s hooks/ directory, unpacked under `dest`."""
    os.makedirs(dest)
    archive = subprocess.run(["git", "-C", HERE, "archive", rev], capture_output=True,
                             check=True).stdout
    subprocess.run(["tar", "-x", "-C", dest], input=archive, check=True)
    return os.path.join(dest, "hooks")


def compare(sessions, base_hooks, head_hooks, scratch):
    before = replay(base_hooks, sessions, scratch)
    after = replay(head_hooks, sessions, scratch)
    b, a = stats(before), stats(after)
    return {"n": len(sessions),
            "prompts": sum(e[0] == "prompt" for s in sessions for e in s["events"]),
            "compactions": sum(e[0] == "compact" for s in sessions for e in s["events"]),
            "base": b, "head": a,
            "ratio": {k: round(a[k] / b[k], 4) if b[k] else None for k in b}}


def main(argv):
    if argv[:1] == ["--child"]:
        child(argv[1], argv[2])
        return 0
    ap = argparse.ArgumentParser(prog="replay_context.py")
    ap.add_argument("--base", default="c1bd5fe")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--host", choices=("omp", "claude", "all"), default="all")
    ap.add_argument("--root")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    sessions = mine(args.host, args.root)
    if not sessions:
        print("replay_context: no session with a prompt", file=sys.stderr)
        return 2
    scratch = tempfile.mkdtemp(prefix="tezgah-replay-")
    try:
        result = compare(sessions, export(args.base, os.path.join(scratch, "base")),
                         export(args.head, os.path.join(scratch, "head")), scratch)
    finally:
        shutil.rmtree(scratch)  # created by mkdtemp above, nothing else
    result.update(base_rev=args.base, head_rev=args.head)
    if args.json:
        print(json.dumps(result))
        return 0
    print("sessions=%d prompts=%d compactions=%d"
          % (result["n"], result["prompts"], result["compactions"]))
    for side in ("base", "head"):
        r = result[side]
        print("%s %s: median=%s p90=%s total=%s bytes/session"
              % (side, result[side + "_rev"], r["median"], r["p90"], r["total"]))
    print("head/base: median=%s p90=%s total=%s" % (
        result["ratio"]["median"], result["ratio"]["p90"], result["ratio"]["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
