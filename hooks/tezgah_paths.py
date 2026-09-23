#!/usr/bin/env python3
"""Where tezgah is armed, what it is armed with, and which kill switches are on.

Shared by every host adapter - the Claude Code hooks, the Codex hooks, the
Cursor hooks, the opencode plugin and the status line - so there is exactly one
answer to "is this repo armed". Stdlib only, importable from any Python.

Roots, in order of precedence:
  1. TEZGAH_ROOTS  - os.pathsep-separated list (CI and one-offs)
  2. ~/.config/tezgah/config.json  {"roots": ["~/Projects", "~/work"]}
  3. ~/Projects    - the historical default, so an existing setup keeps working
Hooks are spawned by the app, not by an interactive shell, so the config file
is the reliable channel; the env var is the escape hatch, not the contract.
"""
import json
import os
import sys

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "tezgah")
CONFIG = os.path.join(CONFIG_DIR, "config.json")
BIN_DIR = os.path.join(CONFIG_DIR, "bin")
STATE_DIR = os.path.join(CONFIG_DIR, "state")
CACHE = os.path.join(HOME, ".cache", "tezgah")
# Hosts that sandbox hook file writes (dsh workspace-write) deny writes to the
# global cache; state that must be written from a hook falls back to the
# platform temp dir, which the sandbox always allows. TEZGAH_FALLBACK_CACHE
# overrides the fallback (tests). Resolved by `fallback_cache()` rather than at
# import: `tempfile` costs ~4 ms of every gated call's import and the tool gate,
# which imports this module, never asks for a cache dir.
DEFAULT_ROOT = os.path.join(HOME, "Projects")
# this file lives in <plugin>/hooks, so the plugin root is one level up and
# every path advertised to a model is derived from here rather than hardcoded
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEGRAPH = "codegraph"
ORX = "orx"
# Tools installed by their own installers land here without the user's shell PATH
# being updated (non-interactive hook/CI shells), so a lookup falls back to these
# per-user bin dirs before declaring a tool missing.
USER_BINS = (os.path.join(HOME, ".local", "bin"), os.path.join(HOME, ".cargo", "bin"))
# canonical kill switches live in CONFIG_DIR; the pre-multi-host setup wrote
# them to ~/.claude, so that stays a recognized channel
OFF_DIRS = (CONFIG_DIR, os.path.join(HOME, ".claude"))
# Where each host keeps its config. One definition, shared by the installer
# (which writes into these) and the agent generator (which decides whose
# per-repo subagent files to render), so "is this host installed?" cannot mean
# two different things in the two places that ask.
XDG_CONFIG = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
HOST_DIRS = {
    "claude": os.path.join(HOME, ".claude"),
    # codex reads a relocated home from CODEX_HOME (an embedding app such as Orca
    # hands each account its own), and that home is the one a codex session
    # actually loads - so it is the one to install into and to check. dsh below
    # follows the same pattern for DSH_HOME.
    "codex": os.environ.get("CODEX_HOME") or os.path.join(HOME, ".codex"),
    "cursor": os.path.join(HOME, ".cursor"),
    "opencode": os.path.join(XDG_CONFIG, "opencode"),
    "dsh": os.environ.get("DSH_HOME") or os.path.join(HOME, ".dsh"),
    "omp": os.path.join(HOME, ".omp"),
}
# a host can be installed with no config dir yet (a CLI on PATH is enough)
HOST_BINS = {"cursor": ("cursor-agent", "cursor"), "opencode": ("opencode",),
             "dsh": ("dsh",), "omp": ("omp",)}


def host_installed(name):
    """True when this host is present on this machine.

    The config dir is the primary signal; the CLI covers a host that is
    installed but has not been run yet. Both the installer's detection report
    and the per-repo agent generation answer with this."""
    if os.path.isdir(HOST_DIRS.get(name) or ""):
        return True
    return any(which_user(b) for b in HOST_BINS.get(name, ()))


def config():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # missing, unreadable or malformed: fall back to defaults
        return {}


def writable_dir(path):
    """True when `path` exists (or can be created) and a file can be written in it.

    A sandboxed host denies this outside the workspace; callers use it to pick a
    writable state dir instead of failing on the first write."""
    try:
        os.makedirs(path, exist_ok=True)
        # The probe name is unique per call (pid + random). A fixed name made two
        # concurrent probes share one file: the sibling's remove deleted it under
        # the first probe, whose remove then failed and read the dir as
        # unwritable - which sent that session's whole ledger to the temp
        # fallback. Unique names leave no shared state, so every OSError here is
        # a real denial. (O_CREAT|O_EXCL would still need a unique name to tell
        # "a sibling holds the probe" from "the dir is not writable"; with one,
        # EEXIST cannot arise and no errno needs special-casing.)
        probe = os.path.join(path, ".tezgah-write-probe-%d-%s"
                             % (os.getpid(), os.urandom(6).hex()))
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


