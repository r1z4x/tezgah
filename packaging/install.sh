#!/bin/sh
# packaging/install.sh - install tezgah on a machine that has nothing yet.
#
#   install.sh [--version V] [--prefix P]
#
# Runs packaging/upgrade.sh (the one place a version is fetched, verified,
# unpacked and made current), then the installer from the tree it made current.
# Needs sh and curl; tar and sha256sum are upgrade.sh's. Env, unlike its flags:
# TEZGAH_REPO, TEZGAH_DIST, TEZGAH_PREFIX, as in upgrade.sh.
set -eu

REPO=${TEZGAH_REPO:-r1z4x/tezgah}
VERSION_ARG=
PREFIX_ARG=
work=
while [ $# -gt 0 ]; do case $1 in
    --version) [ $# -ge 2 ] || { echo "tezgah: --version needs a value" >&2; exit 2; }; VERSION_ARG=$2; shift 2 ;;
    --prefix)  [ $# -ge 2 ] || { echo "tezgah: --prefix needs a value" >&2; exit 2; }; PREFIX_ARG=$2; shift 2 ;;
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "tezgah: unknown option $1" >&2; exit 2 ;;
esac; done

# The default upgrade.sh resolves: the installer is reached through the tree it picks.
PREFIX=${PREFIX_ARG:-${TEZGAH_PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/tezgah}}
finish() { [ -z "$work" ] || rm -rf "$work"; }
trap finish EXIT INT TERM

here=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || echo .)
if [ -f "$here/upgrade.sh" ]; then
    up=$here/upgrade.sh                    # a checkout, or an unpacked release
else
    # Nothing to read it from: the bootstrapper comes from the release this install
    # targets; which *version* that is stays upgrade.sh's answer.
    ref=main
    [ -z "$VERSION_ARG" ] || ref=v$VERSION_ARG
    work=$(mktemp -d "${TMPDIR:-/tmp}/tezgah-install.XXXXXX") || exit 1
    up=$work/upgrade.sh
    curl -fsSL "https://raw.githubusercontent.com/$REPO/$ref/packaging/upgrade.sh" -o "$up" \
        || { echo "tezgah: cannot fetch packaging/upgrade.sh at $ref" >&2; exit 1; }
fi

set -- --prefix "$PREFIX"                  # explicit flags: a prefix may hold a space
[ -z "$VERSION_ARG" ] || set -- --version "$VERSION_ARG" "$@"
sh "$up" "$@"

# Called, not exec'd, so the trap above still removes a fetched bootstrapper. The
# artifact carries the exec bit on bin/tezgah-setup (tests/test_packaging_scripts.py
# holds it to that), so no interpreter lookup is needed here.
"$PREFIX/current/bin/tezgah-setup" --install
