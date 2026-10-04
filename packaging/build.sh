#!/bin/sh
# packaging/build.sh - build the release artifact from the tracked MANIFEST.
#
#   build.sh [--version V] [--out DIR] [--check] [--list]
#
# The artifact carries exactly the tracked listing plus two generated files at
# its root: `VERSION` and a copy of `MANIFEST`. An installed tree has no `.git`,
# and `plugin_files()` (bin/tezgah-setup) can only list itself through that
# manifest - which is not in its own listing, because a *copy* must not carry it.
# The artifact is not a copy, so it carries both.
#
# Nothing else filters the payload: a second include-rule beside `managed()`
# would make the tree's own listing disagree with the tree it describes.
#
# The archive is deterministic and `--check` proves it: sorted names, no
# directory entries, mode from the exec bit alone, uid/gid 0, empty owner names,
# and mtime 0 in every tar header *and* in the gzip header. The tar layer is
# Python's tarfile, not `tar`, because bsdtar has no create-time mtime flag: a
# `tar`-based build is byte-identical only where GNU tar is installed, so a
# digest checked on a laptop would not match the one CI published.
#
# Needs: sh, python3 (TEZGAH_PYTHON overrides). Writes <out>/tezgah-<V>.tar.gz
# and <out>/tezgah-<V>.tar.gz.sha256. Env: TEZGAH_VERSION.
set -eu

VERSION_ARG=
OUT=dist
MODE=build
while [ $# -gt 0 ]; do
    case $1 in
        --version) [ $# -ge 2 ] || { echo "tezgah: --version needs a value" >&2; exit 2; }; VERSION_ARG=$2; shift 2 ;;
        --out)     [ $# -ge 2 ] || { echo "tezgah: --out needs a value" >&2; exit 2; }; OUT=$2; shift 2 ;;
        --check)   MODE=check; shift ;;
        --list)    MODE=list; shift ;;
        -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "tezgah: unknown option $1" >&2; exit 2 ;;
    esac
done

PY=${TEZGAH_PYTHON:-}
[ -n "$PY" ] || PY=$(command -v python3 || command -v python || true)
[ -n "$PY" ] || { echo "tezgah: build.sh needs python3 (set TEZGAH_PYTHON)" >&2; exit 1; }

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEZGAH_ROOT=$ROOT TEZGAH_OUT=$OUT TEZGAH_MODE=$MODE TEZGAH_VERSION_ARG=$VERSION_ARG \
    exec "$PY" - <<'PY'
"""Write dist/tezgah-<version>.tar.gz, its .sha256, and prove the build is reproducible."""
import gzip
import hashlib
import io
import os
import sys
import tarfile
import tempfile

ROOT = os.environ["TEZGAH_ROOT"]

# The tracked listing and the two files the build adds at the archive root.
# MANIFEST is excluded from its own listing by `managed()` in bin/tezgah-setup.
MANIFEST = "MANIFEST"
GENERATED = (MANIFEST, "VERSION")


def fail(msg):
    sys.stderr.write("tezgah: %s\n" % msg)
    raise SystemExit(1)


def version():
    v = os.environ.get("TEZGAH_VERSION_ARG") or os.environ.get("TEZGAH_VERSION")
    if not v:
        v = changelog_version()
    # The version becomes a directory name under the install prefix and part of
    # a file name, so a separator, `.` or `..` must never get through.
    if not v or v != os.path.basename(v) or v in (".", ".."):
        fail("no version: pass --version V, set TEZGAH_VERSION, or add a "
             "`## [x.y.z]` heading to CHANGELOG.md")
    return v


def changelog_version():
    """The newest release heading: the second source `plugin_version()` reads."""
    try:
        with open(os.path.join(ROOT, "CHANGELOG.md")) as fh:
            for line in fh:
                if line.startswith("## ["):
                    return line[4:].split("]")[0].strip()
    except OSError:
        pass
    return ""


