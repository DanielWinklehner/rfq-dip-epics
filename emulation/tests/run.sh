#!/bin/bash
# run.sh - the system tests against the full emulation. Called by `make -C emulation test`.
#
#   emulation/tests/run.sh [pytest arguments]
#
# Starts the emulation (Compose project mist2emu) if none of its containers runs, and stops it
# again at the end; an emulation that was running stays running. Saves the output of the IOC and
# simulator containers to emulation/build/<service>.log while the suite runs (the tests read them
# there: the tools container cannot call Docker). Runs pytest in the tools container, prints the
# update-rate table and exits with pytest's exit code (99: the emulation did not start).
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)        # emulation/
BUILD=$HERE/build
SERVICES=(ioc-rack ioc-hv sim-rack sim-hv)
export MIST2_UID=${MIST2_UID:-$(id -u)} MIST2_GID=${MIST2_GID:-$(id -g)}
COMPOSE=(docker compose -f "$HERE/compose.yaml")

mkdir -p "$BUILD"
rm -f "$BUILD/update-rate.md"
started=0
followers=()

finish() {
    for pid in "${followers[@]}"; do kill "$pid" 2>/dev/null; done
    for pid in "${followers[@]}"; do wait "$pid" 2>/dev/null; done
    if [ "$started" = 1 ]; then
        echo "test: stopping the emulation (it was not running before)"
        "${COMPOSE[@]}" --profile tools down --remove-orphans >/dev/null 2>&1
    fi
}
trap finish EXIT
trap 'exit 130' INT TERM

if [ -n "$("${COMPOSE[@]}" ps -q --status running --status paused "${SERVICES[@]}" 2>/dev/null)" ]; then
    echo "test: the emulation is running; it stays running after the tests"
else
    echo "test: starting the emulation"
    started=1
    "${COMPOSE[@]}" up -d --wait || { echo "test: the emulation did not start"; exit 99; }
fi

for s in "${SERVICES[@]}"; do
    "${COMPOSE[@]}" logs -f --no-color --no-log-prefix "$s" > "$BUILD/$s.log" 2>&1 &
    followers+=($!)
done

# The whole suite, unless the arguments name test files (emulation/tests/test_05_faults.py::...)
paths=0
for a in "$@"; do case $a in emulation/tests*|*.py|*.py::*) paths=1;; esac; done
[ "$paths" = 1 ] || set -- "$@" emulation/tests

t0=$(date +%s)
"${COMPOSE[@]}" --profile tools run --rm -T tools \
    python -m pytest -c emulation/tests/pytest.ini --rootdir emulation/tests "$@"
status=$?

if [ -f "$BUILD/update-rate.md" ]; then
    echo
    cat "$BUILD/update-rate.md"
fi
echo
echo "test: pytest exit code $status after $(( $(date +%s) - t0 )) s; logs in emulation/build/"
exit $status
