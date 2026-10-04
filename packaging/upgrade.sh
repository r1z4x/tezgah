#!/bin/sh
# packaging/upgrade.sh - the one place a version is fetched, verified, unpacked
# and made current.
#
#   upgrade.sh [--version V] [--prefix P]
#
# V defaults to the newest GitHub release of $TEZGAH_REPO; P to
# $TEZGAH_PREFIX, else $XDG_DATA_HOME/tezgah, else ~/.local/share/tezgah. The
# version unpacks at <P>/<V> and <P>/current is pointed at it, so a rollback is
# `ln -sfn <P>/<previous> <P>/current` - the older tree is never removed.
#
# Callers: packaging/install.sh (a first install) and `tezgah-setup --upgrade`.
# Neither re-implements the fetch, the checksum or the flip.
#
# Needs: sh, curl, tar, and sha256sum or shasum. No python.
# Env: TEZGAH_PREFIX, XDG_DATA_HOME, TEZGAH_VERSION, TEZGAH_REPO, TEZGAH_DIST
#      (a directory holding tezgah-<V>.tar.gz + .sha256 - what build.sh --out
#      writes; it swaps the release URL for that directory, one code path, and
#      is how upgrade.sh is exercised without a published release).
set -eu

REPO=${TEZGAH_REPO:-r1z4x/tezgah}
VERSION_ARG=
PREFIX_ARG=

while [ $# -gt 0 ]; do
    case $1 in
        --version) [ $# -ge 2 ] || { echo "tezgah: --version needs a value" >&2; exit 2; }; VERSION_ARG=$2; shift 2 ;;
        --prefix)  [ $# -ge 2 ] || { echo "tezgah: --prefix needs a value" >&2; exit 2; }; PREFIX_ARG=$2; shift 2 ;;
        -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "tezgah: unknown option $1" >&2; exit 2 ;;
    esac
done

die() {
    echo "tezgah: $*" >&2
    exit 1
}

# The newest release tag. The API answers `tag_name`; the raw redirect would
# too, but GitHub answers this without a rate-limit surprise on a repeat run.
latest_release() {
    body=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null) \
        || return 1
    tag=$(printf '%s\n' "$body" \
        | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
    [ -n "$tag" ] || return 1
    printf '%s\n' "${tag#v}"
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | sed 's/[[:space:]].*//'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | sed 's/[[:space:]].*//'
    else
        die "neither sha256sum nor shasum is on PATH - cannot verify the artifact"
    fi
}

PREFIX=${PREFIX_ARG:-${TEZGAH_PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/tezgah}}
VERSION=${VERSION_ARG:-${TEZGAH_VERSION:-}}
if [ -z "$VERSION" ]; then
    VERSION=$(latest_release) || die "cannot read the newest release of $REPO (no release yet, or no network)"
fi
# The version becomes a path component and part of a filename, so a separator
# must never get through.
case $VERSION in
    ""|*/*|.|..) die "bad version '$VERSION' (want X.Y.Z)" ;;
esac

if [ -n "${TEZGAH_DIST:-}" ]; then
    case $TEZGAH_DIST in
        /*) dist=$TEZGAH_DIST ;;
        *)  dist=$PWD/$TEZGAH_DIST ;;
    esac
    base="file://$dist"
else
    base="https://github.com/$REPO/releases/download/v$VERSION"
fi

work=$(mktemp -d "${TMPDIR:-/tmp}/tezgah-upgrade.XXXXXX") || die "cannot create a temp dir"
trap 'rm -rf "$work"' EXIT INT TERM

name=tezgah-$VERSION.tar.gz
curl -fsSL "$base/$name" -o "$work/$name" \
    || die "cannot fetch $name from $base"
curl -fsSL "$base/$name.sha256" -o "$work/$name.sha256" \
    || die "cannot fetch $name.sha256 from $base"

want=$(sed -n '1s/[[:space:]].*//p' "$work/$name.sha256")
got=$(sha256_of "$work/$name")
[ -n "$want" ] || die "$name.sha256 carries no digest"
[ "$want" = "$got" ] || die "checksum mismatch for $name: recorded $want, downloaded $got"
echo "ok      verified $name ($got)"

mkdir -p "$PREFIX" || die "cannot create $PREFIX"
dest=$PREFIX/$VERSION
part=$PREFIX/.$VERSION.part.$$
if [ -e "$dest" ]; then
    echo "ok      kept $dest (already unpacked)"
else
    # Unpack beside the destination, then rename it into place: a failed or
    # interrupted unpack leaves no half tree where a version is expected, and
    # `current` is only touched after this point.
    rm -rf "$part"
    mkdir -p "$part" || die "cannot create $part"
    tar -xzf "$work/$name" -C "$part" || { rm -rf "$part"; die "cannot unpack $name"; }
    mv "$part" "$dest" || { rm -rf "$part"; die "cannot install into $dest"; }
    echo "ok      unpacked $dest"
fi

# Read the old target before the flip, to report what a rollback would return to.
old=$(readlink "$PREFIX/current" 2>/dev/null || true)
# -n: an existing `current` is a symlink to a directory, and without it ln would
# create the new link *inside* the tree it is meant to replace.
ln -sfn "$dest" "$PREFIX/current" || die "cannot point $PREFIX/current at $VERSION"
if [ -n "$old" ]; then
    echo "ok      current -> $VERSION (was $old, still installed)"
else
    echo "ok      current -> $VERSION"
fi