def listing():
    """The manifest's paths, sorted, or the build stops."""
    try:
        with open(os.path.join(ROOT, MANIFEST)) as fh:
            names = sorted({line.strip() for line in fh if line.strip()})
    except OSError:
        fail("no %s in %s - regenerate it with `bin/tezgah-setup --write-manifest`"
             % (MANIFEST, ROOT))
    if not names:
        fail("%s is empty - refusing to build an artifact that carries nothing" % MANIFEST)
    # A listing that names a path the tree does not have would ship a tree whose
    # own listing lies about what it holds.
    gone = [n for n in names if not os.path.lexists(os.path.join(ROOT, n))]
    if gone:
        fail("%s lists %d path(s) missing from %s: %s"
             % (MANIFEST, len(gone), ROOT, ", ".join(gone[:3])))
    return names


def members(names):
    """The archive's contents, sorted.

    No directory entries: every parent of a listed path is implied by that path,
    so the archive cannot record a directory's mode or mtime either."""
    return sorted(set(names).union(GENERATED))


def size_of(name):
    """Bytes the installed file takes, a symlink counting as zero."""
    path = os.path.join(ROOT, name)
    if os.path.islink(path):
        return 0
    try:
        return os.lstat(path).st_size
    except OSError:
        return 0


def add(tar, name, names, ver):
    """Append one member: the head of the archive, so every choice is explicit."""
    info = tarfile.TarInfo(name)
    info.mtime = 0            # fixed: a rebuild must not record this machine's clock
    info.uid = info.gid = 0   # numeric ids of 0, and no owner names at all
    info.uname = info.gname = ""
    if name == "VERSION":
        data = (ver + "\n").encode()
        info.mode = 0o644
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        return
    if name == MANIFEST:
        data = "".join(n + "\n" for n in names).encode()
        info.mode = 0o644
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        return
    path = os.path.join(ROOT, name)
    st = os.lstat(path)
    if os.path.islink(path):
        # bin/codegen.py and friends are tracked as symlinks; dereferencing one
        # would ship a second copy of a script and lose the link the tree has.
        info.type = tarfile.SYMTYPE
        info.linkname = os.readlink(path)
        info.mode = 0o777
        info.size = 0
        tar.addfile(info)
        return
    if not os.path.isfile(path):
        fail("%s is neither a regular file nor a symlink" % name)
    # The exec bit only: umask, ownership and setuid bits belong to the packaging
    # machine, not to the artifact.
    info.mode = 0o755 if st.st_mode & 0o100 else 0o644
    info.size = st.st_size
    with open(path, "rb") as src:
        tar.addfile(info, src)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(path, names, ver):
    """Write the tarball, return its digest.

    Two gzip-header fields are suppressed: `mtime=0` (GzipFile otherwise stamps
    the current time) and `filename=""` (it otherwise records the name of the
    file it is writing, so a build into a differently named path - `--check`'s
    temp file, say - would not match a release)."""
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name in members(names):
                    add(tar, name, names, ver)
    return sha256(path)


def content_hashes(path):
    """member name -> sha256 of its bytes, a symlink hashing its target string."""
    out = {}
    with tarfile.open(path, "r:gz") as tar:
        for info in tar.getmembers():
            if info.issym():
                out[info.name] = "symlink:" + info.linkname
                continue
            fh = tar.extractfile(info)
            out[info.name] = hashlib.sha256(fh.read()).hexdigest() if fh else "?"
    return out


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return "%d %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


def tree_files():
    """Every file in the working tree that the artifact does not carry."""
    found = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            found.append(os.path.relpath(os.path.join(base, name), ROOT))
    return sorted(found)


def left_out(names):
    """Paths in the tree the artifact leaves out, grouped by top-level name.

    Not a hardcoded list (plans, tests, benchmarks) but the actual difference
    between the tree and the listing, so a forgotten `--write-manifest` shows up
    here instead of as a missing file in a released tree."""
    kept = set(members(names))
    groups = {}
    for rel in tree_files():
        if rel in kept:
            continue
        groups.setdefault(rel.split(os.sep)[0], []).append(rel)
    return groups