# The dir cache_dir() resolved, and the pair of candidate paths it resolved.
# A session that starts resolved to the temp fallback and a later probe that
# succeeds must not move its state: the ledger, the session store and the nudge
# marks are all keyed on this answer, so a change mid-session splits one
# session's evidence across two files. Keyed on the candidates so a caller that
# repoints CACHE (tests) still gets a fresh answer.
_CHOSEN_FOR = None
_CHOSEN_DIR = None


def fallback_cache():
    """The sandbox-writable fallback cache dir: `TEZGAH_FALLBACK_CACHE`, else
    `<tempdir>/tezgah`.

    Resolved on use rather than at import, because `tempfile` costs a few ms of
    every gated call and the tool gate - which imports this module - never asks
    for a cache dir. The env var is read here for the same reason: a hook process
    has its environment fixed at start, so the answer cannot differ within one."""
    override = os.environ.get("TEZGAH_FALLBACK_CACHE")
    if override:
        return override
    import tempfile  # deferred: see the note above
    return os.path.join(tempfile.gettempdir(), "tezgah")


def cache_dir():
    """A writable tezgah state dir: the global cache, else the temp fallback.

    The global cache is preferred so state persists across sessions; sandboxed
    hosts (dsh workspace-write) fall back to temp rather than dropping the
    nudge/gate state on the floor.

    Memoised: the answer is fixed for the life of the process once the candidates
    are fixed, so every writer and reader in one session agrees on one dir. A
    later probe that fails does not move a session's state to the other file."""
    global _CHOSEN_FOR, _CHOSEN_DIR
    candidates = (CACHE, fallback_cache())
    if _CHOSEN_FOR == candidates:
        return _CHOSEN_DIR
    chosen = next((d for d in candidates if writable_dir(d)), CACHE)
    # dir before key, so a concurrent caller reads either both old (it computes
    # the same answer) or both new; never a stored-nowhere None
    _CHOSEN_DIR, _CHOSEN_FOR = chosen, candidates
    return chosen


def ai_research_dir():
    """The vendored domain library, inside the plugin checkout that is running.

    Derived from this file's location, like every other path tezgah advertises,
    so it is right on Claude Code too, which runs the plugin from a copy."""
    return os.path.join(PLUGIN_ROOT, "skills", "ai-research")


def roots():
    """Configured roots as absolute real paths, longest (most specific) first."""
    env = os.environ.get("TEZGAH_ROOTS")
    raw = env.split(os.pathsep) if env else (config().get("roots") or [DEFAULT_ROOT])
    out = set()
    for p in raw:
        p = os.path.expanduser((p or "").strip())
        if not p:
            continue
        try:
            out.add(os.path.realpath(p))
        except OSError:
            pass
    return sorted(out, key=len, reverse=True)


def root_for(path):
    """The configured root containing path, or None when tezgah is not armed here."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return None
    for r in roots():
        if real == r or real.startswith(r + os.sep):
            return r
    return None


def which_user(name):
    """`name` on PATH, else in a known per-user bin dir, else None.

    Accepts an absolute path (TEZGAH_*_BIN overrides) unchanged. Keeps detection
    stable across shells: a tool installed to ~/.cargo/bin reads as present even
    when a non-interactive shell never sourced the rc that adds it to PATH."""
    import shutil  # deferred: see the fallback_cache() note above
    found = shutil.which(name)
    if found or os.path.isabs(name):
        return found
    for d in USER_BINS:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def python_cmd():
    """The interpreter a host hook should be started with.

    Four channels, in the order a machine actually answers them: TEZGAH_PYTHON
    (the override a user pins when their interpreter is not on PATH - Windows
    ships `python`/`py` and never `python3`), this process's own absolute
    interpreter (the one proven to work on this machine), then the names the
    platforms ship, `py` last for Windows. The override is returned as given: an
    absolute path outside PATH is a legitimate answer, and quietly starting a
    different interpreter than the one pinned is worse than failing to start.

    `which_user()` is the lookup, so a per-user bin dir counts and `shutil` stays
    a deferred import - the tool gate imports this module on every call."""
    override = os.environ.get("TEZGAH_PYTHON")
    if override:
        return override
    # A real file only when this process was started from one: an embedded
    # interpreter reports None or "", neither of which is a command.
    if sys.executable and os.path.isabs(sys.executable) \
            and os.path.isfile(sys.executable):
        return sys.executable
    for name in ("python3", "python", "py"):
        found = which_user(name)
        if found:
            return found
    # Nothing resolved anywhere: the first documented name, so the host reports
    # "python3: not found" - a named error - instead of a command with no name.
    return "python3"


def hook_command(script):
    """The command string a host hook manifest should carry for `script`.

    One place formats the interpreter/script pair, so a manifest, a template and
    an installer line cannot disagree about it. Both halves are quoted, because
    either can carry a space (`C:\\Program Files\\Python\\python.exe`, a home dir
    under `~/My Projects`) and the host runs this string through its own shell.
    Plain quotes rather than `shlex.quote`: cmd.exe has no single-quote form, so
    a POSIX-only quote would make the Windows half unreadable there."""
    return '"%s" "%s"' % (python_cmd(), script)


def codegraph_bin():
    """The codegraph executable, or None when it is not installed.

    Three channels: a pin (`TEZGAH_CODEGRAPH_BIN`), the config file, then PATH -
    the same shape the retired codebase-memory-mcp resolver had, because the pin
    is what a test or a CI job needs and the config is what an install writes."""
    return which_user(os.environ.get("TEZGAH_CODEGRAPH_BIN")
                      or config().get("codegraph_bin") or CODEGRAPH)


def have_consult_key():
    """True when a consult/codegen provider key is present: OpenRouter,
    DeepSeek or Inception, since both `consult` and `codegen` accept
    `--provider deepseek` / `--provider inception`."""
    return bool(os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("DEEPSEEK_API_KEY")
                or os.environ.get("INCEPTION_API_KEY")
                or os.path.exists(os.path.join(HOME, ".config", "openrouter", "key"))
                or os.path.exists(os.path.join(HOME, ".config", "deepseek", "key"))
                or os.path.exists(os.path.join(HOME, ".config", "inception", "key")))


def have_typesafe_key():
    """True when omp can resolve its TypeSafe (Jev) credential: the env var it
