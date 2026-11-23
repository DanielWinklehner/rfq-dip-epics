#!/bin/bash
# run.sh - the logger's tests. Called by `make -C logger test` (README.md in this directory).
#
#   logger/tests/run.sh [pytest arguments]
#
# Starts the emulation (emulation/compose.yaml) if none of its IOCs runs, and the logger's own
# Compose project (database, logger, Grafana) if it does not run; at the end it stops what it
# started, and puts back what it changed. Runs the unit tests (test_core.py) and the system tests
# (test_system.py) in the logger's image, on the host network, as the logger itself runs.
#
# The test container has no Docker: a test writes one line into logger/build/requests/<id>.req,
# and this script runs it and answers in <id>.done ("<exit code> <output>"):
#   stop|start <service>   ioc-hv, ioc-rack (emulation), db, logger (logger's project)
#   buffer <rows|default>  the logger again, with another buffer size (MIST2LOG_BUFFER_ROWS)
#   stats                  docker stats of the logger and the database
#
# Saved settings: limits.sav of every IOC is read before and after, as emulation/tests/run.sh
# does; a run that changed it fails.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)      # logger/
REPO=$(cd "$HERE/.." && pwd)
BUILD=$HERE/build
REQUESTS=$BUILD/requests
export MIST2_UID=${MIST2_UID:-$(id -u)} MIST2_GID=${MIST2_GID:-$(id -g)}
EMU=(docker compose -f "$REPO/emulation/compose.yaml")
LOG=(docker compose -f "$HERE/compose.yaml" --env-file "$HERE/.env")
set -a; . "$HERE/.env"; set +a
SUBNET=${MIST2_SUBNET:-172.30.0}
started_emu=0
started_log=0

mkdir -p "$REQUESTS"
rm -f "$REQUESTS"/*

saved_settings() {
    docker run --rm -v mist2emu-save:/s:ro --entrypoint sh mist2-ioc:dev -c \
        'for f in /s/*/limits.sav; do [ -f "$f" ] || { echo none; continue; }; echo "== $f"; grep -v "^#" "$f"; done' 2>&1
}
SAVED_BEFORE=$(saved_settings)

server=""
finish() {
    [ -n "$server" ] && kill "$server" 2>/dev/null
    if [ "$started_log" = 1 ]; then
        echo "test: stopping the logger (it was not running before)"
        make -s -C "$HERE" down >/dev/null 2>&1
    else
        "${LOG[@]}" up -d --wait logger >/dev/null 2>&1      # as it was: the buffer of .env, running
    fi
    if [ "$started_emu" = 1 ]; then
        echo "test: stopping the emulation (it was not running before)"
        "${EMU[@]}" --profile tools --profile plant down --remove-orphans >/dev/null 2>&1
    fi
}
trap finish EXIT
trap 'exit 130' INT TERM

if [ -n "$("${EMU[@]}" ps -q --status running ioc-rack ioc-hv 2>/dev/null)" ]; then
    echo "test: the emulation is running; it stays running"
else
    echo "test: starting the emulation"
    started_emu=1
    "${EMU[@]}" up -d --wait >/dev/null || { echo "test: the emulation did not start"; exit 99; }
fi
if [ -n "$("${LOG[@]}" ps -q --status running logger 2>/dev/null)" ]; then
    echo "test: the logger is running; it stays running"
    make -s -C "$HERE" dashboards
else
    echo "test: starting the logger"
    started_log=1
    make -s -C "$HERE" up >/dev/null || { echo "test: the logger did not start"; exit 99; }
fi

serve() {
    local req id action arg out status
    while sleep 0.2; do
        for req in "$REQUESTS"/*.req; do
            [ -e "$req" ] || continue
            id=${req%.req}
            read -r action arg < "$req"
            rm -f "$req"
            case "$action $arg" in
                "stop ioc-hv"|"start ioc-hv"|"stop ioc-rack"|"start ioc-rack")
                    out=$("${EMU[@]}" "$action" "$arg" 2>&1); status=$?
                    [ "$action" = start ] && { "${EMU[@]}" up -d --wait "$arg" >/dev/null 2>&1 || status=$?; } ;;
                "stop db"|"start db"|"stop logger"|"start logger")
                    out=$("${LOG[@]}" "$action" "$arg" 2>&1); status=$? ;;
                "buffer default")
                    out=$("${LOG[@]}" up -d --force-recreate logger 2>&1); status=$? ;;
                buffer\ [0-9]*)
                    out=$(MIST2LOG_BUFFER_ROWS=$arg "${LOG[@]}" up -d --force-recreate logger 2>&1); status=$? ;;
                "stats ")
                    out=$(docker stats --no-stream --format '{{.Name}} CPU {{.CPUPerc}} memory {{.MemUsage}}' \
                          mist2log-logger-1 mist2log-db-1 2>&1); status=$? ;;
                *)  out="refused: $action $arg"; status=2 ;;
            esac
            echo "$status $out" > "$id.tmp"
            mv "$id.tmp" "$id.done"
        done
    done
}
serve &
server=$!

# Both test files, unless the arguments name test files (tests/test_system.py::...)
paths=0
for a in "$@"; do case $a in tests/*|*.py|*.py::*) paths=1;; esac; done
[ "$paths" = 1 ] || set -- "$@" tests/test_core.py tests/test_dashboards.py tests/test_system.py

t0=$(date +%s)
docker run --rm --network host -u "$MIST2_UID:$MIST2_GID" -v "$REPO:/repo" -w /repo/logger \
    --add-host "sim-rack:$SUBNET.21" --add-host "sim-hv:$SUBNET.22" \
    -e HOME=/tmp -e PYTHONPATH=/repo/logger:/repo/emulation/sim:/repo/emulation/tests \
    -e EPICS_CA_AUTO_ADDR_LIST -e EPICS_CA_ADDR_LIST -e MIST2LOG_DB_PORT -e MIST2LOG_DB_PASSWORD \
    -e MIST2LOG_READER_PASSWORD -e MIST2LOG_GRAFANA_PORT -e MIST2LOG_BUFFER_ROWS -e GRAFANA_ADMIN_PASSWORD \
    mist2log:1 python -m pytest -c tests/pytest.ini --rootdir tests "$@"
status=$?
echo
echo "test: pytest exit code $status after $(( $(date +%s) - t0 )) s"
finish; trap - EXIT
[ "$started_emu" = 1 ] || sleep 6          # autosave saves a change within 5 s
SAVED_AFTER=$(saved_settings)
if [ "$SAVED_BEFORE" = "$SAVED_AFTER" ]; then
    echo "test: saved settings (limits.sav) as before the run"
elif echo "$SAVED_BEFORE" | grep -q "^none$"; then
    echo "test: limits.sav did not exist before the run (first start)"
else
    echo "test: FAIL: the run changed the saved settings (limits.sav):"
    diff <(echo "$SAVED_BEFORE") <(echo "$SAVED_AFTER") | sed 's/^/    /'
    [ "$status" = 0 ] && status=1
fi
exit $status