def report(ver, names):
    kept = members(names)
    total = sum(size_of(n) for n in kept)
    print("tezgah %s from %s" % (ver, ROOT))
    print("%d files in the artifact (%d listed, +%s)"
          % (len(kept), len(names), " +".join(GENERATED)))
    print("  %s unpacked" % human(total))
    top = {}
    for name in kept:
        top[name.split("/")[0]] = top.get(name.split("/")[0], 0) + 1
    print("  top level: %s" % ", ".join("%s %d" % (k, top[k]) for k in sorted(top)))
    groups = left_out(names)
    if groups:
        print("left out (in the tree, not in %s): %d file(s)"
              % (MANIFEST, sum(len(v) for v in groups.values())))
        for group in sorted(groups):
            paths = groups[group]
            shown = ", ".join(paths[:3]) + (", ..." if len(paths) > 3 else "")
            print("  %s %d: %s" % (group, len(paths), shown))
    else:
        print("left out (in the tree, not in %s): none" % MANIFEST)
    return 0


def check(tarball, names, ver):
    if not os.path.isfile(tarball):
        fail("no artifact at %s - build it first" % tarball)
    recorded = digest_on_record(tarball)
    want = sha256(tarball)
    fd, tmp = tempfile.mkstemp(prefix="tezgah-check.", suffix=".tar.gz")
    os.close(fd)
    try:
        got = build(tmp, names, ver)
        print("artifact %s" % want)
        print("rebuild  %s" % got)
        if want != got:
            after = content_hashes(tmp)
            before = content_hashes(tarball)
            shown = 0
            for name in sorted(set(before).union(after)):
                if before.get(name) == after.get(name):
                    continue
                where = ("changed" if name in before and name in after
                         else "added" if name not in before else "removed")
                print("  %s %s" % (where, name))
                shown += 1
                if shown == 20:
                    print("  ... more differ")
                    break
            print("FAIL    rebuild differs - the tree changed since %s"
                  % os.path.basename(tarball))
            return 1
        print("ok      a rebuild of this tree is byte-identical")
    finally:
        os.remove(tmp)
    if recorded and recorded != want:
        print("FAIL    %s records %s" % (os.path.basename(tarball) + ".sha256", recorded))
        return 1
    return 0


def digest_on_record(tarball):
    """The digest the .sha256 sidecar claims, or "" when there is none."""
    try:
        with open(tarball + ".sha256") as fh:
            return fh.read().split()[0]
    except (OSError, IndexError):
        return ""


def main():
    ver = version()
    names = listing()
    out = os.environ["TEZGAH_OUT"]
    if not os.path.isabs(out):
        out = os.path.join(ROOT, out)
    if os.environ["TEZGAH_MODE"] == "list":
        return report(ver, names)
    try:
        os.makedirs(out)
    except OSError:
        if not os.path.isdir(out):
            fail("cannot create %s" % out)
    tarball = os.path.join(out, "tezgah-%s.tar.gz" % ver)
    if os.environ["TEZGAH_MODE"] == "check":
        return check(tarball, names, ver)
    digest = build(tarball, names, ver)
    with open(tarball + ".sha256", "w") as fh:
        fh.write("%s  %s\n" % (digest, os.path.basename(tarball)))
    total = sum(size_of(n) for n in members(names))
    shown = os.path.join(os.environ["TEZGAH_OUT"], os.path.basename(tarball))
    print("ok      %s" % shown)
    print("        %d files, %s unpacked, %s compressed"
          % (len(members(names)), human(total), human(os.path.getsize(tarball))))
    print("        sha256 %s" % digest)
    print("        %s.sha256 (what upgrade.sh verifies)" % shown)
    groups = left_out(names)
    if groups:
        print("note    %d file(s) in the tree are not in %s (see --list)"
              % (sum(len(v) for v in groups.values()), MANIFEST))
    return 0


raise SystemExit(main())
PY