…
    reads, or a record in its own login store (`omp auth login typesafe`). omp
    spends this key on `judge()`, auto thinking, unexpected-stop and AI staging
    and silently falls back to a chat model without it. `~/.config/typesafe/key`
    is tezgah's own key-file convention, not a path omp opens, so a key file
    alone does not count here - it only reaches omp through an export. The seam's
    own question is `have_judge_key()`, and the two answers differ in both
    directions."""
    if os.environ.get("TYPESAFE_API_KEY"):
        return True
    store = os.path.join(HOME, ".omp", "agent", "agent.db")
    import sqlite3  # deferred: ~4 ms of every gated call's import, for a store
    try:            # that only the health lines and this question ever open
        with sqlite3.connect("file:%s?mode=ro" % store, uri=True) as conn:
            return conn.execute(
                "select 1 from auth_credentials where provider = ?",
                ("typesafe",)).fetchone() is not None
    except (sqlite3.Error, OSError):
        return False


def have_judge_key():
    """True when tezgah's own judgement seam resolves a credential: the env var
    it reads, else its key file - and, when neither resolves, the OpenRouter
    fallback's own two channels (`OPENROUTER_API_KEY`, `~/.config/openrouter/key`),
    which are the channels `hooks/tezgah_judge.py`'s `credential()` picks
    between. This is what `bin/tezgah-triage`, `bin/tezgah-docs` and the skill
    picker spend. Never omp's login store: the seam does not open it.

    Kept next to `have_typesafe_key()` because the two are asked together and a
    report that showed one answer under both questions was wrong in both
    directions - a key file alone (seam works, omp does not) and a login-store
    record alone (omp works, seam does not). A blank file is not a credential
    here either, so this stays in step with the seam's own `strip() or None`."""
    for env, home in (("TYPESAFE_API_KEY", ".config/typesafe/key"),
                      ("OPENROUTER_API_KEY", ".config/openrouter/key")):
        if os.environ.get(env, "").strip():
            return True
        try:
            with open(os.path.join(HOME, home), encoding="utf-8") as fh:
                if fh.read().strip():
                    return True
        except OSError:
            pass
    return False


def orx_bin():
    """The OpenResearch `orx` executable, or None when it is not installed.

    TEZGAH_ORX_BIN points at a specific binary (tests, CI); otherwise the first
    `orx` on PATH wins, then a known per-user bin dir. Mirrors `codegraph_bin()` so a
    missing tool is a clean None, not a failed lookup at call time."""
    return which_user(os.environ.get("TEZGAH_ORX_BIN") or ORX)


def off(name):
    """A kill switch, canonical (~/.config/tezgah) or legacy (~/.claude)."""
    return any(os.path.exists(os.path.join(d, name)) for d in OFF_DIRS)


def armed(name):
    """An opt-in marker, in the same places the kill switches live.

    `off()` cannot express "the user asked for this": a capability that is off
    until it is wanted needs the opposite file, or a rule the session was simply
    never armed with and a rule the user switched off would look the same."""
    return any(os.path.exists(os.path.join(d, name)) for d in OFF_DIRS)


PONY_LEVEL = os.path.join(CONFIG_DIR, "ponytail.level")
PONY_LEVELS = ("lite", "full", "ultra")


def pony_level():
    """The armed ponytail intensity level, `full` unless the user set one.

    One machine-wide setting rather than a per-session one: the switch is a
    file `bin/tezgah-pony` writes, and a session-keyed level would need a
    session id the CLI does not have. An unreadable or unknown value falls back
    to the default instead of inventing a level."""
    try:
        with open(PONY_LEVEL, encoding="utf-8") as fh:
            value = fh.read().strip().lower()
    except OSError:
        return "full"
    return value if value in PONY_LEVELS else "full"


def tool(name):
    """Stable installed path for a tezgah CLI, else the plugin's own copy, so
    the text injected into a session names something that actually exists."""
    for p in (os.path.join(BIN_DIR, name), os.path.join(PLUGIN_ROOT, "bin", name)):
        if os.path.exists(p):
            return p
    return os.path.join(BIN_DIR, name)
