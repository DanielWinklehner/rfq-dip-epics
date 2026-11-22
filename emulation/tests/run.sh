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
# "<stop|start|restart|kill|pause|unpause> <service>" into emulation/build/docker-requests/<id>.req; this script
# runs it with docker compose, writes "<exit code> <output>" into <id>.done, and follows the log
# of a started container again. Only the IOC services and the loop service are accepted.
#
# MIST2_PLANT=1 (make -C emulation test-loop): with the plant model. A plant this script started
# is stopped again, also when the rest of the emulation was running before.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)        # emulation/
BUILD=$HERE/build
SERVICES=(ioc-rack ioc-hv loop sim-rack sim-hv)
CONTROLLED=" ioc-rack ioc-hv loop "
REQUESTS=$HERE/build/docker-requests
export MIST2_UID=${MIST2_UID:-$(id -u)} MIST2_GID=${MIST2_GID:-$(id -g)}
COMPOSE=(docker compose -f "$HERE/compose.yaml")
PLANT=${MIST2_PLANT:-0}
UP=()
[ "$PLANT" = 1 ] && UP=(--profile plant) && SERVICES+=(plant)
started_plant=0

mkdir -p "$BUILD"
rm -f "$BUILD/update-rate.md" "$BUILD/loop-plant.md"
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
        "${COMPOSE[@]}" --profile tools --profile plant down --remove-orphans >/dev/null 2>&1
    elif [ "$started_plant" = 1 ]; then
        echo "test: stopping the plant (it was not running before)"
        "${COMPOSE[@]}" --profile plant stop plant >/dev/null 2>&1
        "${COMPOSE[@]}" --profile plant rm -f plant >/dev/null 2>&1
    fi
}
trap finish EXIT
trap 'exit 130' INT TERM

if [ -n "$("${COMPOSE[@]}" ps -q --status running --status paused ioc-rack ioc-hv 2>/dev/null)" ]; then
    echo "test: the emulation is running; it stays running after the tests"
    if [ "$PLANT" = 1 ] && [ -z "$("${COMPOSE[@]}" --profile plant ps -q --status running plant 2>/dev/null)" ]; then
        echo "test: starting the plant"
        started_plant=1
        "${COMPOSE[@]}" --profile plant up -d --wait plant || { echo "test: the plant did not start"; exit 99; }
    fi
else
    echo "test: starting the emulation"
    started=1
    "${COMPOSE[@]}" "${UP[@]}" up -d --wait || { echo "test: the emulation did not start"; exit 99; }
fi

for s in "${SERVICES[@]}"; do
    "${COMPOSE[@]}" "${UP[@]}" logs -f --no-color --no-log-prefix "$s" > "$BUILD/$s.log" 2>&1 &
    followers+=($!)
done

# Requests of the tests to stop, start, restart, kill, pause or unpause a container (header).
serve_requests() {
    local req id action service rest out status
    while sleep 0.2; do
        for req in "$REQUESTS"/*.req; do
            [ -e "$req" ] || continue
            id=${req%.req}
            read -r action service rest < "$req"
            rm -f "$req"
            case "$action" in stop|start|restart|kill|pause|unpause) ;; *) action="";; esac
            if [ -z "$action" ] || [ -n "$rest" ] || [[ "$CONTROLLED" != *" $service "* ]]; then
                echo "2 refused: only stop, start, restart, kill, pause or unpause of$CONTROLLED" > "$id.tmp"
            else
                since=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
                out=$("${COMPOSE[@]}" "$action" "$service" 2>&1); status=$?
                if [ "$action" = start ] || [ "$action" = restart ]; then
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

for table in update-rate.md loop-plant.md; do
    if [ -f "$BUILD/$table" ]; then
        echo
        cat "$BUILD/$table"
    fi
done
echo
echo "test: pytest exit code $status after $(( $(date +%s) - t0 )) s; logs in emulation/build/"
exit $status
