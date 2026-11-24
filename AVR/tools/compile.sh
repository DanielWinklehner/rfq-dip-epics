#!/bin/bash
# compile.sh - compile an Arduino sketch of this repository in a container
#
#   AVR/tools/compile.sh <sketch directory> <fqbn>
#
#   AVR/tools/compile.sh AVR/devices/InterlockOpta arduino:mbed_opta:opta
#   AVR/tools/compile.sh AVR/devices/InterlockBox  arduino:avr:mega
#
# Builds the image mist2-arduino:dev (AVR/tools/arduino.Dockerfile) when it is missing, then runs
# arduino-cli compile in a throw-away container as the calling user. The checkout is mounted
# read-only; the libraries are AVR/libcom1 and AVR/libutil of this checkout, not copies.
# Prints arduino-cli's output (all warnings, the sizes) and exits with its exit code.
# Nothing is uploaded: there is no board here.
set -u

usage() { echo "usage: $0 <sketch directory> <fqbn>" >&2; exit 2; }
[ $# -eq 2 ] || usage
[ -d "$1" ] || { echo "compile.sh: no directory '$1'" >&2; exit 2; }

IMAGE=mist2-arduino:dev
TOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$TOOLS/../.." && pwd)
SKETCH=$(cd "$1" && pwd)
FQBN=$2

case "$SKETCH/" in
    "$REPO"/*) REL=${SKETCH#"$REPO"/} ;;
    *) echo "compile.sh: '$1' is not inside $REPO" >&2; exit 2 ;;
esac

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "compile.sh: building $IMAGE (once, several minutes)" >&2
    docker build -t "$IMAGE" -f "$TOOLS/arduino.Dockerfile" "$TOOLS" >&2 || {
        echo "compile.sh: building $IMAGE failed" >&2; exit 3; }
fi

# --warnings all: -Wall -Wextra for the sketch, its headers and the libraries (and the core).
# The build directory lives in the container's /tmp and goes away with it.
# The image's download directory is not writable for this user and nothing is downloaded
# (--network none): point it at /tmp.
docker run --rm --network none -u "$(id -u):$(id -g)" \
    -e ARDUINO_DIRECTORIES_DOWNLOADS=/tmp/staging \
    -v "$REPO:/repo:ro" \
    -w /repo "$IMAGE" \
    arduino-cli compile \
        --fqbn "$FQBN" \
        --library /repo/AVR/libcom1 \
        --library /repo/AVR/libutil \
        --warnings all \
        --build-path /tmp/build \
        "/repo/$REL"
rc=$?
echo "compile.sh: $REL for $FQBN: exit code $rc"
exit $rc
