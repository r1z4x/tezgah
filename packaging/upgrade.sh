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
# Needs: sh, curl, tar, awk, and sha256sum or shasum. No python. Uses `gh` when it
# is on PATH to check the release's build provenance; without it, says so.
# Env: TEZGAH_PREFIX, XDG_DATA_HOME, TEZGAH_VERSION, TEZGAH_REPO, TEZGAH_DIST
#      (a directory holding tezgah-<V>.tar.gz + .sha256 - what build.sh --out
#      writes; it swaps the release URL for that directory, one code path, and
#      is how upgrade.sh is exercised without a published release), TEZGAH_GH
#      (the gh to run for the provenance check; default `gh` on PATH),
#      TEZGAH_GITHUB_TOKEN / GITHUB_TOKEN / GH_TOKEN (the first one set is sent
#      as the bearer a private $TEZGAH_REPO needs; with none, the public URLs).
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

# A private repository answers 404 to `releases/download/...` from a session without
# a token (measured 2026-10-17, with the token as URL userinfo and as a header
# alike), while the REST asset endpoint returns the blob for `Accept:
# application/octet-stream` plus `Authorization: Bearer`. So the token decides which
# URL is read, and a public repository - no token - keeps exactly the URL it had.
token=${TEZGAH_GITHUB_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}

# Every read goes through here, so the bearer cannot be forgotten on one call.
get() {   # get <url> [curl args...]
    if [ -n "$token" ]; then
        curl -fsSL -H "Authorization: Bearer $token" "$@"
    else
        curl -fsSL "$@"
    fi
}

# The id of asset `$2` in the JSON of one release (`$1`). An asset's id is written
# down in one place, its own `url` field, so the JSON is flattened, split at each
# `"url":` - one fragment per asset, from its url to the next one - and the id read
# from the fragment that names the file wanted. Empty, not an error, when the
# release carries no such asset; the caller says so.
asset_id() {
    printf '%s\n' "$1" | tr -d '[:space:]' | awk -v want="\"name\":\"$2\"" '
        { n = split($0, o, "\"url\":")
          for (i = 1; i <= n; i++)
              if (index(o[i], want) && match(o[i], /"id":[0-9]+/))
                  { print substr(o[i], RSTART + 5, RLENGTH - 5); exit } }'
}

# The newest release tag. The API answers `tag_name`; the raw redirect would
# too, but GitHub answers this without a rate-limit surprise on a repeat run.
latest_release() {
    body=$(get "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null) \
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
    assets=
elif [ -n "$token" ]; then
    # The asset endpoint is addressed by id, and the release JSON is the only
    # place that id is written down.
    rel=$(get "https://api.github.com/repos/$REPO/releases/tags/v$VERSION") \
        || die "cannot read release v$VERSION of $REPO with the token in TEZGAH_GITHUB_TOKEN/GITHUB_TOKEN/GH_TOKEN"
    id=$(asset_id "$rel" "tezgah-$VERSION.tar.gz")
    id_sidecar=$(asset_id "$rel" "tezgah-$VERSION.tar.gz.sha256")
    [ -n "$id" ] && [ -n "$id_sidecar" ] \
        || die "release v$VERSION of $REPO carries no tezgah-$VERSION.tar.gz"
    base="https://api.github.com/repos/$REPO/releases/assets"
    assets=$base
else
    base="https://github.com/$REPO/releases/download/v$VERSION"
    assets=
fi

work=$(mktemp -d "${TMPDIR:-/tmp}/tezgah-upgrade.XXXXXX") || die "cannot create a temp dir"
trap 'rm -rf "$work"' EXIT INT TERM

name=tezgah-$VERSION.tar.gz
if [ -n "$assets" ]; then
    # Both files come from the same release, and neither blob is served without
    # this Accept: the endpoint answers JSON metadata otherwise.
    curl -fsSL -H "Accept: application/octet-stream" \
        -H "Authorization: Bearer $token" "$assets/$id" -o "$work/$name" \
        || die "cannot fetch $name from $assets/$id"
    curl -fsSL -H "Accept: application/octet-stream" \
        -H "Authorization: Bearer $token" "$assets/$id_sidecar" -o "$work/$name.sha256" \
        || die "cannot fetch $name.sha256 from $assets/$id_sidecar"
else
    get "$base/$name" -o "$work/$name" \
        || die "cannot fetch $name from $base - if $REPO is private, set TEZGAH_GITHUB_TOKEN, GITHUB_TOKEN or GH_TOKEN"
    get "$base/$name.sha256" -o "$work/$name.sha256" \
        || die "cannot fetch $name.sha256 from $base - if $REPO is private, set TEZGAH_GITHUB_TOKEN, GITHUB_TOKEN or GH_TOKEN"
fi

want=$(sed -n '1s/[[:space:]].*//p' "$work/$name.sha256")
got=$(sha256_of "$work/$name")
[ -n "$want" ] || die "$name.sha256 carries no digest"
[ "$want" = "$got" ] || die "checksum mismatch for $name: recorded $want, downloaded $got"
echo "ok      verified $name ($got)"

# The .sha256 comes from the same place as the tarball, so it proves the
# download is whole, not where it was built. The release workflow attests the
# tarball's build provenance (actions/attest-build-provenance); `gh` can check
# that binding when it is installed. It is not a dependency, so its absence -
# or a gh that cannot answer (signed out, offline) - is said plainly and the
# upgrade goes on: the checksum above stays the gate. TEZGAH_GH names the gh to
# run (tests point it at a stand-in, or at nothing).
gh=${TEZGAH_GH:-gh}
if command -v "$gh" >/dev/null 2>&1; then
    if gh_out=$("$gh" attestation verify "$work/$name" --repo "$REPO" 2>&1); then
        echo "ok      provenance verified: $name was built by $REPO's release workflow"
    else
        echo "WARN    provenance not verified: gh attestation verify $name --repo $REPO said: $(printf '%s\n' "$gh_out" | tail -n 1)"
    fi
else
    echo "note    provenance not checked: gh is not on PATH (check by hand: gh attestation verify $name --repo $REPO)"
fi

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
