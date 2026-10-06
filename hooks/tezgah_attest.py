#!/usr/bin/env python3
"""Runtime attestation: are tezgah's own hook entries armed and unchanged?

`tezgah-setup --report` reads what an install WROTE, and `--report --live` proves
the hooks EXECUTE, but both run only when someone asks. This is the per-session
half: every host's session start compares the hook entries tezgah owns with what
the install recorded, writes one `attest` row, and keeps a drift mark the status
line and the Stop rule's claim row read.

One store, not two: the install record is the per-artifact sha file the contract
artifacts already use (`contract.sha256`, `bin/tezgah-setup::record_contract`),
one line per entry under a `hook:<host>:<entry>` key. An entry is one hook event's
tezgah-owned groups (Claude, dsh, Codex, Cursor - so a removed PreToolUse is named
while PostToolUse stays), opencode's plugin links, and nothing for omp: its bridge
is compared to a fresh render, the way `rules_current` compares a rules file. The
code an entry runs is hashed only on a packaged install (a tree with no `.git`):
a checkout install points into a tree its owner edits on purpose. A hook file
any user can write (0666) is drift too; group write is left alone, because a
umask of 002 (user-private groups) gives every file that.

Drift is evidence, never integrity: the same uid that could edit a hook can edit
the record. It is never a Stop block, and its text never tells the model what to
run - the user reads it and decides.
"""
import hashlib
import json
import os

import tezgah_paths as tp

ROOT = tp.PLUGIN_ROOT
CONTRACT_SHA = os.path.join(tp.CONFIG_DIR, "contract.sha256")
KEY = "hook:%s:%s"
# The scripts a host's registration runs, relative to the tree: one file each,
# so a session start never hashes the plugin tree (about 710 files).
CLAUDE_SCRIPTS = tuple(os.path.join("hooks", n) for n in (
    "projects-auto-init.py", "projects-pretooluse.py", "projects-posttooluse.py",
    "projects-stop.py"))
CODE_TARGETS = {
    "claude": CLAUDE_SCRIPTS, "dsh": CLAUDE_SCRIPTS,
    "codex": (os.path.join("hosts", "codex", "hook.py"),),
    "cursor": (os.path.join("hosts", "cursor", "hook.py"),),
    "opencode": (os.path.join("hosts", "opencode", "plugins", "tezgah.js"),),
    "omp": (os.path.join("hosts", "omp", "hook.py"),),
}
OPENCODE_DIRS = ("plugins", "plugin")
OMP_BRIDGE = os.path.join(tp.HOST_DIRS["omp"], "agent", "hooks", "pre",
                          "tezgah-hook.ts")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def recorded_shas(path=CONTRACT_SHA):
    """{key: sha} from the install record, in sha256sum's `<sha>  <key>` shape."""
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                digest, _, key = line.rstrip("\n").partition("  ")
                if key:
                    out[key] = digest
    except OSError:
        pass
    return out


def own_groups(data, own=False):
    """{event: canonical JSON of its tezgah-owned groups} for a `{"hooks": ...}`
    manifest. In a shared file (Codex, Cursor) only a group naming tezgah is
    tezgah's - the filter `install_codex`/`install_cursor` replace by; in
    tezgah's own manifest (`own`) every group is."""
    hooks = data.get("hooks") if isinstance(data, dict) else None
    out = {}
    for event, groups in (hooks if isinstance(hooks, dict) else {}).items():
        mine = [g for g in groups if own or "tezgah" in json.dumps(g)] \
            if isinstance(groups, list) else []
        if mine:
            out[event] = json.dumps(mine, sort_keys=True)
    return out


def _manifest(path, own):
    try:
        with open(path, encoding="utf-8") as fh:
            return own_groups(json.load(fh), own)
    except (OSError, ValueError):
        return None


def omp_bridge(root=ROOT):
    """The omp extension as an install writes it: the template with this tree's
    hook path, or "" when the template is unreadable."""
    try:
        with open(os.path.join(root, "hosts", "omp", "tezgah-hook.ts.in"),
                  encoding="utf-8") as fh:
            return fh.read().replace(
                "@HOOK@", os.path.join(root, "hosts", "omp", "hook.py"))
    except OSError:
        return ""


def registration(host, root=ROOT):
    """({entry: text}, [files]) for the tezgah-owned hook entries this host has
    on disk; the dict is None when the host's file cannot be read."""
    if host in ("claude", "dsh"):
        path = os.path.join(root, *(("hooks",) if host == "claude"
                                    else ("hosts", "dsh")), "hooks.json")
        return _manifest(path, own=True), [path]
    if host in ("codex", "cursor"):
        path = os.path.join(tp.HOST_DIRS[host], "hooks.json")
        return _manifest(path, own=False), [path]
    if host == "opencode":
        links = (os.path.join(tp.HOST_DIRS["opencode"], d, "tezgah.js")
                 for d in OPENCODE_DIRS)
        return {os.path.basename(os.path.dirname(p)): os.path.realpath(p)
                for p in links if os.path.lexists(p)}, []
    if host == "omp":
        try:
            with open(OMP_BRIDGE, encoding="utf-8") as fh:
                return {"bridge": fh.read()}, [OMP_BRIDGE]
        except OSError:
            return None, [OMP_BRIDGE]
    return None, []


