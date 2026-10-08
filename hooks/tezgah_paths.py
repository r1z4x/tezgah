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


def stable_root(path):
    """`path` as an install names it: one inside a Homebrew keg
    `<brew>/Cellar/tezgah/<version>/libexec` is named through `<brew>/opt/tezgah`
    when that link resolves to the keg, because the next `brew upgrade`'s
    default cleanup deletes the keg. Anything else - a checkout, a release
    prefix, npm, a keg opt/ does not name - is its own path. bin/tezgah-setup
    renders with it and the hooks attest with it, so both read one root."""
    parts = path.split(os.sep)
    for i in range(1, len(parts) - 3):
        if parts[i:i + 2] == ["Cellar", "tezgah"] and parts[i + 3] == "libexec":
            base = os.sep.join(parts[:i]) or os.sep
            opt = os.path.join(base, "opt", "tezgah")
            if os.path.realpath(opt) != os.path.realpath(os.sep.join(parts[:i + 3])):
                return path
            return os.path.join(opt, *parts[i + 3:])
    return path


# this file lives in <plugin>/hooks, so the plugin root is one level up and
# every path advertised to a model is derived from here rather than hardcoded
PLUGIN_ROOT = stable_root(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODEGRAPH = "codegraph"
ORX = "orx"
# Tools installed by their own installers land here without the user's shell PATH
# being updated (non-interactive hook/CI shells), so a lookup falls back to these
# per-user bin dirs before declaring a tool missing.
USER_BINS = (os.path.join(HOME, ".local", "bin"), os.path.join(HOME, ".cargo", "bin"),
             # opencode's own installer puts its binary here
             os.path.join(HOME, ".opencode", "bin"))
# canonical kill switches live in CONFIG_DIR; the pre-multi-host setup wrote
# them to ~/.claude, so that stays a recognized channel
OFF_DIRS = (CONFIG_DIR, os.path.join(HOME, ".claude"))
# The one list of every name `off()` and `armed()` are asked about, and of the
# repo marks read from a root: the installer's uninstall sweep
# (bin/tezgah-setup OFF_SWITCH_NAMES), the context's off-note (`switches()`),
# the opencode plugin's own `off()` and the gate's control rule all answer from
# it, and tests/test_paths.py fails when any of them names a switch it lacks.
# CORE_SWITCHES are the sixteen the always-on contract names. ADR 007 leaves
# UNCLASSIFIED_SWITCHES open - two `off()` names CORE does not list and two
# opt-in markers read with `armed()` - and until the owner classifies them the
# control rule protects them like the rest (bin/tezgah-docs carries the same
# set for its inventory check; the test pins the two equal).
CORE_SWITCHES = ("adhd-off", "consult-off", "docs-judge-off", "exec-mode.off",
                 "judge-off", "lang-off", "orchestrate-off", "ponytail-auto.off",
                 "pretooluse-off", "reminder-off", "research-off", "spec-off",
                 "task-off", "triage-off", "verify-off", "workspace-off")
UNCLASSIFIED_SWITCHES = ("agents-off", "skill-suggest-on", "taste-on",
                         "update-check-off")
SWITCHES = CORE_SWITCHES + UNCLASSIFIED_SWITCHES
REPO_MARKS = (".no-adhd", ".no-graph", ".no-lessons", ".no-plan-gate",
              ".no-ponytail", ".no-taste")
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
        # The cache holds ledgers and pre-write snapshots of the user's files, so
        # a dir tezgah creates is owner-only; audit SEC-05 measured 0755 from the
        # default umask. makedirs applies the mode to the leaf it creates, and an
        # existing dir keeps the mode the user gave it.
        os.makedirs(path, mode=0o700, exist_ok=True)
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
    """Configured roots as absolute real paths, longest (most specific) first.

    `"roots"` is a list; a string is taken as one root and anything else as the
    default. A string iterated as a list armed `~` (all of HOME) and `.` (cwd)."""
    env = os.environ.get("TEZGAH_ROOTS")
    if env:
        raw = env.split(os.pathsep)
    else:
        raw = config().get("roots")
        raw = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
        raw = [p for p in raw if isinstance(p, str) and p.strip()] or [DEFAULT_ROOT]
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
    """The configured root containing path, or None when tezgah is not armed here.

    A linked worktree outside every root is armed when its main checkout is under
    one, and answers its own top level: every caller treats the answer as a base
    `path` sits under, so the configured root would not do there."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return None
    rs = roots()
    for r in rs:
        if real == r or real.startswith(r + os.sep):
            return r
    top = worktree_top(real)
    if top:
        main = _linked_main_at(top)
        if main and any(main == r or main.startswith(r + os.sep) for r in rs):
            return top
    return None


def _toplevel(real):
    """The nearest directory at or above `real` holding a `.git` entry, else None."""
    cur = real
    while not os.path.lexists(os.path.join(cur, ".git")):
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    return cur


def linked_main(path):
    """The main checkout of the nearest linked worktree holding `path`, else None.

    Nearest only: `worktrees` asks it about the repository it was handed, so a
    repo nested inside a worktree (a vendored clone, a submodule) answers None and
    never the checkout it sits in; `worktree_top` is the ancestor walk `root_for`
    uses. Read from the `.git` pointer file (`gitdir: <main>/.git/worktrees/
    <name>`), never from git: `root_for` runs on every gate call and a session
    start's git forks are pinned. A plain checkout (`.git` is a directory), a
    submodule (a `/modules/` pointer) and a bare main (no `.git` component)
    answer None."""
    top = _toplevel(os.path.realpath(path))
    if not top:
        return None
    return _linked_main_at(top)


def worktree_top(path):
    """The top of the linked worktree holding `path`, else None.

    Every `.git`-holding ancestor is tried, nearest first, so a path under the
    worktree's own `.tezgah` or under a repo nested in it still answers the
    worktree. A `.git` directory, a pointer git did not write and a submodule
    pointer are all skipped in favour of an enclosing worktree."""
    cur = os.path.realpath(path)
    while True:
        if os.path.lexists(os.path.join(cur, ".git")) and _linked_main_at(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _linked_main_at(top):
    """`linked_main` for one directory: its main checkout when `top` is a linked
    worktree, else None. A `.git` pointer whose admin directory git did not write
    (its `commondir` missing) is not a worktree."""
    try:
        with open(os.path.join(top, ".git"), encoding="utf-8") as fh:
            line = fh.readline().strip()
    except (OSError, UnicodeDecodeError):  # a directory is the plain checkout
        return None
    if not line.startswith("gitdir:"):
        return None
    gitdir = os.path.normpath(os.path.join(top, line[len("gitdir:"):].strip()))
    dotgit = os.path.dirname(os.path.dirname(gitdir))
    if os.path.basename(os.path.dirname(gitdir)) != "worktrees" \
            or os.path.basename(dotgit) != ".git" \
            or not os.path.isfile(os.path.join(gitdir, "commondir")):
        return None
    return os.path.realpath(os.path.dirname(dotgit))


def worktrees(repo):
    """Every checkout of the repository `repo` is in, main first, as real paths;
    [] outside a git checkout.

    Fork-free, from `<main>/.git/worktrees/*/gitdir` (each names a linked
    worktree's `.git`). An entry whose target is gone - deleted without `git
    worktree remove` - is skipped: git itself keeps it, marked prunable, until
    `git worktree prune`. Each checkout keeps its own `.tezgah`; this only names
    them."""
    main = linked_main(repo)
    if not main:
        main = _toplevel(os.path.realpath(repo))
        if not main or not os.path.isdir(os.path.join(main, ".git")):
            return []
    base = os.path.join(main, ".git", "worktrees")
    out = [main]
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return out
    for name in names:
        try:
            with open(os.path.join(base, name, "gitdir"), encoding="utf-8") as fh:
                pointer = fh.readline().strip()
        except (OSError, UnicodeDecodeError):
            continue
        dot = os.path.join(base, name, pointer)
        if pointer and os.path.exists(dot):
            out.append(os.path.realpath(os.path.dirname(dot)))
    return out


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


# consult's HTTP providers: name -> (key env var, key file under HOME). codegen
# accepts the same three with `--provider`.
PROVIDER_KEYS = {
    "openrouter": ("OPENROUTER_API_KEY", os.path.join(".config", "openrouter", "key")),
    "deepseek": ("DEEPSEEK_API_KEY", os.path.join(".config", "deepseek", "key")),
    "inception": ("INCEPTION_API_KEY", os.path.join(".config", "inception", "key")),
}
# The agent CLIs consult can ask non-interactively: name -> (argv before the
# model flag and the prompt, the model flag, the model family it answers with).
# Every flag was read from the CLI's own `--help` (omp 18.3.1, claude 2.1.283,
# codex-cli 0.153.4 `exec`, opencode 1.18.31 `run`, cursor-agent 2025.09.12);
# gemini is absent because no install was there to read. The prompt goes last
# as one argument and stdin is /dev/null, so a CLI that wants a login prints
# and exits instead of waiting for a key.
CONSULT_CLIS = {
    "omp": (["omp", "-p", "--no-tools", "--no-session", "--no-rules",
             "--no-skills", "--no-extensions", "--no-title"], "--model",
            "whichever model omp is configured for"),
    # `--tools` is variadic, so a boolean flag must follow it before the prompt
    "claude": (["claude", "-p", "--tools", "", "--no-session-persistence"],
               "--model", "Anthropic Claude"),
    "codex": (["codex", "exec", "--skip-git-repo-check", "--ephemeral",
               "-s", "read-only", "--color", "never"], "-m", "OpenAI GPT"),
    "opencode": (["opencode", "run", "--pure"], "-m",
                 "whichever provider/model opencode is configured for"),
    "cursor-agent": (["cursor-agent", "-p", "--output-format", "text"],
                     "--model", "whichever model Cursor is configured for"),
}


def have_provider_key(provider=None):
    """True when an HTTP provider key is present (env var or key file): for
    `provider`, else for any of them. codegen's question, and one half of
    consult's."""
    names = [provider] if provider else list(PROVIDER_KEYS)
    return any(os.environ.get(PROVIDER_KEYS[p][0])
               or os.path.exists(os.path.join(HOME, PROVIDER_KEYS[p][1]))
               for p in names)


def consult_options():
    """The consult members this machine can run now: `cli:<name>` for each
    agent CLI found, then each HTTP provider whose key is present. Empty means
    the second opinion cannot run at all; every surface asks this.

    TEZGAH_CONSULT_CLIS, when set, is the comma list of CLIs that may count
    (empty: none) - the pin a test or CI job needs, as TEZGAH_CODEGRAPH_BIN is
    for the graph, so the machine's own agent CLIs cannot answer for it."""
    pin = os.environ.get("TEZGAH_CONSULT_CLIS")
    allowed = CONSULT_CLIS if pin is None else pin.split(",")
    return (["cli:" + n for n in CONSULT_CLIS if n in allowed and which_user(n)]
            + [p for p in PROVIDER_KEYS if have_provider_key(p)])


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
    """True when tezgah's own judgement seam can ask anyone: the session's own
    CLI (`session_cli()`), else - when the `fallback` setting lets a third party
    answer - a chosen Jev carrier's credential (`jev_carriers()`) or the
    OpenRouter chat fallback's own two channels (`OPENROUTER_API_KEY`,
    `~/.config/openrouter/key`), which are the channels `hooks/tezgah_judge.py`'s
    `providers()` picks between. This is what `bin/tezgah-triage`,
    `bin/tezgah-docs` and the skill picker spend.

    Kept next to `have_typesafe_key()` because the two are asked together and a
    report that showed one answer under both questions was wrong in both
    directions - a key file alone serves the seam and not omp. A blank file is
    not a credential here either, so this stays in step with the seam's own
    `strip() or None`."""
    if session_cli():
        return True
    if fallback_policy() == "none":
        return False
    return bool(openrouter_key() or any(s for _, s in jev_carriers()))


def key_from(envs, path):
    """The first non-blank env var of `envs`, else the file at `path` (`~`
    expanded), else None - stripped either way, because a newline inside an
    Authorization header is an injection, not a typo. The file is the channel a
    hook needs: it runs where `~/.zshenv` never exported the variable."""
    for env in envs:
        value = os.environ.get(env, "").strip()
        if value:
            return value
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def omp_login_key(provider):
    """The API key omp's login store holds for `provider` (`omp auth login`),
    stripped, else None: the newest enabled `api_key` row's `data.key`, read
    read-only. Any error - no store, another schema, a locked file - is None."""
    import sqlite3  # deferred: see have_typesafe_key()
    store = os.path.join(os.path.expanduser("~"), ".omp", "agent", "agent.db")
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % store, uri=True)
        try:
            rows = conn.execute(
                "select data from auth_credentials where provider = ? and "
                "disabled_cause is null order by id desc", (provider,)).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None
    for (data,) in rows:
        try:
            value = json.loads(data).get("key")
        except (TypeError, ValueError, AttributeError):
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def typesafe_key():
    """TypeSafe's credential: TYPESAFE_API_KEY, else `~/.config/typesafe/key`,
    else the active omp login (`omp_login_key("typesafe")`), else None."""
    return (key_from(("TYPESAFE_API_KEY",), "~/.config/typesafe/key")
            or omp_login_key("typesafe"))


def openrouter_key():
    """OpenRouter's credential: OPENROUTER_API_KEY, else its key file."""
    return key_from(("OPENROUTER_API_KEY",), "~/.config/openrouter/key")


def cloudflare_account():
    """The Workers AI account id: CLOUDFLARE_ACCOUNT_ID, else its file."""
    return key_from(("CLOUDFLARE_ACCOUNT_ID",), "~/.config/cloudflare/account_id")


def cloudflare_token():
    """The Workers AI token: JEV_CLOUDFLARE_API_TOKEN, else CLOUDFLARE_API_TOKEN,
    else `~/.config/cloudflare/token`."""
    return key_from(("JEV_CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_TOKEN"),
                    "~/.config/cloudflare/token")


# The Jev carrier a user may choose (`jev_choice()`), and the order `auto`
# tries them in: TypeSafe direct, OpenRouter's System One endpoint, Cloudflare
# Workers AI, any System One-compatible URL (JEV_API_BASE_URL + JEV_API_KEY,
# the names the public jev-mcp server reads), then Cloudflare's own System One
# models Clef and Clef-flash on Workers AI (the same Cloudflare credential).
JEV_CHOICES = ("auto", "typesafe", "openrouter", "cloudflare", "compatible",
               "clef", "clef-flash")


def jev_choice():
    """TEZGAH_JEV_PROVIDER, else JEV_PROVIDER (jev-mcp's name), else config.json
    `jev`, else `auto` - lowercased. An unknown value is kept, so it resolves to
    no carrier instead of silently to another one."""
    for env in ("TEZGAH_JEV_PROVIDER", "JEV_PROVIDER"):
        value = os.environ.get(env, "").strip().lower()
        if value:
            return value
    cfg = config()
    value = cfg.get("jev") if isinstance(cfg, dict) else None
    value = value.strip().lower() if isinstance(value, str) else ""
    return value or "auto"


def jev_carriers():
    """[(carrier, secret), ...] the chosen Jev carriers in the order the seam
    asks them. `auto`: every carrier whose credential resolves. A named one: that
    carrier alone, its secret None when it does not resolve - the seam records
    why rather than substituting another carrier."""
    compatible = (os.environ.get("JEV_API_KEY", "").strip() or None
                  if os.environ.get("JEV_API_BASE_URL", "").strip() else None)
    workers_ai = cloudflare_token() if cloudflare_account() else None
    found = [("typesafe", typesafe_key()), ("jev-openrouter", openrouter_key()),
             ("jev-cloudflare", workers_ai), ("jev-compatible", compatible),
             ("clef", workers_ai), ("clef-flash", workers_ai)]
    choice = jev_choice()
    if choice == "auto":
        return [(name, secret) for name, secret in found if secret]
    name = choice if choice in ("typesafe", "clef", "clef-flash") else "jev-" + choice
    return [(name, dict(found).get(name))]


# How far a model call may leave the session's own vendor (config.json
# `fallback`). `vendor`, the default: the session's own model first, and a
# fallback only to the same vendor's model (a subagent chain may reach Opus
# through OpenRouter; the judge has no such route, so it falls back to nobody
# while the session CLI exists, and to a third party only when there is no
# session CLI at all). `any`: a cross-vendor fallback is allowed after the
# session's own model fails. `none`: no provider but the session's, ever.
FALLBACKS = ("vendor", "any", "none")


def fallback_policy():
    """The configured `fallback` value, `vendor` when unset or unknown."""
    cfg = config()
    value = cfg.get("fallback") if isinstance(cfg, dict) else None
    return value if value in FALLBACKS else "vendor"


# The session CLIs the judgement seam can ask, in detection order, each with
# the env vars its host sets in the processes it spawns. omp sets CLAUDECODE
# too, so it comes first. opencode sets OPENCODE=1 in its own process at start
# (`process.env.OPENCODE="1"` in the 1.18.31 binary), so its plugin's children
# and its shell tool inherit it. cursor-agent gives its shell tool CURSOR_AGENT=1
# and its hooks CURSOR_VERSION (`buildHookEnvironment` in the 2026.10.01
# bundle). codex gives its shell tool CODEX_THREAD_ID (codex-rs
# protocol/src/shell_environment.rs `populate_env`); its hooks get only codex's
# own process env (codex-rs hooks/src/registry.rs), so a codex hook names no
# session - `judge_cli` picks it there.
SESSION_CLIS = (("omp", ("OMPCODE",)), ("claude", ("CLAUDECODE",)),
                ("opencode", ("OPENCODE",)), ("cursor", ("CURSOR_AGENT", "CURSOR_VERSION")),
                ("codex", ("CODEX_THREAD_ID",)))


def session_cli():
    """The session CLI the judgement seam asks - `omp`, `claude`, `opencode`,
    `cursor` or `codex` - else None.

    TEZGAH_JUDGE_CLI, else config.json `judge_cli`, picks one by name; `auto`
    (the default, and any other value) reads the host this process runs under:
    the first CLI in SESSION_CLIS whose marker is set. Either way the answer is
    None when that CLI's binary is missing - an omp session is not handed to
    whatever `claude` is logged in as, and a picked CLI has no stand-in."""
    bins = {"omp": omp_bin, "claude": claude_bin, "opencode": opencode_bin,
            "cursor": cursor_bin, "codex": codex_bin}
    cfg = config()
    pick = (os.environ.get("TEZGAH_JUDGE_CLI", "").strip()
            or (cfg.get("judge_cli") if isinstance(cfg, dict) else None))
    if not isinstance(pick, str) or pick not in bins:
        pick = next((name for name, markers in SESSION_CLIS
                     if any(os.environ.get(m) for m in markers)), None)
    return pick if pick and bins[pick]() else None


def orx_bin():
    """The OpenResearch `orx` executable, or None when it is not installed.

    TEZGAH_ORX_BIN points at a specific binary (tests, CI); otherwise the first
    `orx` on PATH wins, then a known per-user bin dir. Mirrors `codegraph_bin()` so a
    missing tool is a clean None, not a failed lookup at call time."""
    return which_user(os.environ.get("TEZGAH_ORX_BIN") or ORX)


def omp_bin():
    """The omp CLI, or None when it is not installed.

    TEZGAH_OMP_BIN points at a specific binary (tests, CI); otherwise the first
    `omp` on PATH wins, then a known per-user bin dir - the lookup `orx_bin()`
    makes. The installer registers its omp extension through `omp config`, so a
    missing CLI has to be a clean None rather than a failed spawn."""
    return which_user(os.environ.get("TEZGAH_OMP_BIN") or "omp")


def claude_bin():
    """The Claude Code CLI, or None when it is not installed.

    TEZGAH_CLAUDE_BIN points at a specific binary (tests, CI); otherwise the
    lookup `omp_bin()` makes. The installer registers tezgah's plugin through
    `claude plugin`, so the suite must be able to keep the real CLI out."""
    return which_user(os.environ.get("TEZGAH_CLAUDE_BIN") or "claude")


def opencode_bin():
    """The opencode CLI (TEZGAH_OPENCODE_BIN, else `opencode`), or None - the
    lookup `omp_bin()` makes."""
    return which_user(os.environ.get("TEZGAH_OPENCODE_BIN") or "opencode")


def cursor_bin():
    """Cursor's agent CLI (TEZGAH_CURSOR_BIN, else `cursor-agent`), or None -
    the lookup `omp_bin()` makes."""
    return which_user(os.environ.get("TEZGAH_CURSOR_BIN") or "cursor-agent")


def codex_bin():
    """The Codex CLI (TEZGAH_CODEX_BIN, else `codex`), or None - the lookup
    `omp_bin()` makes."""
    return which_user(os.environ.get("TEZGAH_CODEX_BIN") or "codex")


# The values `reply_lang` (config.json) takes. The value itself is the switch:
# `tr` (the default, and what an install without the key reads) asks for Turkish
# replies, `en` for English ones, and `any` drops the Stop language check.
REPLY_LANGS = ("tr", "en", "any")


def reply_lang():
    """The configured reply language, `tr` when unset or not one of REPLY_LANGS."""
    cfg = config()
    value = cfg.get("reply_lang") if isinstance(cfg, dict) else None
    return value if value in REPLY_LANGS else "tr"


# Switch latching (plan 051, ADR 018). A hook process that knows its session
# binds the session's ledger here (`tezgah_integrity.bind_session`), and from
# then on `off()` ignores a switch file whose ctime or mtime is newer than the
# ledger's first row: the agent being judged writes files too, and a switch it
# made mid-session would otherwise disarm the rule judging it. ctime is the
# point - `touch -t` backdates mtime, never ctime. Three ways through:
# - the user's own prompt named the switch (an `authorized` row, `note_turn`);
# - the file is `tezgah-setup --uninstall --full`'s stand-down (STAND_DOWN),
#   which writes pretooluse-off mid-session on purpose;
# - the file is within the first row's second: the row's `ts` is whole seconds.
# An unbound process (every CLI, a hook with no session id) answers as before.
# ponytail: the first two are bytes the agent can also write (an
# `authorized` row, the stand-down text) - the control rule refuses the routes
# the gate sees, and an interpreter writing them is SECURITY.md's residual.
STAND_DOWN = "tezgah-setup --uninstall --full\n"
_LATCH = {"ledger": None, "since": None}


def latch(ledger):
    """Bind this process's `off()` to one session's ledger path (None unbinds)."""
    _LATCH.update(ledger=ledger, since=None)


def _first_ts(ledger):
    import tezgah_store  # deferred: an unbound process never opens the ledger
    try:
        ts = json.loads(tezgah_store.evidence_first(ledger) or "null").get("ts")
    except (*tezgah_store.ERRORS, ValueError, AttributeError):
        return None
    return ts if isinstance(ts, (int, float)) else None


def _authorized(ledger):
    """The switch names this session's `authorized` rows carry: read only when
    a switch is newer than the first row."""
    import tezgah_store
    names = set()
    try:
        found = tezgah_store.evidence_rows(ledger, kind="authorized")
    except tezgah_store.ERRORS:
        return frozenset()
    for text in found:
        try:
            row = json.loads(text)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("authorized"), list):
            names.update(n for n in row["authorized"] if isinstance(n, str))
    return frozenset(names)


def _honored(path, name):
    try:
        # the link's own times too: `stat` follows a link, and a link made now
        # to an old file would read as old
        stats = (os.stat(path), os.lstat(path))
    except OSError:
        return False
    ledger = _LATCH["ledger"]
    if not ledger:
        return True
    if _LATCH["since"] is None:
        _LATCH["since"] = _first_ts(ledger)
    since = _LATCH["since"]
    if since is None or max(t for st in stats for t in (st.st_mtime, st.st_ctime)) \
            < since + 1:
        return True
    if name == "pretooluse-off":
        try:
            with open(path, encoding="utf-8") as fh:
                if fh.read(len(STAND_DOWN) + 1) == STAND_DOWN:
                    return True
        except (OSError, UnicodeDecodeError):
            pass
    return name in _authorized(ledger)


def off(name):
    """A kill switch, canonical (~/.config/tezgah) or legacy (~/.claude),
    latched to the bound session (see `latch`)."""
    return any(_honored(os.path.join(d, name), name) for d in OFF_DIRS)


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


# --- the per-project workspace: <repo>/.tezgah, the only place tezgah writes
# project state. It is ignored by the project's own git and carries a private
# git repository of its own, so the evidence that needs history (a research
# protocol committed before its results, a plan moved to done/) has one without
# ever entering the project's history.
WORKSPACE = ".tezgah"
# git's own XDG config directory: `~/.config/git/config`, read as one of the
# identity channels by `seed_identity`.
CONFIG_DIR_GIT = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
WORKSPACE_IGNORES = ("/.tezgah/", "/.codegraph/")
# The private repository commits as the identity it is configured with - the one
# `ensure_workspace` copies from the project that owns it - and never as a name
# tezgah invented: an author is a claim about who wrote the work, and a log that
# keeps a fabricated one keeps a lie. The signing agent is the only thing
# overridden here, because a workspace commit must not wait on one.
WS_IDENTITY = ("-c", "commit.gpgsign=false",)
# What `ensure_workspace` copies from the project into the workspace. Reading
# `git config --get` in the project already falls back to the global value, so a
# machine that sets either one gets the same identity in both repositories.
IDENTITY_KEYS = ("user.name", "user.email")


def workspace(repo):
    """`<repo>/.tezgah`: every per-project file tezgah keeps lives under it."""
    return os.path.join(repo, WORKSPACE)


# The workspace paths whose text is injected as a standing constraint: each is
# checked for a symlink, because a clone can carry one pointing into its own tree.
WORKSPACE_INJECTED = (".tezgah", os.path.join(".tezgah", "lessons.md"),
                      os.path.join(".tezgah", "plans"),
                      os.path.join(".tezgah", "plans", "open"))


def _git_dirs(gitdir):
    """The checkout's gitdir and, for a linked worktree, the common dir."""
    dirs = [gitdir]
    try:
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as fh:
            dirs.append(os.path.join(gitdir, fh.readline().strip()))
    except OSError:
        pass
    return dirs


def _index_files(gitdir):
    """The index plus every `sharedindex.*` (a split index, `core.splitIndex`,
    keeps most entries there) in the checkout's gitdir and the common dir."""
    import glob  # deferred: the gate imports this module per call
    return [os.path.join(gitdir, "index")] + sorted(
        p for d in _git_dirs(gitdir)
        for p in glob.glob(os.path.join(d, "sharedindex.*")))


def _object_width(gitdir):
    """The object id width the repository's config names: 32 under
    `extensions.objectFormat = sha256`, 20 when a config was read without it,
    None when no config could be read. The index header does not carry it, and
    a guessed width can be satisfied by ground object ids (review U1)."""
    read = False
    for d in _git_dirs(gitdir):
        try:
            with open(os.path.join(d, "config"), encoding="utf-8",
                      errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        read = True
        import re  # deferred: the gate imports this module per call
        if re.search(r"(?im)^\s*objectformat\s*=\s*sha256\s*$", text):
            return 32
    return 20 if read else None


def _index_paths(data, width=None):
    """The entry paths of a v2/v3 index, or None when they cannot be told.

    Only the entries are read: the extensions after them carry other names, and
    the untracked cache (UNTR, `core.untrackedCache`) records an untracked
    `.tezgah` there - a whole-file byte search read the user's own workspace as
    tracked. Each entry is 40 bytes of stat fields, the object id (`width`: 20
    for SHA-1, 32 for SHA-256, from the config), 2 bytes of flags, 2 more when
    v3 sets the extended bit, then the path, NUL-padded to a multiple of 8. A
    parse is accepted only when every entry's name length in its flags (below
    0xFFF) matches the path read. With no width known both are tried, and an
    index both accept is as unreadable as one neither does."""
    version = int.from_bytes(data[4:8], "big")
    count = int.from_bytes(data[8:12], "big")
    accepted = []
    for size in ((width,) if width else (20, 32)):
        paths, off = [], 12
        try:
            for _ in range(count):
                flags = int.from_bytes(data[off + 40 + size:off + 42 + size], "big")
                start = off + 42 + size + (2 if version >= 3 and flags & 0x4000 else 0)
                end = data.index(b"\0", start)
                if (flags & 0xFFF) < 0xFFF and flags & 0xFFF != end - start:
                    raise ValueError
                paths.append(data[start:end])
                off += (end - off + 8) & ~7
            if off > len(data):
                raise ValueError
        except ValueError:
            continue
        accepted.append(paths)
    return accepted[0] if len(accepted) == 1 else None


def workspace_from_repo(root):
    """True when `<root>/.tezgah` came with the repository rather than from
    tezgah, or that cannot be ruled out: its lessons and plans are then data,
    never standing constraints, and no private workspace is initialised in it.

    `.tezgah/` is the user's private workspace: ignored by the project and kept
    in its own repository (`ensure_workspace`). A cloned hostile repository must
    not be able to place rule text into the hook channel framed as a standing
    constraint (audit L-16, SEC-11). It came with the clone when the project's
    own index holds `.tezgah` itself (a symlink or a submodule) or any path under
    it (`_index_tracks_workspace`), or when `.tezgah`, `lessons.md`, `plans` or
    `plans/open` is a symlink - a tracked `.tezgah -> notes` holds no `.tezgah/`
    path at all (review F3). An index that cannot be told is True here, the side
    of a notice (review F9). ponytail: a tree with no `.git` (an unpacked
    tarball) carries no record of where `.tezgah` came from, so it answers False
    and is injected - the ceiling of a provenance check that reads git."""
    if any(os.path.islink(os.path.join(root, rel)) for rel in WORKSPACE_INJECTED):
        return True
    return _index_tracks_workspace(root) is not False


def workspace_tracked(root):
    """True only on positive evidence that the project's own index tracks
    `.tezgah` or a path under it - the reading enforcement needs.

    The injection side reads every can't-tell as "repository-provided"; the task
    rule must not, because a None there switches the user's own plan guard off
    in silence for a symlinked workspace of their own, an unreadable index or a
    v4 query that timed out (review R2). The gate resolves the task on every
    gated call, so the answer is kept in the cache keyed on the index files'
    mtime and size: an unchanged index costs one stat per file and one small
    read, never a re-parse or a `git ls-files` fork."""
    gitdir = _gitdir_of(root)
    if not gitdir:
        return False
    files = [p for p in _index_files(gitdir) if os.path.exists(p)]
    if not files:
        return False
    try:
        key = [[p, os.stat(p).st_mtime_ns, os.stat(p).st_size] for p in files]
    except OSError:
        return False
    store = os.path.join(cache_dir(), "workspace-index.json")
    try:
        with open(store, encoding="utf-8") as fh:
            known = json.load(fh)
    except (OSError, ValueError):
        known = {}
    hit = known.get(root) if isinstance(known, dict) else None
    if isinstance(hit, list) and len(hit) == 2 and hit[0] == key:
        return hit[1] is True
    answer = _index_tracks_workspace(root) is True
    known = known if isinstance(known, dict) else {}
    known[root] = [key, answer]
    try:
        tmp = "%s.%d.tmp" % (store, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(known, fh)
        os.replace(tmp, store)
    except OSError:
        pass
    return answer


def _gitdir_of(root):
    """The gitdir `<root>/.git` names: the directory itself, a worktree's
    `gitdir:` target, "" for no `.git`, None for a `.git` that cannot be read."""
    dot = os.path.join(root, ".git")
    if not os.path.lexists(dot):
        return ""
    if os.path.isdir(dot):
        return dot
    try:
        with open(dot, encoding="utf-8", errors="replace") as fh:
            line = fh.readline().strip()
    except OSError:
        return None
    if not line.startswith("gitdir:"):
        return None
    return os.path.join(root, line[len("gitdir:"):].strip())


def _index_tracks_workspace(root):
    """True when the project's index holds `.tezgah` or a `.tezgah/` path, False
    when it was read and holds neither (or there is no `.git` or no index),
    None when it cannot be told.

    Read from the index files, not from `git ls-files`, because the session-start
    git forks are pinned (GitSpawnBudget): v2/v3 store every path whole, so the
    entries are parsed (`_index_paths`); v4 prefix-compresses paths, so only
    there one `git ls-files` runs. Can't-tell is an unreadable `.git` pointer or
    index, a foreign header, entries no known width parses, and a v4 query that
    fails or times out. Entry paths are compared case-insensitively on every
    platform: on APFS and NTFS defaults a tracked `.TEZGAH/lessons.md` is the
    file `open` reads as `.tezgah/lessons.md` (review N2); a repository that
    really tracks a `.TEZGAH` of its own reads as tracked, the safe side."""
    gitdir = _gitdir_of(root)
    if gitdir is None:
        return None
    if not gitdir:
        return False
    files = _index_files(gitdir)
    if not os.path.exists(files[0]):
        return False
    width = _object_width(gitdir)
    for path in files:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            return None
        if data[:4] != b"DIRC":
            return None
        if int.from_bytes(data[4:8], "big") >= 4:
            import subprocess  # deferred: the gate imports this module per call
            try:
                out = subprocess.run(
                    ("git", "-C", root, "ls-files", "-z", "--", ":(icase).tezgah"),
                    capture_output=True, timeout=5)
            except Exception:
                return None
            return None if out.returncode else bool(out.stdout)
        paths = _index_paths(data, width)
        if paths is None:
            return None
        if any(p.lower() == b".tezgah" or p.lower().startswith(b".tezgah/")
               for p in paths):
            return True
    return False


def ensure_workspace(repo):
    """`<repo>/.tezgah`, created, ignored by the project and holding its own git
    repository; None when `repo` is not a git work tree or a step failed.

    The ignore lines are appended to the project's `.gitignore` only when
    missing, after every line the user wrote, and nothing is staged. A second
    call costs three stats and one file read: the subprocess runs only when
    `.tezgah/.git` does not exist yet. Fail-open: a read-only tree returns None
    and the session goes on."""
    if not os.path.exists(os.path.join(repo, ".git")):
        return None
    ws = workspace(repo)
    # A `.tezgah` that is a symlink (or anything but a directory) came with the
    # repository: following it would `git init` inside the target the clone
    # chose and write the private workspace there (review F3, audit L-16).
    if os.path.islink(ws) or (os.path.lexists(ws) and not os.path.isdir(ws)):
        return None
    # The same for a `.tezgah` the project tracks (any case: `.TEZGAH` is this
    # directory on APFS/NTFS, review N2). Asked only before the first `git
    # init`; once tezgah's own repository is there, the question was answered.
    if (not os.path.exists(os.path.join(ws, ".git"))
            and workspace_from_repo(repo)):
        return None
    try:
        os.makedirs(ws, exist_ok=True)
        path = os.path.join(repo, ".gitignore")
        try:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
        except FileNotFoundError:
            body = ""
        have = {line.strip().strip("/") for line in body.splitlines()}
        missing = [line for line in WORKSPACE_IGNORES if line.strip("/") not in have]
        if missing:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(("\n" if body and not body.endswith("\n") else "")
                         + "".join(line + "\n" for line in missing))
        if not os.path.exists(os.path.join(ws, ".git")):
            import subprocess  # deferred: the gate imports this module per call
            if subprocess.run(["git", "init", "-q", ws],
                              capture_output=True).returncode:
                return None
            seed_identity(repo, ws)
    except (OSError, ValueError):
        return None
    return ws


def _git_config_paths(repo):
    """The config files that could hold this project's identity, most local first.

    `git config` would answer this in one fork, and a session start forks git for
    its own questions - the budget test counts them per question - so the two
    files are read here instead: the repository's own config (following a
    worktree's `gitdir:` pointer, and its common config), then the user's."""
    out = []
    dot = os.path.join(repo, ".git")
    if os.path.isfile(dot):
        try:
            with open(dot, encoding="utf-8", errors="replace") as fh:
                line = fh.readline().strip()
        except OSError:
            line = ""
        if line.startswith("gitdir:"):
            gitdir = line[len("gitdir:"):].strip()
            gitdir = gitdir if os.path.isabs(gitdir) else os.path.join(repo, gitdir)
            out += [os.path.join(gitdir, "config"),
                    os.path.join(gitdir, "..", "..", "config")]
    elif os.path.isdir(dot):
        out.append(os.path.join(dot, "config"))
    out.append(os.path.join(HOME, ".gitconfig"))
    out.append(os.path.join(CONFIG_DIR_GIT, "git", "config"))
    return out


def _identity_in(path):
    """`(name, email)` from one git config file. No `include` is followed and no
    value is expanded: the plain `[user]` lines are what a project sets."""
    name = email = None
    section = ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line[0] in "#;":
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].split('"')[0].strip().lower()
                    continue
                if section != "user" or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip().lower()
                value = value.strip().strip('"')
                if key == "name" and name is None:
                    name = value
                elif key == "email" and email is None:
                    email = value
    except OSError:
        return None, None
    return name, email


def seed_identity(repo, ws=None):
    """Copy the project's git identity into the workspace, at creation.

    The workspace is tezgah's own repository, so its commits have to carry the
    person who owns the code: without this, a machine whose global identity is
    unset refuses the commit, and the earlier answer - forcing a name in our own
    argv - wrote a repository's history under a committer nobody holds. Read from
    the config files rather than through `git config`, so a session start forks no
    extra git (see `_git_config_paths`). Fail-open: no identity anywhere leaves git
    to say so, which is its own honest error."""
    ws = ws or workspace(repo)
    found = {}
    for path in _git_config_paths(repo):
        name, email = _identity_in(path)
        if name and "user.name" not in found:
            found["user.name"] = name
        if email and "user.email" not in found:
            found["user.email"] = email
        if len(found) == len(IDENTITY_KEYS):
            break
    if not found:
        return
    path = os.path.join(ws, ".git", "config")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError:
        return
    if "[user]" in body:
        return
    # inside the `[user]` section the key loses its prefix: `name`, not `user.name`
    block = "".join("\t%s = %s\n" % (key.split(".")[-1], found[key])
                    for key in IDENTITY_KEYS if key in found)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("[user]\n" + block)
    except OSError:
        pass


def ws_git(repo, *args, **kw):
    """`git -C <repo>/.tezgah <args>` with tezgah's commit identity, as a
    CompletedProcess (text, captured unless `kw` says otherwise). Raises OSError
    when git is not installed, like subprocess.run."""
    import subprocess  # deferred: see ensure_workspace
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(["git", "-C", workspace(repo)] + list(WS_IDENTITY)
                          + list(args), **kw)


def guarded_opener(drop_auth=False):
    """An urllib opener whose redirects never carry the bearer off its origin.

    urllib copies the Authorization header onto a redirected request, so a
    301/302 from a repointable endpoint would hand the key to whatever host the
    answer named - or, on a same-host https->http hop, send it in clear. A hop
    that changes the scheme or the host is refused (it surfaces as an
    HTTPError), or, with `drop_auth`, followed without the header so the far end
    answers 401 and the caller reports a key failure; a same-origin redirect is
    followed as urllib would. One copy for the judge seam and codegen (refuse)
    and consult (drop). The import is deferred: see the fallback_cache() note."""
    import urllib.parse
    import urllib.request

    class Guard(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            old, new_url = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
            cross = (new_url.scheme.lower(), new_url.netloc) != (old.scheme.lower(), old.netloc)
            if cross and not drop_auth:
                return None
            new = super().redirect_request(req, fp, code, msg, headers, newurl)
            if new is not None and cross:
                new.remove_header("Authorization")
            return new

    return urllib.request.build_opener(Guard)


def plain_http(url):
    """True for an `http://` endpoint off this machine: the bearer and the body
    would cross the network in clear. Loopback stays allowed - the tests and a
    local gateway point the endpoint overrides at `http://127.0.0.1`."""
    import ipaddress
    import urllib.parse
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() != "http":
        return False
    host = parts.hostname or ""
    if host == "localhost":
        return False
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        return True
