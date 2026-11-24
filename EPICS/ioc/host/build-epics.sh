#!/bin/sh
# build-epics.sh - build EPICS and the MIST-2 IOC application on a real Linux computer
#
#   build-epics.sh [<directory>]        default: /opt/epics
#
# Builds EPICS base, asyn, StreamDevice and autosave from the release tags of the mist2-ioc
# image (emulation/docker/ioc.Dockerfile, the same steps) into <directory>, then the IOC
# application of this checkout (EPICS/ioc). Run it as the user that will run the IOC, not as
# root. A second run goes on where the first one stopped.
#
# Before (Ubuntu):
#   sudo apt install build-essential perl git ca-certificates libreadline-dev libtirpc-dev
#   sudo mkdir -p /opt/epics && sudo chown "$USER": /opt/epics
#
# Tested in containers of Ubuntu 20.04, 22.04 and 24.04 (x86_64). NOT tested on the lab's
# computers.
set -eu

EPICS_BASE_TAG=R7.0.10
ASYN_TAG=R4-46
STREAM_TAG=2.8.26
AUTOSAVE_TAG=R5-11

ROOT=${1:-/opt/epics}
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$(cd "$HERE/.." && pwd)                       # EPICS/ioc of this checkout
JOBS=$(nproc 2>/dev/null || echo 2)

die() { echo "build-epics.sh: $*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "run this as the user that will run the IOC, not as root"
for tool in gcc g++ make perl git; do
    command -v "$tool" >/dev/null 2>&1 || die "'$tool' not found: sudo apt install build-essential perl git ca-certificates libreadline-dev libtirpc-dev"
done
[ -f /usr/include/readline/readline.h ] || die "readline headers not found: sudo apt install libreadline-dev"
[ -d /usr/include/tirpc ] || die "libtirpc headers not found: sudo apt install libtirpc-dev"
mkdir -p "$ROOT/support" 2>/dev/null || true
[ -d "$ROOT/support" ] && [ -w "$ROOT" ] && [ -w "$ROOT/support" ] \
    || die "cannot write to $ROOT: sudo mkdir -p $ROOT && sudo chown \"\$USER\": $ROOT"
ROOT=$(cd "$ROOT" && pwd)

EPICS_BASE=$ROOT/base
SUPPORT=$ROOT/support

# fetch <url> <tag> <directory> [<more git options>]: clone once, a later run keeps the clone
fetch() {
    url=$1; tag=$2; dir=$3; shift 3
    if [ ! -d "$dir/.git" ]; then
        echo "== $dir: $tag"
        git clone --depth 1 --branch "$tag" "$@" "$url" "$dir"
    fi
}

fetch https://github.com/epics-base/epics-base.git "$EPICS_BASE_TAG" "$EPICS_BASE" \
    --recurse-submodules --shallow-submodules
make -C "$EPICS_BASE" -j"$JOBS"

fetch https://github.com/epics-modules/asyn.git "$ASYN_TAG" "$SUPPORT/asyn"
printf 'EPICS_BASE=%s\n' "$EPICS_BASE" > "$SUPPORT/asyn/configure/RELEASE"
make -C "$SUPPORT/asyn" -j"$JOBS"

# Only the library (src): StreamDevice's example IOC registers the VXI-11 driver, which asyn
# is built without.
fetch https://github.com/paulscherrerinstitute/StreamDevice.git "$STREAM_TAG" "$SUPPORT/StreamDevice"
printf 'EPICS_BASE=%s\nASYN=%s\n' "$EPICS_BASE" "$SUPPORT/asyn" > "$SUPPORT/StreamDevice/configure/RELEASE"
make -C "$SUPPORT/StreamDevice" -f Makefile DIRS="configure src" -j"$JOBS"

fetch https://github.com/epics-modules/autosave.git "$AUTOSAVE_TAG" "$SUPPORT/autosave"
printf 'EPICS_BASE=%s\n' "$EPICS_BASE" > "$SUPPORT/autosave/configure/RELEASE"
make -C "$SUPPORT/autosave" -j"$JOBS"

# The IOC application. configure/RELEASE names /opt/epics; any other directory goes into
# configure/RELEASE.local, which is not under version control.
if [ "$ROOT" = /opt/epics ]; then
    [ ! -f "$TOP/configure/RELEASE.local" ] \
        || echo "build-epics.sh: note: $TOP/configure/RELEASE.local exists and overrides /opt/epics" >&2
else
    printf 'SUPPORT=%s\nASYN=$(SUPPORT)/asyn\nSTREAM=$(SUPPORT)/StreamDevice\nAUTOSAVE=$(SUPPORT)/autosave\nEPICS_BASE=%s\n' \
        "$SUPPORT" "$EPICS_BASE" > "$TOP/configure/RELEASE.local"
fi
make -C "$TOP" -j"$JOBS"

ARCH=$("$EPICS_BASE/startup/EpicsHostArch")
[ -x "$TOP/bin/$ARCH/mist2" ] || die "the build ended without $TOP/bin/$ARCH/mist2"

cat <<EOF

Built: $TOP/bin/$ARCH/mist2
Start an IOC:        $TOP/iocBoot/run-ioc.sh <iocRack|iocHV> real
caget, caput, camonitor are in $EPICS_BASE/bin/$ARCH :
    export PATH=$EPICS_BASE/bin/$ARCH:\$PATH
EOF
[ "$ARCH" = linux-x86_64 ] || echo "This computer is $ARCH: export EPICS_HOST_ARCH=$ARCH before run-ioc.sh"