def packaged(root=ROOT):
    """A release tree (tarball, npm, brew) carries no `.git`."""
    return not os.path.exists(os.path.join(root, ".git"))


def code_text(host, root=ROOT):
    """`<relpath> <sha>` per script the host's entries run, or None."""
    lines = []
    for rel in CODE_TARGETS.get(host, ()):
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                lines.append("%s %s" % (rel, hashlib.sha256(fh.read()).hexdigest()))
        except OSError:
            return None
    return "\n".join(lines)


def record_texts(host, root=ROOT):
    """{key: text} an install records for one host (`bin/tezgah-setup::record_hooks`)."""
    entries, _files = registration(host, root)
    out = {}
    if host != "omp":
        out.update((KEY % (host, name), text)
                   for name, text in (entries or {}).items())
    code = code_text(host, root) if packaged(root) else None
    if code is not None:
        out[KEY % (host, "code")] = code
    return out


def drift(host, root=ROOT, shas=None):
    """(drifted, unverified): what differs from the install, and what cannot be
    judged because the install recorded nothing for it."""
    shas = recorded_shas() if shas is None else shas
    prefix = KEY % (host, "")
    recorded = {k[len(prefix):]: v for k, v in shas.items() if k.startswith(prefix)}
    entries, files = registration(host, root)
    found, unknown = [], []
    for path in files:
        try:
            mode = os.stat(path).st_mode & 0o777
        except OSError:
            continue
        if mode & 0o002:
            found.append("%s mode %04o" % (path, mode))
    if entries is None:
        found.append("%s unreadable or missing" % files[0])
    elif host == "omp":
        if entries["bridge"] != omp_bridge(root):
            found.append("omp bridge %s differs from a fresh render" % OMP_BRIDGE)
    else:
        names = set(recorded) - {"code"}
        if not names:
            unknown.append("no install record for %s hook entries" % host)
        for name in sorted(names | set(entries)) if names else ():
            if name not in entries:
                found.append("%s %s entry removed" % (host, name))
            elif name not in recorded:
                found.append("%s %s entry added" % (host, name))
            elif recorded[name] != sha(entries[name]):
                found.append("%s %s entry changed" % (host, name))
    if "code" in recorded:
        code = code_text(host, root)
        if code is None or sha(code) != recorded["code"]:
            found.append("%s hook code changed since install" % host)
    return found, unknown


def drift_mark(session_id, host):
    """The mark one host's drifted session start leaves; its text is the drift
    list. Keyed by session AND host: two hosts can share a session id (a
    `tezgah-context attest` run by hand, a host whose ids collide), and a clean
    start on one must not clear the other's mark."""
    return os.path.join(tp.cache_dir(), "harness-drift", "%s.%s" % (
        hashlib.sha256(str(session_id).encode()).hexdigest()[:16], host))


def mark_text(session_id):
    """The drift lists this session's starts recorded, every host's, or ""."""
    if not session_id:
        return ""
    texts = []
    for host in CODE_TARGETS:
        try:
            with open(drift_mark(session_id, host), encoding="utf-8") as fh:
                text = fh.read().strip()
        except OSError:
            continue
        if text and text not in texts:
            texts.append(text)
    return "; ".join(texts)


def switches():
    """The kill switches present, by name. Before the latching plan (051) lands
    this is all the row can say about them."""
    names = set()
    for d in tp.OFF_DIRS:
        try:
            names.update(n for n in os.listdir(d) if n.endswith((".off", "-off")))
        except OSError:
            pass
    return sorted(names)


def run(host, session_id, cwd=None):
    """One `attest` row for this session start, and the drift mark set or
    cleared to match; the drift list. Outside a root it does nothing."""
    if not session_id or not tp.root_for(cwd or os.getcwd()):
        return None
    found, unknown = drift(host)
    detail = ("drifted: " + "; ".join(found) if found
              else "unverified: " + "; ".join(unknown) if unknown else "ok")
    import tezgah_integrity
    tezgah_integrity.note(session_id, "attest", detail, host=host,
                          switches=",".join(switches()) or None)
    mark = drift_mark(session_id, host)
    try:
        if found:
            os.makedirs(os.path.dirname(mark), exist_ok=True)
            with open(mark, "w", encoding="utf-8") as fh:
                fh.write("; ".join(found) + "\n")
        elif os.path.exists(mark):
            os.remove(mark)
    except OSError:
        pass
    return found
