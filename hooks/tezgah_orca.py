#!/usr/bin/env python3
"""Orca: is this session inside it, which CLI drives it, and what it tracks.

Orca (an IDE for agent sessions) owns worktrees, terminals, its embedded browser
and artifacts, and it exports its own markers into every terminal it starts.
tezgah reads those markers - never writes them - so a session in Orca is told to
create a checkout with `orca worktree create` rather than a raw `git worktree
add` Orca does not list, and `tezgah-status --orca` shows which of a repo's
checkouts Orca tracks. Stdlib only; detection forks nothing, so the session-start
line costs no process. docs/orca.md is the page.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys

# The markers an Orca terminal exports (observed in Orca 1.4.221's env). Any one
# is enough; TERM_PROGRAM=Orca covers a shell that dropped the ORCA_* set.
MARKERS = ("ORCA_WORKTREE_ID", "ORCA_TERMINAL_HANDLE", "ORCA_PANE_KEY")
MAC_APP_CLI = "/Applications/Orca.app/Contents/Resources/bin/orca"
# The file Orca leaves in each per-account codex home it hands out as CODEX_HOME.
MANAGED_HOME = ".orca-managed-home"


def session(env=None):
    """{worktree, terminal, version} when this process runs in an Orca terminal,
    else None. `worktree` is the path half of ORCA_WORKTREE_ID
    (`<repoId>::<path>`)."""
    env = os.environ if env is None else env
    if not any(env.get(k) for k in MARKERS) and env.get("TERM_PROGRAM") != "Orca":
        return None
    return {"worktree": env.get("ORCA_WORKTREE_ID", "").partition("::")[2],
            "terminal": env.get("ORCA_TERMINAL_HANDLE", ""),
            "version": env.get("ORCA_APP_VERSION", "")}


def cli(env=None, platform=None):
    """The argv prefix that runs Orca's CLI, or None. The order is the orca-cli
    skill's: Orca's own ORCA_CLI_COMMAND (WSL), then its exported bin dir, then
    PATH. On Linux outside an Orca terminal a bare `orca` is the GNOME screen
    reader, so only `orca-ide` counts there. TEZGAH_ORCA_BIN pins one binary
    (tests): a missing one is None, never a fallback to the real app."""
    env = os.environ if env is None else env
    platform = platform or sys.platform
    pinned = env.get("TEZGAH_ORCA_BIN")
    if pinned:
        return [pinned] if os.access(pinned, os.X_OK) else None
    if env.get("ORCA_CLI_COMMAND"):
        return shlex.split(env["ORCA_CLI_COMMAND"])
    bindir = env.get("ORCA_CLI_BIN_DIR")
    if bindir and os.access(os.path.join(bindir, "orca"), os.X_OK):
        return [os.path.join(bindir, "orca")]
    path = env.get("PATH", os.defpath)
    name = ("orca-ide" if platform.startswith("linux") and not session(env)
            else "orca")
    found = shutil.which(name, path=path)
    if found:
        return [found]
    if platform == "darwin" and os.access(MAC_APP_CLI, os.X_OK):
        return [MAC_APP_CLI]
    return None


def run(args, timeout=10):
    """`orca <args> --json`'s `result`, or None when there is no CLI, the
    runtime is down or the answer is not `ok`."""
    argv = cli()
    if not argv:
        return None
    try:
        proc = subprocess.run(argv + list(args) + ["--json"], capture_output=True,
                              text=True, timeout=timeout)
        data = json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return data.get("result") if isinstance(data, dict) and data.get("ok") else None


def checkouts(paths):
    """Orca's view of a repository's git checkouts (`paths`, real paths):
    {"tracked": [row per checkout Orca lists], "untracked": [path Orca does not
    list]}, or None when the runtime cannot answer. Read from `orca worktree ps`,
    the one call that carries terminals and agent states together."""
    ps = run(["worktree", "ps", "--limit", "1000"])
    if ps is None:
        return None
    wanted = set(paths)
    tracked = {}
    for row in ps.get("worktrees") or []:
        path = os.path.realpath(row.get("path") or "")
        if path in wanted:
            tracked[path] = {
                "path": path, "name": row.get("displayName") or "",
                "card": row.get("workspaceStatus") or "",
                "status": row.get("status") or "",
                "terminals": row.get("liveTerminalCount") or 0,
                "agents": ["%s:%s" % (a.get("agentType"), a.get("state"))
                           for a in row.get("agents") or []]}
    return {"tracked": [tracked[p] for p in paths if p in tracked],
            "untracked": [p for p in paths if p not in tracked]}


def context_line(env=None):
    """The session-start line for a session inside Orca, or "" outside it."""
    here = session(env)
    if not here:
        return ""
    where = here["worktree"] or "unknown"
    return ("Orca: this session runs in an Orca terminal (worktree `%s`); Orca "
            "owns worktrees, terminals, its embedded browser and artifacts here. "
            "A parallel slice that needs its own checkout gets one from `orca "
            "worktree create --name <slug> --parent-worktree active --json` (add "
            "`--agent <cli> --prompt <brief>` to start its worker there), not "
            "`git worktree add`, which Orca does not list. A long job runs in "
            "`orca terminal create --worktree <selector> --command <cmd> --json`, "
            "not a background shell. Track with `orca worktree ps --json` and "
            "`tezgah-status --orca`; mark checkpoints with `orca worktree set "
            "--worktree active --comment <text>`. Full guide: `orca skills get "
            "orca-cli`." % where)


def summary(codex_home):
    """One `orca:` line for `tezgah-setup --status`: app/runtime, whether this
    shell is in an Orca terminal, and whose codex home CODEX_HOME names; ""
    when Orca is neither installed nor around this shell."""
    argv, here = cli(), session()
    if not argv and not here:
        return ""
    runtime = ((run(["status"]) or {}).get("runtime") or {}) if argv else {}
    parts = ["orca: %s" % (
        "runtime %s reachable" % runtime.get("appVersion", "")
        if runtime.get("reachable") else
        "CLI %s, runtime not reachable (`orca open`)" % argv[-1] if argv else
        "no orca CLI found")]
    parts.append("this shell runs in an Orca terminal (worktree %s)"
                 % (here["worktree"] or "unknown") if here
                 else "this shell is not an Orca terminal")
    if os.path.isfile(os.path.join(codex_home, MANAGED_HOME)):
        parts.append("CODEX_HOME %s is an Orca-managed codex home: tezgah adds "
                     "its hook groups beside Orca's and leaves Orca's entries "
                     "and env alone" % codex_home)
    return "; ".join(parts)
