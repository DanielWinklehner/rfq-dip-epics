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
#
# While the suite runs it also stops, starts and restarts IOC containers when a test asks for it
# (system.py, container()): the tools container has no Docker. A test writes one line
# "<stop|start|restart> <ioc service>" into emulation/build/docker-requests/<id>.req; this script
# runs it with docker compose, writes "<exit code> <output>" into <id>.done, and follows the log
# of a started container again. Only the IOC services are accepted.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)        # emulation/
BUILD=$HERE/build
SERVICES=(ioc-rack ioc-hv ioc-loop sim-rack sim-hv)
IOC_SERVICES=" ioc-rack ioc-hv ioc-loop "
REQUESTS=$HERE/build/docker-requests
export MIST2_UID=${MIST2_UID:-$(id -u)} MIST2_GID=${MIST2_GID:-$(id -g)}
COMPOSE=(docker compose -f "$HERE/compose.yaml")

mkdir -p "$BUILD"
rm -f "$BUILD/update-rate.md"
mkdir -p "$REQUESTS"
rm -f "$REQUESTS"/*
started=0
followers=()

finish() {
    for pid in "${followers[@]}"; do kill "$pid" 2>/dev/null; done
    [ -f "$REQUESTS/followers" ] && while read -r pid; do kill "$pid" 2>/dev/null; done < "$REQUESTS/followers"
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

# Requests of the tests to stop, start or restart an IOC container (header).
serve_requests() {
    local req id action service rest out status
    while sleep 0.2; do
        for req in "$REQUESTS"/*.req; do
            [ -e "$req" ] || continue
            id=${req%.req}
            read -r action service rest < "$req"
            rm -f "$req"
            case "$action" in stop|start|restart) ;; *) action="";; esac
            if [ -z "$action" ] || [ -n "$rest" ] || [[ "$IOC_SERVICES" != *" $service "* ]]; then
                echo "2 refused: only stop, start or restart of$IOC_SERVICES" > "$id.tmp"
            else
                since=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
                out=$("${COMPOSE[@]}" "$action" "$service" 2>&1); status=$?
                if [ "$action" != stop ]; then
                    # the log follower of the container ended with it: follow the new output
                    "${COMPOSE[@]}" logs -f --no-color --no-log-prefix --since "$since" "$service" \
                        >> "$BUILD/$service.log" 2>&1 &
                    echo $! >> "$REQUESTS/followers"
                fi
                echo "$status $out" | tr '\n' ' ' > "$id.tmp"
            fi
            mv "$id.tmp" "$id.done"
        done
    done
}
serve_requests &
followers+=($!)

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
