#!/usr/bin/env python3
"""Is a newer tezgah release out, and the one command that takes it.

Two halves. The notice: `notice_segments()` reads a small cache file and, when it
names a release newer than this install, returns one status-line segment
(`↑X.Y.Z`) drawn beside the logo. A redraw never touches the network: when the
cache is older than CHECK_EVERY it stamps the cache and starts this file as a
detached `check` process, which asks the releases endpoint and writes the
answer for the next redraw. The update: `update()` moves the install to the
newest release through the channel it was installed with - a release prefix
(packaging/upgrade.sh, through bin/tezgah-setup's own `upgrade`), Homebrew, npm
or a git checkout - and re-arms the hosts from the new tree.

Never raising on the notice path: the status line runs it on every redraw, on
every host, and a raise there would cost the session its line. Stdlib only.
"""
import json
import os
import re
import subprocess
import sys
import time

import tezgah_paths as tp

REPO = os.environ.get("TEZGAH_REPO") or "r1z4x/tezgah"
CHECK_EVERY = 24 * 3600
TIMEOUT = 5
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
ARROW = "\u2191"  # ↑: East Asian width Ambiguous, one cell, never an emoji


def cache_path():
    return os.path.join(tp.cache_dir(), "update.json")


def endpoint():
    """Where the newest release is read, repointed by TEZGAH_UPDATE_URL (tests).

    The github.com page and not the REST API: the API allows 60 unauthenticated
    calls an hour per address, which a machine running `gh` or curl against it
    exhausts, while the page answers a HEAD with a redirect whose Location ends
    in the tag (`.../releases/tag/v0.1.1`)."""
    return (os.environ.get("TEZGAH_UPDATE_URL")
            or "https://github.com/%s/releases/latest" % REPO)


TAG_IN_URL = re.compile(r"/releases/tag/(v?\d+\.\d+\.\d+)$")


def tag_from(location, body=b""):
    """The release tag a releases answer names: the redirect's tail, else a
    JSON body's `tag_name` (the API's shape, and what a test fixture serves)."""
    hit = TAG_IN_URL.search(str(location or "").rstrip("/"))
    if hit:
        return hit.group(1)
    try:
        return json.loads(body or b"{}").get("tag_name")
    except (ValueError, AttributeError):
        return None


def parse(value):
    """`X.Y.Z` (an optional leading `v`) as a tuple of ints, or None."""
    hit = SEMVER.match(str(value or "").strip())
    return tuple(int(part) for part in hit.groups()) if hit else None


def disabled():
    """The user's switch (`update-check-off`) or the test seam
    (TEZGAH_UPDATE_CHECK=0): no notice is read and no check is started."""
    return os.environ.get("TEZGAH_UPDATE_CHECK") == "0" or tp.off("update-check-off")


def read_cache():
    try:
        with open(cache_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_cache(data):
    """Write the cache whole, owner-only, through a rename, so a redraw reading it
    mid-write sees the old answer or the new one and never half of either."""
    path = cache_path()
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


# Every 0.x ever published, retired by 1.0.0: npm served 0.17.0 through 0.32.0
# before the 2026-10-04 re-root, then 0.1.1, 0.1.2 and 0.33.0, and none of them
# stays on npm (`npm view @r1z4x/tezgah versions`). 1.0.0 is the first line
# every 0.x install must move to; an install inside the range compares as older
# than every public release, whatever its number says.
# ponytail: a version inside the range is taken as retired, so an install that
# carries this constant is never offered a release inside it. Installs in the
# field keep the range they shipped with (0.1.x and 0.33.0 retired 0.2.0-0.32.0),
# which is why the public line starts at 1.0.0 (pinned in
# tests/test_update.py::Reset).
RETIRED = ((0, 1, 0), (0, 33, 0))


def retired(version):
    """True when `version` is on the retired 0.x line."""
    got = parse(version)
    return bool(got) and RETIRED[0] <= got <= RETIRED[1]


def newer(current, data=None):
    """The cached latest release when it is newer than `current`, else None. A
    public release is newer than any retired version, and a retired latest is
    never offered."""
    data = read_cache() if data is None else data
    latest, mine = parse(data.get("latest")), parse(current)
    if not latest or not mine or retired(data.get("latest")):
        return None
    if latest > mine or retired(current):
        return "%d.%d.%d" % latest
    return None


def due(data, now=None):
    """True when the cache is missing or older than CHECK_EVERY."""
    checked = data.get("checked")
    now = time.time() if now is None else now
    return not isinstance(checked, (int, float)) or now - checked >= CHECK_EVERY


def start_check(data):
    """Stamp the cache, then start one detached `check`.

    The stamp is written first, keeping the latest it already knew, so the
    redraws that follow within the day read a fresh cache and start nothing -
    one process per day however often the line is drawn. An offline check then
    leaves the stamp and the old answer, and the next day asks again."""
    if not write_cache({"checked": int(time.time()), "latest": data.get("latest")}):
        return False
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:  # pragma: no cover - Windows: no console, outlives its parent
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "check"],
                         **kwargs)
        return True
    except OSError:
        return False


