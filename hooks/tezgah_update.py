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


def newer(current, data=None):
    """The cached latest release when it is newer than `current`, else None."""
    data = read_cache() if data is None else data
    latest, mine = parse(data.get("latest")), parse(current)
    if latest and mine and latest > mine:
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
        return [{"key": "update", "state": "ready", "glyph": "",
                 "text": ARROW + latest, "version": latest, "group": -1}]
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


def launcher(kind, here):
    """The installer of the tree the fetch leaves behind. Homebrew installs a
    new keg beside the old one, so its stable `opt/tezgah` link is followed;
    npm and git replace the tree in place."""
    if kind == "brew":
        real = os.path.realpath(here)
        brew_root = real[:real.index(os.sep + "Cellar" + os.sep)]
        return os.path.join(brew_root, "opt", "tezgah", "libexec", "bin",
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


def update(here, prefix, upgrade, dry_run=False, run=subprocess.run):
    """Move this install to the newest release and re-arm it; the exit code.

    `upgrade` is bin/tezgah-setup's own release-prefix path (fetch, verify,
    flip `current`, re-arm), so that channel keeps the one implementation it
    already has. Every other channel prints its two commands before running
    them, and `dry_run` stops after the printing."""
    kind = channel(here, prefix)
    if kind == "prefix":
        return upgrade("", dry_run)
    fetch = fetch_command(kind, here)
    if not fetch:
        print("tezgah update: cannot tell how %s was installed (not a release "
              "prefix, a Homebrew keg, an npm package or a git checkout)" % here)
        return 1
    rearm = rearm_command(launcher(kind, here), tp.config())
    print("update (%s): %s" % (kind, " ".join(fetch)))
    print("  re-arm: %s" % " ".join(rearm))
    if dry_run:
        print("  --dry-run: nothing fetched, nothing re-armed")
        return 0
    code = run(fetch).returncode
    if code != 0:
        print("tezgah update: `%s` exited %d; tezgah was not re-armed"
              % (" ".join(fetch), code))
        return code
    print()
    return run(rearm).returncode


if __name__ == "__main__":
    sys.exit(check() if sys.argv[1:] == ["check"] else 2)