def notice_segments(current):
    """[] or the one segment that says a newer release is out.

    Drawn in the version's own group, so it sits beside the logo on every
    surface: the colored line and render_tiers (omp) join a group with a space,
    and a host that builds its line from `--json` reads the same group."""
    try:
        if disabled() or not current:
            return []
        data = read_cache()
        if due(data):
            start_check(data)
        latest = newer(current, data)
        if not latest:
            return []
        # a retired install's ↑ points at a lower number, so it says why
        return [{"key": "update", "state": "ready", "glyph": "",
                 "text": ARROW + latest + (" (line reset)" if retired(current) else ""),
                 "version": latest, "group": -1}]
    except Exception:
        return []


def check():
    """Ask where the newest release is, once, and write what it said: 0 either
    way, because a failed check is the next day's to retry, not an error."""
    import urllib.error
    import urllib.request

    class _Stay(urllib.request.HTTPRedirectHandler):
        """Hand the redirect back instead of following it: its Location is the
        answer, and the page behind it is a large HTML document."""
        def redirect_request(self, *args, **kwargs):
            return None

    request = urllib.request.Request(endpoint(), method="HEAD",
                                     headers={"User-Agent": "tezgah"})
    try:
        with urllib.request.build_opener(_Stay).open(request, timeout=TIMEOUT) as response:
            tag = tag_from(response.geturl(), response.read(65536))
    except urllib.error.HTTPError as exc:
        tag = tag_from(exc.headers.get("Location")) if 300 <= exc.code < 400 else None
    except Exception:
        return 0
    if parse(tag):
        write_cache({"checked": int(time.time()),
                     "latest": "%d.%d.%d" % parse(tag)})
    return 0


# --- `tezgah update`: one command, the channel the install came through -------
# The channel is read off the tree that is running, the one piece of evidence
# that cannot be stale about how it was installed: a release prefix is
# bin/tezgah-setup's `running_prefix()` (passed in), a Homebrew keg lives under
# `.../Cellar/tezgah/<version>/libexec`, an npm package under a `node_modules`
# directory, and a checkout carries `.git`.
def channel(here, prefix=""):
    real = os.path.realpath(here)
    parts = real.split(os.sep)
    if prefix:
        return "prefix"
    if "Cellar" in parts and parts[parts.index("Cellar") + 1:][:1] == ["tezgah"]:
        return "brew"
    if "node_modules" in parts:
        return "npm"
    if os.path.exists(os.path.join(real, ".git")):
        return "git"
    return ""


def fetch_command(kind, here):
    """The argv that moves the tree to the newest release, per channel."""
    owner = REPO.split("/")[0]
    return {"brew": ["brew", "upgrade", "%s/tezgah/tezgah" % owner],
            "npm": ["npm", "install", "-g", "@%s/tezgah@latest" % owner],
            "git": ["git", "-C", here, "pull", "--ff-only"]}.get(kind)


def npm_global_root(npm, run):
    """`npm root -g`, or "" when npm cannot answer. The tree `npm install -g`
    replaces lives there, which need not be the tree that is running (npx, a
    project-local install, another prefix or node version on PATH)."""
    try:
        out = run([npm, "root", "-g"], capture_output=True, text=True)
    except OSError:
        return ""
    return out.stdout.strip() if out.returncode == 0 and out.stdout else ""


def launcher(kind, here, npm_root=""):
    """The installer of the tree the fetch leaves behind. Homebrew installs a
    new keg beside the old one, so its stable `opt/tezgah` link is followed;
    npm updates the package under its global root; git replaces the tree in
    place."""
    if kind == "brew":
        real = os.path.realpath(here)
        brew_root = real[:real.index(os.sep + "Cellar" + os.sep)]
        return os.path.join(brew_root, "opt", "tezgah", "libexec", "bin",
                            "tezgah-setup")
    if kind == "npm" and npm_root:
        return os.path.join(npm_root, "@" + REPO.split("/")[0], "tezgah", "bin",
                            "tezgah-setup")
    return os.path.join(here, "bin", "tezgah-setup")


def rearm_command(setup, cfg):
    """`--install --no-deps` from the new tree with the hosts and roots the
    install recorded, so an update does not re-ask the install questions."""
    argv = [sys.executable, setup, "--install", "--no-deps"]
    if cfg.get("hosts"):
        argv += ["--hosts", ",".join(cfg["hosts"])]
    if cfg.get("roots"):
        argv += ["--roots", os.pathsep.join(cfg["roots"])]
    return argv


def installed_entries(hosts):
    """{host: {entry: text}} - the tezgah-owned hook entries on disk now, read
    before the fetch moves the tree (`hooks/tezgah_attest.py::registration`)."""
    import tezgah_attest
    return {h: tezgah_attest.registration(h)[0] or {} for h in hosts}


# An absolute path up to a tree's `hosts/` or `hooks/` dir: the tree root, which
# names the release (`.../Cellar/tezgah/<version>/libexec`, `<prefix>/<version>`)
# and so differs between two releases whose hook entries are the same.
TREE_ROOT = re.compile(r"/[^\s\"'`]*?(?=/(?:hosts|hooks)/)")

# What answering no leaves, per channel: the fetch has run, only the hook
# registration waits. Printed with the refusal, so the user knows what is live.
NOT_REARMED = {
    "git": "the checkout is pulled; the hooks already run its new code from "
           "the same path, and only the entries above stay as they were",
    "npm": "the global package is replaced in place; the hooks already run its "
           "new code, and only the entries above stay as they were",
    "brew": "the new keg sits beside the old one; hooks wired to the old keg's "
            "path keep running the old code until you re-arm (a `brew cleanup` "
            "that removes the old keg leaves them pointing at nothing)",
    "prefix": "`current` points at the new tree; hooks wired through it run the "
              "new code, and only the entries above stay as they were",
}


def _same_tree(text):
    return TREE_ROOT.sub("<tree>", text or "")


def hook_change(old, new):
    """The lines that name each hook entry re-arming adds, removes or changes,
    per host, with a unified diff of a changed entry; [] when nothing moves.
    The tree root is compared as `<tree>`: every release lives at its own path,
    and a path that moved with the release is not a hook change."""
    import difflib
    lines = []
    for host in sorted(set(old) | set(new)):
        before = {k: _same_tree(v) for k, v in (old.get(host) or {}).items()}
        after = {k: _same_tree(v) for k, v in (new.get(host) or {}).items()}
        for name in sorted(set(before) | set(after)):
            if before.get(name) == after.get(name):
                continue
            verb = ("adds" if name not in before else "removes" if name not in after
                    else "changes")
            lines.append("  %s: re-arming %s the %s entry" % (host, verb, name))
            if verb == "changes":
                lines += ["    " + ln.rstrip("\n") for ln in difflib.unified_diff(
                    before[name].splitlines(), after[name].splitlines(),
                    "installed", "new release", lineterm="", n=1)]
    return lines


def confirm_rearm(old, setup, run=subprocess.run, tty=None, ask=input):
    """Print what re-arming from `setup` changes in the hook entries and say
    whether to go on (decision 12): the change is printed on every update; a
    yes is waited for only when stdin is a terminal and something changes, so a
    piped or scheduled update keeps working unattended. A tree that cannot list
    its entries (a release older than `--hook-entries`) is re-armed as before,
    and the line says the change was not shown."""
    try:
        proc = run([sys.executable, setup, "--hook-entries"],
                   capture_output=True, text=True)
        new = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, ValueError, TypeError, AttributeError):
        new = None
    if not isinstance(new, dict):
        print("  hook entries: the new tree cannot list them, so the change is "
              "not shown")
        return True
    lines = hook_change(old, {h: new.get(h) or {} for h in old})
    print("  hook entries: %s" % ("re-arming changes these:" if lines
                                  else "unchanged"))
    for line in lines:
        print(line)
    if not lines or not (sys.stdin.isatty() if tty is None else tty):
        return True
    try:
        return ask("  re-arm with these hook entries? [y/N] ").strip().lower() \
            in ("y", "yes")
    except EOFError:
        return False


def update(here, prefix, upgrade, dry_run=False, run=subprocess.run, which=None,
           tty=None, ask=input):
    """Move this install to the newest release and re-arm it; the exit code.

    `upgrade` is bin/tezgah-setup's own release-prefix path (fetch, verify,
    flip `current`, re-arm), so that channel keeps the one implementation it
    already has. Every other channel prints its two commands before running
    them, and `dry_run` stops after the printing. The channel's tool is
    resolved through PATH first (`shutil.which` honours PATHEXT, so Windows'
    `npm.cmd` is found), so a missing one is a message and not a traceback.
    Between the two, the change in tezgah's hook entries is printed and, on a
    terminal, confirmed (`confirm_rearm`)."""
    import shutil
    which = which or shutil.which
    kind = channel(here, prefix)
    if kind == "prefix":
        return upgrade("", dry_run)
    fetch = fetch_command(kind, here)
    if not fetch:
        print("tezgah update: cannot tell how %s was installed (not a release "
              "prefix, a Homebrew keg, an npm package or a git checkout)" % here)
        return 1
    tool = which(fetch[0])
    if not tool:
        print("tezgah update: `%s` is not on PATH, so this %s install cannot "
              "update itself" % (fetch[0], kind))
        return 127
    fetch = [tool] + fetch[1:]
    npm_root = npm_global_root(tool, run) if kind == "npm" else ""
    cfg = tp.config()
    rearm = rearm_command(launcher(kind, here, npm_root), cfg)
    print("update (%s): %s" % (kind, " ".join(fetch)))
    if npm_root and not (os.path.realpath(here) + os.sep).startswith(
            os.path.realpath(npm_root) + os.sep):
        print("  note: this tree is not under `npm root -g` (%s); the global "
              "install there is what moves and what is re-armed" % npm_root)
    print("  re-arm: %s" % " ".join(rearm))
    if dry_run:
        print("  --dry-run: nothing fetched, nothing re-armed")
        return 0
    old = installed_entries(cfg.get("hosts") or [])
    for step, argv in (("fetch", fetch), ("re-arm", rearm)):
        if step == "re-arm" and not confirm_rearm(old, rearm[1], run, tty, ask):
            print("tezgah update: fetched, not re-armed: %s. Re-arm later with `%s`"
                  % (NOT_REARMED[kind], " ".join(rearm)))
            return 1
        try:
            code = run(argv).returncode
        except OSError as exc:
            print("tezgah update: %s `%s` could not start (%s)"
                  % (step, " ".join(argv), exc))
            return 127
        if code != 0:
            print("tezgah update: %s `%s` exited %d%s"
                  % (step, " ".join(argv), code,
                     "; tezgah was not re-armed" if step == "fetch" else ""))
            return code
        if step == "fetch":
            print()
    return 0


if __name__ == "__main__":
    sys.exit(check() if sys.argv[1:] == ["check"] else 2)
